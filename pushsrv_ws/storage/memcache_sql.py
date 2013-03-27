# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from .. import logger, LOG
from pushsrv_ws.storage.sql import (Storage as SqlStorage,
                                    StorageException)
from mozsvc.storage.mcclient import MemcachedClient
import warnings
import time


class Storage(SqlStorage):
    """ memcache fronted data store
    """

    def __init__(self, config, flags={}, **kw):
        try:
            super(Storage, self).__init__(config, flags, **kw)
            self.mc = MemcachedClient(
                    servers=self.settings.get('db.memcache_servers',
                                              'localhost:11211'),
                    key_prefix=self.settings.get('db.mc.prefix', 'sp_'))
            # live elements timeout in 3 days
            self.timeout_live = self.settings.get('db.timeout_live',
                                                  259200)
            # newly created ones time out in an hour
            self.timeout_reg = self.settings.get('db.timeout_reg',
                                                 10800)
            self.timeout_deleted = self.settings.get('db.timeout_deleted',
                                                 86400)
        except Exception, e:
            warnings.warn(repr(e))
            if logger:
                logger.log(msg='Could not initialize Storage "%s"' % str(e),
                           type='error', severity=LOG.CRITICAL)
            raise e

    #TODO: add health_check to check memcache server connection

    def update_channel(self, pk, vers, logger):
        if pk is None:
            return False

        try:
            record, cas = self.mc.gets(pk)
            if record and record['s'] != self.DELETED:
                record['v'] = vers
                record['s'] = self.LIVE
                record['l'] = int(time.time())
                if self.mc.cas(pk, record, cas, self.timeout_live):
                # Only update the db if memcache let you update.
                # nice way to limit updates.
                    return super(Storage, self).update_channel(pk, vers,
                                                               logger)
                return True
            else:
                return self.register_appid(None, pk, logger, vers)
        except Exception, e:
            warnings.warn(repr(e))
            if logger:
                logger.log(msg="Uncaught error %s " % repr(e),
                           type='error', severity=LOG.WARNING)
            raise e
        return False

    def register_appid(self, uaid, appid, logger, version=None):
        try:
            appidarr, cas = self.mc.gets(uaid)
            if appidarr is None:
                appidarr = []
            if appid in appidarr:
                return False
            # Temp patch until all code transitioned to pk
            if '.' in appid:
                pk = appid
                uaid, appid = pk.split('.')
            else:
                pk = '%s.%s' % (uaid, appid)
            # don't re-register.
            rec = self.mc.get(pk)
            if rec:
                return False
            data = {'v': version,
                    's': self.REGISTERED,
                    'l': int(time.time())}
            timeout = self.timeout_reg
            if version:
                data['s'] = self.LIVE
                timeout = self.timeout_live
            if not self.mc.set(pk, data, timeout):
                return False
            appidarr.append(appid)
            ok = self.mc.cas(uaid, appidarr,
                             cas, self.timeout_live)
            while ok is None or not ok:
                # mid air collision?
                appidarr, cas = self.mc.gets(uaid)
                if appid in appidarr:
                    return False
                appidarr.append(appid)
                ok = self.mc.cas(uaid, appidarr, cas, self.timeout_live)
            return super(Storage, self).register_appid(uaid, appid, logger)
        except Exception, e:
            warnings.warn(repr(e))
            if logger:
                logger.log(type='error', severity=LOG.ERROR, msg=repr(e))
            return False
        return True

    def delete_appid(self, uaid, appid, logger, clearOnly=False):
        if appid is None or uaid is None:
            return False
        try:
            if '.' in appid:
                pk = appid
                uaid, appid = appid.split('.')
            else:
                pk = '%s.%s' % (uaid, appid)
            appidarr, cas = self.mc.gets(uaid)
            loc = appidarr.index(appid)
            del appidarr[loc]
            if not self.mc.cas(uaid, appidarr, cas):
                return False
            # We don't care if we repeatedly delete this record.
            dmw = self.mc.get(pk)
            if clearOnly:
                self.mc.delete(pk)
            else:
                dmw['s'] = self.DELETED
                self.mc.set(pk, dmw, self.timeout_deleted)
            return super(Storage, self).delete_appid(uaid, appid,
                                                     logger, clearOnly)
        except ValueError, e:
            return False
        except Exception, e:
            warnings.warn(repr(e))
            if logger:
                logger.log(type='error', severity=LOG.WARN, msg=repr(e))
            return False
        return True

    def _restore(self, uaid, last_accessed=None, logger=None):
        """ Restore memcache from sql """
        #TODO: finish
        data = super(Storage, self).get_updates(self, uaid, logger,
                                                withLatest=True)
        if not data or not len(data.get('updates')):
            return {'updates': [], 'expired': []}
        appidarr = []
        for update in data.get('updates'):
            appid = update['channelID']
            appidarr.append(appid)
            self.mc.set('%s.%s' % (uaid, appid), {
                's': self.LIVE,
                'l': update['last'] or int(time.time()),
                'v': update['version']}, self.timeout_live)
        return self.get_updates(uaid, last_accessed, logger)

    def get_updates(self, uaid, last_accessed=None, logger=None):
        if uaid is None:
            raise StorageException('No UserAgentID provided')
        try:
            result = {'updates': [], 'expired': []}
            appidarr, cas = self.mc.gets(uaid)
            if appidarr is None:
                return result
            keys = [uaid + '.' + appid for appid in appidarr]
            recs = self.mc.get_multi(keys)
            if (len(recs) < len(appidarr)):
                return self._restore(uaid, last_accessed, logger)
            for appid in appidarr:
                pk = '%s.%s' % (uaid, appid)
                try:
                    rec = recs[pk]
                except KeyError:
                    del appidarr[pk]
                    continue
                if last_accessed:
                    if rec['l'] < last_accessed:
                        continue
                if rec['s'] == self.LIVE:
                    result['updates'].append({'channelID': appid,
                                              'version': rec['v']})
                if rec['s'] == self.DELETED:
                    result['expired'].append(appid)
                    del appidarr[appidarr.index(appid)]
                    self.mc.delete(pk)
            if len(result['expired']):
                self.mc.cas(uaid, appidarr, cas)
            return result
        except Exception, e:
            warnings.warn(repr(e))
            if logger:
                logger.log(type='error', severity=LOG.WARN, msg=repr(e))
            raise e
        return False

    def reload_data(self, uaid, data, logger):
        # Only allow if we're in recovery?
        if uaid is None:
            raise StorageException('No UserAgentID specified')
        if data is None or len(data) == 0:
            raise StorageException('No Data specified')
        if self._uaid_is_known(uaid):
            raise StorageException('Already Loaded Data')
        appidarr = []
        try:
            for datum in data:
                appid = datum.get('channelID')
                appidarr.append(appid)
                pk = '%s.%s' % (uaid, appid)
                data = {'s': self.LIVE,
                        'l': int(time.time()),
                        'v': datum.get('version')}
                self.mc.add(pk, data, self.timeout_live)
            self.mc.add(uaid, appidarr)
            return ','.join(self.mc.get(uaid))
        except Exception, e:
            warnings.warn(repr(e))
            if logger:
                logger.log(type='error', severity=LOG.WARN, msg=repr(e))
        return False

    def _get_record(self, pk):
        result = []
        try:
            result = self.mc.get(pk)
            if result is None:
                result = super(Storage, self)._get_record(pk)
            if not result:
                return result
            uaid, appid = pk.split('.')
            return {'uaid': uaid,
                    'version': result['v'],
                    'state': result['s'],
                    'last': result['l']}
        except Exception, e:
            warnings.warn(repr(e))
            if logger:
                logger.log(type='error', severity=LOG.WARN, msg=repr(e))

    def _uaid_is_known(self, uaid):
        return self.mc.get(uaid) is not None

    def _gc(self, settings):
        if self.flags.get('recovery'):
            return
        # delete all records marked deleted that are older
        #   than db.clean.deleted
        # delete all records that are unused older than db.clean.unused

    def _load(self, data=[]):
        appids = {}
        for datum in data:
            uaid = datum['uaid']
            if not uaid in appids:
                appids[uaid] = []
            pk = '%s.%s' % (datum['uaid'], datum['channelID'])
            self.mc.add(pk, {'v': datum['version'],
                             'l': datum.get('last_accessed'),
                             's': datum.get('state', 1)},
                             self.timeout_live)
            appids[uaid].append(datum['channelID'])
        for uaid in appids:
            self.mc.add(uaid, appids[uaid])
        super(Storage, self)._load(data)

    def purge(self):
        super(Storage, self).purge()
        with self.mc._connect() as mc:
            mc.flush_all()

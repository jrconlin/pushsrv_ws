# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import time
import warnings
from . import StorageBase, StorageException
from .. import LOG
from sqlalchemy import (Column, Integer, String,
                        create_engine, MetaData, text)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

Base = declarative_base()


class SimplePushSQL(Base):
    __tablename__ = 'simplepush_ws'
    ## this should be a multi-column index. No idea how to do that
    ## cleanly in SQLAlchemy's ORM.
    appid = Column('appid', String(36), primary_key=True, unique=True)
    uaid = Column('uaid', String(36), index=True)
    vers = Column('version', String(36), nullable=True)
    last = Column('last_accessed', Integer, index=True)
    state = Column('state', Integer, default=1)
    pk = Column('pk', String(70), index=True)


class Storage(StorageBase):
    __database__ = 'simplepush'
    DELETED = 0
    LIVE = 1
    REGISTERED = 2
    logger = None

    def __init__(self, config, flags={}, logger=None, **kw):
        try:
            super(Storage, self).__init__(config, **kw)
            self.metadata = MetaData()
            self._connect()
            self.flags = flags
            self.logger = logger
            #TODO: add the most common index.
        except Exception, e:
            warnings.warn(repr(e))
            if self.logger:
                self.logger.log(msg='Could not initialize Storage "%s"' %
                                str(e),
                                type='error', severity=LOG.CRITICAL)
            raise e

    def _connect(self):
        try:
            userpass = ''
            host = ''
            if (self.settings.get('db.user')):
                userpass = '%s:%s@' % (self.settings.get('db.user'),
                                       self.settings.get('db.password'))
            if (self.settings.get('db.host')):
                host = '%s' % self.settings.get('db.host')
            dsn = '%s://%s%s/%s' % (self.settings.get('db.type', 'mysql'),
                                    userpass, host,
                                    self.settings.get('db.db',
                                                      self.__database__))
            self.engine = create_engine(dsn, pool_recycle=3600)
            Base.metadata.create_all(self.engine)
            self.Session = scoped_session(sessionmaker(bind=self.engine,
                                                       expire_on_commit=True))
            #self.metadata.create_all(self.engine)
        except Exception, e:
            warnings.warn(repr(e))
            if self.logger:
                self.logger.log(msg='Could not connect to db "%s"' % repr(e),
                           type='error', severity=LOG.EMERGENCY)
            raise e

    def health_check(self):
        try:
            healthy = True
            session = self.Session()
            sp = SimplePushSQL(appid='test', uaid='test',
                               pk='test.test',
                               vers=0, last=int(time.time()))
            session.commit()
            sp = self.session.query(SimplePushSQL).filter_by(pk='test.test')
            session.delete(sp)
        except Exception, e:
            warnings.warn(str(e))
            return False
        return healthy

    def update_channel(self, pk, vers, logger):
        if pk is None:
            return False
        session = self.Session()
        try:
            if '.' not in pk:
                rec = session.query(SimplePushSQL).filter(
                            SimplePushSQL.appid == pk,
                            SimplePushSQL.state != self.DELETED).first()
            else:
                rec = session.query(SimplePushSQL).filter(
                                SimplePushSQL.pk == pk,
                                SimplePushSQL.state != self.DELETED).first()
            if (rec):
                rec.vers = vers
                rec.state = self.LIVE
                rec.last = int(time.time())
                session.commit()
            else:  # ES
                return self.register_appid(None, pk, logger, vers)
            return True
        except Exception, e:
            warnings.warn(repr(e))
            session.rollback()
            if logger:
                logger.log(msg="Uncaught error %s " % repr(e),
                           type='error', severity=LOG.WARNING)
            raise e
        return False

    def register_appid(self, uaid, appid, logger, version=None):
        try:
            session = self.Session()
            # Temp patch until all code transitioned to pk
            if '.' in appid:
                pk = appid
                uaid, appid = pk.split('.')
            else:
                pk = '%s.%s' % (uaid, appid)
            session.add(SimplePushSQL(pk=pk,
                                      uaid=uaid,
                                      appid=appid,
                                      state=self.REGISTERED,
                                      vers=version,
                                      last=int(time.time())))
            session.commit()
        except Exception, e:
            import pdb; pdb.set_trace()
            warnings.warn(repr(e))
            if logger:
                logger.log(type='error', severity=LOG.ERROR, msg=repr(e))
            return False
        return True

    def delete_appid(self, uaid, appid, logger, clearOnly=False):
        if appid is None or uaid is None:
            return False
        try:
            session = self.Session()
            if '.' in appid:
                pk = appid
                uaid, appid = appid.split('.')
            else:
                pk = '%s.%s' % (uaid, appid)
            rec = session.query(SimplePushSQL).filter_by(pk=pk).first()
            if rec:
                if clearOnly:
                    session.delete(rec)
                else:
                    rec.state = self.DELETED
                session.commit()
        except Exception, e:
            warnings.warn(repr(e))
            if logger:
                logger.log(type='error', severity=LOG.WARN, msg=repr(e))
            return False
        return True

    def get_updates(self, uaid, last_accessed=None, logger=None,
                    withLatest=False):
        if uaid is None:
            raise StorageException('No UserAgentID provided')
        try:
            sql = ('select appid, version, state, last_accessed from ' +
                   '%s where uaid=:uaid' % SimplePushSQL.__tablename__)
            params = {'uaid': uaid}
            if last_accessed:
                sql += ' and last_accessed >= :last'
                params['last'] = last_accessed
            records = self.engine.execute(text(sql), **dict(params))
            updates = []
            expired = []
            for record in records:
                if record.state:
                    data = {'channelID': record.appid,
                                    'version': record.version}
                    if withLatest:
                        data['last'] = record.last
                    updates.append(data)
                else:
                    expired.append(record.appid)
            if not len(updates) and self.flags.get('recovery'):
                return None
            return {'updates': updates,
                    'expired': expired}
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
        try:
            session = self.Session()
            digest = []
            if session.query(SimplePushSQL).filter_by(uaid=uaid).count():
                return False
            for datum in data:
                appid = datum.get('channelID')
                session.add(SimplePushSQL(appid=appid,
                                          uaid=uaid,
                                          vers=datum.get('version')))
                digest.append(datum.get('channelID'))
            session.commit()
            return ",".join(digest)
        except Exception, e:
            warnings.warn(repr(e))
            if logger:
                logger.log(type='error', severity=LOG.WARN, msg=repr(e))
        return False

    def _get_record(self, pk):
        try:
            session = self.Session()
            rec = session.query(SimplePushSQL).filter_by(pk=pk).first()
            if rec is None:
                return None
            result = rec.__dict__
            result['version'] = result['vers']
            del result['vers']
            return result
        except Exception, e:
            warnings.warn(repr(e))
            if self.logger:
                self.logger.log(type='error', severity=LOG.WARN, msg=repr(e))

    def _uaid_is_known(self, uaid):
        return self.Session().query(SimplePushSQL).filter_by(
                uaid=uaid).first() is not None

    def _gc(self, settings):
        if self.flags.get('recovery'):
            return
        now = time.time()
        # delete all records marked deleted that are older than
        #   db.clean.deleted
        # delete all records that are unused older than db.clean.unused

    def _load(self, data=[]):
        session = self.Session()
        for datum in data:
            pk = '%s.%s' % (datum['uaid'], datum['channelID'])
            session.add(SimplePushSQL(pk=pk,
                                      appid=datum['channelID'],
                                      uaid=datum['uaid'],
                                      vers=datum['version'],
                                      last=datum.get('last_accessed'),
                                      state=datum.get('state', 1)))
        session.commit()

    def purge(self):
        session = self.Session()
        sql = 'delete from %s;' % SimplePushSQL.__tablename__
        self.engine.execute(text(sql))
        session.commit()

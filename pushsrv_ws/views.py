# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import time
import tornado.web
import traceback
from .constants import LOG
from .storage import StorageException
from datetime import datetime
from utils import gen_id, get_last_accessed, gen_endpoint


class RESTPushBase(tornado.web.RequestHandler):
    def initialize(self, config=None, storage=None, logger=None, flags=None,
                   dispatch=None):
        self.storage = storage
        self.logger = logger
        self.config = config
        self.flags = flags
        self.dispatch = dispatch


""" Handlers for REST functions.
"""


class RegisterHandler(RESTPushBase):
    def put(self, args=None, **kw):
        request = self.request
        appid = args or gen_id()
        uaid = request.headers.get('X-UserAgent-ID', gen_id())
        gid = '%s.%s' % (uaid, appid)
        if self.storage.register_appid(uaid, gid, self.logger):
            self.write(json.dumps({'channelID': appid,
                              'uaid': uaid,
                              'pushEndpoint': gen_endpoint(self.config, gid)}))
        else:
            self.send_error(409)  # CONFLICT

    def get(self, args=None, **kw):
        self.write(json.dumps({'error': 'Obsolete. Use PUT'}))


class ItemHandler(RESTPushBase):
    def delete(self, gid=None, **kw):
        if gid is None:
            return self.write_error(403)  # Bad URL
        if not self.storage.delete_appid(gid, self.logger):
            return self.write_error(500)
        return self.write(json.dumps({}))


class UpdateHandler(RESTPushBase):
    def get(self, arg=None, **kw):
        uaid = self.request.headers.get('X-UserAgent-ID')
        if not uaid:
            return self.write_error(403)
        last_accessed = get_last_accessed(self.request)
        try:
            updates = self.storage.get_updates(uaid, last_accessed,
                                               self.logger)
        except StorageException, e:
            self.logger.log(msg=repr(e), type='error', severity=LOG.DEBUG)
            return self.write_error(410)  # GONE
        if updates is False:
            return self.write_error(500)  # SERVER ERROR
        return self.write(json.dumps(updates))

    def post(self, arg=None, **kw):
        uaid = self.request.headers.get('X-UserAgent-ID')
        if not uaid:
            return self.write_error(403)
        try:
            # we don't really care what the old data was,
            # but if we did, we'd do something like the following:
            #data = json.loads(self.request.body)
            #digest = self.storage.reload_data(data)
            return self.write(json.dumps({'digest': []}))
        except Exception:
            self.logger.log(msg=traceback.format_exc(), type='error',
                            severity=LOG.WARN)
            return self.write_error(410)  # GONE

    def put(self, gid=None, **kw):
        if gid is None:
            return self.write_error(403)  #
        version = int(time.mktime(datetime.utcnow().timetuple()))
        (uaid, channelID) = gid.split('.')
        try:
            if self.storage.update_channel(gid, version, self.logger):
                if self.dispatch:
                    self.dispatch.queue(uaid, channelID)
                return self.write(json.dumps({}))
            else:
                return self.write_error(503)
        except Exception, e:
            self.logger.log(msg=traceback.format_exc(), type='error',
                            severity=LOG.CRITICAL)
            raise e


class StatusHandler(RESTPushBase):
    def get(self, arg=None, **kw):
        ## TODO: Perform simple health-checks
        return self.write("ok")

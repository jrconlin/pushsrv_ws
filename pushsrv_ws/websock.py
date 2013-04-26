# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from .constants import LOG
from .wsdispatch import WSDispatch
from utils import gen_id, gen_endpoint
import json
import time
import tornado.websocket


class WSException(Exception):
    pass


class PushWSHandler(tornado.websocket.WebSocketHandler):

    """ Core websocket Handler.

        For alternate protocols, it's recommended to superclass this core
        and add appropriate calls where needed. (e.g. device wake-up wrappers
        for flush())
    """

    uaid = None

    def __init__(self, application=None, request=None, **kw):
        self.config = kw.get('config', {})
        self.storage = kw.get('storage', {})
        self.flags = kw.get('flags', {})
        self.logger = kw.get('logger')
        self.dispatch = kw.get('dispatch', WSDispatch())
        # unit test flag.
        self.test = kw.get('test', False)
        if self.test:
            self.return_buffer = ''
        # protocol handlers
        self.funcs = {'hello': self.hello,
                      'register': self.register,
                      'unregister': self.unregister,
                      'ack': self.ack,
                      'ping': self.ping}
        if (not kw.get('test', False)):
            super(PushWSHandler, self).__init__(application, request)

    # Websocket core functions
    def open(self, *args, **kw):
        if self.config.get('heartbeat_secs'):
            instance = tornado.ioloop.IOLoop.instance()
            self.hb_handle = instance.add_timeout(
                time.time() + int(self.config.get('heartbeat_secs')),
                self.heartbeat)
        pass

    def on_message(self, message):
        """ Handle all incoming websocket messages and dispatch to
            appropriate function.
        """
        try:
            msg = json.loads(message)
            mt = msg['messageType']
            if mt not in self.funcs.keys():
                self.error('Unknown command: %s' % msg)
                return
            result, chain = self.funcs[mt](msg)
            self.send(result)
            while chain is not None:
                result, chain = chain(message)
                self.send(result)
        except Exception, e:
            self.logger.log(type='error', msg=repr(e), severity=LOG.ERROR)
            self.error('Unable to process message (see logs)')

    def on_connection_close(self):
        """ The websocket connection has been severed, either directly
            by the client or indirectly via network instability.

            Attempt to garbage collect.
        """
        if self.uaid:
            self.dispatch.release(self.uaid)
        self.uaid = None
        if hasattr(self, 'hb_handle'):
            tornado.ioloop.IOLoop.instance().remove_timeout(self.hb_handle)
            self.hb_handle = None

    def close(self):
        """ Close a websocket
        """
        if not self.test:
            return super(PushWSHandler, self).close()

    def heartbeat(self):
        """ This is required to keep the ELB from killing the connection.
        """
        instance = tornado.ioloop.IOLoop.instance()
        if hasattr(self, 'hb_handle'):
            instance.remove_timeout(self.hb_handle)
        self.send({"messageType": 'heartbeat',
                   "data": time.time()})
        self.hb_handle = instance.add_timeout(
            time.time() + int(self.config.get('heartbeat_secs')),
            self.heartbeat)


    ## Protocol handler functions.
    def hello(self, msg):
        """ Register the UAID as an active listener.
        """
        status = 200
        if 'uaid' in msg:
            self.uaid = msg['uaid']
        else:
            self.uaid = gen_id()
        if not self.dispatch.register(self.uaid, self.flush, msg):
            self.logger.log(type='error',
                            severity=LOG.DEBUG,
                            msg="Could not register uaid %s" % self.uaid)
            status = 500
            # This is a bad request. Close the channel immediately.
            try:
                self.send({"messageType": "hello",
                           "status": status,
                           "uaid": self.uaid})
            except Exception:
                pass
            self.close()
        # chain the flush function to send existing data.
        # Note: For alternate protocols (e.g. UDP, initialize the calls here.)
        return ({"messageType": "hello",
                "status": status,
                "uaid": self.uaid}, self.flush)

    def register(self, msg):
        """ Request a new endpoint for a channelID
        """
        status = 200
        gid = '%s.%s' % (self.uaid, msg['channelID'])
        response = {"messageType": "register",
                    "status": status,
                    "pushEndpoint": gen_endpoint(self.config, gid) }
        return (response, None)

    def unregister(self, msg):
        """ Drop the channelID
        """
        status = 200
        response = {"messageType": "unregister",
                    "status": status,
                    "channelID": msg['channelID']}
        return (response, None)

    def ack(self, msg):
        """ Client is responding that has processed the channelIDs.
            Remove them from storage
        """
        content = self.storage.get_updates(self.uaid, None, self.logger)
        ids = {}
        for item in content['updates']:
            ids[item['channelID']] = item['version']
        for item in msg['expired']:
            self.storage.delete_appid(self.uaid, item, self.logger,
                                      clearOnly=True)
        for item in msg['updates']:
            try:
                if ids[item['channelID']] == item['version']:
                    self.storage.delete_appid(self.uaid, item['channelID'],
                                              self.logger, clearOnly=True)
            except KeyError:
                continue
        # if there's anything left, send it again.
        return (None, self.flush)

    def ping(self, msg):
        return({'messageType':'pong'}, None)

    ## Utility Functions.
    def flush(self, uaid=None, channelID=None, msg=None):
        """ Fetch all pending notifications and publish to client.

            This function is registered to be called whenever a new
            Notification is posted via the REST interface.

        """
        content = self.storage.get_updates(self.uaid, None, self.logger)
        # only send data if we have any.
        if len(content['updates']) or len(content['expired']):
            content['messageType'] = 'notification'
            # force a send here since we can be called outside of the chain
            try:
                self.send(content)
            except IOError:
                self.on_connection_close()
                self._retry()
        # Already sent content, and no additional action required
        # remove any retransmittal timers
        return (None, None)

    def error(self, err, send=True):
        """ Standardize error response
        """
        self.logger.log(type='error', msg=err, severity=LOG.DEBUG)
        if send:
            errmsg = {'messageType': 'error',
                      'error': err}
            try:
                self.send(json.dumps(errmsg))
            except Exception:
                self.on_connection_close()
                raise

    def send(self, message):
        """ Return a response to the client.

            Overwrite for partner specific responses
        """
        if message is None:
            return
        try:
            if not self.test:
                self.write_message(message)
            else:
                self.return_buffer += json.dumps(message)
        except Exception, e:
            self.logger.log(type="error", severity=LOG.ERROR,
                            msg='Unable to send message %s ' % repr(e))
            self.on_connection_close()
            raise
        pass

    def _retry(self):
        ## Use whatever proprietary means to wake the remote device.
        ## Note: if using something like an IP ping, may want to only
        ## attempt a wake up one or two times. IP address may be
        ## reassigned, causing us to spend a lot of effort keeping someone
        ## else's phone from sleeping.
        #
        # instance = torando.ioloop.IOLoop.current()
        # if self.to is None:
        #   self.to = instance.add_timeout(self.config.get('timeout', 600),
        #                                  self.dispatch.wakeDevice())
        #
        pass

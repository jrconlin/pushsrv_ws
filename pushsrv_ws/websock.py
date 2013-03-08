from .constants import LOG
from utils import gen_id, gen_endpoint
import json
import tornado.websocket
import uuid


class WSDispatch():
    """ Very simple message dispatcher.

        It stores a callback for each registered UAID.
    """

    _uaids={}

    def __init__(self, config={}, flags={}):
        pass

    def _uuid2idx(self, uaid):
        try:
            idx = uuid.UUID(uaid).bytes
        except:
            idx = uaid
        return idx

    def register(self, uaid, callback):
        idx = self._uuid2idx(uaid)
        if idx not in self._uaids.keys():
            self._uaids[idx] = callback
            return True
        return False

    def queue(self, uaid, channelID, message):
        idx = self._uuid2idx(uaid)
        try:
            if self._uaids[idx](channelID, message):
                return True
        except KeyError:
          # archive message
          pass
        return False

    def release(self, uaid):
        idx = self._uuid2idx(uaid)
        del self._uaids[idx]


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
        self.funcs = {'hello': self.hello,
                      'register': self.register,
                      'unregister': self.unregister,
                      'ack': self.ack}
        super(PushWSHandler, self).__init__(application, request)

    # Websocket core functions
    def open(self):
        """ Perform initial websocket connection.

            This is not the "hello" handshake.
        """
        pass

    def on_message(self, message):
        """ Handle all incoming messages and dispatch to appropriate function.
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
            import pdb; pdb.set_trace()
            self.error('Unhandled exception: %s' % repr(e))

    def on_connection_close(self):
        """ The connection has been severed. Attempt to garbage collect.
        """
        if self.uaid:
            self.dispatch.release(self.uaid)
        self.uaid = None
        self.close()

    ## Protocol handler functions.
    def hello(self, msg):
        """ Register the UAID as an active listener.
        """
        status = 200
        self.uaid = msg['uaid'] or gen_id()
        if not self.dispatch.register(self.uaid, self.flush):
            self.logger.log(type='error',
                            severity=LOG.DEBUG,
                            msg="Could not register uaid %s" % self.uaid)
            status = 500
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
            import pdb; pdb.set_trace()
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
            self.send(content)
        # Already sent content, and no additional action required
        return (None, None)

    def error(self, err, send=True):
        """ Standardize error response
        """
        self.logger.log(type='error', msg=err, severity=LOG.DEBUG)
        if send:
            errmsg = {'messageType': 'error',
                      'error': err }
            try:
                self.send(json.dumps(errmsg))
            except Exception, e:
                self.on_connection_close()

    def send(self, message):
        """ Return a response to the client.

        Overwrite for partner specific responses """
        if message is None:
            return
        try:
            self.write_message(message)
        except Exception, e:
            import pdb; pdb.set_trace()
            self.error('Reply failed %s ' % repr(e), False)
        pass

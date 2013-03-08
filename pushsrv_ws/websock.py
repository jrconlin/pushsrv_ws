import tornado.websocket
import json
import traceback
import uuid
from utils import gen_id, gen_endpoint
from .constants import LOG, VERS
from .storage import StorageException


class WSDispatch():
    """ Very simple message dispatcher.

        Do we need thread locking? (tornado doesn't require it.)
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

    uaid = None
    content = {}

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

    def error(self, err, send=True):
        self.logger.log(type='error', msg=err)
        if send:
            errmsg = {'messageType': 'error',
                      'error': err }
            try:
                self.send(json.dumps(errmsg))
            except Exception, e:
                self.on_connection_close()

    def open(self):
        # perform handshake, associate UAID to handler
        pass

    def on_message(self, message):
        try:
            import pdb; pdb.set_trace()
            msg = json.loads(message)
            mt = msg['messageType']
            if mt not in self.funcs.keys():
                self.error('Unknown command: %s' % msg)
            result, chain = self.funcs[mt](msg)
            self.send(result)
            while chain is not None:
                result, chain = chain(message)
                self.send(result)
        except Exception, e:
            import pdb; pdb.set_trace()
            self.error('Unhandled exception: %s' % repr(e))

    def on_connection_close(self):
        # garbage collection
        if self.uaid:
            self.dispatch.release(self.uaid)
        self.uaid = None
        self.close()
        pass

    def flush(self, uaid=None, channelID=None, msg=None):
        # fetch pending messages from storage
        content = self.storage.get_updates(self.uaid, None, self.logger)
        # only send data if we have any.
        import pdb; pdb.set_trace()
        if len(content['updates']) or len(content['expired']):
            content['messageType'] = 'notification'
            # force a send here since we can be called outside of the chain
            self.send(content)
        # Already sent content, and no additional action required
        return (None, None)


    def hello(self, msg):
        # register UAID
        import pdb; pdb.set_trace();
        status = 200
        self.uaid = msg['uaid'] or gen_id()
        # register the UAID with dispatch as a listener,
        # and call the flush function when new data is submitted.
        if not self.dispatch.register(self.uaid, self.flush):
            status = 500
        return ({"messageType": "hello",
                "status": status,
                "uaid": self.uaid}, self.flush)

    def register(self, msg):
        # register new channelID
        status = 200
        # return ack
        gid = '%s.%s' % (self.uaid, msg['channelID'])
        response = {
                "messageType": "register",
                "status": status,
                "pushEndpoint": gen_endpoint(self.config, gid) }
        return (response, None)

    def unregister(self, msg):
        # unregister the channelID
        status = 200
        response  = {"messageType": "unregister",
                     "status": status,
                     "channelID": msg['channelID']}
        return (response, None)

    def ack(self, msg):
        # remove pending ChannelID content from memcache
        for item in msg.updates:
            try:
                if self.content[item['channelID']] == item.version:
                    del self.content[item['channelID']]
            except KeyError:
                continue
        # if there's anything left, send it again.
        return (None, self.flush)

    def send(self, message):
        """ Overwrite for partner specific responses """
        if message is None:
            return
        try:
            self.write_message(message)
        except Exception, e:
            import pdb; pdb.set_trace()
            self.error('Reply failed %s ' % repr(e), False)
        pass

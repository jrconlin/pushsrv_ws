import tornado.websocket
import json
import traceback
from utils import gen_id, get_last_accessed
from .constants import LOG, VERS
from .storage import StorageException

class PushWSHandler(tornado.websocket.WebSocketHandler):

    def __init__(self, application=None, request=None, **kw):
        self.config = kw.get('config', {})
        self.storage = kw.get('storage', {})
        self.flags = kw.get('flags', {})
        self.logger = kw.get('logger')
        super(PushWSHandler, self).__init__(application, request)

    def open(self):
        # perform handshake, associate UAID to handler
        pass

    def on_message(self, message):
        # route message to sub-handler
        pass

    def on_connection_close(self):
        # garbage collection
        pass


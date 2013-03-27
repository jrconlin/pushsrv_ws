# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from . import TConfig, FakeLogger
from ..websock import PushWSHandler
from pushsrv_ws.storage.sql import (Storage)
import json
import unittest2


# I *REALLY* hope that tornado is awesome when it comes to handling
# websockets. Because it's crap like this...

class TestWS(unittest2.TestCase):

    def setUp(self):
        self.storage = Storage(config=TConfig({'db.type': 'sqlite',
                                               'db.db': ':memory:'}))
        self.logger = FakeLogger()
        self.app = PushWSHandler(logger=self.logger, storage=self.storage,
                                 test=True)

    # teardown does bad things.
    def test_ws(self):
        # HELLO Message
        self.app.on_message(
            json.dumps({'messageType': 'hello',
                        'uaid': 'test',
                        'channelIDs': ['alpha',
                                       'beta'],
                        'interface': {'ip': '127.0.0.1',
                                      'port': '1234'}
                       }))
        ret_obj = json.loads(self.app.return_buffer)
        self.assertEqual(ret_obj['status'], 200)
        self.assertEqual(ret_obj['uaid'], 'test')
        self.assertEqual(ret_obj['messageType'], 'hello')
        self.app.return_buffer = ''
        # register a new channel
        self.app.on_message(
            json.dumps({'messageType': 'register',
                        'channelID': 'test_ch'}))
        ret_obj = json.loads(self.app.return_buffer)
        self.app.return_buffer = ''
        self.assertEqual(ret_obj['status'], 200)
        self.assertEqual(ret_obj['messageType'], 'register')
        assert('test.test_ch' in ret_obj['pushEndpoint'])
        # fake a new message on the endpoint.
        self.app.storage.update_channel('test.test_ch', 1234, self.logger)
        self.app.dispatch.queue('test', 'test_ch')
        ret_obj = json.loads(self.app.return_buffer)
        self.app.return_buffer = ''
        self.assertEqual(ret_obj['messageType'], 'notification')
        self.assertEqual(ret_obj['updates'][0]['version'], "1234")
        # send an ACK
        ret_obj['messageType'] = 'ack'
        self.app.on_message(json.dumps(ret_obj))
        # check that the records have been cleared.
        content = self.app.storage.get_updates('test', None, self.logger)
        self.assertEqual(len(content['updates']), 0)

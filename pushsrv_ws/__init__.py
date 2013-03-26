 This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""Main entry point
"""

from ConfigParser import (ConfigParser, NoSectionError)
from pushsrv_ws.constants import LOG
from pushsrv_ws.utils import _resolve_name
from pushsrv_ws.views import (RegisterHandler, ItemHandler, UpdateHandler)
from tornado.options import define
import tornado.web
import tornado.websocket
import traceback

define("config", default="pushsrv.ini", help="Configuration file path")


def safe_get(config, section, key, default=None):
    try:
        if type(config) == dict:
            return config.get(key, default)
        cf = dict(config.items(section))
        return cf.get(key, default)
    except Exception, e:
        traceback.print_exc()
        return default


def main(options, **kw):
    configp = ConfigParser()
    settings_file = ''
    try:
        settings_file = options.config
        configp.readfp(open(settings_file))
        config = dict(configp.items('app:main'))
        try:
            sconfig = dict(configp.items('server:main'))
        except NoSectionError:
            sconfig = {}
    except AttributeError:
        if type(options) == dict:
            config = options
            configp = config
            sconfig = {}
    ## Live configuration options
    flags = _resolve_name(safe_get(configp, 'app:main', 'flags.backend',
                           "pushsrv_ws.storage.fakeflags.ConfigFlags"))(config)
    ## backend data storage tool
    storage = _resolve_name(safe_get(configp, 'app:main', 'db.backend',
                              "pushsrv_ws.storage.sql.Storage"))(config, flags)
    ## Logging and metrics
    logger = _resolve_name(safe_get(configp, 'app:main', 'logging.backend',
                           "pushsrv_ws.logger.Logging"))(config, settings_file)
    ## Websocket dispatcher
    ## NOTE: if you're adding proprietary network elements (e.g. UDP wakeup)
    ##   please subclass pushsrv_ws/websock.py and set the configuration to
    ##   load the new file as the dispatch.backend
    dispatch = _resolve_name(safe_get(configp, 'app:main', 'dispatch.backend',
                           "pushsrv_ws.websock.WSDispatch"))(config, flags)

    ## Websocket Handler (NOTE, this is initialized on call)
    wshandler = _resolve_name(safe_get(configp, 'app:main',
                                       'websockhandler.backend',
                                       'pushsrv_ws.websock.PushWSHandler'))
    init_args = {'config': config,
                 'storage': storage,
                 'flags': flags,
                 'logger': logger,
                 'dispatch': dispatch}
    ## Entry points for the REST API, including the PUT update handler
    application = tornado.web.Application([
        (r"/v1/register/([^/]*)", RegisterHandler, init_args),
        (r"/v1/update/([^/]*)", UpdateHandler, init_args),
        (r"/v1/([^/]*)", ItemHandler, init_args),
        (r"/ws", wshandler, init_args)
    ], init_args)
    port = int(sconfig.get('port', '8081'))
    logger.log(type='debug', severity=LOG.INFO,
               msg="Starting on port %s" % port)
    application.listen(port)
    tornado.ioloop.IOLoop.instance().start()



from tornado.options import define, options
from ConfigParser import (ConfigParser, NoSectionError)
from pushsrv_ws.views import (RegisterHandler, ItemHandler, UpdateHandler)
import tornado.web
import tornado.websocket
from pushsrv_ws.utils import _resolve_name
from pushsrv_ws.constants import LOG
from pushsrv_ws.websock import (PushWSHandler)


define("config", default="pushsrv.ini", help="Configuration file path")


def safe_get(config, section, key, default=None):
    try:
        cf = dict(config.items(section))
        return cf.get(key, default)
    except Exception, e:
        import pdb; pdb.set_trace()
        print e
        return default


def main(options):
    configp = ConfigParser()
    settings_file = options.config
    configp.readfp(open(settings_file))
    config = dict(configp.items('app:main'))
    flags = _resolve_name(safe_get(configp, 'app:main', 'flags.backend',
                           "pushsrv_ws.storage.fakeflags.ConfigFlags"))(config)
    storage = _resolve_name(safe_get(configp, 'app:main', 'db.backend',
                              "pushsrv_ws.storage.sql.Storage"))(config, flags)
    logger = _resolve_name(safe_get(configp, 'app:main', 'logging.backend',
                           "pushsrv_ws.logger.Logging"))(config, settings_file)
    """ path, handler, dict(args) """
    init_args = {'config':config,
                 'storage':storage,
                 'flags':flags,
                 'logger':logger}

    import pdb; pdb.set_trace()
    application = tornado.web.Application([
        (r"/v1/register/([^/]*)", RegisterHandler, init_args),
        (r"/v1/update/([^/]*)", UpdateHandler, init_args),
        (r"/v1/([^/]*)", ItemHandler, init_args),
        (r"/ws", PushWSHandler, init_args)
    ], init_args)
    try:
        sconfig = dict(configp.items('server:main'))
    except NoSectionError:
        sconfig = {}
    port = int(sconfig.get('port', '8081'))
    logger.log(type='debug', severity=LOG.INFO,
               msg="Starting on port %s" % port)
    application.listen(port)
    tornado.ioloop.IOLoop.instance().start()



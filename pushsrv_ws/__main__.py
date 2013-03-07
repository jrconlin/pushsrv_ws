from tornado.options import define, options
from pushsrv_ws import main

if not 'config' in options:
    define("config", default="pushsrv.ini", help="Configuration file path")

if __name__ == "__main__":
    main(options)

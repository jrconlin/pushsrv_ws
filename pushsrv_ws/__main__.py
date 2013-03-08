# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from pushsrv_ws import main
from tornado.options import define, options

if not 'config' in options:
    define("config", default="pushsrv.ini", help="Configuration file path")

if __name__ == "__main__":
    main(options)

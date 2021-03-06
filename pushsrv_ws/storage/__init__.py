# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dateutil import parser
from inspect import stack
import string


class StorageException(Exception):
    pass


class StorageBase(object):

    def __init__(self, config, **kw):
        self.config = config
        self.settings = config
        self.alphabet = string.digits + string.letters
        self.memory = {}

    def parse_date(self, datestr):
        if not datestr:
            return None
        try:
            return float(datestr)
        except ValueError:
            pass
        try:
            return float(parser.parse(datestr).strftime('%s'))
        except ValueError:
            pass
        return None

    # customize for each memory model

    def health_check(self):
        """ Check that the current model is working correctly """
        raise StorageException('No health check specified for %s' %
                                self.__class__.__name__)

    def purge(self):
        """ Purge all listings (ONLY FOR TESTING) """
        raise StorageException('Undefined required method: ' %
                               stack()[0][3])

    def gen_pk(self, uaid, appid):
        return ("%s.%s" % (uaid, appid))

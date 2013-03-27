# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from email import utils as eut
import calendar
import uuid


def str_to_UTC(datestr):
    """ convert a standard HTTP-date format to UTC seconds
    """
    secs = 0
    try:
        timet = eut.parsedate_tz(datestr)
        secs = int(calendar.timegm(timet[:8])) + timet[9]
    except Exception, e:
        raise e
    return secs


def get_last_accessed(request):
    """ bottleneck method to pull the appropriate "last_accessed"
        time from a given request.

        (Currently uses the "If-Modified-Since" header)
    """
    last_accessed = None
    last_accessed = None
    last_accessed_str = request.headers.get('If-Modified-Since')
    if last_accessed_str:
        last_accessed = str_to_UTC(last_accessed_str)
    return last_accessed


def gen_id(**kw):
    """ Generate a globally unique ID
    """
    base = uuid.uuid4().hex
    return base


def gen_endpoint(config, path):
    """ Generate a templated endpoint based on config information
    """
    template = config.get('endpoint.template',
                          '{proto}://{host}/{ver}update/{path}')
    return template.format(proto=config.get('endpoint.proto', 'http'),
                           host=config.get('endpoint.host', 'localhost:8081'),
                           ver=config.get('endpoint.ver', 'v1/'),
                           path=path)


def _resolve_name(name):
    """Resolves the python name path and returns the corresponding class.
    """
    ret = None
    parts = name.split('.')
    cursor = len(parts)
    module_name = parts[:cursor]
    last_exc = None

    while cursor > 0:
        try:
            ret = __import__('.'.join(module_name))
            break
        except ImportError, exc:
            last_exc = exc
            if cursor == 0:
                raise
            cursor -= 1
            module_name = parts[:cursor]

    for part in parts[1:]:
        try:
            ret = getattr(ret, part)
        except AttributeError:
            if last_exc is not None:
                raise last_exc
            raise ImportError(Name)

    if ret is None:
        if last_exc is not None:
            raise last_exc
        raise ImportError(name)

    return ret

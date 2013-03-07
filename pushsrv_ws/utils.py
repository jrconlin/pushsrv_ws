from email import utils as eut
import calendar
import uuid


def str_to_UTC(datestr):
    secs = 0
    try:
        timet = eut.parsedate_tz(datestr)
        secs = int(calendar.timegm(timet[:8])) + timet[9]
    except Exception, e:
        import pdb; pdb.set_trace();
        raise e
    return secs


def get_last_accessed(request):
    last_accessed = None
    last_accessed = None
    last_accessed_str = request.headers.get('If-Modified-Since')
    if last_accessed_str:
        last_accessed = str_to_UTC(last_accessed_str)
    return last_accessed


def gen_id(**kw):
    base = uuid.uuid4().hex
    return base


def _resolve_name(name):
    """Resolves the name and returns the corresponding object."""
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

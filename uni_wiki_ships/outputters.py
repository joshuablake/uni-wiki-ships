import inspect
import logging
import sys
import common
logger = logging.getLogger(__name__)

class InvalidLocation(common.AppException): pass

def available():
    return [i[0] for i in inspect.getmembers(sys.modules[__name__], callable)
                if not i[0].startswith('_')]

class _Outputter(object):
    def __init__(self, arguments, multiple_files):
        self.argument = arguments
        self.multiple_files = multiple_files
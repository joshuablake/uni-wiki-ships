import common
import errno
import inspect
import logging
import os
import sys
logger = logging.getLogger(__name__)

class InvalidSetup(common.AppException): pass

def available():
    return [i[0] for i in inspect.getmembers(sys.modules[__name__], inspect.isclass)
                if issubclass(i[1], _Outputter) and not i[0].startswith('_')]
    
class _Outputter(object):
    def __init__(self, argument, formatter, wiki):
        """Setup new outputter and validate inputs
        Params:
            argument (str): argument pass on command line
            multiple_files (bool): whether output will be in multiple files
        
        """
        
        self.argument = argument
        self.multiple_files = formatter.MULTIPLE_FILES
        self.formatter = formatter
        self.wiki = wiki
        self._validate()
    
    def _validate(self):
        pass 
        
class File(_Outputter):
    def __call__(self, output):
        logger.debug(output)
        if self.multiple_files:
            try:
                os.mkdir(self.argument)
            except OSError as e:
                if e.errno != errno.EEXIST or os.path.isfile(self.argument):
                    raise 
            for name, content in output.iteritems():
                self._write_file(os.path.join(self.argument,
                        name+self.formatter.FILE_EXT), content)
        else:
            self._write_file(self.argument, output)
                
    def _write_file(self, name, content):
        with open(name, 'w') as f:
            f.write(content.encode('UTF-8'))
        
    def _validate(self):
        if not self.argument:
            raise InvalidSetup('Need to pass path to file')

class Stdout(_Outputter):
    def __call__(self, text):
        print(text)
    
    def _validate(self):
        if self.multiple_files:
            raise InvalidSetup(
                    'Stdout needs format where only single file produced')
            
class Wiki(_Outputter):
    def _validate(self):
        if not self.wiki.logged_in:
            raise InvalidSetup('Need login to edit wiki')
        if not self.multiple_files:
            raise InvalidSetup('Must edit multiple wiki pages')
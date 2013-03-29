from io import BytesIO
from urllib import quote
import attributes
import collections
import csv
import inspect
import logging
import sys
import os
import errno
import common
logger = logging.getLogger(__name__)

class InvalidLocation(common.AppException): pass

def available():
    return [i[0] for i in inspect.getmembers(sys.modules[__name__], inspect.isclass)
                if issubclass(i[1], _Formatter) and not i[0].startswith('_')]

class _Formatter(object):
    """Format the results"""
    MULTIPLE_FILES = False
    FILE_EXT = '.txt'
    
    def __call__(self, pages, ships, missing_pages, output_loc):
        self.pages = pages
        return self.format(
            self.check(pages, ships), missing_pages
        )
       
    def check(self, pages, ships):
        """Check the value for attributes on a ship wikipage
        
        Args:
            pages (dict): {ship_name: page_content} in wikitext
            ships (dict): {ship_name: {attribute_name: value}} for expected values
            attributes (list): list of attributes
        Returns:
            (dict): {ship_name: WrongAttr_tuple}
                WrongAttr_tuple: a named tuple with
                    (attribute_name, current_value, correct_value)
            
        """
        WrongAttr = collections.namedtuple('WrongAttr', ['attr', 'current', 'correct'])
        wrong = collections.defaultdict(list)
        for ship, page in pages.iteritems():
            for attribute in attributes.attributes:
                try:
                    expected = attribute.process(ships[ship])
                except attributes.NotPresentError:
                    logger.debug('Ship %s has no value in db for %s', ship, attribute)
                    expected = None
                try:
                    value = attribute.extract(page)
                except attributes.NotPresentError:
                    logger.info('%s has no value for %s', ship, attribute)
                    if not expected == None:
                        wrong[ship].append(WrongAttr(attribute, None, expected))
                    continue
                if not value == expected and abs(value - (expected or 0)) > 1:
                    logger.info('%s has incorrect value for %s', ship, attribute)
                    wrong[ship].append(WrongAttr(attribute, value, expected))
                else:
                    logger.debug('%s has correct value for %s', ship, attribute)
        return wrong
    
    def format(self, wrong_attrs, missing_pages):
        """Take incorrect attributes and output in correct format"""
        raise NotImplementedError()
                
class Text(_Formatter):
    def format(self, wrong_attrs, missing_pages):
        """Format as a human-readable text string"""
        ret = []
        for k in wrong_attrs:
            for i in wrong_attrs[k]:
                ret.append('{} has {} as {} but should be {}'\
                      .format(k, i.attr, i.current, i.correct))
        ret.append(', '.join(missing_pages) + 'are missing from wiki')
        return '\n'.join(ret)    
    
class Csv(_Formatter):
    FILE_EXT = '.csv'
    
    def format(self, wrong_attrs, missing_pages):
        """Format as CSV"""
        string = BytesIO()
        writer = csv.writer(string)
        writer.writerow(['Ship', 'Attribute', 'Current Value', 'Correct Value',
                         'Link'])
        for k in wrong_attrs:
            for i in wrong_attrs[k]:
                row = (k, i.attr, i.current, i.correct,
                       'http://wiki.eveuniversity.org/'+quote(k))
                logger.debug('Row: '+', '.join(str(i) for i in row))
                writer.writerow(row)
        for i in missing_pages:
            row = (i, 'Missing page', None, None,
                   'http://wiki.eveuniversity.org/'+quote(i))
            logger.debug('Row: '+', '.join(str(i) for i in row))
            writer.writerow(row)
        ret = string.getvalue()
        string.close()
        return ret

class Wikitext(_Formatter):
    MULTIPLE_FILES = True
    
    def format(self, wrong_attrs, missing_pages):
        """Format as Wikitext"""
        out = {}
        for k in wrong_attrs:
            page = self.pages[k]
            for i in wrong_attrs[k]:
                correct = '{0:,.9999g}'.format(i.correct)
                if correct.endswith('.0'): correct = correct[:-2]
                page = i.attr.regex.sub(r'|{}={}'\
                                    .format(i.attr, correct), page)
            out[k] = page
        return out
        
if __name__ == '__main__':
    print('\n'.join(available()))
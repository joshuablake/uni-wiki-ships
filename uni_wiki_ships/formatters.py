from atrributes import attributes, NotPresentError
import collections
import logging
import sys
import inspect
logger = logging.getLogger(__name__)

def available():
    return [i[0] for i in inspect.getmembers(sys.modules[__name__], inspect.isclass)
                if issubclass(i[1], _Formatter) and not i[0].startswith('_')]

class _Formatter(object):
    """Format the results"""
    
    def __call__(self, pages, ships, missing_pages, output_loc):
        self.output(
            self.format(
                self.check(pages, ships, attributes), missing_pages
            ),
            output_loc
        )
       
    def check(self, pages, ships, attributes):
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
            for attribute in attributes:
                try:
                    expected = attribute.process(ships[ship])
                except NotPresentError:
                    logger.debug('Ship %s has no value in db for %s', ship, attribute)
                    expected = None
                try:
                    value = attribute.extract(page)
                except NotPresentError:
                    logger.info('%s has no value for %s', ship, attribute)
                    if not expected == None:
                        wrong[ship].append(WrongAttr(attribute.name, None, expected))
                    continue
                if not value == expected and abs(value - (expected or 0)) > 1:
                    logger.info('%s has incorrect value for %s', ship, attribute)
                    wrong[ship].append(WrongAttr(attribute.name, value, expected))
                else:
                    logger.debug('%s has correct value for %s', ship, attribute)
        return wrong
    
    def format(self, wrong_attrs, missing_pages):
        """Take incorrect attributes and output in correct format"""
        raise NotImplementedError()
    
    def ouput(self, string, location):
        """Take formatted string and dump to location"""
        if location == 'stdout':
            out_file = sys.stdout
        else:
            out_file = open(location, 'wb')
        with out_file as write:
            write.write(string)
            
if __name__ == '__main__':
    print('\n'.join(available()))
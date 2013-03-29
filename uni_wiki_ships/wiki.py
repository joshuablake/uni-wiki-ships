from time import sleep
from urllib import quote
import datetime
import json
import logging
import urllib2
logger = logging.getLogger(__name__)

class Wiki(object):
    def __init__(self, url, delay):
        self._url = url
        self.delay = delay
    
    def login(self, username, password):
        pass
    
    def get_pages(self, pages):
        """Get pages from wiki in raw wikitext format
    
        Args:
            pages (list): pages to get
            pause (int): seconds to pause between queries to wiki
        Returns:
            (dict): format of {page: content}
        
        """
        #next_run in past so first run never delayed
        next_run = datetime.datetime.now() - datetime.timedelta(hours=1)
        output = {}
        missing = []
        for i in range(0, len(pages), 50):
            url = 'http://wiki.eveuniversity.org/w/api.php?'\
                    'action=query&format=json&prop=revisions&rvprop=content&'\
                    'titles=' + '|'.join([quote(i) for i in pages[i:i+50]])
            logger.debug('Fetching from wiki: '+url)
            while datetime.datetime.now() < next_run:
                sleep(1)
            try:
                response = urllib2.urlopen(url)
            except urllib2.HTTPError as e:
                logger.warning('Error code %s for page %s response was %s',
                          e.code, url, e.read())
                continue
            finally:
                next_run = datetime.datetime.now() + datetime.timedelta(seconds=self.delay)
            for page in json.load(response)['query']['pages'].values():
                try:
                    content = page['revisions'][0]['*']
                except KeyError:
                    if 'missing' in page:
                        logger.info('No page %s', page['title'])
                        missing.append(page['title'])
                    else:
                        raise
                    continue
                output[page['title']] = content
        return output, missing

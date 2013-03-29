from common import AppException
from time import sleep
from urllib import quote
import datetime
import json
import logging
import urllib2
logger = logging.getLogger(__name__)

class InvalidLogin(AppException): pass

class Wiki(object):
    def __init__(self, url, delay):
        self._url = url
        self.delay = delay
    
    def _build_url(self, action, **params):
        return '{}/w/api.php?action={}&{}'.format(
                self._url, action,
                '&'.join('{}={}'.format(k, v) for k, v in params.iteritems()))
        
    def _make_request(self, action, post=False, **kwargs):
        if post:
            kwargs['format'] = 'json'
            request = urllib2.Request(self._build_url(action), kwargs)
        else:
            request = urllib2.Request(self._build_url(action, format='json', **kwargs))
        logger.debug('Fetching from wiki: '+request.get_full_url())
        try:
            response = urllib2.urlopen(request)
        except urllib2.HTTPError as e:
            logger.warning('Error code %s for page %s response was %s',
                      e.code, request.get_full_url(), e.read())
            raise
        return json.load(response)
    
    def login(self, username, password):
        response = self._make_request('login', post=True, lgname=username, lgpassword=password)
        print(response)
    
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
        pages_to_fetch = len(pages) / 50
        for i in range(0, len(pages), 50):
            while datetime.datetime.now() < next_run:
                sleep(1)
            print('Fetching page {} of {}'.format(i / 50 + 1, pages_to_fetch))
            try:
                response = self._make_request('query', prop='revisions',
                                rvprop='content',
                                titles='|'.join([quote(i) for i in pages[i:i+50]]))
            except urllib2.HTTPError:
                pass
            else:
                for page in response['query']['pages'].values():
                    try:
                        content = page['revisions'][0]['*']
                    except KeyError:
                        if 'missing' in page:
                            logger.info('No page %s', page['title'])
                            missing.append(page['title'])
                        else:
                            raise
                    else:
                        output[page['title']] = content
            next_run = datetime.datetime.now() + datetime.timedelta(seconds=self.delay)
        return output, missing
#!/usr/bin/env python
"""Compare E-Uni's Wiki to the CCP SDE

Usage:
    python wiki_pages.py [options] OUTPUT

Argument OUTPUT:
    Either a file or stdout to print to screen
    
Options:
    -h, --help             Print help message and exit
    -f, --format [FORMAT]  Select the format. May be any function starting 'format_'
    -p, --pause  [TIME]    Time in secssto pause between queries to wiki.
                            Defaults to 10.

"""

from argparse import ArgumentParser
from decimal import Decimal
from os import path
from time import sleep
from urllib import quote
import datetime
import formatters
import json
import logging
import sqlite3
import sys
import urllib2
logger = logging.getLogger(__name__)

REMOTE_DATABASE_LOC = 'http://www.fuzzwork.co.uk/dump/retribution-1.0.7-463858/eve.sqlite.bz2'
"""Location of static dump"""

def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is one of "yes" or "no".
    
    """
    valid = {"yes":True,   "y":True,  "ye":True,
             "no":False,     "n":False}
    if default == None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "\
                             "(or 'y' or 'n').\n")

def get_pages(to_download, pause):
    """Get pages from wiki in raw wikitext format
    
    Args:
        to_download (list): pages to get
        pause (int): seconds to pause between queries to wiki
    Returns:
        (dict): format of {page: content}
    
    """
    #next_run in past so first run never delayed
    next_run = datetime.datetime.now() - datetime.timedelta(hours=1)
    output = {}
    missing = []
    for i in range(0, len(to_download), 50):
        url = 'http://wiki.eveuniversity.org/w/api.php?'\
                'action=query&format=json&prop=revisions&rvprop=content&'\
                'titles=' + '|'.join([quote(i) for i in to_download[i:i+50]])
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
            next_run = datetime.datetime.now() + datetime.timedelta(seconds=pause)
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

def get_ships(db=path.join(path.dirname(__file__), 'eve.db')):
    """Extract ship attributes from database
    
    Args:
        db_attrs (list): valid attributes to return
        db (str): path to database
    Returns:
        (dict): format of {ship_name: {attribute_name: value}}
        
    """
    try:
        db_conn = sqlite3.connect(db)
        db_ships = db_conn.execute(
            'SELECT types.typeName, types.mass, types.capacity, types.volume, '
            'attributes.attributeName, attTypes.valueInt, attTypes.valueFloat '
            'FROM invTypes types '
            'INNER JOIN dgmTypeAttributes attTypes ON attTypes.typeID = types.typeID '
            'INNER JOIN dgmAttributeTypes attributes ON attributes.attributeID = attTypes.attributeID '
            'INNER JOIN invGroups ON types.groupID = invGroups.groupID '
            'WHERE invGroups.categoryID = 6 AND types.published = 1 '
            'AND types.typeName = "Skiff"')
        ships = {}
        for i in db_ships:
            ships[i[0]] = ships.get(i[0], {'mass':i[1], 'capacity':i[2], 'volume':i[3]})
            try:
                ships[i[0]][i[4]] = Decimal(str(i[5] or i[6] or 0))
            except TypeError:
                phrase = 'Invalid value for {} on {} with value {}'.format(i[4], i[0], i[5] or i[6])
                logger.warning(phrase)
    
    finally:
        db_conn.close()
    
    logger.debug('Ships fetched: %s', ships.keys())
    return ships

def get_database(remote=REMOTE_DATABASE_LOC, local=path.join(path.dirname(__file__), 'eve.db')):
    from bz2 import decompress
    with open(local, 'wb') as local_file:
        local_file.write(decompress(urllib2.urlopen(remote).read())) 
        
def invalid_format(parser):
    parser.error('Invalid format please choose from {}'\
                  .format(', '.join([i for i in formatters.available()])))

def main():
    parser = ArgumentParser(description='Find incorrect ships on wiki')
    parser.add_argument('output_file', default='stdout', 
            help='File to save output to, use "stdout" to print to screen')
    parser.add_argument('-f', '--format', action='store', default='text',
            help='Format for the output')
    parser.add_argument('-p', '--pause', default=15, type=int,
            help='Number of seconds to wait between requests to wiki. '
                 'Defaults to 30', action='store')
    args = parser.parse_args()
    logger.debug('Args: %s', args)
    
    try:
        formatter = getattr(formatters, args.format.capitalize())()
    except AttributeError:
        invalid_format(parser)
        
    try:
        ships = get_ships()
    except sqlite3.Error:
        if not query_yes_no('No valid local database, '
                            'should it be downloaded (~100mb file)?'):
            parser.exit()
        get_database(REMOTE_DATABASE_LOC)
        parser.exit('Done!')
        
    pages, missing_pages = get_pages(ships.keys(), args.pause)
    
    try:
        formatter(pages, ships, missing_pages, args.output_file)
    except EnvironmentError as e:
        try:
            filename = e.filename
        except AttributeError:
            filename = parser.output_file
        parser.error('Error accessing file {}: {}'.format(filename, e.strerror))
        
    except NotImplementedError:
        invalid_format(parser)
    
if __name__ == '__main__':
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)
    filelog = logging.FileHandler(path.join(path.dirname(__file__), 'log.txt'))
    filelog.setLevel(logging.DEBUG)
    filelog.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    log.addHandler(filelog)
    main()
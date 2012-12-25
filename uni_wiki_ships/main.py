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
from io import BytesIO
from os import path
from time import sleep
from urllib import quote
from atrributes import attributes, NotPresentError
import collections
import csv
import datetime
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
            'WHERE invGroups.categoryID = 6 AND types.published = 1 ')
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

def check_values(pages, ships, attributes):
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

def format_text(wrong_attrs, missing_pages):
    ret = []
    for k in wrong_attrs:
        for i in wrong_attrs[k]:
            ret.append('{} has {} as {} but should be {}'\
                  .format(k, i.attr, i.current, i.correct))
    ret.append(', '.join(missing_pages) + 'are missing from wiki')
    return '\n'.join(ret)

def format_csv(wrong_attrs, missing_pages):
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

def get_database(remote=REMOTE_DATABASE_LOC, local=path.join(path.dirname(__file__), 'eve.db')):
    from bz2 import decompress
    with open(local, 'wb') as local_file:
        local_file.write(decompress(urllib2.urlopen(remote).read())) 

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
        format_func = globals()['format_'+args.format]
    except KeyError:
        parser.error('Invalid format {} please choose from'.format(
                        args.format,
                        ', '.join([i for i in globals()
                                   if i.startswith('format_')]
                    )))
    
    try:
        ships = get_ships()
    except sqlite3.Error:
        if not query_yes_no('No valid local database, '
                            'should it be downloaded (~100mb file)?'):
            parser.exit()
        get_database(REMOTE_DATABASE_LOC)
        parser.exit('Done!')
        
    pages, missing_pages = get_pages(ships.keys(), args.pause)
    
    if args.output_file == 'stdout':
        out_file = sys.stdout
    else:
        try:
            out_file = open(args.output_file, 'wb')
        except IOError:
            parser.error('Invalid file '+args.output_file)
    with out_file as write:
        write.write(format_func(check_values(pages, ships, attributes), missing_pages))
    
if __name__ == '__main__':
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)
    filelog = logging.FileHandler(path.join(path.dirname(__file__), 'log.txt'))
    filelog.setLevel(logging.DEBUG)
    filelog.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    log.addHandler(filelog)
    main()
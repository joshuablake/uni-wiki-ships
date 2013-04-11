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
from urllib import quote
import datetime
import formatters
import json
import logging
import sqlite3
import sys
import urllib2
from formatters import InvalidLocation
import outputters
from outputters import InvalidSetup
from wiki import Wiki, RequestError
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())

REMOTE_DATABASE_LOC = 'http://www.fuzzwork.co.uk/dump/retribution-1.1-84566/eve.db.bz2'
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
    
    return ships

def get_database(remote=REMOTE_DATABASE_LOC, local=path.join(path.dirname(__file__), 'eve.db')):
    from bz2 import decompress
    logger.info('Fetching %s into %s', remote, local)
    req = urllib2.Request(remote, headers={'User-Agent' : "E-Uni Wiki Bot"}) 
    with open(local, 'wb') as local_file:
        try:
            local_file.write(decompress(urllib2.urlopen(req).read())) 
        except urllib2.HTTPError, e:
            print('Error fetching webpage. The server said:')
            print(e.fp.read())
        
def main():
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)
    filelog = logging.FileHandler(path.join(path.dirname(__file__), 'log.txt'))
    filelog.setLevel(logging.DEBUG)
    filelog.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    log.addHandler(filelog)
    
    parser = ArgumentParser(description='Find incorrect ships on wiki', prog="wikiships")
    parser.add_argument('-F', '--file', action='store',
            help='File to save output to, use "stdout" to print to screen')
    parser.add_argument('-f', '--format', action='store', default='text',
            help='Format for the output')
    parser.add_argument('-o', '--output', action='store', default='stdout',
            help='How to output text')
    parser.add_argument('--pause', default=1, type=int,
            help='Number of seconds to wait between requests to wiki. '
                 'Defaults to 30', action='store')
    parser.add_argument('-u', '--user', action='store',
            help='Username of the wiki user')
    parser.add_argument('-p', '--password', action='store',
            help='Password of the wiki user')
    args = parser.parse_args()
    logger.debug('Args: %s', args)
    args.password
    try:
        formatter = getattr(formatters, args.format.capitalize())()
    except AttributeError:
        parser.error('Invalid format please choose from {}'\
                  .format(', '.join([i for i in formatters.available()])))
    
    try:
        outputter = getattr(outputters, args.output.capitalize())
    except AttributeError:
        parser.error('Invalid output {} please choose from {}'\
                  .format(args.output, ', '.join([i for i in outputters.available()])))
        
    try:
        ships = get_ships()
    except sqlite3.Error:
        if not query_yes_no('No valid local database, '
                            'should it be downloaded (~100mb file)?'):
            parser.exit()
        get_database(REMOTE_DATABASE_LOC)
        print('Done!')
        
    wiki = Wiki('http://wiki.eveuniversity.org', args.pause)
    try:
        user = args.user
        password = args.password
    except AttributeError:
        pass
    else:
        try:
            wiki.login(user, password)
        except RequestError as e:
            parser.error(e)
    pages, missing_pages = wiki.get_pages(ships.keys())
    
    try:
        outputter = outputter(args.file, formatter)
    except outputters.InvalidSetup as e:
        parser.error(e)
        
    try:
        outputter(formatter(pages, ships, missing_pages, args.file))
    except EnvironmentError as e:
        try:
            filename = e.filename
        except AttributeError:
            filename = parser.file
        parser.error('Error accessing file {}: {}'.format(filename, e.strerror))
    except InvalidLocation as e:
        parser.error('Invalid location {}: {}'.format(args.file, e))
    
if __name__ == '__main__':
    main()
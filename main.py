from decimal import Decimal
from os import path
from time import sleep
from urllib import quote
import datetime
import logging
import re
import sqlite3
import urllib2
logger = logging.getLogger(__name__)

#Format (db name, wiki name,[ unit], [ transform])
#TODO: warp speed
def resist(x):
    return 1 - x

ATTRIBUTES = (
['powerOutput', 'powergrid', ' MW',],
['cpuOutput', 'cpu', ' tf',],
['capacitorCapacity', 'capacitor', ' GJ',],
['hiSlots', 'highs',],
['turretSlotsLeft', 'turrets',],
['launcherSlotsLeft', 'launchers',],
['medSlots', 'mediums',],
['lowSlots', 'lows',],
['mass', 'mass', ' kg'],
['volume', 'volume', ' m&#179'],
['capacity', 'cargohold', ' m&#179'],
['droneCapacity', 'dronebay', ' m&#179'],
['droneBandwidth', 'bandwidth', ' Mbit/sec'],
['hp', 'structurehp', ' HP',],
['shieldCapacity', 'shieldhp', ' HP',],
['armorHP', 'armorhp', ' HP',],
['maxVelocity', 'maxvelocity', ' m/s',],
['agility', 'inertia', '', lambda x: round(x, 3),],
['maxTargetRange', 'targetrange', '', lambda x: x/1000,],
['maxLockedTargets', 'maxlockedtargets',],
['shieldEmDamageResonance', 'shieldem', '', lambda x: (1-x)*100,],
['armorEmDamageResonance', 'armorem', '', lambda x: (1-x)*100,],
['shieldExplosiveDamageResonance', 'shieldexp', '', lambda x: (1-x)*100,],
['armorExplosiveDamageResonance', 'armorexp', '', lambda x: (1-x)*100,],
['shieldKineticDamageResonance', 'shieldkin', '', lambda x: (1-x)*100,],
['armorKineticDamageResonance', 'armorkin', '', lambda x: (1-x)*100,],
['shieldThermalDamageResonance', 'shieldtherm', '', lambda x: (1-x)*100,],
['armorThermalDamageResonance', 'armortherm', '', lambda x: (1-x)*100,],
['scanResolution', 'scanres', ' mm',],
)

def get_pages(pages, loc=path.join(path.dirname(__file__), 'wiki-pages'), download=True):
    next_run = datetime.datetime.now() - datetime.timedelta(hours=1)
    output = {}
    for page in pages:
        file_name = path.join(loc, page+'.txt')
        
        if path.isfile(file_name):
            logger.debug('Found %s in cache', page)
            with open(file_name, 'r') as out:
                output[page] = out.read()
        elif download:
            url = 'http://wiki.eveuniversity.org/{}?action=raw'.format(quote(page))
            logger.debug('Downloading %s at %s', url, next_run)
            while datetime.datetime.now() < next_run:
                sleep(1)
            try:
                response = urllib2.urlopen(url)
            except urllib2.HTTPError as e:
                if e.code == 404:
                    logger.info('No page %s', page)
                else:
                    logger.warning('Unknown error code %s for page %s response was %s',
                          e.code, url, e.read())
                continue
            finally:
                next_run = datetime.datetime.now() + datetime.timedelta(seconds=30)
            content = response.read()
            output[page] = content
            with open(file_name, 'w') as out:
                out.write(content)
    return output

def parse_attributes(attributes):
    parsed = []
    for attr in attributes:
        try:
            unit = attr[2]
        except IndexError:
            unit = ''
        try:
            function = attr[3]
        except IndexError:
            function = lambda x: x
        parsed.append((attr[0], attr[1], unit, function))
    return parsed 

def get_ships(attributes, db=path.join(path.dirname(__file__), 'eve.db')):
    db_attrs = [i[0] for i in attributes]
    try:
        db_conn = sqlite3.connect(db)
        db_ships = db_conn.execute(
            'SELECT types.typeName, types.mass, types.capacity, types.volume, '
            'attributes.attributeName, attTypes.valueInt, attTypes.valueFloat '
            'FROM invTypes types '
            'INNER JOIN dgmTypeAttributes attTypes ON attTypes.typeID = types.typeID '
            'INNER JOIN dgmAttributeTypes attributes ON attributes.attributeID = attTypes.attributeID '
            'INNER JOIN invGroups ON types.groupID = invGroups.groupID '
            'WHERE invGroups.categoryID = 6 AND types.published = 1')
        ships = {}
        for i in db_ships:
            ships[i[0]] = ships.get(i[0], {'mass':i[1], 'capacity':i[2], 'volume':i[3]})
            try:
                ships[i[0]][i[4]] = Decimal(str(i[5] or i[6] or 0))
            except TypeError:
                if i[4] in db_attrs:
                    phrase = 'Invalid value for {} on {} with value {}'.format(i[4], i[0], i[5] or i[6])
                    logger.warning(phrase)
                    print phrase
    
    finally:
        db_conn.close()
    
    return ships

def main():
    attributes = parse_attributes(ATTRIBUTES)
    ships = get_ships(attributes)
    
    pages = get_pages(ships.keys(), download=False)
    regex = {}
    for attribute in attributes:
        regex[attribute] = re.compile(r'\|{}=([\d,\.]+){}'.format(attribute[1], attribute[2]))
    
    for ship in pages.keys():
        for attribute in attributes:
            logger.debug('Attribute: %s Ship: %s', attribute[0], ship)
            try:
                expected = Decimal(str(attribute[3](Decimal(ships[ship][attribute[0]]))))
            except KeyError:
                logger.debug('Ship %s has no value in db for %s', ship, attribute[1])
                expected = None
            try:
                value = Decimal(
                        re.search(regex[attribute], pages[ship])\
                        .expand(r'\1').replace(',', ''))
            except AttributeError:
                if not expected == None:
                    print('{} attribute not found on ship {}'.format(attribute[1], ship))
                continue
            if not value == expected and abs(value - (expected or 0)) > 1:
                print('For ship {} {} is {} but should be {}'\
                      .format(ship, attribute[1], value, expected))
    
if __name__ == '__main__':
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)
    strm = logging.StreamHandler()
    strm.setLevel(logging.INFO)
    filelog = logging.FileHandler(path.join(path.dirname(__file__), 'log.txt'))
    filelog.setLevel(logging.DEBUG)
    log.addHandler(strm)
    log.addHandler(filelog)
    main()
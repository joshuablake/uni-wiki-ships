from os import path
from time import sleep
import datetime
import sqlite3
import urllib2

def get_pages(pages, dir=path.join(path.dirname(__file__), 'wiki-pages')):
    next_run = datetime.datetime.now() - datetime.timedelta(hours=1)
    output = {}
    for page in pages:
        file_name = path.join(dir, page+'.txt')
        
        if path.isfile(file_name):
            with open(file_name, 'r') as out:
                output[page] = out.read()
            continue
            
        while datetime.datetime.now() < next_run:
            sleep(1)
        try:
            response = urllib2.urlopen('http://wiki.eveuniversity.org/{}?action=raw'\
                                       .format(page))
        except urllib2.HTTPError as e:
            if e.code == 404:
                print('No page {}'.format(page))
            else:
                print('Unknown error code {} for page {} response was {}'\
                      .format(e.code, page, e.read()))
        next_run = datetime.datetime.now() + datetime.timedelta(seconds=30)
        content = response.read()
        output[page] = content
        with open(file_name, 'w') as out:
            out.write(content)

def main():
    db_conn = sqlite3.connect(path.join(path.dirname(__file__), 'eve.db'))
    db_ships = db_conn.execute(
'SELECT types.typeName, types.mass, types.capacity, types.volume, '
'attributes.attributeName, attTypes.valueInt, attTypes.valueFloat '
'FROM invTypes types '
'INNER JOIN dgmTypeAttributes attTypes ON attTypes.typeID = types.typeID '
'INNER JOIN dgmAttributeTypes attributes ON attributes.attributeID = attTypes.attributeID '
'INNER JOIN invGroups ON types.groupID = invGroups.groupID '
'WHERE invGroups.categoryID = 6') 
    ships = {}
    for i in db_ships:
        ships[i[0]] = ships.get(i[0], {'mass': i[1], 'capacity':i[2], 'volume': i[3]})
        ships[i[0]][i[4]] = i[5] or i[6]
    db_conn.close()
    
    get_pages(ships.keys())
    
if __name__ == '__main__':
    main()
from common import AppException
from decimal import Decimal
import logging
import re
logger = logging.getLogger(__name__)

class NotPresentError(AppException): pass

class Attribute(object):
    """An attribute
    
    Represents an attribute that can be assigned to a ship. Allows processing
    of the attribute and other utility functions
    
    """
    
    def __init__(self, db_name, wiki_name, unit='', function=lambda x: x):
        """Create an attribute
        
        Args:
            db_name (str): the name in the database
            wiki_name (str): the name on the wiki
            unit (str): the unit this attribute is measured in. not currently used
            function (callable): a function that accepts the value from db as an
                                    argument and returns the wikified value
                                    
        """
        self.function = function
        self.name = wiki_name
        self.regex = re.compile(r'''
            \|         #section starts with |
            {}         #followed by the wiki name
            =          #then an equals
            ([\d,\.]+) #allow numbers, thousand seperator and decimal points'''\
            .format(self.name), re.X)
        self.db_name = db_name
        if not unit or unit.startswith(' '):
            self.unit = unit
        else:
            self.unit = ' '+unit
        attributes.append(self)
        logger.debug('Created attribute %s', self)
        
        
    def __str__(self):
        return self.name
    
    def process(self, values):
        """Process a db values into a wiki value
        
        Args:
            values (dict): the db values for a ship {db_name: value}
        Returns:
            (decimal): the correct value for this attribute
        Throws:
            NotPresentError: no db value for this attribute
            
        """
        try:
            value = values[self.db_name]
        except KeyError:
            raise NotPresentError('No value given for %s', self)
        return Decimal(self.function(Decimal(str(value))))
    
    def extract(self, page):
        """Extract the value from a wiki page for this attribute
        
        Args:
            page (str): a wiki page
        Returns:
            (decimal): the value on the page
        Throws:
            NotPresentError: there is no value for this attribute on the page
            
        """
        try: 
            return Decimal(
                    self.regex.search(page)\
                    .expand(r'\1').replace(',', ''))
        except AttributeError:
            raise NotPresentError('No value for ' + str(self))  
    
class SensorStrength(Attribute):
    """Special case for sensor strength"""
   
    def __init__(self):
        """Call parent with correct values"""
        super(SensorStrength, self).__init__('', 'sensorvalue', 'points')
    
    def process(self, values):
        types = ['Ladar', 'Radar', 'Magnetometric', 'Gravimetric']
        return [values[i] for i in types
                if values['scan{}Strength'.format(i) > 0]][0]
        
CONFIG = (
    ('powerOutput', 'powergrid', ' MW',),
    ('cpuOutput', 'cpu', ' tf',),
    ('capacitorCapacity', 'capacitor', ' GJ',),
    ('hiSlots', 'highs',),
    ('turretSlotsLeft', 'turrets',),
    ('launcherSlotsLeft', 'launchers',),
    ('medSlots', 'mediums',),
    ('lowSlots', 'lows',),
    ('mass', 'mass', ' kg'),
    ('volume', 'volume', ' m&#179'),
    ('capacity', 'cargohold', ' m&#179'),
    ('droneCapacity', 'dronebay', ' m&#179'),
    ('droneBandwidth', 'bandwidth', ' Mbit/sec'),
    ('hp', 'structurehp', ' HP',),
    ('shieldCapacity', 'shieldhp', ' HP',),
    ('armorHP', 'armorhp', ' HP',),
    ('maxVelocity', 'maxvelocity', ' m/s',),
    ('agility', 'inertia', '', lambda x: round(x, 3),),
    ('maxTargetRange', 'targetrange', '', lambda x: x / 1000,),
    ('maxLockedTargets', 'maxlockedtargets',),
    ('shieldEmDamageResonance', 'shieldem', '', lambda x: (1 - x) * 100,),
    ('armorEmDamageResonance', 'armorem', '', lambda x: (1 - x) * 100,),
    ('shieldExplosiveDamageResonance', 'shieldexp', '', lambda x: (1 - x) * 100,),
    ('armorExplosiveDamageResonance', 'armorexp', '', lambda x: (1 - x) * 100,),
    ('shieldKineticDamageResonance', 'shieldkin', '', lambda x: (1 - x) * 100,),
    ('armorKineticDamageResonance', 'armorkin', '', lambda x: (1 - x) * 100,),
    ('shieldThermalDamageResonance', 'shieldtherm', '', lambda x: (1 - x) * 100,),
    ('armorThermalDamageResonance', 'armortherm', '', lambda x: (1 - x) * 100,),
    ('scanResolution', 'scanres', ' mm',),
)
attributes = []
for i in CONFIG:
    Attribute(*i)
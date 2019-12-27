import logging
import struct
import datetime

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.const import (TEMP_CELSIUS, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_PRESSURE, STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'airthings_wave_plus'

CONF_MAC = 'mac'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string,
})

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=15)

SENSOR_TYPES = [
    # key            name                unit          icon         device class
    [ 'temperature', 'Temperature',      TEMP_CELSIUS, None,        DEVICE_CLASS_TEMPERATURE ],
    [ 'co2',         'CO2',              'ppm',        'mdi:cloud', None ],
    [ 'pressure',    'Pressure',         'mbar',       'mdi:gauge', DEVICE_CLASS_PRESSURE ],
    [ 'humidity',    'Humidity',         '%',          None,        DEVICE_CLASS_HUMIDITY ],
    [ 'voc',         'VOC',              'ppm',        'mdi:cloud', None ],
    [ 'short_radon', 'Short-term Radon', 'Bq/m3',      'mdi:cloud', None ],
    [ 'long_radon',  'Long-term Radon',  'Bq/m3',      'mdi:cloud', None ],
]


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    reader = AirthingsWavePlusDataReader(config.get(CONF_MAC))

    sensors = []
    for [key, name, unit, icon, device_class] in SENSOR_TYPES:
        sensors.append( AirthingsSensorEntity(reader, key, name, unit, icon, device_class) )
    add_devices(sensors)

class AirthingsWavePlusDataReader:
    def __init__(self, mac):
        self._mac = mac
        self._state = {}

    def get_data(self, key):
        if key in self._state:
            return self._state[key]
        return STATE_UNKNOWN

    @property
    def mac(self):
        return self._mac

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        _LOGGER.debug(f"Updating data from Airthings Wave Plus {self._mac}")
        
        import pygatt
        from pygatt.backends import Characteristic
        adapter = pygatt.backends.GATTToolBackend()
        #char = 'b42e2a68-ade7-11e4-89d3-123b93f75cba'
        
        try:
            # reset_on_start must be false - reset is hardcoded to execute sudo, which doesn't exist
            # in the hass.io Docker container.
            adapter.start(reset_on_start=False)
            device = adapter.connect(self._mac)
            
            # Unclear why this does not work. Seems broken in the command line tool too. Hopefully handle is stable...
            #value = device.char_read(char,timeout=10)
            value = device.char_read_handle('0x000d',timeout=10)
            (humidity, light, sh_rad, lo_rad, temp, pressure, co2, voc) = struct.unpack('<xbxbHHHHHHxxxx', value)
            
            self._state['humidity']    = humidity / 2.0
            self._state['light']       = light * 1.0
            self._state['short_radon'] = sh_rad
            self._state['long_radon']  = lo_rad
            self._state['temperature'] = temp / 100.0
            self._state['pressure']    = pressure / 50.0
            self._state['co2']         = co2 * 1.0
            self._state['voc']         = voc * 1.0
        finally:
            adapter.stop()

class AirthingsSensorEntity(Entity):
    """Representation of a Sensor."""

    def __init__(self, reader, key, name, unit, icon, device_class):
        """Initialize the sensor."""
        self._reader = reader
        self._key = key
        self._name = name
        self._unit = unit
        self._icon = icon
        self._device_class = device_class

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Airthings Wave Plus {}'.format(self._name)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def device_class(self):
        """Return the icon of the sensor."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._reader.get_data(self._key)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def unique_id(self):
        return '{}-{}'.format(self._reader.mac, self._name)

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self._reader.update()

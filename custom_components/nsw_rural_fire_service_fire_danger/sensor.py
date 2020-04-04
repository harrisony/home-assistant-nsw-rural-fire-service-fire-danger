"""
NSW Rural Fire Service - Fire Danger.

https://github.com/exxamalte/home-assistant-customisations
"""
import logging
from datetime import timedelta
from pyexpat import ExpatError

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.rest.sensor import RestData
from homeassistant.const import (
    STATE_UNKNOWN, ATTR_ATTRIBUTION, CONF_FORCE_UPDATE
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)


CONF_DISTRICT_NAME = 'district_name'

DEFAULT_METHOD = 'GET'
DEFAULT_NAME = 'Fire Danger'
DEFAULT_VERIFY_SSL = True
DEFAULT_FORCE_UPDATE = True

SCAN_INTERVAL = timedelta(minutes=60)

SENSOR_ATTRIBUTES = {
    # <XML Key>: [<Display Name>, <Conversion Function>]
    'RegionNumber':
        ('region_number', lambda x: int(x)),
    'Councils':
        ('councils', lambda x: x.split(';')),
    'DangerLevelToday':
        ('danger_level_today', lambda x: x.lower().capitalize()),
    'DangerLevelTomorrow':
        ('danger_level_tomorrow', lambda x: x.lower().capitalize()),
    'FireBanToday':
        ('fire_ban_today', lambda x: x == 'Yes'),
    'FireBanTomorrow':
        # Note: Possibly misleading, Seems to return 'No' even if tomorrows
        # danger level has not been set. I would have thought a TOBAN and the 
        # level are set at the same time. Possibly misleading?
        # However this is how it's presented on the RFS website
        ('fire_ban_tomorrow', lambda x: x == 'Yes')
}


XML_DISTRICT = 'District'
XML_FIRE_DANGER_MAP = 'FireDangerMap'
XML_NAME = 'Name'

ESA_DISTRICTS = {'ACT'}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DISTRICT_NAME): cv.string,
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor."""
    district_name = config.get(CONF_DISTRICT_NAME)

    if district_name in ESA_DISTRICTS:
        api = ESAFireDangerApi()
        _LOGGER.info("District {} is in ACT ESA jurisdiction".format(district_name))
    else:
        api = RFSFireDangerApi()
        _LOGGER.info("District {} is in NSW RFS jurisdiction".format(district_name))
    force_update = config.get(CONF_FORCE_UPDATE)

    # Must update the sensor now (including fetching the rest resource) to
    # ensure it's updating its state.
    add_entities([NswFireServiceFireDangerSensor(
            hass, api, district_name, force_update)], True)

class RFSFireDangerApi:
    """Get the latest data and update the states."""

    DEFAULT_ATTRIBUTION = 'NSW Rural Fire Service'
    URL = 'http://www.rfs.nsw.gov.au/feeds/fdrToban.xml'
    def __init__(self):
        self.rest = RestData(DEFAULT_METHOD, self.URL, None, None, None, DEFAULT_VERIFY_SSL)
        self.rest.update()
        self._data = None

    def update(self):
        """Get the latest data from REST API and update the state."""
        self.rest.update()
        self._data = self.rest.data

    @property
    def data(self):
        return self._data

    @property
    def extra_attrs(self):
        return dict()


class ESAFireDangerApi(RFSFireDangerApi):
    """Get the latest data and update the states."""

    DEFAULT_ATTRIBUTION = 'ACT Emergency Services Agency'
    URL = 'https://esa.act.gov.au/feeds/firedangerrating.xml'

    def update(self):
        self.rest.update()
        self._data = self.rest.data
        # At the end of the bushfire season, the ESA return a blank file
        if not self._data:
            api = RFSFireDangerApi()
            api.rest.update()
            self._data = api.rest.data
            self.DEFAULT_ATTRIBUTION = api.DEFAULT_ATTRIBUTION #TODO: This should likely b e a property or something
            _LOGGER.warn("Requested data from ESA API but falling back to RFS")

    @property
    def extra_attrs(self):
        import xmltodict
        if not self.data:
            return dict()

        parse = xmltodict.parse(self.data)
        if 'rss' not in parse:
            return dict()

        value = parse['rss']['channel']

        return {'publish date': value['pubDate'],
                'build date': value['lastBuildDate']}

class NswFireServiceFireDangerSensor(Entity):
    """Implementation of the sensor."""

    def __init__(self, hass, api, district_name, force_update):
        """Initialize the sensor."""
        self._hass = hass
        self.api = api
        self._district_name = district_name
        self._name = 'Fire Danger in {}'.format(self._district_name)
        self._icon = "mdi:fire"
        self._state = STATE_UNKNOWN
        self._force_update = force_update
        self._attributes = {
            'district': district_name,
            ATTR_ATTRIBUTION: api.DEFAULT_ATTRIBUTION
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def available(self):
        """Return if the sensor data are available."""
        return self.api.data is not None

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    def update(self):
        """Get the latest data from REST API and update the state."""
        self.api.update()
        value = self.api.data
        attributes = {
            'district': self._district_name,
            ATTR_ATTRIBUTION: self.api.DEFAULT_ATTRIBUTION,
            **self.api.extra_attrs
        }
        self._state = STATE_UNKNOWN
        if value:
            try:
                import xmltodict

                value = xmltodict.parse(value)
                # this is for the ESA
                if XML_FIRE_DANGER_MAP not in value:
                    value = value['rss']['channel']
                    value[XML_FIRE_DANGER_MAP][XML_DISTRICT] = [value[XML_FIRE_DANGER_MAP][XML_DISTRICT]]

                districts = {k[XML_NAME]: dict(k) for k in value[XML_FIRE_DANGER_MAP][XML_DISTRICT]}

                sensor_district = districts.get(self._district_name)

                for xml_key, xml_replacement in SENSOR_ATTRIBUTES.items():
                    if xml_key not in sensor_district:
                        # Ignore items not in sensor_attributes
                        continue
                    attr_value = sensor_district.get(xml_key)
                    conversion = xml_replacement[1]
                    if conversion:
                        text_value = conversion(attr_value)
                    attributes[xml_replacement[0]]  = text_value

                self._state = attributes['danger_level_today']
            except ExpatError as ex:
                _LOGGER.warning("Unable to parse XML data: %s", ex)
        self._attributes = attributes

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

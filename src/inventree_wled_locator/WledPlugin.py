"""Use WLED to locate InvenTree StockLocations.."""

import logging

import requests
from django.core.validators import MinValueValidator
from django.utils.translation import ugettext_lazy as _
from plugin import InvenTreePlugin
from plugin.mixins import LocateMixin, SettingsMixin
from stock.models import StockLocation

logger = logging.getLogger('inventree')


class WledPlugin(LocateMixin, SettingsMixin, InvenTreePlugin):
    """Use WLED to locate InvenTree StockLocations.."""

    NAME = 'WledPlugin'
    SLUG = 'inventree-wled-locator'
    TITLE = "WLED Locator"

    def set_led(self, target_led: int):
        """Turn on a specific LED."""
        base_url = f'http://{self.get_setting("ADDRESS")}/json/state'
        color_black = '000000'
        color_marked = 'FF0000'

        # Turn off all segments
        json = requests.get(base_url).json()
        print(json)

        requests.post(base_url, json={"seg": {"i": [0, self.get_setting("MAX_LEDS"), color_black]}})

        # Turn on target led
        requests.post(base_url, json={"seg": {"i": [target_led, color_marked]}})

        json = requests.get(base_url).json()
        print(json)

    def locate_stock_location(self, location_pk):
        """Locate a StockLocation.

        Args:
            location_pk: primary key for location
        """
        logger.info(f"Attempting to locate location ID {location_pk}")

        try:
            location = StockLocation.objects.get(pk=location_pk)
            logger.info(f"Location exists at '{location.pathstring}'")

            # Tag metadata
            self.set_led(13, location.get_metadata('wled_led'))

        except (ValueError, StockLocation.DoesNotExist):  # pragma: no cover
            logger.error(f"Location ID {location_pk} does not exist!")

    SETTINGS = {
        'ADDRESS': {
            'name': _('IP Address'),
            'description': _('IP address of your WLED device'),
        },
        'MAX_LEDS': {
            'name': _('Max LEDs'),
            'description': _('Maximum number of LEDs in your WLED device'),
            'default': 1,
            'validator': [
                int,
                MinValueValidator(1),
            ],
        },
    }

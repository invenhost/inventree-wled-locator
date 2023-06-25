"""Use WLED to locate InvenTree StockLocations.."""

import logging

import requests
from common.notifications import NotificationBody
from django.conf.urls import url
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from InvenTree.helpers_model import notify_users
from plugin import InvenTreePlugin
from plugin.mixins import LocateMixin, SettingsMixin, UrlsMixin
from stock.models import StockLocation

logger = logging.getLogger('inventree')


class WledPlugin(UrlsMixin, LocateMixin, SettingsMixin, InvenTreePlugin):
    """Use WLED to locate InvenTree StockLocations.."""

    NAME = 'WledPlugin'
    SLUG = 'inventree-wled-locator'
    TITLE = "WLED Locator"

    NO_LED_NOTIFICATION = NotificationBody(
        name=_("No location for {verbose_name}"),
        slug='{app_label}.no_led_{model_name}',
        message=_("No LED number is assigned for {verbose_name}"),
    )

    SETTINGS = {
        'ADDRESS': {
            'name': _('IP Address'),
            'description': _('IP address of your WLED device'),
        },
        'MAX_LEDS': {
            'name': _('Max LEDs'),
            'description': _('Maximum number of LEDs in your WLED device'),
            'default': 1,
            'validator': [int, MinValueValidator(1), ],
        },
    }

    superusers = list(get_user_model().objects.filter(is_superuser=True).all())

    def locate_stock_location(self, location_pk):
        """Locate a StockLocation.

        Args:
            location_pk: primary key for location
        """
        logger.info(f"Attempting to locate location ID {location_pk}")

        try:
            location = StockLocation.objects.get(pk=location_pk)
            led_nbr = location.get_metadata('wled_led')
            if led_nbr:
                self._set_led(led_nbr)
            else:
                # notify superusers that a location has no LED number
                logger.error(f"Location ID {location_pk} has no WLED LED number!")
                notify_users(self.superusers, location, StockLocation, content=self.NO_LED_NOTIFICATION)

        except (ValueError, StockLocation.DoesNotExist):  # pragma: no cover
            logger.error(f"Location ID {location_pk} does not exist!")

    def view_off(self, request):
        """Turn off all LEDs."""
        self._set_led()
        return redirect(self.settings_url)

    def setup_urls(self):
        """Return the URLs defined by this plugin."""
        return [
            url(r'off/', self.view_off, name='off'),
        ]

    def get_settings_content(self, request):
        """Add context to the settings panel."""
        return f"""
        <h3>WLED controlls</h3>
        <p>Turn off all LEDs: <a href="{reverse('plugin:inventree-wled-locator:off')}">turn off</a></p>
        """

    def _set_led(self, target_led: int = None):
        """Turn on a specific LED."""
        base_url = f'http://{self.get_setting("ADDRESS")}/json/state'
        color_black = '000000'
        color_marked = 'FF0000'

        # Turn off all segments
        requests.post(base_url, json={"seg": {"i": [0, self.get_setting("MAX_LEDS"), color_black]}})

        # Turn on target led
        if target_led:
            requests.post(base_url, json={"seg": {"i": [target_led, color_marked]}})

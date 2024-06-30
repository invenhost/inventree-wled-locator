"""Use WLED to locate InvenTree StockLocations.."""

import json
import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import re_path, reverse
from django.utils.translation import gettext_lazy as _

import requests
from stock.models import StockLocation

from common.notifications import NotificationBody
from InvenTree.helpers_model import notify_users
from plugin import InvenTreePlugin
from plugin.mixins import LocateMixin, SettingsMixin, UrlsMixin

logger = logging.getLogger("inventree")


def superuser_check(user):
    """Check if a user is a superuser."""
    return user.is_superuser


class WledPlugin(UrlsMixin, LocateMixin, SettingsMixin, InvenTreePlugin):
    """Use WLED to locate InvenTree StockLocations.."""

    NAME = "WledPlugin"
    SLUG = "inventree-wled-locator"
    TITLE = "WLED Locator"

    NO_LED_NOTIFICATION = NotificationBody(
        name=_("No location for {verbose_name}"),
        slug="{app_label}.no_led_{model_name}",
        message=_("No LED number is assigned for {verbose_name}"),
    )

    SETTINGS = {
        "ADDRESS": {
            "name": _("IP Address"),
            "description": _("IP address of your WLED device"),
        },
        "MAX_LEDS": {
            "name": _("Max LEDs"),
            "description": _("Maximum number of LEDs in your WLED device"),
            "default": 1,
            "validator": [
                int,
                MinValueValidator(1),
            ],
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
            led_nbr = int(location.get_metadata("wled_led"))
            if led_nbr is not None:
                self._set_led(led_nbr)
            else:
                # notify superusers that a location has no LED number
                logger.error(f"Location ID {location_pk} has no WLED LED number!")
                notify_users(
                    self.superusers,
                    location,
                    StockLocation,
                    content=self.NO_LED_NOTIFICATION,
                )

        except (ValueError, StockLocation.DoesNotExist):  # pragma: no cover
            logger.error(f"Location ID {location_pk} does not exist!")

    def view_off(self, request):
        """Turn off all LEDs."""
        if not superuser_check(request.user):
            raise PermissionError("Only superusers can turn off all LEDs")

        self._set_led(request=request)
        return redirect(self.settings_url)

    def view_unregister(self, request, pk):
        """Unregister an LED."""
        if not superuser_check(request.user):
            raise PermissionError("Only superusers can turn off all LEDs")

        try:
            item = StockLocation.objects.get(pk=pk)
            item.set_metadata("wled_led", None)
        except StockLocation.DoesNotExist:
            pass
        return redirect(self.settings_url)

    def view_register(self, request, pk=None, led=None, context=None):
        """Register an LED."""
        if not superuser_check(request.user):
            raise PermissionError("Only superusers can turn off all LEDs")

        if pk is None and led is None and str(request.body, encoding="utf8") == "":
            return JsonResponse(
                {
                    "actions": {
                        "POST": [
                            "stocklocation",
                            "led",
                        ],
                    }
                }
            )
        elif request.body is not None:
            data = json.loads(request.body)
            pk = data.get("stocklocation")
            led = data.get("led")

        try:
            item = StockLocation.objects.get(pk=pk)
            previous_entry = item.get_metadata("wled_led")
            item.set_metadata("wled_led", led)
            if previous_entry and previous_entry != led:
                return JsonResponse(
                    {
                        "success": f"Location was registered to {previous_entry}, changed to {led}",
                    }
                )
            return JsonResponse(
                {
                    "success": "Allocation registered, refresh the page to see it in the list"
                }
            )
        except StockLocation.DoesNotExist:
            pass
        return redirect(self.settings_url)

    def setup_urls(self):
        """Return the URLs defined by this plugin."""
        return [
            re_path(r"off/", self.view_off, name="off"),
            re_path(
                r"unregister/(?P<pk>\d+)/", self.view_unregister, name="unregister"
            ),
            re_path(
                r"register/(?P<pk>\d+)/(?P<led>\w+)/",
                self.view_register,
                name="register",
            ),
            re_path(r"register/", self.view_register, name="register-simple"),
        ]

    def get_settings_content(self, request):
        """Add context to the settings panel."""
        stocklocations = StockLocation.objects.filter(metadata__isnull=False).all()

        target_locs = [
            {"name": loc.pathstring, "led": loc.get_metadata("wled_led"), "id": loc.id}
            for loc in stocklocations
            if loc.get_metadata("wled_led")
        ]
        stock_strings = "".join(
            [
                f"""<tr>
            <td>{a["name"]}</td>
            <td>{a["led"]}</td>
            <td><a class="btn btn-primary" href="{reverse("plugin:inventree-wled-locator:unregister", kwargs={"pk": a["id"]})}">unregister</a></td>
        </tr>"""
                for a in target_locs
            ]
        )
        return f"""
        <h3>WLED controls</h3>
        <a class="btn btn-primary" href="{reverse('plugin:inventree-wled-locator:off')}">Turn off</a>
        <button class="btn btn-primary" onclick="led_register()">Register LED</button>
        <table class="table table-striped">
            <thead><tr><th>Location</th><th>LED</th><th>Actions</th></tr></thead>
            <tbody>{stock_strings}</tbody>
        </table>
        <script>
        function led_register() {{
            constructForm('{reverse("plugin:inventree-wled-locator:register-simple")}', {{
                title: 'Register LED',
                actions: 'POST',
                method: 'POST',
                url: '{reverse("plugin:inventree-wled-locator:register-simple")}',
                fields: {{
                    'stocklocation': {{'model': 'stocklocation', label: 'Location', type: 'related field', api_url: '{reverse("api-location-list")}', required: true, }},
                    'led': {{'label': 'LED', 'type': 'integer', 'min': 0, 'max': {self.get_setting("MAX_LEDS")} }},
                }},
            }});
        }}

        </script>
        """

    def _set_led(self, target_led: int = None, request=None):
        """Turn on a specific LED."""
        address = self.get_setting("ADDRESS")
        max_leds = self.get_setting("MAX_LEDS")

        # Ensure there are settings
        if not address:
            if request:
                messages.add_message(
                    request, messages.WARNING, "No IP address set for WLED"
                )
            return

        base_url = f"http://{address}/json/state"
        color_black = "000000"
        color_marked = "FF0000"

        # Turn off all segments
        requests.post(
            base_url,
            json={"seg": {"i": [0, max_leds, color_black]}},
            timeout=3,
        )

        # Turn on target led
        if target_led is not None:
            requests.post(
                base_url,
                json={"seg": {"i": [target_led, color_marked]}},
                timeout=3,
            )

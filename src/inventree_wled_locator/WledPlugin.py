"""Use WLED to locate InvenTree StockLocations.."""

from plugin import InvenTreePlugin
# from plugin.mixins import SettingsMixin
# from django.utils.translation import gettext_lazy as _


class WledPlugin(InvenTreePlugin):
    """Use WLED to locate InvenTree StockLocations.."""

    NAME = 'WledPlugin'
    SLUG = 'inventree_wled_locator'
    TITLE = "WLED Locator"

    def your_function_here(self):
        """Do something."""
        pass

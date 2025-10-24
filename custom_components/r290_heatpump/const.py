# Version: 1.0.1
# Last modified: 2025-10-24 17:33 by CNC-Buddy
"""Constants for the R290 Heat Pump integration."""

from homeassistant.const import Platform

DOMAIN = "r290_heatpump"

PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.SELECT, Platform.BUTTON, Platform.SWITCH]

# Version: 1.0.1
# Last modified: 2025-10-24 17:33 by CNC-Buddy
from typing import Dict

PV_CURVE_CONFIG: Dict[str, dict] = {
    "heating_curve": {
        "prefix": "heating",
        "grid_threshold_default": 2.0,
        "grid_threshold_min_default": 2.0,
        "grid_threshold_max_default": 3.0,
        "grid_offset_min_default": 0.0,
        "grid_offset_max_default": 0.0,
        "battery_threshold_default": 80.0,
        "hold_default": 15,
        "external_hold_default": 5.0,
    },
    "floor_heating_curve": {
        "prefix": "floor_heating",
        "grid_threshold_default": 2.0,
        "grid_threshold_min_default": 2.0,
        "grid_threshold_max_default": 3.0,
        "grid_offset_min_default": 0.0,
        "grid_offset_max_default": 0.0,
        "battery_threshold_default": 80.0,
        "hold_default": 15,
        "external_hold_default": 5.0,
    },
    "hot_water_curve": {
        "prefix": "hotwater",
        "grid_threshold_default": 5.0,
        "grid_threshold_min_default": 5.0,
        "grid_threshold_max_default": 7.0,
        "grid_offset_min_default": 0.0,
        "grid_offset_max_default": 0.0,
        "battery_threshold_default": 90.0,
        "hold_default": 20,
        "external_hold_default": 5.0,
    },
    "cooling_curve": {
        "prefix": "cooling",
        "grid_threshold_default": 3.0,
        "grid_threshold_min_default": 3.0,
        "grid_threshold_max_default": 4.0,
        "grid_offset_min_default": 0.0,
        "grid_offset_max_default": 0.0,
        "battery_threshold_default": 70.0,
        "hold_default": 15,
        "external_hold_default": 5.0,
    },
}

PV_OFFSET_STEPS = list(range(-10, 11))
PV_OFFSET_OPTIONS = {step: f"{step:+d} degC" for step in PV_OFFSET_STEPS}

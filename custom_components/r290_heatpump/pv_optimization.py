from typing import Dict

PV_CURVE_CONFIG: Dict[str, dict] = {
    "heating_curve": {
        "prefix": "heating",
        "grid_threshold_default": 2.0,
        "battery_threshold_default": 80.0,
        "cooldown_default": 15,
    },
    "floor_heating_curve": {
        "prefix": "floor_heating",
        "grid_threshold_default": 2.0,
        "battery_threshold_default": 80.0,
        "cooldown_default": 15,
    },
    "hot_water_curve": {
        "prefix": "hotwater",
        "grid_threshold_default": 5.0,
        "battery_threshold_default": 90.0,
        "cooldown_default": 20,
    },
    "cooling_curve": {
        "prefix": "cooling",
        "grid_threshold_default": 3.0,
        "battery_threshold_default": 70.0,
        "cooldown_default": 15,
    },
}

PV_OFFSET_STEPS = list(range(-10, 11))
PV_OFFSET_OPTIONS = {step: f"{step:+d} degC" for step in PV_OFFSET_STEPS}

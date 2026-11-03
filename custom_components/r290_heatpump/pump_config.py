"""Shared auxiliary-pump configuration for HA flows and validation."""
from __future__ import annotations
import math

from .pump_logic import DEFAULTS, RANGES, validate_settings
from .pump_sources import normalize_pump_sources

PUMP_TYPE = "auxiliary_pump"
ENTITY_FIELDS = {
    "speed_entity": (["number", "light", "fan"], False, True),
    "enable_entity": (["switch", "input_boolean"], False, False),
    "demand_entity": (["binary_sensor", "sensor", "switch", "input_boolean"], True, True),
    "dhw_entity": (["binary_sensor", "sensor", "switch", "input_boolean"], False, True),
    "defrost_entities": (["binary_sensor", "sensor"], True, True),
    "frequency_entities": (["sensor"], True, True),
    "flow_entities": (["sensor"], True, True),
    "supply_entities": (["sensor"], True, True),
    "return_entities": (["sensor"], True, True),
    "legacy_automations": (["automation"], True, False),
    "pump_power_entity": (["sensor"], False, False),
    "heat_energy_entity": (["sensor"], False, False),
    "electric_energy_entity": (["sensor"], False, False),
    "tank_entity": (["sensor"], False, False),
    "buffer_entity": (["sensor"], False, False),
    "outdoor_entity": (["sensor"], False, False),
}
CONTROL_FIELDS = {"speed_entity", "enable_entity", "demand_entity", "dhw_entity",
                  "defrost_entities", "frequency_entities", "flow_entities",
                  "supply_entities", "return_entities", "legacy_automations"}


def pump_schema(values=None, *, limits=False):
    import voluptuous as vol
    from homeassistant.helpers.selector import selector

    values = normalize_pump_sources(values)
    schema = {}
    if limits:
        for key, default in DEFAULTS.items():
            # Kept in stored settings for backwards compatibility only. The
            # internal-pump demand now determines when the path closes.
            if key == "postrun_seconds":
                continue
            marker = vol.Required(key, default=values.get(key, default))
            schema[marker] = bool if key == "commissioned" else vol.All(vol.Coerce(float), vol.Range(min=RANGES[key][0], max=RANGES[key][1]))
    else:
        schema[vol.Required("name", default=values.get("name", "Zusatzpumpe"))] = str
        for key, (domains, multiple, required) in ENTITY_FIELDS.items():
            # A suggestion is editable and removable. A schema default would
            # silently reinsert a cleared optional mapping on form submission.
            options = {"description": {"suggested_value": values[key]}} if values.get(key) else {}
            marker = (vol.Required if required else vol.Optional)(key, **options)
            schema[marker] = selector({"entity": {"domain": domains, "multiple": multiple}})
    return vol.Schema(schema)


def validate_config(hass, values, *, exclude_entry=None):
    """Validate identity, pairing and actuator capability, without calling services."""
    values = validate_settings(normalize_pump_sources(values))
    name = values.get("name", "Zusatzpumpe")
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise ValueError("name_required_max_100")
    values["name"] = name.strip()
    for key, (domains, multiple, required) in ENTITY_FIELDS.items():
        value = values.get(key)
        if not value:
            if required:
                raise ValueError(f"{key}: required")
            continue
        ids = value if multiple else [value]
        if not isinstance(ids, list) or len(ids) != len(set(ids)):
            raise ValueError(f"{key}: duplicate or invalid selection")
        for entity_id in ids:
            if not isinstance(entity_id, str) or entity_id.split(".")[0] not in domains or not hass.states.get(entity_id):
                raise ValueError(f"{key}: invalid entity")
    lengths = [len(values.get(key, [])) for key in ("frequency_entities", "flow_entities", "supply_entities", "return_entities")]
    if not lengths[0] or len(set(lengths)) != 1 or lengths[0] > 11:
        raise ValueError("unit_list_lengths")
    if set(values["supply_entities"]) & set(values["return_entities"]):
        raise ValueError("supply_return_identical")
    speed = values["speed_entity"]
    if speed.startswith("number."):
        if not values.get("enable_entity"):
            raise ValueError("number_requires_enable")
        state = hass.states.get(speed)
        lo, hi = state.attributes.get("min"), state.attributes.get("max")
        if lo is None or hi is None or values["output_min"] < float(lo) or values["output_max"] > float(hi):
            raise ValueError("actuator_range")
        step = float(state.attributes.get("step", 1))
        if not all(math.isfinite(v) for v in (float(lo), float(hi), step)) or step <= 0:
            raise ValueError("actuator_range")
        for endpoint in (values["output_min"], values["output_max"]):
            steps = (endpoint - float(lo)) / step
            if not math.isclose(steps, round(steps), abs_tol=1e-6):
                raise ValueError("calibration_must_match_native_step")
        resolution = step / (values["output_max"] - values["output_min"]) * 100
        if resolution > values["max_step"]:
            raise ValueError("actuator_resolution_exceeds_control_step")
    elif speed.startswith("light."):
        modes = hass.states.get(speed).attributes.get("supported_color_modes", [])
        if not modes or set(modes) <= {"onoff"}:
            raise ValueError("brightness_required")
    elif speed.startswith("fan."):
        if not (int(hass.states.get(speed).attributes.get("supported_features", 0)) & 1):
            raise ValueError("percentage_required")
        if float(hass.states.get(speed).attributes.get("percentage_step", 1)) > min(values["max_step"], 1):
            raise ValueError("actuator_resolution_exceeds_control_step")
    for entry in hass.config_entries.async_entries("r290_heatpump"):
        other = {**entry.data, **entry.options}
        if entry.entry_id != exclude_entry and other.get("device_type") == PUMP_TYPE:
            if other.get("speed_entity") == speed or (values.get("enable_entity") and other.get("enable_entity") == values["enable_entity"]):
                raise ValueError("actuator_already_configured")
    return values

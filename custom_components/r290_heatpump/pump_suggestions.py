"""Read-only, registry-based suggestions for auxiliary-pump setup.

Never enable entities, infer external actuators from names, or change entries.
The four unit lists must describe the same units in the same order.
"""
from __future__ import annotations

from homeassistant.helpers import entity_registry as er
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .connection import resolve_bridge
from .pump_sources import PUMP_STATUS_SOURCES, normalize_pump_sources

UNIT_SOURCES = {
    "frequency_entities": "compressor_operating_frequency",
    "flow_entities": "water_flow",
    "supply_entities": "water_outlet_temperature_t7",
    "return_entities": "return_water_temperature_t6",
}
TEMPERATURE_SOURCES = {
    "tank_entity": "water_tank_temperature",
    "buffer_entity": "buffer_tank_temperature_t10",
    "outdoor_entity": "external_ambient_temperature_t1",
}
ENERGY_UNITS = {"Wh", "kWh", "MWh", "GJ", "MJ"}
TEMPERATURE_UNITS = {"°C", "C", "°F"}


def _slave(entry):
    try:
        value = int(entry.data["slave"])
        return value if 1 <= value <= 247 else None
    except (KeyError, TypeError, ValueError):
        return None


def _group(hass, entry):
    try:
        bridge = resolve_bridge(hass, entry)
    except (ConfigEntryNotReady, ValueError, TypeError, KeyError):
        # An unresolved explicit bridge must not be merged into another plant.
        return ("unresolved", entry.entry_id)
    if bridge:
        return ("bridge", bridge.entry_id)
    return ("endpoint", entry.data.get("host"), entry.data.get("port", 502),
            entry.data.get("connection_type", "rtuovertcp"))


def _units(hass, entries, registry, existing):
    pumps = {e.entry_id: e for e in entries if e.data.get("device_type") == "heat_pump"
             and not getattr(e, "disabled_by", None) and _slave(e) is not None}
    # Options: preserve the selected subset and order, including reverse order.
    # Custom sensor lists cannot safely identify the underlying plant.
    selected = None
    for key in UNIT_SOURCES:
        if key not in existing:
            continue
        ids = existing[key]
        if not isinstance(ids, list) or not ids:
            return []
        owners = [registry.entities.get(entity_id) for entity_id in ids]
        order = [getattr(meta, "config_entry_id", None) for meta in owners]
        if any(owner not in pumps for owner in order) or len(set(order)) != len(order):
            return []
        if selected is not None and selected != order:
            return []
        selected = order
    if selected is None:
        plant = hass.data.get(DOMAIN, {}).get("_panel", {}).get("settings", {}).get("plant")
        if plant:
            selected = plant.get("unit_ids", [])
            if not selected or any(uid not in pumps for uid in selected):
                return []
    units = [pumps[key] for key in selected] if selected else sorted(pumps.values(), key=lambda e: (_slave(e), e.entry_id))
    if not units or len(units) > 11 or len({_group(hass, e) for e in units}) != 1:
        return []
    if len({_slave(e) for e in units}) != len(units):
        return []
    return units


def suggest_pump_entities(hass, existing=None):
    """Return editable proposed mappings, with saved values (even empty) winning."""
    existing = normalize_pump_sources(existing)
    registry = er.async_get(hass)
    entries = list(hass.config_entries.async_entries(DOMAIN))
    units = _units(hass, entries, registry, existing)
    result = {}

    def usable(entity_id, *, units=None, boolean=False):
        if not isinstance(entity_id, str):
            return False
        meta = registry.entities.get(entity_id)
        if meta and meta.disabled_by:
            return False
        state = hass.states.get(entity_id)
        if state is None or state.attributes.get("restored"):
            return False
        if units is not None and state.attributes.get("unit_of_measurement") not in units:
            return False
        if boolean and str(state.state).lower() not in {"on", "off", "true", "false", "1", "0"}:
            return False
        return True

    def find(entry, fragment, **checks):
        uid = f"r290_heatpump_{fragment}_slave_{_slave(entry)}"
        matches = [meta.entity_id for meta in registry.entities.values()
                   if meta.platform == DOMAIN and meta.config_entry_id == entry.entry_id
                   and meta.unique_id == uid and meta.entity_id.startswith("sensor.")
                   and not meta.disabled_by and usable(meta.entity_id, **checks)]
        return matches[0] if len(matches) == 1 else None

    if units:
        quantities = {
            "frequency_entities": {"Hz"},
            "flow_entities": {"L/min", "l/min", "L/m", "l/m", "m³/h", "m3/h", "L/h", "l/h"},
            "supply_entities": TEMPERATURE_UNITS, "return_entities": TEMPERATURE_UNITS,
        }
        paired = {key: [find(entry, fragment, units=quantities[key]) for entry in units]
                  for key, fragment in UNIT_SOURCES.items()}
        # Do not silently omit a unit from one list or from all four lists.
        # An incomplete column stays empty; complete columns still cover every unit.
        for key, ids in paired.items():
            if all(ids):
                result[key] = ids
        # Complete per-unit lists; the controller combines each list with OR.
        # No helper entity and no name-based cross-plant matching are needed.
        for key, fragment in PUMP_STATUS_SOURCES.items():
            signals = [find(entry, fragment, boolean=True) for entry in units]
            if all(signals):
                result[key] = signals
        # Use the master for common measurements only when present (or one unit).
        master = next((entry for entry in units if _slave(entry) == 1), units[0] if len(units) == 1 else None)
        if master:
            for key, fragment in TEMPERATURE_SOURCES.items():
                if entity_id := find(master, fragment, units=TEMPERATURE_UNITS):
                    result[key] = entity_id

    # Reuse explicit plant mappings/COP sources only for an unambiguous plant.
    # Several separate bridges need a deliberate selection by the user.
    if units:
        cops = [{**e.data, **e.options} for e in entries
                if e.data.get("device_type") == "cop_calculator" and not getattr(e, "disabled_by", None)]
        for target, source in (("heat_energy_entity", "heat_meter"), ("electric_energy_entity", "power_meter")):
            candidates = {c[source] for c in cops if isinstance(c.get(source), str)
                          and c[source].startswith("sensor.") and usable(c[source], units=ENERGY_UNITS)}
            if len(candidates) == 1:
                result[target] = candidates.pop()
        # An explicitly configured COP split signal represents DHW already.
        # Do not confuse electric backup heating or a selected mode with DHW.
        candidates = {c["cop_split_sensor"] for c in cops if c.get("cop_split_enabled")
                      and isinstance(c.get("cop_split_sensor"), str)
                      and c["cop_split_sensor"].startswith("binary_sensor.")
                      and usable(c["cop_split_sensor"], boolean=True)}
        if len(candidates) == 1:
            result["dhw_entity"] = candidates.pop()
        panel = hass.data.get(DOMAIN, {}).get("_panel", {}).get("settings", {})
        display_units = {**{key: TEMPERATURE_UNITS for key in TEMPERATURE_SOURCES},
                         "pump_power_entity": {"W", "kW"},
                         "heat_energy_entity": ENERGY_UNITS, "electric_energy_entity": ENERGY_UNITS}
        for key, allowed in display_units.items():
            value = panel.get(key)
            if isinstance(value, str) and value.startswith("sensor.") and usable(value, units=allowed):
                result[key] = value
    return {**result, **existing}

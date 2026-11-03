"""Explicit plant description. Saving it never writes hardware or remaps a controller."""
from copy import deepcopy

CHOICES = {
    "mode": {"single", "cascade"},
    "heating": {"direct", "buffer_parallel", "buffer_series"},
    "separation": {"none", "plate"},
    "dhw": {"none", "coil", "plate"},
    "aux_position": {"none", "common_supply", "common_return", "heating_supply"},
    "emitters": {"radiators", "floor", "mixed"},
    "isolation": {"none", "pump_linked", "feedback"},
}


def legacy_plant(entries):
    units = [e.entry_id for e in entries.values() if e.data.get("device_type") == "heat_pump"
             and not getattr(e, "disabled_by", None)]
    controllers = [e.entry_id for e in entries.values() if e.data.get("device_type") == "auxiliary_pump"]
    return {"mode": "single" if len(units) == 1 else "cascade", "unit_ids": units,
            "heating": "buffer_parallel", "separation": "plate", "dhw": "coil",
            "aux_position": "common_supply", "emitters": "radiators",
            "isolation": "none", "valve_entities": {}, "controller_id": controllers[0] if len(controllers) == 1 else ""}


def validate_plant(value, entries, states):
    if not isinstance(value, dict) or set(value) - {*CHOICES, "unit_ids", "valve_entities", "controller_id"}:
        raise ValueError("Invalid plant configuration / Anlagenaufbau ungültig")
    result = deepcopy(value)
    for key, choices in CHOICES.items():
        if result.get(key) not in choices:
            raise ValueError(f"{key}: invalid choice")
    units = result.get("unit_ids")
    if (not isinstance(units, list) or any(not isinstance(x, str) for x in units)
            or not 1 <= len(units) <= 11 or len(set(units)) != len(units)):
        raise ValueError("Select 1–11 different heat pumps / 1–11 unterschiedliche Wärmepumpen wählen")
    if (result["mode"] == "single") != (len(units) == 1):
        raise ValueError("Single unit needs one device; cascade needs at least two / Geräteanzahl passt nicht zur Anlagenart")
    for uid in units:
        entry = entries.get(uid)
        if not entry or entry.data.get("device_type") != "heat_pump" or getattr(entry, "disabled_by", None):
            raise ValueError("Heat pump missing or disabled / Wärmepumpe fehlt oder ist deaktiviert")
    valves = result.get("valve_entities", {})
    if not isinstance(valves, dict) or set(valves) - set(units):
        raise ValueError("Valve assignment outside selected plant")
    for uid, entity_id in valves.items():
        if not isinstance(entity_id, str) or (entity_id and (entity_id.split('.')[0] not in
                         {"sensor", "binary_sensor", "switch", "input_boolean"} or states.get(entity_id) is None)):
            raise ValueError("Invalid valve feedback / Ungültige Ventilrückmeldung")
    if result["isolation"] == "feedback" and any(not valves.get(uid) for uid in units):
        raise ValueError("Assign open feedback for every valve / Offen-Rückmeldung für jeden Kugelhahn zuordnen")
    result["valve_entities"] = valves
    controller = result.get("controller_id", "")
    if not isinstance(controller, str) or (controller and (controller not in entries or
            entries[controller].data.get("device_type") != "auxiliary_pump")):
        raise ValueError("Invalid auxiliary controller")
    if result["aux_position"] == "none" and controller:
        raise ValueError("No auxiliary pump selected / Ohne Zusatzpumpe keinen Regler zuordnen")
    result["controller_id"] = controller
    return result


def controller_problem(plant, config, registry):
    """Require exact ordered device bindings; do not silently change saved mappings."""
    if plant["aux_position"] not in {"common_supply", "common_return"}:
        return "Automatic control requires a common pump / Automatik benötigt eine gemeinsame Zusatzpumpe"
    for key in ("frequency_entities", "flow_entities", "supply_entities", "return_entities"):
        owners = [getattr(registry.entities.get(eid), "config_entry_id", None) for eid in config.get(key, [])]
        if owners != plant["unit_ids"]:
            return "Controller sources differ from plant / Reglerquellen passen nicht zu den ausgewählten Geräten"
    return None

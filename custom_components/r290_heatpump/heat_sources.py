"""Optional heat-source observation. No actuator services or register writes."""
from copy import deepcopy

SOURCE_IDS = ("dhw_heater", "buffer_heater", "secondary")
STATUS_FIELDS = {"request_entity", "feedback_entity", "dhw_pump_entity", "heating_pump_entity"}
NUMERIC_FIELDS = {"power_entity", "energy_entity", "heat_entity", "dhw_temperature_entity", "heating_temperature_entity"}
ENTITY_FIELDS = STATUS_FIELDS | NUMERIC_FIELDS
KINDS = {"gas", "oil", "pellet", "wood", "solar", "district", "other"}


def defaults():
    return {key: {"enabled": False, "kind": "other", "serves": "dhw" if key == "dhw_heater" else "heating",
                  "managed_by": "observe", "entry_id": "", "electricity_scope": "unknown",
                  **({"placement": "buffer"} if key == "buffer_heater" else {}),
                  **{field: "" for field in ENTITY_FIELDS}} for key in SOURCE_IDS}


def validate(value, entries, states, plant):
    if not isinstance(value, dict) or set(value) - set(SOURCE_IDS):
        raise ValueError("Invalid heat sources / Ungültige Wärmeerzeuger")
    result = defaults()
    for key, source in value.items():
        if not isinstance(source, dict) or set(source) - set(result[key]):
            raise ValueError(f"{key}: invalid fields")
        cfg = {**result[key], **deepcopy(source)}
        if not isinstance(cfg["enabled"], bool):
            raise ValueError(f"{key}: enabled must be boolean")
        for field, choices in {"kind": KINDS, "serves": {"dhw", "heating", "both"},
                               "managed_by": {"observe", "heat_pump", "external"},
                               "electricity_scope": {"unknown", "included", "separate"}}.items():
            if not isinstance(cfg[field], str) or cfg[field] not in choices:
                raise ValueError(f"{key}: invalid {field}")
        target = "dhw" if key == "dhw_heater" else "heating"
        if key != "secondary" and cfg["serves"] != target:
            raise ValueError(f"{key}: invalid storage assignment")
        if key == "buffer_heater" and (not isinstance(cfg["placement"], str)
                                      or cfg["placement"] not in {"buffer", "supply", "return"}):
            raise ValueError("Invalid heating heater placement / Einbauort der Zusatzheizung ungültig")
        uid = cfg["entry_id"]
        if not isinstance(uid, str) or (cfg["enabled"] and uid and
                (uid not in plant["unit_ids"] or uid not in entries or getattr(entries[uid], "disabled_by", None))):
            raise ValueError(f"{key}: selected heat pump missing / Zugeordnete Wärmepumpe fehlt")
        if cfg["enabled"]:
            if cfg["managed_by"] == "heat_pump" and not uid:
                raise ValueError(f"{key}: select controlling heat pump / Steuernde Wärmepumpe auswählen")
            if cfg["serves"] in {"dhw", "both"} and plant["dhw"] == "none":
                raise ValueError("DHW heat source needs a DHW tank / WW-Wärmeerzeuger benötigt einen WW-Speicher")
            if key == "buffer_heater" and cfg["placement"] == "buffer" and plant["heating"] == "direct":
                raise ValueError("Buffer heater needs a buffer / Puffer-Heizstab benötigt einen Puffer")
        for field in ENTITY_FIELDS:
            eid = cfg[field]
            domains = {"sensor", "binary_sensor", "switch", "input_boolean"} if field in STATUS_FIELDS else {"sensor"}
            if not isinstance(eid, str) or (eid and (eid.split(".")[0] not in domains or
                    (cfg["enabled"] and states.get(eid) is None))):
                raise ValueError(f"{key}: invalid {field} / Messquelle fehlt oder ist ungeeignet")
            if eid and cfg["enabled"] and field in NUMERIC_FIELDS:
                unit = states.get(eid).attributes.get("unit_of_measurement")
                allowed = {"W", "kW"} if field == "power_entity" else {"Wh", "kWh", "MWh"} if field in {"energy_entity", "heat_entity"} else {"°C", "°F"}
                if unit not in allowed:
                    raise ValueError(f"{key}: {field} requires {' / '.join(sorted(allowed))}")
        result[key] = cfg
    return result


def history_entities(sources):
    return {source[field] for source in sources.values() if isinstance(source, dict) and source.get("enabled")
            for field in ENTITY_FIELDS if isinstance(source.get(field), str) and source[field]}

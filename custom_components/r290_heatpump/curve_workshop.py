"""Allowlisted curve configuration edits, committed together in one entry update."""
from hashlib import sha256
import json
from decimal import Decimal

from .analytics import number
from .pv_optimization import PV_CURVE_CONFIG
from .curve_math import LIMITS, ENDPOINT_KEYS, points_from_options, validate_points, endpoint_options, replace_endpoints

# key, display label, group, unique-id suffix (None for base curve numbers)
FIELDS = [
    ("t_out_min", "Außen · kalter Stützpunkt", "basis", None),
    ("t_flow_max", "Soll · am kalten Stützpunkt", "basis", None),
    ("t_out_max", "Außen · warmer Stützpunkt", "basis", None),
    ("t_flow_min", "Soll · am warmen Stützpunkt", "basis", None),
    ("heatcurve_active", "Kurvenregelung", "basis", "curve_active"),
    ("pv_enabled", "PV-Optimierung", "pv", "pv_optimization"),
    ("pv_grid_threshold_min_kw", "PV-Schwelle 1 · kW", "pv", "pv_grid_threshold_min_kw"),
    ("pv_grid_offset_min", "Offset ab Schwelle 1", "pv", "pv_grid_offset_min"),
    ("pv_grid_threshold_max_kw", "PV-Schwelle 2 · kW", "pv", "pv_grid_threshold_max_kw"),
    ("pv_grid_offset_max", "Offset ab Schwelle 2", "pv", "pv_grid_offset_max"),
    ("pv_battery_threshold_pct", "Batterieschwelle · %", "pv", "pv_battery_threshold_pct"),
    ("pv_battery_offset", "Batterie-Offset", "pv", "pv_battery_offset"),
    ("pv_offset_reset_kw", "Rücksetzschwelle · kW", "pv", "pv_offset_reset_kw"),
    ("pv_hold_minutes", "PV-Haltezeit · min", "pv", "pv_hold_minutes"),
    ("external_offset_enabled", "Externe Anhebung", "pv", "external_heating_offset"),
    ("external_offset_value", "Externer Offset · °C", "pv", "external_offset"),
    ("external_offset_hold_minutes", "Externe Haltezeit · min", "pv", "external_offset_hold"),
    ("inertia_hours", "Sollwert glätten · Stunden", "fine", None),
    ("stepsize_c", "Mindeständerung · °C", "fine", None),
]


def snapshot(entry, entities):
    cfg = PV_CURVE_CONFIG.get(entry.data.get("device_type"))
    if cfg is None:
        return None
    controls = []
    for key, label, section, suffix in FIELDS:
        uid = (f"r290_heatpump_{cfg['prefix']}_{suffix}_{entry.entry_id}" if suffix
               else f"r290_heatpump_heatcurve_{entry.entry_id}_{key}")
        meta = next((e for e in entities if e.config_entry_id == entry.entry_id and e.unique_id == uid and not e.disabled_by), None)
        if meta:
            controls.append(dict(key=key, label=label, section=section, id=meta.entity_id))
    # A digest detects options changes even while entity states lag a reload.
    revision = sha256(json.dumps([dict(entry.data), dict(entry.options)], sort_keys=True, default=str).encode()).hexdigest()
    try:
        points, error = points_from_options({**entry.data, **entry.options}), None
    except ValueError as err:
        points, error = [], str(err)
    return dict(entry_id=entry.entry_id, revision=revision,
                outdoor_entity=entry.data.get("outdoor_sensor"), controls=controls,
                points=points, point_limits=LIMITS, point_error=error,
                custom_points="curve_points" in {**entry.data, **entry.options})


def validate(entry, snap, changes, states, points=None):
    if not isinstance(changes, list) or not (0 if points is not None else 1) <= len(changes) <= len(FIELDS):
        raise ValueError("Ungültige Anzahl von Kurvenänderungen")
    allowed = {c["id"]: c for c in snap["controls"]}
    values, seen = {}, set()
    for change in changes:
        entity_id = change.get("entity_id")
        if entity_id not in allowed or entity_id in seen:
            raise ValueError("Entität gehört nicht zu dieser Kurve oder ist doppelt")
        seen.add(entity_id)
        state = states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable") or state.state != change.get("expected"):
            raise ValueError("Wert seit Vorschau geändert oder nicht verfügbar. Entwurf verwerfen und erneut prüfen.")
        value = change.get("value")
        domain = entity_id.split(".")[0]
        if domain == "number":
            value = number(value)
            lo, hi = state.attributes.get("min"), state.attributes.get("max")
            if value is None or lo is None or hi is None or not float(lo) <= value <= float(hi):
                raise ValueError("Wert außerhalb der Entitätsgrenzen")
            step = Decimal(str(state.attributes.get("step", 1)))
            if step > 0 and (Decimal(str(value)) - Decimal(str(lo))) % step:
                raise ValueError("Wert passt nicht zur Schrittweite")
        elif domain == "select" and value in state.attributes.get("options", []):
            value = int(str(value).split()[0])
            if not -10 <= value <= 10:
                raise ValueError("Ungültiger PV-Offset")
        elif domain == "switch" and value in ("on", "off"):
            value = value == "on"
        else:
            raise ValueError("Nicht unterstützter Kurvenwert")
        values[allowed[entity_id]["key"]] = value
    existing = {**entry.data, **entry.options}
    if points is not None:
        if ENDPOINT_KEYS & values.keys():
            raise ValueError("Stützpunkte und alte Endpunktfelder nicht gleichzeitig ändern")
        clean = validate_points(points)
        values.update(curve_points=clean, **endpoint_options(clean))
    elif "curve_points" in existing and ENDPOINT_KEYS & values.keys():
        clean = replace_endpoints(existing, values)
        values.update(curve_points=clean, **endpoint_options(clean))
    effective = {**existing, **values}
    points_from_options(effective)
    if float(effective.get("t_out_min", -15)) >= float(effective.get("t_out_max", 20)):
        raise ValueError("Der kalte Außenstützpunkt muss unter dem warmen liegen")
    if {"pv_grid_threshold_min_kw", "pv_grid_threshold_max_kw"} & values.keys():
        defaults = PV_CURVE_CONFIG[entry.data["device_type"]]
        if float(effective.get("pv_grid_threshold_min_kw", defaults["grid_threshold_min_default"])) > float(effective.get("pv_grid_threshold_max_kw", defaults["grid_threshold_max_default"])):
            raise ValueError("PV-Schwelle 1 darf Schwelle 2 nicht überschreiten")
    return values

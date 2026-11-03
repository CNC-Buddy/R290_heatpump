"""Display-only electrical overview and migration of legacy schematic nodes."""
from __future__ import annotations

from copy import deepcopy
import re

COMPONENTS = {"pv", "battery", "house", "grid"}
FIELDS = {"pv_power", "house_power", "battery_power", "battery_soc", "grid_power", "hp_power"}
DEFAULTS = {"enabled": False, "battery_positive": "unknown", "grid_positive": "unknown",
            **dict.fromkeys(FIELDS, "")}


def validate(value, states):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError("Invalid electrical overview / Ungültige Stromübersicht")
    result = {**DEFAULTS, **value}
    if type(result["enabled"]) is not bool:
        raise ValueError("enabled must be a boolean")
    for key, allowed in (("battery_positive", {"unknown", "charge", "discharge"}),
                         ("grid_positive", {"unknown", "import", "export"})):
        if not isinstance(result[key], str) or result[key] not in allowed:
            raise ValueError(key)
    for key in FIELDS:
        entity = result[key]
        if not isinstance(entity, str) or entity and not re.fullmatch(r"sensor\.[a-z0-9_]+", entity):
            raise ValueError(key)
        state = states.get(entity) if entity else None
        # Preserve temporarily absent sources. Never accept energy counters as power.
        units = {"%"} if key == "battery_soc" else {"W", "kW", "MW"}
        if state and state.attributes.get("unit_of_measurement") not in units:
            raise ValueError(f"{key}: {'%' if key == 'battery_soc' else 'W / kW / MW'} required / erforderlich")
    return result


def history_entities(config):
    return {config[key] for key in FIELDS if isinstance(config.get(key), str) and config[key]}


def migrate(settings):
    """Keep plumbing coordinates, routes and heaters; retain originals for recovery.

    Only unequivocal legacy bindings are prefilled. Sign conventions cannot be
    inferred from a cable or a sensor name and therefore remain unknown.
    """
    schematic = settings.get("schematic", {})
    graphs = {key: schematic.get(key) for key in ("draft", "published")}
    removed = {key: {n["id"] for n in graph.get("nodes", [])
                     if n["type"] in COMPONENTS or n["type"] == "junction" and n.get("circuit") == "electric"}
               for key, graph in graphs.items() if isinstance(graph, dict)}
    if not any(removed.values()):
        return settings
    result = deepcopy(settings)
    candidates = {key: set() for key in FIELDS}
    found = False
    for key, ids in removed.items():
        if not ids:
            continue
        original = graphs[key]
        for node in original.get("nodes", []):
            kind, bindings = node["type"], node.get("bindings", {})
            if kind not in COMPONENTS:
                continue
            found = True
            for field, source in ((f"{kind}_power", bindings.get("value")),
                                  ("battery_soc", bindings.get("soc") if kind == "battery" else None)):
                if isinstance(source, str) and re.fullmatch(r"sensor\.[a-z0-9_]+", source):
                    candidates[field].add(source)
        result["schematic"].setdefault("electric_backup", {}).setdefault(key, deepcopy(original))
        graph = result["schematic"][key]
        graph["nodes"] = [n for n in graph["nodes"] if n["id"] not in ids]
        graph["edges"] = [e for e in graph["edges"] if e["from"]["node"] not in ids and e["to"]["node"] not in ids]
        if key == "published" and not graph["nodes"]:
            result["schematic"][key] = None
    if "electric" not in result:
        result["electric"] = {**DEFAULTS, "enabled": found,
                              **{key: next(iter(ids)) for key, ids in candidates.items() if len(ids) == 1}}
    result["schematic"]["revision"] = schematic.get("revision", 0) + 1
    return result

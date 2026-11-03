"""Display-only plant graph. No entity services, register writes or control logic.

The same bounded component catalogue is consumed by the browser. Ports, rather
than drawn line intersections, define connectivity. Separate exchanger/coil
groups never mix fluids. Validation is a graph check, not hydraulic sizing.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
import math
from pathlib import Path
import re

ID = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")
ENTITY = re.compile(r"(?:sensor|binary_sensor|switch|input_boolean|number|input_number|select|input_select|fan|climate)\.[a-z0-9_]+\Z")
BINDINGS = {"value", "supply", "return", "status", "flow", "phase", "fan", "soc"}
CIRCUITS = {"wp", "heating", "we2", "warmwater", "electric"}


@lru_cache(maxsize=1)
def catalogue():
    return json.loads((Path(__file__).parent / "frontend" / "schematic-catalog.json").read_text(encoding="utf-8"))


def ports(node):
    result = {}
    for key, definition in catalogue()[node["type"]]["ports"].items():
        port = dict(definition)
        if port["circuit"] == "$":
            port["circuit"] = node["circuit"]
        if port["leg"] == "$":
            port["leg"] = node["leg"]
        result[key] = port
    return result


def _coord(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 3600


def validate_graph(value):
    """Reject unknown fields, forged ports, fluid mixing and unbounded input."""
    if not isinstance(value, dict) or set(value) != {"version", "nodes", "edges"} or type(value.get("version")) is not int or value["version"] != 1:
        raise ValueError("Invalid schematic version / Ungültige Schaubildversion")
    nodes, edges = value["nodes"], value["edges"]
    if not isinstance(nodes, list) or not isinstance(edges, list) or len(nodes) > 80 or len(edges) > 160:
        raise ValueError("Maximum 80 components and 160 pipes / Maximal 80 Bauteile und 160 Leitungen")
    by_id = {}
    for node in nodes:
        if not isinstance(node, dict) or set(node) - {"id", "type", "label", "x", "y", "circuit", "leg", "bindings", "flip", "flip_y", "tank", "temperature_zones"}:
            raise ValueError("Invalid component / Ungültiges Bauteil")
        key, kind = node.get("id"), node.get("type")
        if not isinstance(key, str) or not ID.fullmatch(key) or key in by_id or not isinstance(kind, str) or kind not in catalogue():
            raise ValueError("Invalid or duplicate component ID / Ungültige oder doppelte Bauteil-ID")
        if not _coord(node.get("x")) or not _coord(node.get("y")):
            raise ValueError("Invalid component position / Ungültige Bauteilposition")
        if not isinstance(node.get("label", ""), str) or len(node.get("label", "")) > 70:
            raise ValueError("Label: maximum 70 characters / Name: maximal 70 Zeichen")
        spec = catalogue()[kind]
        if node.get("circuit") not in spec["circuits"] or node.get("leg") not in spec["legs"]:
            raise ValueError("Invalid component circuit / Unzulässiger Bauteilkreis")
        if (node["circuit"] == "electric") != (node["leg"] == "power") or any(type(node.get(k, False)) is not bool for k in ("flip", "flip_y")):
            raise ValueError("Invalid component orientation or medium / Ungültige Ausrichtung oder Medium")
        bindings = node.get("bindings", {})
        if not isinstance(bindings, dict) or set(bindings) - BINDINGS or any(not isinstance(v, str) or (v and not ENTITY.fullmatch(v)) for v in bindings.values()):
            raise ValueError("Invalid read-only source / Ungültige Anzeigequelle")
        by_id[key] = node
    for node in nodes:
        if "tank" in node and (node["type"] != "heater" or not isinstance(node["tank"], str) or by_id.get(node["tank"], {}).get("type") not in {"buffer", "dhw_tank"}):
            raise ValueError("Invalid heater mount / Ungültige Heizstabzuordnung")
        if "temperature_zones" in node:
            zones = node["temperature_zones"]
            if node["type"] not in {"buffer", "dhw_tank"} or not isinstance(zones, list) or len(zones) > 4:
                raise ValueError("Invalid tank zones / Ungültige Speicherzonen")
            previous = None
            for zone in zones:
                if (not isinstance(zone, dict) or set(zone) != {"entity", "height"}
                        or not isinstance(zone["entity"], str)
                        or zone["entity"] and not re.fullmatch(r"sensor\.[a-z0-9_]+", zone["entity"])
                        or not _coord(zone["height"]) or not 5 <= zone["height"] <= 95
                        or previous is not None and zone["height"] - previous < 8):
                    raise ValueError("Invalid temperature sensor or height / Ungültiger Fühler oder Höhe")
                previous = zone["height"]
    edge_ids, occupied = set(), set()
    for edge in edges:
        if not isinstance(edge, dict) or set(edge) - {"id", "from", "to", "points", "route"}:
            raise ValueError("Invalid pipe / Ungültige Leitung")
        key = edge.get("id")
        if not isinstance(key, str) or not ID.fullmatch(key) or key in edge_ids:
            raise ValueError("Invalid or duplicate pipe ID / Ungültige oder doppelte Leitungs-ID")
        edge_ids.add(key)
        pair = []
        for end in ("from", "to"):
            endpoint = edge.get(end)
            if not isinstance(endpoint, dict) or set(endpoint) != {"node", "port"} or not all(isinstance(v, str) for v in endpoint.values()):
                raise ValueError("Invalid pipe endpoint / Ungültiger Leitungsanschluss")
            n, port = endpoint["node"], endpoint["port"]
            if n not in by_id or port not in ports(by_id[n]) or (n, port) in occupied:
                raise ValueError("Unknown or occupied port; use a junction / Anschluss unbekannt oder belegt; T-Stück verwenden")
            occupied.add((n, port))
            pair.append(ports(by_id[n])[port])
        if edge["from"]["node"] == edge["to"]["node"]:
            raise ValueError("A pipe must connect two components / Leitung muss zwei Bauteile verbinden")
        a, b = pair
        if a["circuit"] != b["circuit"] or a["leg"] != b["leg"] or a["direction"] == "in" or b["direction"] == "out":
            raise ValueError("Incompatible fluid, supply/return or direction / Wasserkreis, Vor-/Rücklauf oder Richtung passen nicht")
        points = edge.get("points", [])
        if not isinstance(points, list) or len(points) > 16 or any(not isinstance(p, list) or len(p) != 2 or not all(_coord(c) for c in p) for p in points):
            raise ValueError("Invalid pipe waypoints / Ungültige Leitungsknickpunkte")
        if "route" in edge:
            route = edge["route"]
            if (not isinstance(route, list) or not 2 <= len(route) <= 256
                    or any(not isinstance(p, list) or len(p) != 2
                           or not all(type(c) in (int, float) and math.isfinite(c) and -100 <= c <= 4000 for c in p) for p in route)
                    or any(a[0] != b[0] and a[1] != b[1] for a, b in zip(route, route[1:]))):
                raise ValueError("Invalid saved pipe route / Ungültiger gespeicherter Leitungsweg")
    return deepcopy(value)


def completeness(graph):
    """Find missing port pairs and pumps/sources without a closed directed loop."""
    nodes = {n["id"]: n for n in graph["nodes"]}
    used, adjacency, problems = set(), {}, []
    for e in graph["edges"]:
        # Do not depend on client object key order.
        a = (e["from"]["node"], e["from"]["port"])
        b = (e["to"]["node"], e["to"]["port"])
        used.update((a, b)); adjacency.setdefault(a, set()).add(b)
    if not nodes:
        return ["No components / Keine Bauteile"]
    for node in nodes.values():
        key, spec = node["id"], catalogue()[node["type"]]
        p = ports(node)
        for group in spec["groups"]:
            connected = [name for name in group if (key, name) in used]
            if connected and len(connected) != len(group):
                problems.append(f"{key}: Open connections / Offene Anschlüsse ({', '.join(n for n in group if n not in connected)})")
            for src in group:
                for dst in group:
                    if src != dst and p[src]["direction"] != "out" and p[dst]["direction"] != "in":
                        adjacency.setdefault((key, src), set()).add((key, dst))
        if not node.get("tank") and not any((key, name) in used for name in p):
            problems.append(f"{key}: Not connected / Nicht verbunden")
        if spec.get("require_all") and any((key, name) not in used for name in p):
            problems.append(f"{key}: All ports required / Alle Anschlüsse erforderlich")
    for node in nodes.values():
        if not catalogue()[node["type"]].get("closed_loop"):
            continue
        p = ports(node)
        for name, port in p.items():
            if port["direction"] != "out":
                continue
            start, stack, seen = (node["id"], name), [], set()
            stack.extend(adjacency.get(start, ()))
            while stack:
                cur = stack.pop()
                if cur == start:
                    break
                if cur not in seen:
                    seen.add(cur); stack.extend(adjacency.get(cur, ()))
            else:
                problems.append(f"{node['id']}: No closed loop / Kein geschlossener Kreis")
                break
    return list(dict.fromkeys(problems))


def history_entities(config):
    result = set()
    for graph in (config.get("draft"), config.get("published")):
        if not isinstance(graph, dict):
            continue
        for node in graph.get("nodes", []):
            result.update(e for e in node.get("bindings", {}).values() if e)
            result.update(z["entity"] for z in node.get("temperature_zones", []) if z.get("entity"))
    return result

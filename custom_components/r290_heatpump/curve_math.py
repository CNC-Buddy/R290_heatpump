"""Pure, shared contract for legacy and piecewise-linear temperature curves."""
import math
from decimal import Decimal

MAX_POINTS = 10
# Outdoor range of the existing helpers; target range of user registers 0300–0303.
LIMITS = {"outdoor_min": -30, "outdoor_max": 35,
          "target_min": -20, "target_max": 80, "step": 0.1, "max_points": MAX_POINTS}
DEFAULTS = {"t_out_min": -15.0, "t_out_max": 20.0,
            "t_flow_min": 25.0, "t_flow_max": 50.0}
ENDPOINT_KEYS = frozenset(DEFAULTS)


def finite(value):
    if isinstance(value, bool):
        raise ValueError("Kurvenwerte müssen endliche Zahlen sein")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as err:
        raise ValueError("Kurvenwerte müssen endliche Zahlen sein") from err
    if not math.isfinite(value):
        raise ValueError("Kurvenwerte müssen endliche Zahlen sein")
    return value


def validate_points(points):
    if not isinstance(points, list) or not 2 <= len(points) <= MAX_POINTS:
        raise ValueError("Eine Kurve benötigt 2 bis 10 Stützpunkte")
    clean = []
    for point in points:
        if not isinstance(point, dict) or set(point) != {"outdoor", "target"}:
            raise ValueError("Jeder Stützpunkt benötigt Außen- und Solltemperatur")
        values = {key: finite(point[key]) for key in ("outdoor", "target")}
        for key, value in values.items():
            if not LIMITS[f"{key}_min"] <= value <= LIMITS[f"{key}_max"]:
                raise ValueError("Stützpunkt außerhalb des zulässigen Temperaturbereichs")
            if Decimal(str(value)) % Decimal("0.1"):
                raise ValueError("Stützpunkte benötigen Schritte von 0,1 °C")
        if clean and values["outdoor"] <= clean[-1]["outdoor"]:
            raise ValueError("Außentemperaturen müssen von kalt nach warm eindeutig ansteigen")
        clean.append(values)
    return clean


def points_from_options(options):
    # An invalid explicit curve must never silently turn into a default curve.
    if "curve_points" in options:
        return validate_points(options["curve_points"])
    values = {key: finite(options.get(key, default)) for key, default in DEFAULTS.items()}
    return validate_points([
        {"outdoor": values["t_out_min"], "target": values["t_flow_max"]},
        {"outdoor": values["t_out_max"], "target": values["t_flow_min"]},
    ])


def endpoint_options(points):
    return {"t_out_min": points[0]["outdoor"], "t_flow_max": points[0]["target"],
            "t_out_max": points[-1]["outdoor"], "t_flow_min": points[-1]["target"]}


def replace_endpoints(options, changes):
    points = points_from_options(options)
    for key, index, field in (("t_out_min", 0, "outdoor"), ("t_flow_max", 0, "target"),
                              ("t_out_max", -1, "outdoor"), ("t_flow_min", -1, "target")):
        if key in changes:
            points[index][field] = changes[key]
    return validate_points(points)


def interpolate(points, outdoor):
    outdoor = finite(outdoor)
    if outdoor <= points[0]["outdoor"]:
        return points[0]["target"]
    for left, right in zip(points, points[1:]):
        if outdoor <= right["outdoor"]:
            ratio = (outdoor - left["outdoor"]) / (right["outdoor"] - left["outdoor"])
            return left["target"] + ratio * (right["target"] - left["target"])
    return points[-1]["target"]

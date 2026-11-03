"""Deterministic auxiliary-pump decisions. No HA imports or hardware writes."""
from __future__ import annotations

from dataclasses import dataclass, field
import math


DEFAULTS = {
    "min_speed": 30.0, "max_speed": 100.0, "safe_speed": 60.0,
    "defrost_speed": 100.0, "manual_speed": 60.0,
    "heating_delta": 5.0, "dhw_delta": 5.0, "deadband": 0.5,
    "min_flow": 15.0, "max_step": 2.0, "interval": 30.0,
    "startup_seconds": 60.0, "postrun_seconds": 120.0,
    "max_age": 180.0, "output_min": 0.0, "output_max": 100.0,
    "commissioned": False,
}
RANGES = {
    "min_speed": (1, 100), "max_speed": (1, 100), "safe_speed": (1, 100),
    "defrost_speed": (1, 100), "manual_speed": (1, 100),
    "heating_delta": (1, 15), "dhw_delta": (1, 15), "deadband": (0.1, 3),
    "min_flow": (1, 200), "max_step": (0.1, 10), "interval": (10, 300),
    "startup_seconds": (10, 600), "postrun_seconds": (0, 1800),
    "max_age": (30, 1800), "output_min": (-10000, 10000),
    "output_max": (-10000, 10000),
}
MODES = ("observe", "manual", "auto")


def validate_settings(values: dict) -> dict:
    result = {**DEFAULTS, **values}
    for key, (lo, hi) in RANGES.items():
        value = float(result[key])
        if not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f"{key}: {lo} … {hi}")
        result[key] = value
    if not result["min_speed"] <= result["safe_speed"] <= result["max_speed"]:
        raise ValueError("min_speed <= safe_speed <= max_speed")
    if not result["safe_speed"] <= result["defrost_speed"] <= result["max_speed"]:
        raise ValueError("safe_speed <= defrost_speed <= max_speed")
    if not result["min_speed"] <= result["manual_speed"] <= result["max_speed"]:
        raise ValueError("manual_speed outside limits")
    if result["output_min"] >= result["output_max"]:
        raise ValueError("output_min < output_max")
    if result["max_age"] < result["interval"]:
        raise ValueError("max_age >= interval")
    if not isinstance(result["commissioned"], bool):
        raise ValueError("commissioned must be boolean")
    return result


@dataclass(frozen=True)
class UnitReading:
    frequency: float | None
    flow: float | None
    supply: float | None
    return_temperature: float | None


@dataclass(frozen=True)
class Snapshot:
    demand: bool | None
    dhw: bool | None
    defrost: bool | None
    units: tuple[UnitReading, ...]
    actual_speed: float | None = None
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class Decision:
    phase: str
    speed: float
    reason: str
    target_delta: float | None = None
    deltas: tuple[float, ...] = ()
    active_units: int = 0
    issues: tuple[str, ...] = ()
    command_allowed: bool = True


@dataclass
class PumpLogic:
    settings: dict
    running_since: float | None = None
    idle_since: float | None = None
    last_adjustment: float = -math.inf
    previous: Decision | None = field(default=None, init=False)

    def __post_init__(self):
        self.settings = validate_settings(self.settings)

    def decide(self, sample: Snapshot, now: float, mode: str = "auto") -> Decision:
        """Use monotonic seconds. Frequency zero alone never authorizes stopping."""
        s = self.settings
        actual = sample.actual_speed
        retained = self.previous.speed if self.previous and self.previous.speed > 0 else s["safe_speed"]
        base = actual if actual is not None and math.isfinite(actual) and actual > 0 else max(retained, s["safe_speed"])
        base = max(s["min_speed"], min(s["max_speed"], base))
        active = [u for u in sample.units if u.frequency is not None and u.frequency > 0]
        issues = list(sample.issues)
        if not sample.units or any(u.frequency is None for u in sample.units):
            issues.append("compressor_unavailable")
        if sample.demand is None or sample.defrost is None or sample.dhw is None:
            issues.append("operating_state_unavailable")
        deltas = tuple(u.supply - u.return_temperature for u in active
                       if u.supply is not None and u.return_temperature is not None)

        def decision(phase, speed, reason, target=None, command_allowed=True):
            value = Decision(phase, round(speed, 2), reason, target, deltas,
                             len(active), tuple(dict.fromkeys(issues)), command_allowed)
            self.previous = value
            return value

        # The internal pump relay also opens this installation's isolation
        # valves. Neither compressor status nor a timer proves an open path.
        if sample.demand is False:
            self.running_since = self.idle_since = None
            if active or sample.defrost is True:
                issues.append("demand_status_conflict")
            return decision("idle", 0.0, "hydraulic_path_closed")
        if sample.demand is None:
            self.running_since = self.idle_since = None
            # Hold the physical output, not a previous proposal. In particular,
            # missing inputs must never switch a stopped pump on. With unknown
            # feedback the displayed proposal is zero, but NO command is sent.
            held = actual if actual is not None and math.isfinite(actual) else 0.0
            return decision("fallback", held, "demand_unavailable_hold", command_allowed=False)
        if sample.defrost is True:
            self.idle_since = None
            self.running_since = now  # settle again after defrost
            return decision("defrost", s["defrost_speed"], "defrost_priority")
        if issues:
            self.idle_since = None
            self.running_since = now  # full settling period after data recovery
            return decision("fallback", max(base, s["safe_speed"]), "invalid_inputs")

        # Any post-circulation is bounded by the internal pump's demand. The
        # legacy postrun option cannot extend circulation through closed valves.
        self.idle_since = None
        if self.running_since is None:
            self.running_since = now
        if any(u.flow is None for u in active):
            return decision("fallback", max(base, s["safe_speed"]), "flow_unavailable")
        if any(u.flow < s["min_flow"] for u in active):
            return decision("flow_guard", s["max_speed"], "minimum_flow")
        if now - self.running_since < s["startup_seconds"]:
            return decision("startup", max(base, s["safe_speed"]), "settling_timer")
        if not active:
            return decision("circulation", s["safe_speed"], "demand_without_compressor")
        if len(deltas) != len(active) or any(not math.isfinite(v) or v < -1 or v > 30 for v in deltas):
            return decision("fallback", max(base, s["safe_speed"]), "temperature_unavailable")

        phase = "dhw" if sample.dhw else "heating"
        target = s["dhw_delta"] if sample.dhw else s["heating_delta"]
        if mode == "manual":
            return decision(phase, s["manual_speed"], "manual_target", target)
        if now - self.last_adjustment < s["interval"] and self.previous:
            return decision(phase, self.previous.speed, "adjustment_interval", target)
        self.last_adjustment = now
        # The largest spread limits reduction when two parallel units operate.
        error = max(deltas) - target
        step = s["max_step"] if error > s["deadband"] else -s["max_step"] if error < -s["deadband"] else 0
        speed = max(s["min_speed"], min(s["max_speed"], base + step))
        return decision(phase, speed, "increase_flow" if step > 0 else "reduce_flow" if step < 0 else "within_deadband", target)

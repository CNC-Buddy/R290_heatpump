"""Conservative summaries of irregular, state-change-based recorder histories."""
from __future__ import annotations
import math


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def summarize(points, start, end, *, kind="value", gap_limit=900):
    """Timestamps in seconds, values may be None. Never interpolate counters.

    Counter timestamps expose the *changes* recorder knows about. Long gaps can
    mean a stationary counter or missed radio packets; neither is silently
    interpreted as precise daily production. Report the uncertainty instead.
    """
    points = sorted((float(t), number(v)) for t, v in points if float(t) <= end)
    duration = max(0, end - start)
    known_seconds = runtime = integrated = 0.0
    starts = resets = 0
    previous = None
    previous_at = start
    counter_delta = 0.0
    increments = []
    max_gap = 0.0
    first_value = last_value = None
    for index, (at, value) in enumerate(points):
        if at <= start:
            previous, previous_at = value, at
            if value is not None:
                first_value = last_value = value
            continue
        begin = max(start, previous_at)
        seconds = max(0, at - begin)
        if previous is not None:
            known_seconds += seconds
            if previous > 0:
                runtime += seconds
            integrated += previous * seconds / 3600
        if value is not None:
            if first_value is None:
                first_value = value
            last_value = value
        if previous is not None and value is not None:
            if previous == 0 and value > 0:
                starts += 1
            if kind == "energy":
                delta = value - previous
                if delta < 0:
                    resets += 1
                else:
                    counter_delta += delta
                    if delta > 0:
                        gap = at - previous_at
                        max_gap = max(max_gap, gap)
                        increments.append({"at": at, "value": delta, "interval_seconds": gap})
        previous, previous_at = value, at
    if previous is not None:
        seconds = max(0, end - max(start, previous_at))
        known_seconds += seconds
        runtime += seconds if previous > 0 else 0
        integrated += previous * seconds / 3600
    tail_age = max(0, end - previous_at) if points else None
    boundary_age = max(0, start - points[0][0]) if points and points[0][0] <= start else None
    uncertain = (kind == "energy" and (resets > 0 or max_gap > gap_limit or
                 tail_age is None or tail_age > gap_limit or boundary_age is None or
                 boundary_age > gap_limit or known_seconds < duration))
    return {"delta": counter_delta if kind == "energy" and first_value is not None else None,
            "runtime_hours": runtime / 3600, "starts": starts,
            "integral": integrated, "coverage": known_seconds / duration if duration else 0,
            "resets": resets, "max_increment_gap": max_gap,
            "last_change_age": tail_age, "uncertain": uncertain,
            "increments": increments, "first": first_value, "last": last_value}


def thin(points, limit=720):
    """Envelope sampling retains spikes, gaps and endpoints for chart rendering."""
    if len(points) <= limit:
        return points
    stride = max(1, math.ceil(len(points) / max(1, (limit - 2) // 4)))
    result = [points[0]]
    for i in range(1, len(points) - 1, stride):
        bucket = points[i:i + stride]
        valid = [p for p in bucket if p[1] is not None]
        candidates = [bucket[0], bucket[-1]]
        if valid:
            candidates.extend([min(valid, key=lambda p: p[1]), max(valid, key=lambda p: p[1])])
        missing = next((p for p in bucket if p[1] is None), None)
        if missing:
            candidates.append(missing)
        result.extend(sorted({tuple(p) for p in candidates}, key=lambda p: p[0]))
    result.append(points[-1])
    return result

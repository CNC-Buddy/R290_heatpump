"""Bounded transport measurements, equally available in legacy and auto."""

from collections import deque
from math import ceil
import time


class TransportMetrics:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.started = clock()
        self.samples = deque(maxlen=5000)

    def record(self, unit, kind, began, acquired, ok):
        now = self.clock()
        self.samples.append(
            (now, unit, kind, max(0, now - acquired), max(0, acquired - began), not ok)
        )

    def snapshot(self):
        now = self.clock()
        rows = [r for r in self.samples if now - r[0] <= 60]
        durations = sorted(r[3] for r in rows)
        return {
            "transactions_last_minute": len(rows),
            "errors_last_minute": sum(r[5] for r in rows),
            "latency_mean": sum(durations) / len(rows) if rows else None,
            "latency_p95": (durations[ceil(len(rows) * 0.95) - 1] if rows else None),
            "max_lock_wait": max((r[4] for r in rows), default=0),
            "transport_time_fraction": min(
                1, sum(durations) / max(1, min(60, now - self.started))
            ),
        }

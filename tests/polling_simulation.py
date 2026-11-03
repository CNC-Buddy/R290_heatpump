"""24-hour deterministic model; no HA, network, equipment or elapsed-day wait."""

import asyncio
import importlib
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType("simulation_component")
package.__path__ = [str(ROOT / "custom_components/r290_heatpump")]
sys.modules[package.__name__] = package
Scheduler = importlib.import_module("simulation_component.polling.scheduler").Scheduler


async def simulate():
    now = 0.0
    calls = {1: 0, 2: 0}
    active = max_active = 0
    healthy_max_age = 0.0
    progress = 21600
    busy = 0.0
    addresses = sorted(
        {
            r["address"]
            for r in json.loads(
                (
                    ROOT
                    / "custom_components/r290_heatpump/frontend/register-catalog.json"
                ).read_text("utf-8")
            )["records"]
        }
    )

    async def read(unit, start, count):
        nonlocal now, active, max_active, busy
        active += 1
        max_active = max(active, max_active)
        calls[unit] += 1
        offline = unit == 2 and 7200 <= now < 7800
        latency = 1.0 if offline else 0.025 + count * 0.001
        now += latency
        busy += latency
        active -= 1
        if offline:
            raise TimeoutError("Simulated 10-minute device outage")
        return list(range(start, start + count))

    async def write(*args):
        raise AssertionError("Simulation must not generate write operations")

    scheduler = Scheduler(
        read,
        write,
        {"polling_profile": "auto", "block_size": 20, "block_pause": 0.05},
        clock=lambda: now,
        utc=lambda: str(now),
        start_worker=False,
    )
    for unit in (1, 2):
        for address in addresses:
            scheduler.register(
                f"unit:{unit}", unit, address, 30 if address < 256 else 600
            )
        for address in (0x40, 0x58, 0x5E):
            scheduler.register("control", unit, address, 8, max_age=30)
    while now < 86400:
        await scheduler.run_once()
        for address in (0x40, 0x58, 0x5E):
            sample = scheduler.cache.get((1, address))
            if sample and sample.received is not None:
                healthy_max_age = max(healthy_max_age, now - sample.received)
        due = [
            max(d.due, d.blocked_until, scheduler.backoff.get(u, 0), scheduler._next_io)
            for (u, _), d in scheduler.demands.items()
        ]
        now = max(now + 0.001, min(due))
        if now >= progress:
            print(f"Simulated {progress/3600:.0f} hours", flush=True)
            progress += 21600
    assert max_active == 1
    assert healthy_max_age < 30, healthy_max_age
    assert scheduler.get(2, 0x58) is not None, "Failed unit did not recover"
    assert len(scheduler.cache) == len(addresses) * 2
    assert not scheduler.jobs
    report = {
        "type": "deterministic simulation, not a field measurement",
        "simulated_hours": 24,
        "units": 2,
        "registered_registers": len(scheduler.demands),
        "requests_by_unit": calls,
        "failed_unit_outage_minutes": 10,
        "healthy_unit_control_max_age_seconds": round(healthy_max_age, 3),
        "transport_time_fraction": round(busy / now, 4),
        "max_simultaneous_transactions": max_active,
        "write_operations": 0,
        "all_registers_received": True,
        "failed_unit_recovered": True,
        "errors_by_unit": {u: s["errors"] for u, s in scheduler.stats.items()},
    }
    await scheduler.stop()
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts/nextgen-simulation.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(simulate())

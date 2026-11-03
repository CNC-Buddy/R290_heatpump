"""Collect bounded, read-only realtime snapshots for register comparison.

Reuses the validated FC03-only transport. Reads 0x0040..0x00FF on units 1/2;
does not access parameter registers or send any device-control commands.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from probe_unknown_registers import read_registers

ROOT = Path(__file__).resolve().parents[1]


def collect(host, port, cycles=8, interval=30):
    if not (1 <= cycles <= 20 and 15 <= interval <= 60):
        raise ValueError("Expected 1..20 cycles and 15..60 seconds between cycles")
    started = datetime.now(timezone.utc)
    path = ROOT / "artifacts" / ("register-investigation-" + started.strftime("%Y%m%dT%H%M%SZ") + ".json")
    if path.exists():
        raise FileExistsError(path)
    result = dict(started_at=started.isoformat(),
                  method="FC03 only; existing proxy; units 1/2; 0x0040..0x00FF; blocks <=32; sequential reads, not simultaneous",
                  interval_seconds=interval, planned_cycles=cycles, samples=[], errors=[])
    failures = 0
    try:
        for cycle in range(cycles):
            cycle_start = time.monotonic()
            for slave in (1, 2):
                for address in range(0x40, 0x100, 32):
                    requested = datetime.now(timezone.utc).isoformat()
                    try:
                        values = read_registers(host, port, slave, address, 32)
                        received = datetime.now(timezone.utc).isoformat()
                        result["samples"].extend(dict(cycle=cycle, at=received, requested_at=requested,
                            slave=slave, address=address+i, raw=value,
                            signed=value if value < 32768 else value-65536)
                            for i, value in enumerate(values))
                        failures = 0
                    except (OSError, ValueError) as exc:
                        result["errors"].append(dict(cycle=cycle, at=requested, slave=slave,
                            address=address, count=32, error=str(exc)))
                        failures += 1
                    if failures >= 3:
                        break
                    time.sleep(.5)
                if failures >= 3:
                    break
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            frequencies = {str(s["slave"]): s["raw"] for s in result["samples"]
                           if s["cycle"] == cycle and s["address"] == 0x40}
            print(json.dumps(dict(cycle=cycle+1, frequencies_hz=frequencies,
                samples=len(result["samples"]), errors=len(result["errors"]), path=str(path))), flush=True)
            if failures >= 3:
                result["stopped_reason"] = "Three consecutive read failures; no further requests"
                break
            if cycle < cycles-1:
                time.sleep(max(0, interval-(time.monotonic()-cycle_start)))
    finally:
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--cycles", default=8, type=int)
    parser.add_argument("--interval", default=30, type=int)
    args = parser.parse_args()
    print(collect(args.host, args.port, args.cycles, args.interval))

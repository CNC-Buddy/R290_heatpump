"""Read-only panel diagnostics; no entity creation or register write path."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import json
from pathlib import Path
import re


@lru_cache(maxsize=1)
def catalog():
    return json.loads((Path(__file__).parent / "frontend/register-catalog.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=8192)
def record_for(unique_id):
    base = re.sub(r"_slave_\d+(?:_v2)?$", "", unique_id)
    match = re.search(r"_([0-9a-f]{4})_slave_", unique_id, re.I)
    for record in catalog()["records"]:
        if match and record["address"] == int(match[1], 16):
            return record
        if any(e["unique_id"] == base for e in record.get("entities", [])):
            return record
    return None


def fault_entity(entity):
    record = record_for(entity.unique_id)
    return bool(record and record["section"] == 1 and "fault" in record["name"].lower())


def fault_history(hass, start, end, ids):
    from homeassistant.components.recorder import history
    states = history.get_significant_states(hass, start, end, ids,
        include_start_time_state=True, significant_changes_only=False,
        minimal_response=False, no_attributes=True)
    events = []
    # Keep text bitfields and unavailable gaps. Initial state is not a new fault.
    for entity_id in ids:
        previous = object()
        for index, state in enumerate(states.get(entity_id, [])):
            if state.state == previous:
                continue
            events.append({"entity_id": entity_id, "at": state.last_updated.isoformat(),
                           "state": state.state, "initial": index == 0})
            previous = state.state
    events.sort(key=lambda e: e["at"], reverse=True)
    return {"start": start.isoformat(), "end": end.isoformat(), "events": events[:2000],
            "total": len(events), "truncated": len(events) > 2000,
            "entity_ids": ids, "recorded_ids": [e for e in ids if states.get(e)]}


async def read_registers(hass, entry_id, addresses, entries, domain):
    """Bounded FC03, serialized by the existing hub, throttled per entry."""
    if entry_id not in entries or entries[entry_id].data.get("device_type") != "heat_pump":
        raise ValueError("Unknown heat pump entry")
    allowed = {r["address"] for r in catalog()["records"] if r["kind"] == "holding"}
    if not addresses or len(addresses) > 20 or any(type(a) is not int for a in addresses):
        raise ValueError("Choose 1–20 consecutive documented addresses")
    if addresses != list(range(addresses[0], addresses[0]+len(addresses))) or not set(addresses) <= allowed:
        raise ValueError("Addresses outside the register catalog or not consecutive")
    runtime = hass.data[domain].get(entry_id, {})
    if not runtime.get("hub"):
        raise ValueError("Heat pump is not loaded")
    now = datetime.now(timezone.utc)
    if runtime.get("_diagnostic_busy") or now < runtime.get("_diagnostic_after", now):
        raise ValueError("Diagnostic read already running or throttled")
    runtime["_diagnostic_busy"] = True
    try:
        hub = runtime["hub"]
        args = (int(entries[entry_id].data.get("slave", 1)), addresses[0], len(addresses))
        values = await hub.async_read_block(*args, owner=entry_id, priority=4) if getattr(hub, "scheduler", None) else await hub.async_read_block(*args)
        if len(values) != len(addresses):
            raise ValueError("Incomplete register response")
        return {"entry_id": entry_id, "received_at": datetime.now(timezone.utc).isoformat(),
                "values": dict(zip(addresses, values))}
    finally:
        runtime["_diagnostic_busy"] = False
        runtime["_diagnostic_after"] = datetime.now(timezone.utc) + timedelta(seconds=2)

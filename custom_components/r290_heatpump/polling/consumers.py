"""Control consumers can tighten freshness independently of display profiles."""


def sync_requirements(hass, domain):
    runtime = hass.data.get(domain, {})
    schedulers = {
        v["hub"].scheduler
        for v in runtime.get("_connections", {}).values()
        if v["hub"].scheduler
    }
    if not schedulers:
        return
    from homeassistant.helpers import entity_registry as er
    from ..panel_diagnostics import record_for
    from ..pump_sources import PUMP_STATUS_REGISTERS

    registry = er.async_get(hass)
    if registry is None:
        return
    active = set()
    for entry_id, value in list(runtime.items()):
        if not isinstance(value, dict):
            continue
        controller = value.get("controller")
        entry = value.get("entry")
        if controller:
            owner = f"consumer:{entry_id}"
            active.add(owner)
            ids = [
                e
                for key in (
                    "frequency_entities",
                    "flow_entities",
                    "supply_entities",
                    "return_entities",
                    "defrost_entities",
                    "demand_entity",
                )
                for e in controller.config.get(key, [])
            ]
            ids.append(controller.config.get("dhw_entity"))
            age = float(controller.config["max_age"])
            interval = max(5, min(controller.config["interval"], age / 3))
        elif entry and entry.data.get("device_type", "").endswith("_curve"):
            owner = f"consumer:{entry_id}"
            active.add(owner)
            config = {**entry.data, **entry.options}
            ids = [config.get("outdoor_sensor")]
            age = 90
            interval = 30
        else:
            continue
        for scheduler in schedulers:
            scheduler.unregister(owner)
        for entity_id in ids:
            meta = registry.async_get(entity_id) if entity_id else None
            if not meta or meta.platform != domain or meta.disabled_by:
                continue
            record = record_for(meta.unique_id)
            # The catalog lists register entities; generated bit sensors are
            # not necessarily listed individually. They need the same freshness.
            source_uid = meta.unique_id.rsplit("_slave_", 1)[0]
            bits = PUMP_STATUS_REGISTERS.get(source_uid.removeprefix("r290_heatpump_"))
            address = bits[0] if bits else record["address"] if record else None
            source = runtime.get(meta.config_entry_id, {})
            scheduler = getattr(source.get("hub"), "scheduler", None)
            if address is not None and scheduler:
                scheduler.register(
                    owner,
                    int(source.get("slave", 1)),
                    address,
                    interval,
                    max_age=age,
                )
    for scheduler in schedulers:
        stale = {
            owner
            for d in scheduler.demands.values()
            for owner in d.owners
            if owner.startswith("consumer:") and owner not in active
        }
        for owner in stale:
            scheduler.unregister(owner)

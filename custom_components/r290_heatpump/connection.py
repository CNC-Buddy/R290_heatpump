"""One connection per bridge, shared by its independently configured entries."""
from __future__ import annotations

import asyncio

from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .hub import R290HeatPumpModbusHub
from .polling.profiles import DEFAULTS as POLLING_DEFAULTS, settings as polling_settings

BRIDGE_ENTRY_ID = "bridge_entry_id"
CONNECTION_DEFAULTS = {
    "port": 502,
    "connection_type": "rtuovertcp",
    "connect_timeout": 8.0,
    "connect_retries": 2,
    "request_timeout": 5.0,
    "block_size": 49,
    "block_pause": 0.05,
}
CONNECTION_KEYS = {"host", *CONNECTION_DEFAULTS, *POLLING_DEFAULTS}


def connection_settings(data):
    """Read all connection settings from one authoritative source."""
    settings = {key: data.get(key, default) for key, default in CONNECTION_DEFAULTS.items()}
    settings["host"] = data["host"]
    for key in ("port", "connect_retries", "block_size"):
        settings[key] = int(settings[key])
    for key in ("connect_timeout", "request_timeout", "block_pause"):
        settings[key] = float(settings[key])
    return {**settings, **polling_settings(data)}


def _endpoint(data):
    return (data.get("host"), int(data.get("port", 502)), data.get("connection_type", "rtuovertcp"))


class DuplicateBridgeError(ValueError):
    """A second bridge would run an independent scheduler on the same socket."""


def check_bridge_endpoint(hass, settings, exclude_entry_id=None):
    endpoint = (str(settings.get('host', '')).strip().lower().rstrip('.'), int(settings.get('port', 502)))
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == exclude_entry_id or entry.data.get('device_type') != 'modbus_bridge':
            continue
        other = (str(entry.data.get('host', '')).strip().lower().rstrip('.'), int(entry.data.get('port', 502)))
        if endpoint == other:
            raise DuplicateBridgeError('A bridge already owns this host and port; add slaves to that bridge')


def resolve_bridge(hass, entry):
    """Bind legacy entries to the bridge, including stale pre-proxy addresses."""
    if entry.data.get("device_type") in ("cop_calculator", "auxiliary_pump"):
        return None
    if entry.data.get("device_type") == "modbus_bridge":
        return entry
    bridges = [e for e in hass.config_entries.async_entries(DOMAIN)
               if e.data.get("device_type") == "modbus_bridge"]
    bridge_id = entry.data.get(BRIDGE_ENTRY_ID)
    if bridge_id:
        bridge = next((e for e in bridges if e.entry_id == bridge_id), None)
        if bridge is None:
            raise ConfigEntryNotReady("The configured Modbus bridge no longer exists")
        return bridge
    matches = [e for e in bridges if _endpoint(e.data) == _endpoint(entry.data)]
    if len(matches) == 1:
        return matches[0]
    # Older flows always copied the sole bridge's address into each child.
    # That copy may already be stale after changing the bridge to a proxy.
    if len(bridges) == 1:
        return bridges[0]
    return None


def entity_settings(entry):
    """Only entity-specific changes require a platform reload."""
    return (
        {k: v for k, v in entry.data.items() if k not in CONNECTION_KEYS and k != BRIDGE_ENTRY_ID},
        dict(entry.options),
    )


def _lock(store):
    return store.setdefault("_connection_lock", asyncio.Lock())


def _hub_kwargs(settings):
    return {
        "host": settings["host"], "port": settings["port"],
        "mode": settings["connection_type"],
        "connect_timeout": settings["connect_timeout"],
        "connect_retries": settings["connect_retries"],
        "request_timeout": settings["request_timeout"],
    }


async def async_acquire_connection(hass, entry):
    """Return a shared hub without opening an additional socket per entry."""
    store = hass.data.setdefault(DOMAIN, {})
    async with _lock(store):
        # A bridge update may be waiting for in-flight I/O. Read its metadata
        # only after that update has committed, never from a stale snapshot.
        bridge = resolve_bridge(hass, entry)
        settings = connection_settings((bridge or entry).data)
        if bridge and settings['polling_profile'] == 'auto':
            try:
                check_bridge_endpoint(hass, settings, bridge.entry_id)
            except DuplicateBridgeError as err:
                raise ConfigEntryNotReady(str(err)) from err
        key = ("bridge", bridge.entry_id) if bridge else ("endpoint", *_endpoint(settings))
        connections = store.setdefault("_connections", {})
        shared = connections.get(key)
        if shared is None:
            shared = {"hub": R290HeatPumpModbusHub(**_hub_kwargs(settings)), "users": set()}
            await shared["hub"].configure_polling(settings)
            connections[key] = shared
        else:
            await shared["hub"].async_reconfigure(**_hub_kwargs(settings))
        shared["users"].add(entry.entry_id)
        if bridge:
            store["hub"] = shared["hub"]
            store["connection"] = settings
            if entry is not bridge:
                updated = {**entry.data, **settings, BRIDGE_ENTRY_ID: bridge.entry_id}
                if updated != dict(entry.data):
                    hass.config_entries.async_update_entry(entry, data=updated)
        return shared["hub"], key, settings, bridge


async def async_release_connection(hass, entry, runtime):
    """Close a shared connection only after its last entry has been unloaded."""
    store = hass.data[DOMAIN]
    async with _lock(store):
        connections = store.get("_connections", {})
        key = runtime.get("connection_key")
        shared = connections.get(key)
        if shared is None:
            return
        shared["users"].discard(entry.entry_id)
        if shared["users"]:
            return
        await shared["hub"].async_close()
        connections.pop(key, None)
        if store.get("hub") is shared["hub"]:
            store.pop("hub", None)


async def async_update_bridge_connection(hass, bridge, values=None, *, validate=False):
    """Switch every reader/writer atomically, then persist the new endpoint."""
    store = hass.data.setdefault(DOMAIN, {})
    reload_entries = []
    async with _lock(store):
        settings = connection_settings(bridge.data if values is None else values)
        if settings['polling_profile'] == 'auto':
            check_bridge_endpoint(hass, settings, bridge.entry_id)
        related = []
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("device_type") in ("cop_calculator", "auxiliary_pump"):
                continue
            try:
                parent = resolve_bridge(hass, entry)
            except ConfigEntryNotReady:
                continue
            if parent and parent.entry_id == bridge.entry_id:
                related.append(entry)

        key = ("bridge", bridge.entry_id)
        shared = store.get("_connections", {}).get(key)
        hub = shared["hub"] if shared else R290HeatPumpModbusHub(**_hub_kwargs(settings))
        try:
            # Reconfigure the existing object: entity write paths keep references
            # to it, so replacing only a dictionary or batch hub is insufficient.
            await hub.async_reconfigure(**_hub_kwargs(settings), validate=validate)
            if shared and polling_settings(settings) != hub.polling_config:
                for related_entry in related:
                    runtime = store.get(related_entry.entry_id)
                    if runtime and runtime.get("connection_key") == key:
                        await runtime["batch"].async_shutdown()
                        reload_entries.append(related_entry.entry_id)
            await hub.configure_polling(settings)
        finally:
            if shared is None:
                await hub.async_close()

        store["connection"] = settings
        for entry in related:
            runtime = store.get(entry.entry_id)
            if runtime and runtime.get("connection_key") == key:
                runtime["batch"].update_batch_params(
                    block_size=settings["block_size"], block_pause=settings["block_pause"]
                )
            updated = {**entry.data, **settings}
            if entry.entry_id != bridge.entry_id:
                updated[BRIDGE_ENTRY_ID] = bridge.entry_id
            if updated != dict(entry.data):
                hass.config_entries.async_update_entry(entry, data=updated)

    # Reload only after releasing the connection lock. The bridge retains the
    # same transport while child entries detach and reattach their consumers.
    for entry_id in reload_entries:
        await hass.config_entries.async_reload(entry_id)

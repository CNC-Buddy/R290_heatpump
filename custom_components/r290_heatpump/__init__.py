# Version: 1.0.2
# Last modified: 2025-11-11 14:11 by CNC-Buddy
"""R290 Heat Pump Integration - Init."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_SLAVE
from homeassistant.helpers import device_registry as dr

from .hub import ModbusBatchManager
from .connection import (
    async_acquire_connection,
    async_release_connection,
    async_update_bridge_connection,
    entity_settings,
)

DOMAIN = "r290_heatpump"
PLATFORMS = ["sensor", "number", "select", "button", "switch"]

_LOGGER = logging.getLogger(__name__)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Apply bridge settings in place; reload only entity-specific changes."""
    if entry.data.get("device_type") == "modbus_bridge":
        await async_update_bridge_connection(hass, entry)
        return
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    if runtime.get("entity_settings") == entity_settings(entry):
        return
    await hass.config_entries.async_reload(entry.entry_id)


def _bridge_device(hass, bridge):
    """Keep the existing primary hub ID and link child devices to it."""
    bridges = [e for e in hass.config_entries.async_entries(DOMAIN)
               if e.data.get("device_type") == "modbus_bridge"]
    identifier = ("r290_heatpump_bridge" if bridges[0].entry_id == bridge.entry_id
                  else f"r290_heatpump_bridge_{bridge.entry_id}")
    registry = dr.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=bridge.entry_id,
        identifiers={(DOMAIN, identifier)},
        name="R290 Heat Pump Modbus Bridge",
        manufacturer="R290 Heat Pump", model="Modbus Bridge",
    )
    return device, identifier


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the integration from YAML (not used, UI only)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up R290 Heat Pump from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    device_type = entry.data.get("device_type", "heat_pump")

    # Early exit: COP calculator does not need Modbus host/port
    if device_type == "cop_calculator":
        hass.data[DOMAIN][entry.entry_id] = {"entry": entry}
        _LOGGER.info("Setting up R290 Heat Pump COP Calculator entry: %s", entry.title)
        _LOGGER.debug("Forwarding entry %s to platforms: %s", entry.entry_id, PLATFORMS)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(_async_update_listener))
        return True

    hub, connection_key, settings, bridge = await async_acquire_connection(hass, entry)
    unit = int(entry.data.get(CONF_SLAVE) or 1)

    _LOGGER.info(
        "Setting up R290 Heat Pump entry: %s (host=%s, port=%s, slave=%s)",
        entry.title,
        settings["host"],
        settings["port"],
        unit,
    )

    batch = ModbusBatchManager(
        hass, hub, unit, block_size=settings["block_size"],
        block_pause=settings["block_pause"], config_entry=entry,
    )

    runtime = hass.data[DOMAIN][entry.entry_id] = {
        "entry": entry,
        "hub": hub,
        "batch": batch,
        "slave": unit,
        "connection_key": connection_key,
        "entity_settings": entity_settings(entry),
    }

    try:
        parent = None
        if bridge:
            parent, identifier = _bridge_device(hass, bridge)
            runtime["bridge_device_identifier"] = identifier
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        if parent and entry.entry_id != bridge.entry_id:
            registry = dr.async_get(hass)
            for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
                if device.id != parent.id and device.via_device_id != parent.id:
                    registry.async_update_device(device.id, via_device_id=parent.id)
    except BaseException:
        await batch.async_shutdown()
        await async_release_connection(hass, entry, runtime)
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False
    runtime = hass.data[DOMAIN].pop(entry.entry_id, None)
    if runtime and "batch" in runtime:
        await runtime["batch"].async_shutdown()
        await async_release_connection(hass, entry, runtime)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reload config entry."""
    if await async_unload_entry(hass, entry):
        await async_setup_entry(hass, entry)

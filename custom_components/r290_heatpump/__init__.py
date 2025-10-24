# Version: 1.0.1
# Last modified: 2025-10-24 17:33 by CNC-Buddy
"""R290 Heat Pump Integration - Init."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SLAVE

from .hub import R290HeatPumpModbusHub, ModbusBatchManager

DOMAIN = "r290_heatpump"
PLATFORMS = ["sensor", "number", "select", "button", "switch"]

_LOGGER = logging.getLogger(__name__)


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
        return True

    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 502)
    unit = int(entry.data.get(CONF_SLAVE) or 1)

    _LOGGER.info(
        "Setting up R290 Heat Pump entry: %s (host=%s, port=%s, slave=%s)",
        entry.title,
        host,
        port,
        unit,
    )

    # Hub-Instanz pro Entry erzeugen (geteilt für alle Plattformen)
    hub = R290HeatPumpModbusHub(host, port, mode=entry.data.get("connection_type", "rtuovertcp"))
    batch = ModbusBatchManager(hass, hub, unit)

    hass.data[DOMAIN][entry.entry_id] = {
        "hub": hub,
        "batch": batch,
        "slave": unit,
    }

    # Domain-level registry so options flows and bridge status can work
    domain_store = hass.data[DOMAIN]
    try:
        managers = domain_store.setdefault("_batch_managers", {})
        managers[int(unit)] = batch
    except Exception:
        pass
    if device_type == "modbus_bridge":
        domain_store["hub"] = hub
        domain_store["connection"] = {
            "host": host,
            "port": port,
            "connection_type": entry.data.get("connection_type", "rtuovertcp"),
            "connect_timeout": entry.data.get("connect_timeout", 8.0),
            "connect_retries": entry.data.get("connect_retries", 2),
            "request_timeout": entry.data.get("request_timeout", 5.0),
            "block_size": entry.data.get("block_size", 49),
            "block_pause": entry.data.get("block_pause", 0.05),
        }

    # Plattform-Setup: ab HA 2025.1 muss awaited werden
    _LOGGER.debug("Forwarding entry %s to platforms: %s", entry.entry_id, PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hub_data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if hub_data:
        hub = hub_data.get("hub")
        try:
            await hub.async_close()
        except Exception as err:
            _LOGGER.warning("Error closing Modbus hub for %s: %s", entry.title, err)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

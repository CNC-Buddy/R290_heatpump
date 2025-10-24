# Version: 1.0.1
# Last modified: 2025-10-24 17:33 by CNC-Buddy
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the R290 Heat Pump button entities."""
    device_type = entry.data.get("device_type", "heat_pump")
    entities = []

    if device_type == "modbus_bridge":
        store = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if not store or "hub" not in store:
            _LOGGER.error("Internal Modbus hub not initialised")
            return
        hub = store["hub"]

        device_info = DeviceInfo(
            identifiers={(DOMAIN, "r290_heatpump_bridge")},
            name="R290 Heat Pump Modbus Bridge",
            manufacturer="R290 Heat Pump",
            model="Modbus Bridge",
            sw_version="1.0.0",
        )

        entities.append(R290HeatPumpModbusReconnectButton(hass, hub, device_info))

    async_add_entities(entities, update_before_add=False)

    for entity in entities:
        hass.data.setdefault(DOMAIN, {})[entity.entity_id] = entity


class R290HeatPumpModbusReconnectButton(ButtonEntity):
    def __init__(self, hass: HomeAssistant, hub, device_info: DeviceInfo) -> None:
        super().__init__()
        self._hass = hass
        self._hub = hub
        self._attr_name = "Reconnect Modbus"
        self._attr_unique_id = "r290_heatpump_bridge_reconnect"
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        try:
            try:
                await self._hub.async_close()
            except Exception:
                pass
            await self._hub.async_connect()
            # Try to refresh the bridge status sensor
            ent = self._hass.data.get(DOMAIN, {}).get("sensor.r290_heatpump_bridge_status")
            if ent is not None:
                try:
                    await ent.async_update()
                    ent.async_write_ha_state()
                except Exception:
                    pass
        except Exception as err:
            _LOGGER.error("Reconnect failed: %s", err)






# Version: 1.0.1
# Last modified: 2025-10-24 17:33 by CNC-Buddy
import logging
from datetime import datetime, timezone
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.exceptions import HomeAssistantError

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
            identifiers={(DOMAIN, store["bridge_device_identifier"])},
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
        self._reconnecting = False
        self._last_reconnect = None
        self._last_reconnect_error = None
        self._verified_slaves = []

    @property
    def extra_state_attributes(self):
        return {
            "reconnecting": self._reconnecting,
            "last_reconnect": self._last_reconnect,
            "last_reconnect_error": self._last_reconnect_error,
            "verified_slaves": self._verified_slaves,
        }

    async def _refresh_status(self):
        ent = self._hass.data.get(DOMAIN, {}).get("sensor.r290_heatpump_bridge_status")
        if ent is not None and getattr(ent, "_hub", None) is self._hub:
            try:
                await ent.async_update()
                ent.async_write_ha_state()
            except Exception:
                _LOGGER.debug("Could not publish reconnect status", exc_info=True)

    async def async_press(self) -> None:
        # Repeated clicks while waiting for existing I/O must not queue more
        # reconnects. In-flight writes keep their shared I/O lock until done.
        if self._reconnecting:
            return
        self._reconnecting = True
        self._last_reconnect = datetime.now(timezone.utc).isoformat()
        self._last_reconnect_error = None
        self._verified_slaves = []
        self.async_write_ha_state()
        try:
            await self._hub.async_reconnect()
            await self._refresh_status()
            batches = []
            probes = {}
            for runtime in list(self._hass.data.get(DOMAIN, {}).values()):
                if not isinstance(runtime, dict) or runtime.get("hub") is not self._hub:
                    continue
                batch = runtime.get("batch")
                if batch is None or batch in batches:
                    continue
                probe = batch.reconnect_probe()
                if probe is not None:
                    batches.append(batch)
                    probes.setdefault(probe[0], probe[1])
            failures = []
            for unit, address in probes.items():
                try:
                    await self._hub.async_read_block(unit, address, 1)
                    self._verified_slaves.append(unit)
                except Exception as err:
                    failures.append(f"Slave {unit}, register 0x{address:04X}: {err}")
            for batch in batches:
                probe = batch.reconnect_probe()
                if probe is not None and probe[0] in self._verified_slaves:
                    batch.request_refresh_soon()
            if failures:
                raise RuntimeError("; ".join(failures))
        except Exception as err:
            self._last_reconnect_error = str(err)
            _LOGGER.error("Reconnect failed: %s", err)
            raise HomeAssistantError(f"Modbus reconnect failed: {err}") from err
        finally:
            self._reconnecting = False
            await self._refresh_status()
            self.async_write_ha_state()






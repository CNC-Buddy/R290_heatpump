# Version: 1.0.1
# Last modified: 2025-10-24 17:33 by CNC-Buddy
import asyncio
import logging
from typing import Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SLAVE, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import slugify

from .const import DOMAIN
from .pv_optimization import PV_CURVE_CONFIG
from .user_parameters import USER_PARAMETERS_SWITCHES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    device_type = entry.data.get("device_type")

    if device_type == "heat_pump":
        slave_id = entry.data.get(CONF_SLAVE)
        if slave_id is None:
            _LOGGER.error("Config entry %s missing slave id for switch setup", entry.entry_id)
            return

        store = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if not store or "hub" not in store:
            _LOGGER.error("Internal Modbus hub not initialised (switch)")
            return

        hub = store["hub"]
        batch = store.get("batch")
        fast_interval = entry.options.get(
            CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, 60)
        )
        long_interval = entry.options.get("long_scan_interval", entry.data.get("long_scan_interval", 600))

        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"r290_heatpump_{slave_id}_user_parameters")},
            name=f"R290 Heat Pump (Slave {slave_id}) - User Parameters",
            manufacturer="R290 Heat Pump",
            model="Modbus Device",
            sw_version="1.0.0",
        )

        entities: list[SwitchEntity] = []
        if int(slave_id) == 1:
            for switch_info in USER_PARAMETERS_SWITCHES:
                info = dict(switch_info)
                info["unique_id"] = f"{info['unique_id']}_slave_{slave_id}"
                entity = R290HeatPumpWaterCirculationSwitch(
                    hass=hass,
                    entry=entry,
                    switch_info=info,
                    slave_id=int(slave_id),
                    scan_interval=int(fast_interval),
                    off_interval=int(long_interval),
                    hub=hub,
                    batch=batch,
                    device_info=device_info,
                )
                entities.append(entity)
        if entities:
            async_add_entities(entities, update_before_add=True)
            for ent in entities:
                hass.data.setdefault(DOMAIN, {})[ent.entity_id] = ent
        return

    entities = []
    if device_type in ("heating_curve", "floor_heating_curve", "hot_water_curve", "cooling_curve"):
        dev_id, dev_name = {
            "heating_curve": ("r290_heatpump_heating_curve", "R290 Heat Pump Heating Curve"),
            "floor_heating_curve": ("r290_heatpump_floor_heating_curve", "R290 Heat Pump Floor Heating Curve"),
            "hot_water_curve": ("r290_heatpump_hotwater_curve", "R290 Heat Pump Hot Water Curve"),
            "cooling_curve": ("r290_heatpump_cooling_curve", "R290 Heat Pump Cooling Curve"),
        }.get(device_type, ("r290_heatpump_heating_curve", "R290 Heat Pump Heating Curve"))
        device_info = DeviceInfo(
            identifiers={(DOMAIN, dev_id)},
            name=dev_name,
            manufacturer="R290 Heat Pump",
            model="Heating Curve",
            sw_version="1.0.0",
        )
        curve_prefix = {
            "heating_curve": "heating",
            "floor_heating_curve": "floor_heating",
            "hot_water_curve": "hotwater",
            "cooling_curve": "cooling",
        }.get(device_type, "heating")
        entities.append(HeatcurveActiveSwitch(hass, entry, device_info))
        entities.append(HeatcurveExternalOffsetSwitch(hass, entry, device_info, curve_prefix))
        slave_id = int(entry.data.get(CONF_SLAVE, 1))
        if slave_id == 1 and device_type in PV_CURVE_CONFIG:
            curve_cfg = PV_CURVE_CONFIG[device_type]
            prefix = curve_cfg.get("prefix", "heating")
            friendly_curve = {
                "heating": "Heating Curve",
                "floor_heating": "Floor Heating Curve",
                "hotwater": "Hot Water Curve",
                "cooling": "Cooling Curve",
            }.get(prefix, "Heating Curve")
            pv_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"r290_heatpump_{slave_id}_{prefix}_pv_optimization")},
                name=f"R290 Heat Pump PV Optimization ({friendly_curve})",
                manufacturer="R290 Heat Pump",
                model="PV Optimization",
                sw_version="1.0.0",
            )
            entities.append(
                HeatcurvePvOptimizationSwitch(
                    hass, entry, pv_device_info, device_type, prefix
                )
            )

    if entities:
        async_add_entities(entities, update_before_add=False)
        for ent in entities:
            hass.data.setdefault(DOMAIN, {})[ent.entity_id] = ent


class R290HeatPumpWaterCirculationSwitch(SwitchEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        switch_info: dict,
        slave_id: int,
        scan_interval: int,
        off_interval: int,
        hub,
        batch,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__()
        self._hass = hass
        self._entry = entry
        self._hub = hub
        self._batch = batch
        self._slave = slave_id
        self._address = int(switch_info["address"])
        self._duration_address: Optional[int] = switch_info.get("duration_address")
        if self._duration_address is not None:
            self._duration_address = int(self._duration_address)
        self._duration_scale = float(switch_info.get("duration_scale", 1))
        self._default_duration_minutes = float(switch_info.get("default_duration_minutes", 5))
        self._on_value = int(switch_info.get("on_value", 1))
        self._off_value = int(switch_info.get("off_value", 0))
        self._scan_interval = int(scan_interval)
        self._off_enforce_interval = max(1, int(off_interval))
        self._device_info = device_info
        self._name = switch_info.get("name", "Water Zirculation")
        self._unique_id = switch_info.get("unique_id")
        self._auto_off_task: Optional[asyncio.Task] = None
        self._off_enforce_task: Optional[asyncio.Task] = None

        self._attr_name = self._name
        self._attr_unique_id = self._unique_id
        self._attr_device_info = device_info
        self._attr_should_poll = True
        self._attr_is_on = False

        try:
            base = slugify(self._name)
            self.entity_id = f"switch.r290_heatpump_{base}_slave_{self._slave}"
        except Exception:
            pass

    async def async_added_to_hass(self) -> None:
        try:
            if self._batch:
                self._batch.register(self._address, self._scan_interval)
                if self._duration_address is not None:
                    self._batch.register(self._duration_address, self._scan_interval)
        except Exception as err:
            _LOGGER.debug("Failed to register batch addresses for %s: %s", self._name, err)
        self._start_off_enforcer()

    async def async_will_remove_from_hass(self) -> None:
        self._cancel_auto_off()
        self._stop_off_enforcer()

    @property
    def is_on(self) -> bool:
        return bool(self._attr_is_on)

    async def async_turn_on(self, **kwargs) -> None:
        try:
            self._cancel_auto_off()
            self._stop_off_enforcer()
            await self._write_register(self._on_value)
            self._attr_is_on = True
            await self._ensure_auto_off_task()
        except Exception as err:
            _LOGGER.error("Failed to start water circulation: %s", err)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        try:
            self._cancel_auto_off()
            await self._write_register(self._off_value)
        except Exception as err:
            _LOGGER.error("Failed to stop water circulation: %s", err)
        finally:
            self._attr_is_on = False
            self.async_write_ha_state()
            self._start_off_enforcer()

    async def async_update(self) -> None:
        try:
            value = None
            if self._batch:
                value = self._batch.get_cached(self._address, self._scan_interval)
            if value is not None:
                state = int(value)
                is_on = state == self._on_value
                if is_on != self._attr_is_on:
                    self._attr_is_on = is_on
                if is_on:
                    self._stop_off_enforcer()
                    await self._ensure_auto_off_task()
                else:
                    self._cancel_auto_off()
                    self._start_off_enforcer()
        except Exception as err:
            _LOGGER.debug("Switch update failed for %s: %s", self._name, err)

    async def _ensure_auto_off_task(self) -> None:
        if self._auto_off_task and not self._auto_off_task.done():
            return
        minutes = await self._get_duration_minutes()
        if minutes <= 0:
            return

        async def _auto_off():
            try:
                await asyncio.sleep(minutes * 60)
                current = await self._read_current_state()
                if current is None or current == self._on_value:
                    await self._write_register(self._off_value)
                    self._attr_is_on = False
                    self.async_write_ha_state()
                    self._start_off_enforcer()
            except asyncio.CancelledError:
                raise
            except Exception as err:
                _LOGGER.warning("Auto-off for %s failed: %s", self._name, err)
            finally:
                self._auto_off_task = None

        self._auto_off_task = self._hass.loop.create_task(_auto_off())

    def _start_off_enforcer(self) -> None:
        if self._off_enforce_task and not self._off_enforce_task.done():
            return

        async def _enforce_loop():
            try:
                while True:
                    await asyncio.sleep(self._off_enforce_interval)
                    if self._attr_is_on or (self._auto_off_task and not self._auto_off_task.done()):
                        continue
                    current = None
                    if self._batch:
                        cached = self._batch.get_cached(self._address, self._scan_interval)
                        if cached is not None:
                            current = int(cached)
                    if current is None:
                        current = await self._read_current_state()
                    if current is None or current != self._off_value:
                        await self._write_register(self._off_value)
                        if self._attr_is_on:
                            self._attr_is_on = False
                            self.async_write_ha_state()
            except asyncio.CancelledError:
                raise
            except Exception as err:
                _LOGGER.debug("Off-state enforcement for %s failed: %s", self._name, err)
            finally:
                self._off_enforce_task = None

        self._off_enforce_task = self._hass.loop.create_task(_enforce_loop())

    def _stop_off_enforcer(self) -> None:
        if self._off_enforce_task:
            self._off_enforce_task.cancel()
            self._off_enforce_task = None

    def _cancel_auto_off(self) -> None:
        if self._auto_off_task:
            self._auto_off_task.cancel()
            self._auto_off_task = None

    async def _get_duration_minutes(self) -> float:
        if self._duration_address is None:
            return self._default_duration_minutes
        duration: Optional[int] = None
        if self._batch:
            cached = self._batch.get_cached(self._duration_address, self._scan_interval)
            if cached is not None:
                duration = int(cached)
        if duration is None:
            try:
                res = await self._hub.async_pb_call(self._slave, self._duration_address, 1, "holding")
                if not res.isError() and res.registers:
                    duration = int(res.registers[0])
            except Exception as err:
                _LOGGER.debug("Reading water circulation time failed: %s", err)
        if duration is None:
            duration = int(self._default_duration_minutes)
        return max(0, float(duration) * self._duration_scale)

    async def _write_register(self, value: int) -> None:
        await self._hub.async_pb_write_register(self._slave, self._address, int(value))
        try:
            if self._batch and hasattr(self._batch, "request_refresh"):
                await self._batch.request_refresh(self._scan_interval)
        except Exception:
            pass

    async def _read_current_state(self) -> Optional[int]:
        try:
            res = await self._hub.async_pb_call(self._slave, self._address, 1, "holding")
            if not res.isError() and res.registers:
                return int(res.registers[0])
        except Exception as err:
            _LOGGER.debug("Failed to read current switch state: %s", err)
        return None


class HeatcurveActiveSwitch(SwitchEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, device_info: DeviceInfo) -> None:
        super().__init__()
        self._hass = hass
        self._entry = entry
        type_name = {
            "heating_curve": "Heating Curve Active",
            "floor_heating_curve": "Floor Heating Curve Active",
            "hot_water_curve": "Hot Water Curve Active",
            "cooling_curve": "Cooling Curve Active",
        }.get(entry.data.get("device_type"), "Heating Curve Active")
        self._attr_name = type_name
        curve_prefix = {
            "heating_curve": "heating",
            "floor_heating_curve": "floor_heating",
            "hot_water_curve": "hotwater",
            "cooling_curve": "cooling",
        }.get(entry.data.get("device_type"), "heating")
        self._attr_unique_id = f"r290_heatpump_{curve_prefix}_curve_active_{entry.entry_id}"
        self._attr_device_info = device_info
        self._attr_should_poll = False
        try:
            self.entity_id = f"switch.r290_heatpump_{curve_prefix}_curve_active"
        except Exception:
            pass

    @property
    def is_on(self) -> bool:
        return bool(self._entry.options.get("heatcurve_active", False))

    async def async_turn_on(self, **kwargs) -> None:
        opts = dict(self._entry.options)
        opts["heatcurve_active"] = True
        self._hass.config_entries.async_update_entry(self._entry, options=opts)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        opts = dict(self._entry.options)
        opts["heatcurve_active"] = False
        self._hass.config_entries.async_update_entry(self._entry, options=opts)
        self.async_write_ha_state()





class HeatcurveExternalOffsetSwitch(SwitchEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, device_info: DeviceInfo, prefix: str) -> None:
        super().__init__()
        self._hass = hass
        self._entry = entry
        self._curve_prefix = prefix
        curve_names = {
            "heating": "Heating Curve External Offset",
            "floor_heating": "Floor Heating External Offset",
            "hotwater": "Hot Water External Offset",
            "cooling": "Cooling External Offset",
        }
        self._attr_name = curve_names.get(prefix, "Heating Curve External Offset")
        self._attr_unique_id = f"r290_heatpump_{prefix}_external_heating_offset_{entry.entry_id}"
        self._attr_device_info = device_info
        self._attr_should_poll = False
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_is_on = bool(entry.options.get("external_offset_enabled", False))
        try:
            self.entity_id = f"switch.r290_heatpump_{prefix}_external_heating_offset"
        except Exception:
            pass

    @property
    def is_on(self) -> bool:
        return self._attr_is_on

    async def async_added_to_hass(self) -> None:
        self._attr_is_on = bool(self._entry.options.get("external_offset_enabled", False))
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        opts = dict(self._entry.options)
        opts["external_offset_enabled"] = True
        self._hass.config_entries.async_update_entry(self._entry, options=opts)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        opts = dict(self._entry.options)
        opts["external_offset_enabled"] = False
        self._hass.config_entries.async_update_entry(self._entry, options=opts)
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_update(self) -> None:
        self._attr_is_on = bool(self._entry.options.get("external_offset_enabled", False))



class HeatcurvePvOptimizationSwitch(SwitchEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_info: DeviceInfo,
        device_type: str,
        prefix: str,
    ) -> None:
        super().__init__()
        self._hass = hass
        self._entry = entry
        self._device_type = device_type
        self._curve_prefix = prefix
        curve_names = {
            "heating_curve": "Heating Curve PV Optimization",
            "floor_heating_curve": "Floor Heating Curve PV Optimization",
            "hot_water_curve": "Hot Water Curve PV Optimization",
            "cooling_curve": "Cooling Curve PV Optimization",
        }
        name = curve_names.get(device_type, "Heating Curve PV Optimization")
        self._attr_name = name
        self._attr_unique_id = f"r290_heatpump_{self._curve_prefix}_pv_optimization_{entry.entry_id}"
        self._attr_device_info = device_info
        self._attr_should_poll = False
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_is_on = bool(entry.options.get("pv_enabled", False))
        try:
            self.entity_id = f"switch.r290_heatpump_{self._curve_prefix}_pv_optimization"
        except Exception:
            pass

    async def async_turn_on(self, **kwargs) -> None:
        opts = dict(self._entry.options)
        opts["pv_enabled"] = True
        self._hass.config_entries.async_update_entry(self._entry, options=opts)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        opts = dict(self._entry.options)
        opts["pv_enabled"] = False
        self._hass.config_entries.async_update_entry(self._entry, options=opts)
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_update(self) -> None:
        self._attr_is_on = bool(self._entry.options.get("pv_enabled", False))



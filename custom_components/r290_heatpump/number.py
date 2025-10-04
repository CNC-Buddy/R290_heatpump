from typing import Optional
import logging
from homeassistant.components.number import NumberEntity, NumberDeviceClass, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SLAVE, UnitOfTemperature, UnitOfTime, PERCENTAGE
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import slugify

from .unit_system_parameters import UNIT_SYSTEM_WRITABLE_PARAMETERS
from .user_parameters import USER_PARAMETERS_WRITABLE_NUMBERS
from .pv_optimization import PV_CURVE_CONFIG
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the R290 Heat Pump number entities."""
    device_type = entry.data.get("device_type", "heat_pump")
    entities = []

    if device_type == "heat_pump":
        slave_id = entry.data[CONF_SLAVE]
        long_interval = entry.options.get("long_scan_interval", entry.data.get("long_scan_interval", 600))
        store = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if not store or "hub" not in store:
            _LOGGER.error("Internal Modbus hub not initialised")
            return
        hub = store["hub"]
        batch = store.get("batch")

        unit_system_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"r290_heatpump_{slave_id}_unit_system_parameters")},
            name=f"R290 Heat Pump (Slave {slave_id}) - Unit System Parameters",
            manufacturer="R290 Heat Pump",
            model="Modbus Device",
            sw_version="1.0.0",
        )

        user_params_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"r290_heatpump_{slave_id}_user_parameters")},
            name=f"R290 Heat Pump (Slave {slave_id}) - User Parameters",
            manufacturer="R290 Heat Pump",
            model="Modbus Device",
            sw_version="1.0.0",
        )

        for param_info in UNIT_SYSTEM_WRITABLE_PARAMETERS:
            param_data = param_info.copy()
            name_slug = slugify(param_info["name"])  # e.g. p259_mixing_valve_full_cycle_time
            addr = param_info.get("address")
            try:
                addr_hex = f"{int(addr):04X}"
            except Exception:
                addr_hex = str(addr)
            param_data["unique_id"] = f"r290_heatpump_{name_slug}_{addr_hex}_slave_{slave_id}_v2"
            number_entity = R290HeatPumpModbusNumber(
                hass, entry, param_data, slave_id, long_interval, hub, unit_system_device_info, batch
            )
            entities.append(number_entity)

        # Add user-parameter writable numbers (e.g., temperature setpoints) only for slave 1
        if int(slave_id) == 1:
            for param_info in USER_PARAMETERS_WRITABLE_NUMBERS:
                param_data = param_info.copy()
                name_slug = slugify(param_info["name"])  # e.g. indoor_temperature_set_point
                addr = param_info.get("address")
                try:
                    addr_hex = f"{int(addr):04X}"
                except Exception:
                    addr_hex = str(addr)
                param_data["unique_id"] = f"r290_heatpump_{name_slug}_{addr_hex}_slave_{slave_id}_v2"
                number_entity = R290HeatPumpModbusNumber(
                    hass, entry, param_data, slave_id, long_interval, hub, user_params_device_info, batch
                )
                entities.append(number_entity)

    elif device_type in ("heating_curve", "floor_heating_curve", "hot_water_curve", "cooling_curve"):
        # Expose parameter numbers that persist into entry.options
        name_map = {
            "heating_curve": ("r290_heatpump_heating_curve", "R290 Heat Pump Heating Curve"),
            "floor_heating_curve": ("r290_heatpump_floor_heating_curve", "R290 Heat Pump Floor Heating Curve"),
            "hot_water_curve": ("r290_heatpump_hotwater_curve", "R290 Heat Pump Hot Water Curve"),
            "cooling_curve": ("r290_heatpump_cooling_curve", "R290 Heat Pump Cooling Curve"),
        }
        dev_id, dev_name = name_map.get(device_type, ("r290_heatpump_heating_curve", "R290 Heat Pump Heating Curve"))
        device_info = DeviceInfo(
            identifiers={(DOMAIN, dev_id)},
            name=dev_name,
            manufacturer="R290 Heat Pump",
            model="Heating Curve",
            sw_version="1.0.0",
        )
        defs = {
            "t_out_min": (-30, 10, 1, -15.0),
            "t_out_max": (0, 35, 1, 20.0),
            "t_flow_min": (20, 60, 1, 25.0),
            "t_flow_max": (25, 70, 1, 50.0),
            "inertia_hours": (0.0, 24.0, 0.1, 0.0),
            "deadband_c": (0.0, 2.0, 0.1, 0.5),
        }
        for key, (vmin, vmax, step, default) in defs.items():
            init = entry.options.get(key, default)
            entities.append(HeatCurveParamNumber(hass, entry, device_info, key, init, vmin, vmax, step))

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
            grid_default = entry.options.get("pv_grid_threshold_kw", entry.data.get("pv_grid_threshold_kw", curve_cfg.get("grid_threshold_default", 2.0)))
            battery_default = entry.options.get("pv_battery_threshold_pct", entry.data.get("pv_battery_threshold_pct", curve_cfg.get("battery_threshold_default", 80.0)))
            cooldown_default = entry.options.get("pv_cooldown_minutes", entry.data.get("pv_cooldown_minutes", curve_cfg.get("cooldown_default", 15)))
            entities.append(
                HeatcurvePvNumber(
                    entry,
                    pv_device_info,
                    key="pv_grid_threshold_kw",
                    prefix=prefix,
                    name="PV Grid Threshold",
                    unit="kW",
                    device_class=NumberDeviceClass.POWER,
                    min_value=0.0,
                    max_value=50.0,
                    step=0.1,
                    default_value=float(grid_default),
                )
            )
            entities.append(
                HeatcurvePvNumber(
                    entry,
                    pv_device_info,
                    key="pv_battery_threshold_pct",
                    prefix=prefix,
                    name="PV Battery Threshold",
                    unit=PERCENTAGE,
                    device_class=NumberDeviceClass.BATTERY,
                    min_value=0.0,
                    max_value=100.0,
                    step=1.0,
                    default_value=float(battery_default),
                )
            )
            entities.append(
                HeatcurvePvNumber(
                    entry,
                    pv_device_info,
                    key="pv_cooldown_minutes",
                    prefix=prefix,
                    name="PV Cooldown",
                    unit=UnitOfTime.MINUTES,
                    device_class=None,
                    min_value=0.0,
                    max_value=240.0,
                    step=1.0,
                    default_value=float(cooldown_default),
                )
            )

    _LOGGER.info("Registering %s number entities for %s", len(entities), device_type)
    async_add_entities(entities, update_before_add=True)

    for entity in entities:
        hass.data.setdefault(DOMAIN, {})[entity.entity_id] = entity


class R290HeatPumpModbusNumber(NumberEntity):
    """Representation of an R290 Heat Pump number (writable parameter)."""

    def __init__(self, hass, entry, param_info, slave_id, scan_interval, hub, device_info, batch_manager):
        super().__init__()
        self._hass = hass
        self._entry = entry
        self._address = param_info["address"]
        self._scale = param_info["scale"]
        self._unit = param_info["unit"]
        self._name = param_info["name"]
        self._unique_id = param_info["unique_id"]
        self._device_class = param_info["device_class"]
        self._min_value = param_info["min_value"]
        self._max_value = param_info["max_value"]
        self._step = param_info["step"]
        self._mode = param_info["mode"]
        self._precision = param_info["precision"]
        self._data_type = param_info.get("data_type", "int16")
        self._input_type = param_info.get("input_type", "holding")
        self._slave_id = slave_id
        self._hub = hub
        self._batch = batch_manager
        self._scan_interval = scan_interval
        self._value = None
        self._registered = False

        self._attr_name = self._name
        self._attr_native_value = self._value
        self._attr_native_unit_of_measurement = self._unit
        self._attr_device_class = self._device_class
        self._attr_unique_id = self._unique_id
        self._attr_device_info = device_info
        self._attr_should_poll = True
        self._attr_native_min_value = self._min_value
        self._attr_native_max_value = self._max_value
        self._attr_native_step = self._step
        self._attr_mode = self._mode

        try:
            base = slugify(self._name)
            self.entity_id = f"number.r290_heatpump_{base}_slave_{self._slave_id}"
        except Exception:
            pass

        _LOGGER.debug("Number %s initialisiert mit unique_id=%s", self._name, self._attr_unique_id)

    async def async_added_to_hass(self):
        _LOGGER.info("Number %s added to Home Assistant", self._name)
        try:
            if self._batch:
                interval = int(self._scan_interval)
                try:
                    self._batch.register(self._address, interval)
                    self._registered = True
                except Exception:
                    pass
                if hasattr(self._batch, "request_refresh"):
                    try:
                        await self._batch.request_refresh(interval)
                    except Exception:
                        pass
        except Exception as e:
            _LOGGER.debug("Initial number register failed for %s: %s", self._name, e)

    async def async_set_native_value(self, value):
        try:
            raw = value
            try:
                raw = float(value)
            except Exception:
                pass
            write_value = int(round(raw / self._scale))
            if str(self._data_type).lower() == "int16" and write_value < 0:
                write_value &= 0xFFFF
            await self._hub.async_pb_write_register(self._slave_id, self._address, write_value)
            self._attr_native_value = float(raw)
            _LOGGER.debug("Wert %s (raw=%s) in Register %s geschrieben", value, write_value, self._address)
            try:
                if self._batch and hasattr(self._batch, "request_refresh"):
                    await self._batch.request_refresh(int(self._scan_interval))
            except Exception:
                pass
        except Exception as e:
            _LOGGER.error("Fehler beim Schreiben von Modbus-Daten an %s (addr=%s, raw=%s): %s", self._name, self._address, value, e)

    async def async_update(self):
        try:
            if self._batch and not self._registered:
                try:
                    interval = int(self._scan_interval)
                    self._batch.register(self._address, interval)
                    self._registered = True
                except Exception as e:
                    _LOGGER.debug("Initial number register failed for %s: %s", self._name, e)
            value = None
            if self._batch:
                value = self._batch.get_cached(self._address, int(self._scan_interval))
            if value is not None:
                raw = int(value)
                if str(self._data_type).lower() == "int16":
                    if raw >= 0x8000:
                        raw -= 0x10000
                self._attr_native_value = round(raw * self._scale, self._precision)
        except Exception as e:
            _LOGGER.debug("Number update failed for %s: %s", self._name, e)


class HeatCurveParamNumber(NumberEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, device_info: DeviceInfo, key: str, value: float, vmin: float, vmax: float, step: float):
        super().__init__()
        self._hass = hass
        self._entry = entry
        self._key = key
        # Map keys to friendly names and entity_id suffixes
        name_map = {
            "t_out_min": ("Min Outdoor temperature for maximum flow temperature", "t_out_min"),
            "t_out_max": ("Max Outdoor temperature for minimum flow temperature", "t_out_max"),
            "t_flow_min": ("Minimum flow temperature", "t_flow_min"),
            "t_flow_max": ("Maximum flow temperature", "t_flow_max"),
            "inertia_hours": ("Inertia (hours)", "inertia_hours"),
            "deadband_c": ("Deadband (degC)", "deadband_c"),
        }
        friendly, base_suffix = name_map.get(key, (key, key))
        self._attr_name = friendly
        self._attr_unique_id = f"r290_heatpump_heatcurve_{entry.entry_id}_{key}"
        self._attr_device_info = device_info
        self._attr_should_poll = False
        # Units/Device class per key
        if key == "inertia_hours":
            self._attr_native_unit_of_measurement = "h"
            self._attr_device_class = None
        else:
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_device_class = NumberDeviceClass.TEMPERATURE
        self._attr_native_min_value = vmin
        self._attr_native_max_value = vmax
        self._attr_native_step = step
        self._attr_native_value = float(value)
        # Prefer input field over slider
        self._attr_mode = NumberMode.BOX
        # Stable entity_id names (domain number)
        try:
            curve_prefix = {
                "heating_curve": "heating",
                "floor_heating_curve": "floor_heating",
                "hot_water_curve": "hotwater",
                "cooling_curve": "cooling",
            }.get(entry.data.get("device_type"), "heating")
            suffix = f"{curve_prefix}_{base_suffix}"
            self.entity_id = f"number.r290_heatpump_{suffix}"
        except Exception:
            pass

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = float(value)
        opts = dict(self._entry.options)
        opts[self._key] = float(value)
        self._hass.config_entries.async_update_entry(self._entry, options=opts)
        self.async_write_ha_state()





class HeatcurvePvNumber(NumberEntity):
    def __init__(
        self,
        entry: ConfigEntry,
        device_info: DeviceInfo,
        *,
        key: str,
        prefix: str,
        name: str,
        unit: str,
        device_class: Optional[NumberDeviceClass],
        min_value: float,
        max_value: float,
        step: float,
        default_value: float,
    ) -> None:
        super().__init__()
        self._entry = entry
        self._key = key
        curve_names = {
            "heating": "Heating Curve",
            "floor_heating": "Floor Heating Curve",
            "hotwater": "Hot Water Curve",
            "cooling": "Cooling Curve",
        }
        friendly_curve = curve_names.get(prefix, "Heating Curve")
        self._attr_name = f"{friendly_curve} {name}"
        self._attr_unique_id = f"r290_heatpump_{prefix}_{key}_{entry.entry_id}"
        self._attr_device_info = device_info
        self._attr_should_poll = False
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_native_min_value = float(min_value)
        self._attr_native_max_value = float(max_value)
        self._attr_native_step = float(step)
        self._attr_mode = NumberMode.BOX
        self._default_value = float(default_value)
        value = self._entry.options.get(self._key, self._entry.data.get(self._key, self._default_value))
        try:
            self._attr_native_value = float(value)
        except (TypeError, ValueError):
            self._attr_native_value = self._default_value
        try:
            suffix = self._key.replace("pv_", "pv_")
            self.entity_id = f"number.r290_heatpump_{prefix}_{suffix}"
        except Exception:
            pass

    async def async_added_to_hass(self) -> None:
        opts = dict(self._entry.options)
        if self._key in opts:
            try:
                self._attr_native_value = float(opts[self._key])
            except (TypeError, ValueError):
                self._attr_native_value = self._default_value
                opts[self._key] = self._attr_native_value
        else:
            opts[self._key] = self._attr_native_value
        self.hass.config_entries.async_update_entry(self._entry, options=opts)

        data_store = dict(self._entry.data)
        data_store[self._key] = self._attr_native_value
        self.hass.config_entries.async_update_entry(self._entry, data=data_store)
        self.async_write_ha_state()


    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = float(value)
        opts = dict(self._entry.options)
        opts[self._key] = float(value)
        self.hass.config_entries.async_update_entry(self._entry, options=opts)
        data_store = dict(self._entry.data)
        data_store[self._key] = float(value)
        self.hass.config_entries.async_update_entry(self._entry, data=data_store)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        try:
            self._attr_native_value = float(self._entry.options.get(self._key, self._entry.data.get(self._key, self._default_value)))
        except (TypeError, ValueError):
            self._attr_native_value = self._default_value





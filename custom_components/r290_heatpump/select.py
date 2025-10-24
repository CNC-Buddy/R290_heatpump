# Version: 1.0.1
# Last modified: 2025-10-24 17:33 by CNC-Buddy
import logging
from typing import Dict
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SLAVE
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import slugify

from .const import DOMAIN
from .user_parameters import USER_PARAMETERS_SELECTS
from .pv_optimization import PV_CURVE_CONFIG, PV_OFFSET_OPTIONS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    device_type = entry.data.get("device_type", "heat_pump")
    entities = []

    if device_type == "heat_pump":
        slave_id = entry.data[CONF_SLAVE]
        store = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if not store or "hub" not in store:
            _LOGGER.error("Internal Modbus hub not initialised")
            return
        hub = store["hub"]
        batch = store.get("batch")
        long_interval = entry.options.get("long_scan_interval", entry.data.get("long_scan_interval", 7200))

        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"r290_heatpump_{slave_id}_user_parameters")},
            name=f"R290 Heat Pump (Slave {slave_id}) - User Parameters",
            manufacturer="R290 Heat Pump",
            model="Modbus Device",
            sw_version="1.0.0",
        )

        if int(slave_id) == 1:
            for par in USER_PARAMETERS_SELECTS:
                param = par.copy()
                param["unique_id"] = f"{param['unique_id']}_slave_{slave_id}"
                ent = R290HeatPumpModbusSelect(
                    hub, batch, slave_id, param, device_info, scan_interval=long_interval
                )
                entities.append(ent)

    elif device_type in PV_CURVE_CONFIG:
        slave_id = int(entry.data.get(CONF_SLAVE, 1))
        if slave_id == 1:
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
                HeatcurvePvOffsetSelect(
                    entry,
                    pv_device_info,
                    option_key="pv_grid_offset_min",
                    prefix=prefix,
                    title="PV Grid Offset Min",
                    legacy_keys=("pv_grid_offset",),
                )
            )
            entities.append(
                HeatcurvePvOffsetSelect(
                    entry,
                    pv_device_info,
                    option_key="pv_grid_offset_max",
                    prefix=prefix,
                    title="PV Grid Offset Max",
                    legacy_keys=("pv_grid_offset",),
                )
            )
            entities.append(
                HeatcurvePvOffsetSelect(
                    entry,
                    pv_device_info,
                    option_key="pv_battery_offset",
                    prefix=prefix,
                    title="PV Battery Offset",
                )
            )

    _LOGGER.info("Registering %s select entities for %s", len(entities), device_type)
    async_add_entities(entities, update_before_add=True)

    for entity in entities:
        hass.data.setdefault(DOMAIN, {})[entity.entity_id] = entity


class R290HeatPumpModbusSelect(SelectEntity):
    def __init__(self, hub, batch, slave_id: int, param: Dict, device_info: DeviceInfo, *, scan_interval: int) -> None:
        super().__init__()
        self._hub = hub
        self._batch = batch
        self._slave = slave_id
        self._address = param["address"]
        self._name = param["name"]
        self._unique_id = param["unique_id"]
        self._options: Dict[str, int] = param["options"]  # map label -> value
        self._reverse: Dict[int, str] = {v: k for k, v in self._options.items()}
        self._scan_interval = int(scan_interval)
        self._current_option = None

        self._attr_name = self._name
        self._attr_unique_id = self._unique_id
        self._attr_device_info = device_info
        self._attr_should_poll = True
        try:
            base = slugify(self._name)
            self.entity_id = f"select.r290_heatpump_{base}_slave_{self._slave}"
        except Exception:
            pass

    @property
    def current_option(self) -> str | None:
        return self._current_option

    @property
    def options(self) -> list[str]:
        return list(self._options.keys())

    async def async_added_to_hass(self):
        try:
            if self._batch:
                self._batch.register(self._address, self._scan_interval)
        except Exception:
            pass

    async def async_select_option(self, option: str) -> None:
        if option not in self._options:
            raise ValueError("Invalid option")
        value = self._options[option]
        await self._hub.async_pb_write_register(self._slave, self._address, int(value))
        self._current_option = option

    async def async_update(self):
        try:
            value = None
            if self._batch:
                value = self._batch.get_cached(self._address, self._scan_interval)
            if value is not None:
                self._current_option = self._reverse.get(int(value), self._current_option)
        except Exception as e:
            _LOGGER.debug("Select update failed for %s: %s", self._name, e)




class HeatcurvePvOffsetSelect(SelectEntity):
    def __init__(
        self,
        entry: ConfigEntry,
        device_info: DeviceInfo,
        *,
        option_key: str,
        prefix: str,
        title: str,
        legacy_keys: tuple[str, ...] | None = None,
    ) -> None:
        super().__init__()
        self._entry = entry
        self._option_key = option_key
        self._prefix = prefix
        self._title = title
        self._legacy_keys = tuple(legacy_keys or ())
        self._legacy_value: int | None = None
        for legacy_key in self._legacy_keys:
            raw = entry.options.get(legacy_key, entry.data.get(legacy_key))
            if raw is None:
                continue
            try:
                self._legacy_value = int(float(raw))
                break
            except (TypeError, ValueError):
                continue
        self._value_labels = PV_OFFSET_OPTIONS
        self._label_values = {label: value for value, label in self._value_labels.items()}
        self._current_value = 0
        self._attr_device_info = device_info
        self._attr_should_poll = False
        self._attr_entity_category = EntityCategory.CONFIG

        curve_names = {
            "pv_grid_offset": "PV Grid Offset",
            "pv_grid_offset_min": "PV Grid Offset Min",
            "pv_grid_offset_max": "PV Grid Offset Max",
            "pv_battery_offset": "PV Battery Offset",
        }
        base_name = curve_names.get(option_key, title)
        friendly_curve = {
            "heating": "Heating Curve",
            "floor_heating": "Floor Heating Curve",
            "hotwater": "Hot Water Curve",
            "cooling": "Cooling Curve",
        }.get(prefix, "Heating Curve")

        self._attr_name = f"{friendly_curve} {base_name}"
        self._attr_unique_id = (
            f"r290_heatpump_{prefix}_{option_key}_{entry.entry_id}"
        )
        try:
            suffix = option_key.replace("pv_", "pv_")
            self.entity_id = f"select.r290_heatpump_{prefix}_{suffix}"
        except Exception:
            pass

    @property
    def options(self) -> list[str]:
        return list(self._value_labels.values())

    @property
    def current_option(self) -> str | None:
        return self._value_labels.get(self._current_value)

    async def async_added_to_hass(self) -> None:
        try:
            raw = self._entry.options.get(
                self._option_key,
                self._entry.data.get(
                    self._option_key,
                    self._legacy_value if self._legacy_value is not None else 0,
                ),
            )
            value = int(float(raw))
        except (TypeError, ValueError):
            value = 0
        hass = self.hass or getattr(self._entry, "hass", None)
        if value not in PV_OFFSET_OPTIONS:
            value = 0
        opts = dict(self._entry.options)
        opts[self._option_key] = value
        for legacy_key in self._legacy_keys:
            opts.pop(legacy_key, None)
        if hass is not None:
            hass.config_entries.async_update_entry(self._entry, options=opts)
        data_store = dict(self._entry.data)
        data_store[self._option_key] = value
        for legacy_key in self._legacy_keys:
            data_store.pop(legacy_key, None)
        if hass is not None:
            hass.config_entries.async_update_entry(self._entry, data=data_store)
        self._current_value = value
        self._attr_current_option = self._value_labels.get(self._current_value)
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        if option not in self._label_values:
            raise ValueError("Invalid option")
        value = self._label_values[option]
        self._current_value = value
        self._attr_current_option = option
        opts = dict(self._entry.options)
        opts[self._option_key] = value
        for legacy_key in self._legacy_keys:
            opts.pop(legacy_key, None)
        # Use the Home Assistant instance provided by the Entity base class
        # instead of a private attribute to avoid attribute errors during
        # service calls (e.g. select/select_option).
        if self.hass is not None:
            self.hass.config_entries.async_update_entry(self._entry, options=opts)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        try:
            raw = self._entry.options.get(
                self._option_key,
                self._entry.data.get(
                    self._option_key,
                    self._legacy_value if self._legacy_value is not None else 0,
                ),
            )
            self._current_value = int(float(raw))
        except (TypeError, ValueError):
            self._current_value = 0
        self._attr_current_option = self._value_labels.get(self._current_value)




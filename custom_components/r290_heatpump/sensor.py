# Version: 1.0.1
# Last modified: 2025-10-24 17:33 by CNC-Buddy
import logging
from datetime import datetime, timedelta
from typing import Optional

from homeassistant.components.sensor import SensorEntity, SensorStateClass

from homeassistant.core import HomeAssistant, callback

from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from homeassistant.config_entries import ConfigEntry

from homeassistant.const import CONF_SLAVE, CONF_SCAN_INTERVAL, STATE_OFF, STATE_ON, UnitOfTime

from homeassistant.helpers.device_registry import DeviceInfo

from homeassistant.util import slugify, dt as dt_util



from .main import MAIN_SENSORS, COMPRESSOR_DIAGNOSTIC_COUNTERS

from .realtimedata import REALTIMEDATA_SENSORS

from .unit_system_parameters import UNIT_SYSTEM_READONLY_SENSORS

from .user_parameters import USER_PARAMETERS_SENSORS

from .cop_calculator import setup_cop_sensors

from .temperature_curve import R290HeatPumpTemperatureCurveSensor

from .const import DOMAIN



_LOGGER = logging.getLogger(__name__)





async def async_setup_entry(

    hass: HomeAssistant,

    entry: ConfigEntry,

    async_add_entities: AddEntitiesCallback,

) -> None:

    """Set up the R290 Heat Pump Modbus sensor entities."""

    device_type = entry.data.get("device_type", "heat_pump")

    entities = []



    if device_type == "heat_pump":

        slave_id = entry.data[CONF_SLAVE]

        fast_interval = entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, 60))

        long_interval = entry.options.get("long_scan_interval", entry.data.get("long_scan_interval", 600))

        store = hass.data.get(DOMAIN, {}).get(entry.entry_id)

        if not store or "hub" not in store:

            _LOGGER.error("Internal Modbus hub not initialised")

            return

        hub = store["hub"]

        batch = store.get("batch")



        main_device_info = DeviceInfo(

            identifiers={(DOMAIN, f"r290_heatpump_{slave_id}_main")},

            name=f"R290 Heat Pump (Slave {slave_id}) - Main",

            manufacturer="R290 Heat Pump",

            model="Modbus Device",

            sw_version="1.0.0",

        )

        for sensor_info in MAIN_SENSORS:

            sensor_data = sensor_info.copy()

            sensor_data["unique_id"] = f"{sensor_info['unique_id']}_slave_{slave_id}"

            if int(slave_id) != 1:

                sensor_data.setdefault("enabled_by_default", False)

            # Main should follow fast scan interval

            sensor = R290HeatPumpModbusSensor(hass, entry, sensor_data, slave_id, fast_interval, hub, main_device_info, batch)

            entities.append(sensor)

        # Add compressor diagnostic counters for all slaves.
        # Enable by default for all slaves.
        for counter in COMPRESSOR_DIAGNOSTIC_COUNTERS:
            compressor_status_entity_id = (
                f"sensor.r290_heatpump_{counter['status_slug']}_slave_{slave_id}"
            )
            enabled_default = True

            entities.append(
                R290HeatPumpCompressorStartCounter(
                    status_entity_id=compressor_status_entity_id,
                    slave_id=int(slave_id),
                    device_info=main_device_info,
                    entity_name=counter["start_name"],
                    unique_id_prefix=counter["start_unique_id"],
                    enabled_default=enabled_default,
                )
            )

            entities.append(
                R290HeatPumpCompressorRuntimeSensor(
                    status_entity_id=compressor_status_entity_id,
                    slave_id=int(slave_id),
                    device_info=main_device_info,
                    entity_name=counter["runtime_name"],
                    unique_id_prefix=counter["runtime_unique_id"],
                    enabled_default=enabled_default,
                )
            )



        if int(slave_id) == 1:

            user_params_device_info = DeviceInfo(

                identifiers={(DOMAIN, f"r290_heatpump_{slave_id}_user_parameters")},

                name=f"R290 Heat Pump (Slave {slave_id}) - User Parameters",

                manufacturer="R290 Heat Pump",

                model="Modbus Device",

                sw_version="1.0.0",

            )

            for sensor_info in USER_PARAMETERS_SENSORS:

                sensor_data = sensor_info.copy()

                sensor_data["unique_id"] = f"{sensor_info['unique_id']}_slave_{slave_id}"

                sensor = R290HeatPumpModbusSensor(hass, entry, sensor_data, slave_id, long_interval, hub, user_params_device_info, batch)

                entities.append(sensor)



        realtimedata_device_info = DeviceInfo(

            identifiers={(DOMAIN, f"r290_heatpump_{slave_id}_real_time_data")},

            name=f"R290 Heat Pump (Slave {slave_id}) - Real Time Data",

            manufacturer="R290 Heat Pump",

            model="Modbus Device",

            sw_version="1.0.0",

        )

        for sensor_info in REALTIMEDATA_SENSORS:

            sensor_data = sensor_info.copy()

            sensor_data["unique_id"] = f"{sensor_info['unique_id']}_slave_{slave_id}"

            sensor = R290HeatPumpModbusSensor(hass, entry, sensor_data, slave_id, fast_interval, hub, realtimedata_device_info, batch)

            entities.append(sensor)



        unit_system_device_info = DeviceInfo(

            identifiers={(DOMAIN, f"r290_heatpump_{slave_id}_unit_system_parameters")},

            name=f"R290 Heat Pump (Slave {slave_id}) - Unit System Parameters",

            manufacturer="R290 Heat Pump",

            model="Modbus Device",

            sw_version="1.0.0",

        )

        for sensor_info in UNIT_SYSTEM_READONLY_SENSORS:

            sensor_data = sensor_info.copy()

            sensor_data["unique_id"] = f"{sensor_info['unique_id']}_slave_{slave_id}"

            sensor = R290HeatPumpModbusSensor(hass, entry, sensor_data, slave_id, long_interval, hub, unit_system_device_info, batch)

            entities.append(sensor)

    elif device_type == "modbus_bridge":

        # Expose simple bridge sensors so a device appears and options are reachable

        store = hass.data.get(DOMAIN, {}).get(entry.entry_id)

        if not store or "hub" not in store:

            _LOGGER.error("Internal Modbus hub not initialised (bridge)")

            return

        hub = store["hub"]

        batch = store.get("batch")

        bridge_device_info = DeviceInfo(

            identifiers={(DOMAIN, "r290_heatpump_bridge")},

            name="R290 Heat Pump Modbus Bridge",

            manufacturer="R290 Heat Pump",

            model="Modbus Bridge",

            sw_version="1.0.0",

        )

        # Status sensor

        status_info = {

            "name": "Modbus Bridge Status",

            "unique_id": "r290_heatpump_bridge_status",

            "address": 0,

            "scale": 1,

            "unit": None,

            "device_class": None,

            "state_class": None,

            "precision": 0,

        }

        entities.append(R290HeatPumpModbusStatusSensor(hass, entry, status_info, 1, 0, hub, bridge_device_info, batch))



        # Info sensors: host, port, connection type

        entities.append(R290HeatPumpModbusBridgeInfoSensor(hass, entry, bridge_device_info, "Host", "host", "r290_heatpump_bridge_host"))

        entities.append(R290HeatPumpModbusBridgeInfoSensor(hass, entry, bridge_device_info, "Port", "port", "r290_heatpump_bridge_port"))

        entities.append(R290HeatPumpModbusBridgeInfoSensor(hass, entry, bridge_device_info, "Connection Type", "connection_type", "r290_heatpump_bridge_connection_type"))



    elif device_type in ("heating_curve", "floor_heating_curve", "hot_water_curve", "cooling_curve"):

        # Provide computed curve sensors under dedicated devices per type

        store = hass.data.get(DOMAIN, {}).get(entry.entry_id)

        if not store or "hub" not in store:

            _LOGGER.error("Internal Modbus hub not initialised (curve)")

            return

        hub = store["hub"]

        meta_map = {

            "heating_curve": ("r290_heatpump_heating_curve", "R290 Heat Pump Heating Curve", 0x0301, "sensor.r290_heatpump_heating_curve_now", "Heating Curve Now"),

            "floor_heating_curve": ("r290_heatpump_floor_heating_curve", "R290 Heat Pump Floor Heating Curve", 0x0303, "sensor.r290_heatpump_floor_heating_curve_now", "Floor Heating Curve Now"),

            "hot_water_curve": ("r290_heatpump_hotwater_curve", "R290 Heat Pump Hot Water Curve", 0x0302, "sensor.r290_heatpump_hotwater_curve_now", "Hot Water Curve Now"),

            "cooling_curve": ("r290_heatpump_cooling_curve", "R290 Heat Pump Cooling Curve", 0x0300, "sensor.r290_heatpump_cooling_curve_now", "Cooling Curve Now"),

        }

        dev_id, dev_name, addr, ent_id, disp = meta_map[device_type]

        device_info = DeviceInfo(

            identifiers={(DOMAIN, dev_id)},

            name=dev_name,

            manufacturer="R290 Heat Pump",

            model="Temperature Curve",

            sw_version="1.0.0",

        )

        entities.append(R290HeatPumpTemperatureCurveSensor(hass, entry, device_info, hub, modbus_address=addr, custom_entity_id=ent_id, display_name=disp))



    elif device_type == "cop_calculator":

        # Ensure a stable, per-entry device for COP sensors

        cop_device_info = DeviceInfo(

            identifiers={(DOMAIN, f"r290_heatpump_cop_calculator_{entry.entry_id}")},

            name="R290 Heat Pump COP Calculator",

            manufacturer="R290 Heat Pump",

            model="COP Calculator",

            sw_version="1.0.0",

        )

        entities.extend(setup_cop_sensors(hass, entry, cop_device_info))



    _LOGGER.info("Registering %s sensor entities for %s", len(entities), device_type)

    async_add_entities(entities, update_before_add=True)



    for entity in entities:

        hass.data.setdefault(DOMAIN, {})[entity.entity_id] = entity





class R290HeatPumpModbusSensor(SensorEntity):

    """Representation of a R290 Heat Pump Modbus sensor."""



    def __init__(self, hass, entry, sensor_info, slave_id, scan_interval, hub, device_info, batch_manager):

        super().__init__()

        self._hass = hass

        self._entry = entry

        self._address = sensor_info["address"]

        self._scale = sensor_info["scale"]

        self._unit = sensor_info["unit"]

        self._name = sensor_info["name"]

        self._unique_id = sensor_info["unique_id"]

        self._device_class = sensor_info["device_class"]

        self._state_class = sensor_info["state_class"]

        self._precision = sensor_info["precision"]

        self._slave_id = slave_id

        self._state = None

        self._hub = hub

        self._batch = batch_manager

        self._scan_interval = scan_interval



        self._attr_native_unit_of_measurement = self._unit

        self._attr_device_class = self._device_class

        # Normalize state_class to HA enum for long-term statistics

        sc = sensor_info.get("state_class")

        if isinstance(sc, str):

            sc_map = {

                "measurement": SensorStateClass.MEASUREMENT,

                "total": SensorStateClass.TOTAL,

                "total_increasing": SensorStateClass.TOTAL_INCREASING,

            }

            self._attr_state_class = sc_map.get(sc.lower())

        else:

            self._attr_state_class = sc

        self._attr_unique_id = self._unique_id

        self._attr_device_info = device_info

        self._attr_should_poll = True

        # Optional: default enabled flag and bit label mapping for bitfield sensors

        self._bit_labels = sensor_info.get("bit_labels")

        self._bitfield = sensor_info.get("bitfield", False)

        self._bit_index = sensor_info.get("bit")

        self._bit_on_state = sensor_info.get("on_state", STATE_ON)

        self._bit_off_state = sensor_info.get("off_state", STATE_OFF)

        if self._bit_labels:

            # Text state, avoid numerical state_class

            self._attr_state_class = None

        if self._bit_index is not None:

            self._unit = None

            self._attr_native_unit_of_measurement = None

            self._attr_state_class = None

        self._attr_entity_registry_enabled_default = sensor_info.get("enabled_by_default", True)



        # Optional entity category (e.g. diagnostic for bit-derived sensors)
        entity_category = sensor_info.get("entity_category")
        if entity_category in (EntityCategory.DIAGNOSTIC, EntityCategory.CONFIG):
            self._attr_entity_category = entity_category
        elif isinstance(entity_category, str):
            try:
                self._attr_entity_category = EntityCategory(entity_category)
            except Exception:
                pass

        # Harmonize entity_id pattern: sensor.r290_heatpump_<slug-name>_slave_<id>

        try:

            base = slugify(self._name)

            self.entity_id = f"sensor.r290_heatpump_{base}_slave_{self._slave_id}"

        except Exception:

            pass



    @property

    def name(self):

        return self._name



    @property

    def state(self):

        return self._state



    @property

    def state_class(self):

        return self._attr_state_class



    @property

    def unit_of_measurement(self):

        return self._unit



    @property

    def unique_id(self):

        return self._unique_id





    @property

    def device_info(self):

        return self._attr_device_info



    async def async_added_to_hass(self):

        _LOGGER.info("Sensor %s added to Home Assistant", self._name)

        try:

            if self._batch:

                interval = int(self._scan_interval)

                self._batch.register(self._address, interval)

                if hasattr(self._batch, "request_refresh"):

                    await self._batch.request_refresh(interval)

        except Exception as e:

            _LOGGER.debug("Initial read failed for %s: %s", self._name, e)



    async def async_update(self):

        try:

            value = None

            if self._batch:

                value = self._batch.get_cached(self._address, int(self._scan_interval))

            if value is not None:

                if self._bit_index is not None:



                    try:



                        iv = int(value)



                        self._state = self._bit_on_state if iv & (1 << int(self._bit_index)) else self._bit_off_state



                    except Exception:



                        self._state = None



                elif self._bit_labels is not None:

                    try:

                        iv = int(value)

                        labels = [lbl for bit, lbl in sorted(self._bit_labels.items()) if iv & (1 << int(bit)) and lbl]

                        self._state = ", ".join(labels) if labels else "None"

                    except Exception:

                        # fallback to raw value if decoding fails

                        self._state = str(value)

                elif self._bitfield:

                    try:

                        iv = int(value)

                        bits = [str(b) for b in range(16) if iv & (1 << b)]

                        self._state = "Bits: " + ", ".join(bits) if bits else "None"

                    except Exception:

                        self._state = str(value)

                else:

                    self._state = round(value * self._scale, self._precision)

            # else: keep last state until batch provides a value

        except Exception as e:

            _LOGGER.debug("Sensor update failed for %s: %s", self._name, e)





class R290HeatPumpModbusStatusSensor(SensorEntity):

    """Simple status sensor for Modbus Bridge config entry."""



    def __init__(self, hass, entry, sensor_info, slave_id, scan_interval, hub, device_info, batch_manager):

        super().__init__()

        self._hass = hass

        self._entry = entry

        self._name = sensor_info["name"]

        self._unique_id = sensor_info["unique_id"]

        self._hub = hub

        self._attr_unique_id = self._unique_id

        self._attr_device_info = device_info

        self._attr_should_poll = True

        self._state = None



        # Stable entity_id for bridge status

        self.entity_id = "sensor.r290_heatpump_bridge_status"



    @property

    def name(self):

        return self._name



    @property

    def state(self):

        return self._state



    @property

    def extra_state_attributes(self):

        try:

            domain_store = self._hass.data.get(DOMAIN, {})

            conn = domain_store.get("connection", {})

            host = conn.get("host")

            port = conn.get("port")

            mode = conn.get("connection_type")

            connected = bool(getattr(getattr(self._hub, "_client", None), "connected", False))

            return {

                "host": host,

                "port": port,

                "connection_type": mode,

                "connected": connected,

            }

        except Exception:

            return None



    async def async_update(self):

        try:

            connected = bool(getattr(getattr(self._hub, "_client", None), "connected", False))

            self._state = "Connected" if connected else "Disconnected"

        except Exception:

            self._state = "Unknown"





class R290HeatPumpModbusBridgeInfoSensor(SensorEntity):

    """Info sensors for Modbus Bridge connection parameters (host/port/type)."""



    def __init__(self, hass, entry, device_info, name: str, key: str, unique_id: str):

        super().__init__()

        self._hass = hass

        self._entry = entry

        self._name = f"Modbus Bridge {name}"

        self._key = key

        self._attr_unique_id = unique_id

        self._attr_device_info = device_info

        self._attr_should_poll = True

        self._state = None

        # Deterministic entity_ids for bridge info sensors

        if self._key == "host":

            self.entity_id = "sensor.r290_heatpump_bridge_host"

        elif self._key == "port":

            self.entity_id = "sensor.r290_heatpump_bridge_port"

        elif self._key == "connection_type":

            self.entity_id = "sensor.r290_heatpump_bridge_connection_type"



    @property

    def name(self):

        return self._name



    @property

    def state(self):

        return self._state



    async def async_update(self):

        try:

            domain_store = self._hass.data.get(DOMAIN, {})

            conn = domain_store.get("connection", {})

            value = conn.get(self._key)

            self._state = value

        except Exception:

            self._state = None









class _CompressorCounterBase(SensorEntity, RestoreEntity):
    """Base class for compressor diagnostic counters."""

    def __init__(
        self,
        *,
        status_entity_id: str,
        slave_id: int,
        device_info: DeviceInfo,
        entity_name: str,
        unique_id_prefix: str,
        enabled_default: bool = True,
    ) -> None:
        super().__init__()
        self._status_entity_id = status_entity_id
        self._slave_id = slave_id
        self._remove_state_listener = None
        self._attr_device_info = device_info
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_should_poll = False
        self._attr_entity_registry_enabled_default = enabled_default
        self._base_entity_name = entity_name
        self._unique_id_prefix = unique_id_prefix

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        await RestoreEntity.async_will_remove_from_hass(self)
        if self._remove_state_listener is not None:
            self._remove_state_listener()
            self._remove_state_listener = None


class R290HeatPumpCompressorStartCounter(_CompressorCounterBase):
    """Counts compressor start events (off -> on transitions)."""

    def __init__(
        self,
        *,
        status_entity_id: str,
        slave_id: int,
        device_info: DeviceInfo,
        entity_name: str,
        unique_id_prefix: str,
        enabled_default: bool = True,
    ) -> None:
        super().__init__(
            status_entity_id=status_entity_id,
            slave_id=slave_id,
            device_info=device_info,
            entity_name=entity_name,
            unique_id_prefix=unique_id_prefix,
            enabled_default=enabled_default,
        )
        self._count: int = 0
        self._attr_name = f"{self._base_entity_name} (Slave {slave_id})"
        self._attr_unique_id = f"{self._unique_id_prefix}_slave_{slave_id}"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = "starts"
        self._last_state: Optional[str] = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await RestoreEntity.async_added_to_hass(self)
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "", "unknown", "unavailable"):
            try:
                self._count = int(float(last_state.state))
            except (ValueError, TypeError):
                self._count = 0

        current = self.hass.states.get(self._status_entity_id)
        if current is not None:
            self._last_state = current.state

        self._remove_state_listener = async_track_state_change_event(
            self.hass,
            [self._status_entity_id],
            self._handle_state_change,
        )
        self.async_write_ha_state()

    @callback
    def _handle_state_change(self, event) -> None:
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if new_state is None:
            return
        if new_state.state == STATE_ON and (old_state is None or old_state.state != STATE_ON):
            self._count += 1
            self.async_write_ha_state()
        self._last_state = new_state.state

    @property
    def native_value(self) -> int:
        return int(self._count)


class R290HeatPumpCompressorRuntimeSensor(_CompressorCounterBase):
    """Tracks compressor runtime in seconds, never resetting."""

    def __init__(
        self,
        *,
        status_entity_id: str,
        slave_id: int,
        device_info: DeviceInfo,
        entity_name: str,
        unique_id_prefix: str,
        enabled_default: bool = True,
    ) -> None:
        super().__init__(
            status_entity_id=status_entity_id,
            slave_id=slave_id,
            device_info=device_info,
            entity_name=entity_name,
            unique_id_prefix=unique_id_prefix,
            enabled_default=enabled_default,
        )
        self._total_seconds: float = 0.0
        self._current_on_start: Optional[datetime] = None
        self._remove_interval = None
        self._attr_name = f"{self._base_entity_name} (Slave {slave_id})"
        self._attr_unique_id = f"{self._unique_id_prefix}_slave_{slave_id}"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfTime.HOURS

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await RestoreEntity.async_added_to_hass(self)
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "", "unknown", "unavailable"):
            try:
                uom = None
                try:
                    uom = last_state.attributes.get("unit_of_measurement")
                except Exception:
                    uom = None
                # If previous unit was hours, convert to seconds; if it was seconds
                # or unknown, assume seconds (older versions stored seconds).
                val = float(last_state.state)
                if str(uom).lower() in (str(UnitOfTime.HOURS).lower(), "h", "hours", "hour"):
                    self._total_seconds = val * 3600.0
                else:
                    self._total_seconds = val
            except (ValueError, TypeError):
                self._total_seconds = 0.0

        current = self.hass.states.get(self._status_entity_id)
        if current is not None and current.state == STATE_ON:
            self._current_on_start = dt_util.utcnow()

        self._remove_state_listener = async_track_state_change_event(
            self.hass,
            [self._status_entity_id],
            self._handle_state_change,
        )
        self._remove_interval = async_track_time_interval(
            self.hass,
            self._handle_interval,
            timedelta(minutes=1),
        )
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        if self._remove_interval is not None:
            self._remove_interval()
            self._remove_interval = None

    @callback
    def _handle_state_change(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        now = dt_util.utcnow()
        if new_state.state == STATE_ON:
            if self._current_on_start is None:
                self._current_on_start = now
            self.async_write_ha_state()
            return

        if self._current_on_start is not None:
            self._total_seconds += (now - self._current_on_start).total_seconds()
            self._current_on_start = None
            self.async_write_ha_state()

    @callback
    def _handle_interval(self, now) -> None:
        if self._current_on_start is not None:
            self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        total = self._total_seconds
        if self._current_on_start is not None:
            total += (dt_util.utcnow() - self._current_on_start).total_seconds()
        return round(total / 3600.0, 2)















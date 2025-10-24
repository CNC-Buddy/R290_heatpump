# Version: 1.0.1
# Last modified: 2025-10-24 17:33 by CNC-Buddy
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_SLAVE, CONF_SCAN_INTERVAL
from homeassistant.helpers.selector import selector

from .hub import R290HeatPumpModbusHub
from .dashboard import async_setup_dashboard
from .pv_optimization import PV_CURVE_CONFIG

_LOGGER = logging.getLogger(__name__)

DOMAIN = "r290_heatpump"

DEVICE_TYPES = {
    "modbus_bridge": "Modbus Bridge",
    "heat_pump": "Heat Pump",
    "cop_calculator": "COP Calculator",
    # Only expose the four concrete curve kinds
    "heating_curve": "Heating Curve",
    "floor_heating_curve": "Floor Heating Curve",
    "cooling_curve": "Cooling Curve",
    "hot_water_curve": "Hot Water Curve",
}


class R290HeatPumpModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return R290HeatPumpOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            device_type_display = user_input["device_type"]
            device_type = next(key for key, value in DEVICE_TYPES.items() if value == device_type_display)
            if device_type == "modbus_bridge":
                return await self.async_step_modbus_bridge()
            if device_type == "heat_pump":
                return await self.async_step_heat_pump()
            if device_type == "cop_calculator":
                return await self.async_step_cop_calculator()
            if device_type in ("heating_curve", "floor_heating_curve", "cooling_curve", "hot_water_curve"):
                # Merke die Auswahl und gehe direkt in den Kurven-Flow ohne erneute Auswahl
                self._selected_curve_kind = device_type
                return await self.async_step_temperature_curve()
            errors["base"] = "invalid_device_type"

        # Build choices, hide COP calculator if already configured
        device_types = dict(DEVICE_TYPES)
        has_cop = any(e.data.get("device_type") == "cop_calculator" for e in self.hass.config_entries.async_entries(DOMAIN))
        if has_cop and "cop_calculator" in device_types:
            device_types.pop("cop_calculator")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("device_type"): vol.In(list(device_types.values()))}),
            errors=errors,
        )

    async def async_step_modbus_bridge(self, user_input=None):
        errors = {}
        schema = vol.Schema(
            {
                vol.Required("connection_type", default="rtuovertcp"): vol.In(["rtuovertcp", "tcp"]),
                vol.Required("host"): str,
                vol.Required("port", default=502): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Optional("connect_timeout", default=10.0): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=60.0)),
                vol.Optional("connect_retries", default=2): selector({"number": {"min": 0, "max": 10, "step": 1, "mode": "box"}}),
                vol.Optional("request_timeout", default=8.0): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=30.0)),
                vol.Optional("block_size", default=49): selector({"number": {"min": 1, "max": 125, "step": 1, "mode": "box"}}),
                vol.Optional("block_pause", default=0.1): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
                # Optional: create the Lovelace dashboard on first setup
                vol.Optional("create_dashboard", default=True): bool,
            }
        )
        if user_input is not None:
            try:
                connection_type = user_input["connection_type"]
                host = user_input["host"]
                port = user_input["port"]
                hub = R290HeatPumpModbusHub(host=host, port=port, mode=connection_type, connect_timeout=float(user_input.get("connect_timeout", 8.0)), connect_retries=int(user_input.get("connect_retries", 2)), request_timeout=float(user_input.get("request_timeout", 5.0)))
                await hub.async_connect()
                try:
                    await hub.async_close()
                except Exception:
                    pass
                # Create dashboard immediately if selected
                try:
                    if bool(user_input.get("create_dashboard", True)):
                        await async_setup_dashboard(self.hass)
                except Exception:
                    _LOGGER.debug("Dashboard creation deferred or failed during flow; can be retried via options.")
                return self.async_create_entry(
                    title="R290 Heat Pump Modbus Bridge",
                    data={
                        "device_type": "modbus_bridge",
                        "connection_type": connection_type,
                        "host": host,
                        "port": port,
                        "connect_timeout": float(user_input.get("connect_timeout", 8.0)),
                        "connect_retries": int(user_input.get("connect_retries", 2)),
                        "request_timeout": float(user_input.get("request_timeout", 5.0)),
                        "block_size": int(user_input.get("block_size", 49)),
                        "block_pause": float(user_input.get("block_pause", 0.05)),
                        "create_dashboard": bool(user_input.get("create_dashboard", True)),
                    },
                )
            except Exception as err:
                _LOGGER.error("Modbus bridge flow error: %s", err)
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="modbus_bridge", data_schema=schema, errors=errors)

    async def async_step_heat_pump(self, user_input=None):
        errors = {}
        existing = next(
            (e for e in self.hass.config_entries.async_entries(DOMAIN) if e.data.get("device_type") == "modbus_bridge" and e.data.get("host")),
            None,
        )

        if existing is not None:
            schema = vol.Schema(
                {
                    vol.Required(CONF_SLAVE, default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=11)),
                    vol.Required(CONF_SCAN_INTERVAL, default=60): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
                    vol.Required("long_scan_interval", default=600): vol.All(vol.Coerce(int), vol.Range(min=60, max=86400)),
                }
            )
            if user_input is not None:
                try:
                    slave_id = user_input[CONF_SLAVE]
                    fast = user_input[CONF_SCAN_INTERVAL]
                    slow = user_input["long_scan_interval"]
                    return self.async_create_entry(
                        title=f"R290 Heat Pump (Slave {slave_id})",
                        data={
                            "device_type": "heat_pump",
                            "connection_type": existing.data.get("connection_type", "rtuovertcp"),
                            "host": existing.data["host"],
                            "port": existing.data.get("port", 502),
                            CONF_SLAVE: slave_id,  # WICHTIG: Verwende CONF_SLAVE als Key
                            CONF_SCAN_INTERVAL: fast,
                            "long_scan_interval": slow,
                            # Übernehme auch die anderen Connection-Parameter
                            "connect_timeout": existing.data.get("connect_timeout", 8.0),
                            "connect_retries": existing.data.get("connect_retries", 2),
                            "request_timeout": existing.data.get("request_timeout", 5.0),
                            "block_size": existing.data.get("block_size", 49),
                            "block_pause": existing.data.get("block_pause", 0.05),
                        },
                    )
                except Exception as err:
                    _LOGGER.error("Heat pump flow error: %s", err)
                    errors["base"] = "cannot_connect"
            return self.async_show_form(step_id="heat_pump", data_schema=schema, errors=errors)

        schema = vol.Schema(
            {
                vol.Required("connection_type", default="rtuovertcp"): vol.In(["rtuovertcp", "tcp"]),
                vol.Required("host"): str,
                vol.Required("port", default=502): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required(CONF_SLAVE, default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=11)),
                vol.Required(CONF_SCAN_INTERVAL, default=60): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
                vol.Required("long_scan_interval", default=600): vol.All(vol.Coerce(int), vol.Range(min=60, max=86400)),
            }
        )
        if user_input is not None:
            try:
                connection_type = user_input["connection_type"]
                host = user_input["host"]
                port = user_input["port"]
                slave_id = user_input[CONF_SLAVE]
                fast = user_input[CONF_SCAN_INTERVAL]
                slow = user_input["long_scan_interval"]
                hub = R290HeatPumpModbusHub(host=host, port=port, mode=connection_type, connect_timeout=10.0, connect_retries=2)
                await hub.async_connect()
                try:
                    await hub.async_close()
                except Exception:
                    pass
                return self.async_create_entry(
                    title=f"R290 Heat Pump (Slave {slave_id})",
                    data={
                        "device_type": "heat_pump",
                        "connection_type": connection_type,
                        "host": host,
                        "port": port,
                        CONF_SLAVE: slave_id,  # WICHTIG: Verwende CONF_SLAVE als Key
                        CONF_SCAN_INTERVAL: fast,
                        "long_scan_interval": slow,
                    },
                )
            except Exception as err:
                _LOGGER.error("Heat pump flow error: %s", err)
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="heat_pump", data_schema=schema, errors=errors)

    async def async_step_cop_calculator(self, user_input=None):
        errors = {}
        # Prevent multiple COP entries
        if any(e.data.get("device_type") == "cop_calculator" for e in self.hass.config_entries.async_entries(DOMAIN)):
            errors["base"] = "already_configured"
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            heat_meter = user_input["heat_meter"]
            power_sel = user_input["power_meter"]
            trig_heat = bool(user_input.get("cop_trigger_on_heat", True))
            trig_power = bool(user_input.get("cop_trigger_on_power", True))
            # No database needed for COP
            # Basic validation
            if heat_meter == power_sel:
                errors["heat_meter"] = "same_sensor_selected"
            elif not self.hass.states.get(heat_meter) or not self.hass.states.get(power_sel):
                errors["base"] = "invalid_sensor"
            else:
                return self.async_create_entry(
                    title="R290 Heat Pump COP Calculator",
                    data={
                        "device_type": "cop_calculator",
                        "heat_meter": heat_meter,
                        "power_meter": power_sel,
                        # Store trigger prefs in data for initial setup; options may override later
                        "cop_trigger_on_heat": trig_heat,
                        "cop_trigger_on_power": trig_power,
                    },
                )
        # Simple form: only meters required
        return self.async_show_form(
            step_id="cop_calculator",
            data_schema=vol.Schema(
                {
                    vol.Required("heat_meter"): selector({"entity": {"domain": "sensor"}}),
                    vol.Required("power_meter"): selector({"entity": {"domain": "sensor"}}),
                    vol.Optional("cop_trigger_on_heat", default=True): bool,
                    vol.Optional("cop_trigger_on_power", default=True): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_temperature_curve(self, user_input=None):
        errors = {}
        kind = getattr(self, "_selected_curve_kind", None) or "heating_curve"

        existing_bridge = next(
            (
                e
                for e in self.hass.config_entries.async_entries(DOMAIN)
                if e.data.get("device_type") == "modbus_bridge" and e.data.get("host")
            ),
            None,
        )

        if existing_bridge is not None:
            schema = vol.Schema(
                {
                    vol.Required("outdoor_sensor"): selector({"entity": {"domain": "sensor"}}),
                    vol.Optional("pv_power_sensor"): selector({"entity": {"domain": "sensor"}}),
                    vol.Optional("pv_battery_sensor"): selector({"entity": {"domain": "sensor"}}),
                }
            )

            if user_input is not None:
                outdoor_sensor = user_input.get("outdoor_sensor")
                pv_power = user_input.get("pv_power_sensor")
                pv_battery = user_input.get("pv_battery_sensor")

                try:
                    if not outdoor_sensor or not self.hass.states.get(outdoor_sensor):
                        errors["outdoor_sensor"] = "invalid_sensor"
                        raise ValueError
                    if pv_power and not self.hass.states.get(pv_power):
                        errors["pv_power_sensor"] = "invalid_sensor"
                        raise ValueError
                    if pv_battery and not self.hass.states.get(pv_battery):
                        errors["pv_battery_sensor"] = "invalid_sensor"
                        raise ValueError

                    data = {
                        "device_type": kind,
                        "connection_type": existing_bridge.data.get("connection_type", "rtuovertcp"),
                        "host": existing_bridge.data["host"],
                        "port": existing_bridge.data.get("port", 502),
                        "outdoor_sensor": outdoor_sensor,
                        CONF_SLAVE: 1,
                        "connect_timeout": existing_bridge.data.get("connect_timeout", 8.0),
                        "connect_retries": existing_bridge.data.get("connect_retries", 2),
                        "request_timeout": existing_bridge.data.get("request_timeout", 5.0),
                        "block_size": existing_bridge.data.get("block_size", 49),
                        "block_pause": existing_bridge.data.get("block_pause", 0.05),
                    }
                    if pv_power:
                        data["pv_power_sensor"] = pv_power
                    if pv_battery:
                        data["pv_battery_sensor"] = pv_battery

                    return self.async_create_entry(
                        title={
                            "heating_curve": "R290 Heat Pump Heating Curve",
                            "floor_heating_curve": "R290 Heat Pump Floor Heating Curve",
                            "cooling_curve": "R290 Heat Pump Cooling Curve",
                            "hot_water_curve": "R290 Heat Pump Hot Water Curve",
                        }.get(kind, "R290 Heat Pump Temperature Curve"),
                        data=data,
                    )
                except ValueError:
                    pass
                except Exception as err:
                    _LOGGER.error("Temperature curve flow error: %s", err)
                    errors["base"] = "cannot_connect"

            return self.async_show_form(step_id="temperature_curve", data_schema=schema, errors=errors)

        schema = vol.Schema(
            {
                vol.Required("connection_type", default="rtuovertcp"): vol.In(["rtuovertcp", "tcp"]),
                vol.Required("host"): str,
                vol.Required("port", default=502): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required("outdoor_sensor"): selector({"entity": {"domain": "sensor"}}),
                vol.Optional("pv_power_sensor"): selector({"entity": {"domain": "sensor"}}),
                vol.Optional("pv_battery_sensor"): selector({"entity": {"domain": "sensor"}}),
            }
        )

        if user_input is not None:
            connection_type = user_input["connection_type"]
            host = user_input["host"]
            port = user_input["port"]
            outdoor_sensor = user_input.get("outdoor_sensor")
            pv_power = user_input.get("pv_power_sensor")
            pv_battery = user_input.get("pv_battery_sensor")

            try:
                if not outdoor_sensor or not self.hass.states.get(outdoor_sensor):
                    errors["outdoor_sensor"] = "invalid_sensor"
                    raise ValueError
                if pv_power and not self.hass.states.get(pv_power):
                    errors["pv_power_sensor"] = "invalid_sensor"
                    raise ValueError
                if pv_battery and not self.hass.states.get(pv_battery):
                    errors["pv_battery_sensor"] = "invalid_sensor"
                    raise ValueError

                hub = R290HeatPumpModbusHub(host=host, port=port, mode=connection_type, connect_timeout=10.0, connect_retries=2)
                await hub.async_connect()
                await hub.async_close()

                data = {
                    "device_type": kind,
                    "connection_type": connection_type,
                    "host": host,
                    "port": port,
                    "outdoor_sensor": outdoor_sensor,
                    CONF_SLAVE: 1,
                }
                if pv_power:
                    data["pv_power_sensor"] = pv_power
                if pv_battery:
                    data["pv_battery_sensor"] = pv_battery

                return self.async_create_entry(
                    title={
                        "heating_curve": "R290 Heat Pump Heating Curve",
                        "floor_heating_curve": "R290 Heat Pump Floor Heating Curve",
                        "cooling_curve": "R290 Heat Pump Cooling Curve",
                        "hot_water_curve": "R290 Heat Pump Hot Water Curve",
                    }.get(kind, "R290 Heat Pump Temperature Curve"),
                    data=data,
                )
            except ValueError:
                pass
            except Exception as err:
                _LOGGER.error("Temperature curve flow error: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(step_id="temperature_curve", data_schema=schema, errors=errors)

    async def async_step_import(self, import_info):
        return await self.async_step_user(import_info)


class R290HeatPumpOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}
        data = self._entry.data
        opts = dict(self._entry.options)
        device_type = data.get("device_type")
        default_fast = opts.get(CONF_SCAN_INTERVAL, data.get(CONF_SCAN_INTERVAL, 60))
        default_long = opts.get("long_scan_interval", data.get("long_scan_interval", 600))
        domain_store = self.hass.data.get(DOMAIN, {})
        conn = domain_store.get("connection", {})
        default_mode = conn.get("connection_type", data.get("connection_type", "rtuovertcp"))
        default_host = conn.get("host", data.get("host", ""))
        default_port = conn.get("port", data.get("port", 502))

        if device_type == "modbus_bridge":
            schema = vol.Schema(
                {
                    vol.Required("connection_type", default=default_mode): vol.In(["rtuovertcp", "tcp"]),
                    vol.Required("host", default=default_host): str,
                    vol.Required("port", default=default_port): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                    vol.Optional("connect_timeout", default=conn.get("connect_timeout", 8.0)): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=60.0)),
                    vol.Optional("connect_retries", default=conn.get("connect_retries", 2)): selector({"number": {"min": 0, "max": 10, "step": 1, "mode": "box"}}),
                    vol.Optional("request_timeout", default=conn.get("request_timeout", 5.0)): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=30.0)),
                    vol.Optional("block_size", default=conn.get("block_size", 49)): selector({"number": {"min": 1, "max": 125, "step": 1, "mode": "box"}}),
                    vol.Optional("block_pause", default=conn.get("block_pause", 0.05)): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
                    # Action checkbox to (re)create the Lovelace dashboard on demand
                    vol.Optional("recreate_dashboard", default=False): bool,
                }
            )
        elif device_type == "cop_calculator":
            # Defaults from current data
            cur_heat = data.get("heat_meter", "")
            cur_power = data.get("power_meter")
            if isinstance(cur_power, str):
                p_default = cur_power
            else:
                p_default = ""
            trig_heat_def = bool(opts.get("cop_trigger_on_heat", data.get("cop_trigger_on_heat", True)))
            trig_power_def = bool(opts.get("cop_trigger_on_power", data.get("cop_trigger_on_power", True)))
            schema = vol.Schema(
                {
                    vol.Required("heat_meter", default=cur_heat): selector({"entity": {"domain": "sensor"}}),
                    vol.Required("power_meter", default=p_default): selector({"entity": {"domain": "sensor"}}),
                    vol.Optional("cop_trigger_on_heat", default=trig_heat_def): bool,
                    vol.Optional("cop_trigger_on_power", default=trig_power_def): bool,
                }
            )
        elif device_type in PV_CURVE_CONFIG:
            default_outdoor = opts.get("outdoor_sensor", data.get("outdoor_sensor", ""))
            default_power = opts.get("pv_power_sensor", data.get("pv_power_sensor"))
            default_battery = opts.get("pv_battery_sensor", data.get("pv_battery_sensor"))
            schema = vol.Schema(
                {
                    vol.Required("outdoor_sensor", default=default_outdoor): selector({"entity": {"domain": "sensor"}}),
                    vol.Optional("pv_power_sensor", default=default_power): selector({"entity": {"domain": "sensor"}}),
                    vol.Optional("pv_battery_sensor", default=default_battery): selector({"entity": {"domain": "sensor"}}),
                }
            )
        else:
            schema = vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=default_fast): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
                    vol.Required("long_scan_interval", default=default_long): vol.All(vol.Coerce(int), vol.Range(min=60, max=86400)),
                }
            )

        if user_input is not None:
            try:
                if device_type == "modbus_bridge":
                    mode = user_input["connection_type"]
                    host = user_input["host"]
                    port = int(user_input["port"])
                    test_hub = R290HeatPumpModbusHub(host=host, port=port, mode=mode, connect_timeout=float(user_input.get("connect_timeout", 8.0)), connect_retries=int(user_input.get("connect_retries", 2)), request_timeout=float(user_input.get("request_timeout", 5.0)))
                    await test_hub.async_connect()
                    try:
                        await test_hub.async_close()
                    except Exception:
                        pass

                    domain_store = self.hass.data.setdefault(DOMAIN, {})
                    old_hub = domain_store.get("hub")
                    new_hub = R290HeatPumpModbusHub(host=host, port=port, mode=mode, connect_timeout=float(user_input.get("connect_timeout", 8.0)), connect_retries=int(user_input.get("connect_retries", 2)), request_timeout=float(user_input.get("request_timeout", 5.0)))
                    await new_hub.async_connect()
                    domain_store["hub"] = new_hub
                    domain_store["connection"] = {
                        "host": host,
                        "port": port,
                        "connection_type": mode,
                        "connect_timeout": float(user_input.get("connect_timeout", 8.0)),
                        "connect_retries": int(user_input.get("connect_retries", 2)),
                        "request_timeout": float(user_input.get("request_timeout", 5.0)),
                        "block_size": int(user_input.get("block_size", 49)),
                        "block_pause": float(user_input.get("block_pause", 0.05)),
                    }
                    # Update all batch managers with new hub and parameters
                    batch_managers = domain_store.get("_batch_managers", {})
                    for unit, batch in batch_managers.items():
                        batch.replace_hub(new_hub)
                        batch.update_batch_params(
                            block_size=int(domain_store["connection"].get("block_size", 49)),
                            block_pause=float(domain_store["connection"].get("block_pause", 0.05)),
                        )
                    
                    # Update store references for all entries
                    for key, store in list(domain_store.items()):
                        if not isinstance(store, dict) or "entry" not in store:
                            continue
                        store["hub"] = new_hub
                    
                    if old_hub is not None:
                        try:
                            await old_hub.async_close()
                        except Exception:
                            pass

                    current = dict(self._entry.data)
                    current.update({
                        "connection_type": mode,
                        "host": host,
                        "port": port,
                        "connect_timeout": float(user_input.get("connect_timeout", 8.0)),
                        "connect_retries": int(user_input.get("connect_retries", 2)),
                        "request_timeout": float(user_input.get("request_timeout", 5.0)),
                        "block_size": int(user_input.get("block_size", 49)),
                        "block_pause": float(user_input.get("block_pause", 0.05)),
                    })
                    self.hass.config_entries.async_update_entry(self._entry, data=current)
                    # Recreate dashboard if requested
                    try:
                        if bool(user_input.get("recreate_dashboard", False)):
                            await async_setup_dashboard(self.hass)
                    except Exception:
                        _LOGGER.debug("Dashboard creation deferred or failed in options flow.")
                    try:
                        ent = self.hass.data.get(DOMAIN, {}).get("sensor.r290_heatpump_bridge_status")
                        if ent is not None:
                            await ent.async_update()
                            ent.async_write_ha_state()
                    except Exception:
                        pass
                    return self.async_create_entry(title="Options", data=self._entry.options)
                elif device_type == "cop_calculator":
                    heat = user_input["heat_meter"]
                    power_sel = user_input["power_meter"]
                    trig_heat = bool(user_input.get("cop_trigger_on_heat", True))
                    trig_power = bool(user_input.get("cop_trigger_on_power", True))
                    current = dict(self._entry.data)
                    # Remove any legacy db_url
                    current.pop("db_url", None)
                    current.update({"heat_meter": heat, "power_meter": power_sel})
                    self.hass.config_entries.async_update_entry(self._entry, data=current)
                    new_opts = dict(self._entry.options)
                    new_opts["cop_trigger_on_heat"] = trig_heat
                    new_opts["cop_trigger_on_power"] = trig_power
                    return self.async_create_entry(title="Options", data=new_opts)
                elif device_type in PV_CURVE_CONFIG:
                    new_opts = dict(self._entry.options)

                    outdoor_sensor = user_input["outdoor_sensor"]
                    pv_power = user_input.get("pv_power_sensor")
                    pv_battery = user_input.get("pv_battery_sensor")

                    if not outdoor_sensor or not self.hass.states.get(outdoor_sensor):
                        errors["outdoor_sensor"] = "invalid_sensor"
                        raise ValueError
                    if pv_power and not self.hass.states.get(pv_power):
                        errors["pv_power_sensor"] = "invalid_sensor"
                        raise ValueError
                    if pv_battery and not self.hass.states.get(pv_battery):
                        errors["pv_battery_sensor"] = "invalid_sensor"
                        raise ValueError

                    current_data = dict(self._entry.data)
                    current_data["outdoor_sensor"] = outdoor_sensor
                    self.hass.config_entries.async_update_entry(self._entry, data=current_data)

                    if pv_power in (None, ""):
                        new_opts.pop("pv_power_sensor", None)
                    else:
                        new_opts["pv_power_sensor"] = pv_power

                    if pv_battery in (None, ""):
                        new_opts.pop("pv_battery_sensor", None)
                    else:
                        new_opts["pv_battery_sensor"] = pv_battery

                    return self.async_create_entry(title="Options", data=new_opts)
                else:
                    fast = int(user_input[CONF_SCAN_INTERVAL])
                    slow = int(user_input["long_scan_interval"])
                    return self.async_create_entry(title="Options", data={CONF_SCAN_INTERVAL: fast, "long_scan_interval": slow})
            except Exception as err:
                _LOGGER.error("Options flow error: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)







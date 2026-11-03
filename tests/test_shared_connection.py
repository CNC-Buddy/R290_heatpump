"""Offline regression tests for shared Modbus routing and entry lifecycle.

Run: python -m unittest discover -s tests -v
Home Assistant services and the TCP client are doubles; no network is used.
The integration modules, options flow and curve callbacks execute unchanged.
"""
import asyncio
import importlib
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock


def module(name, **attrs):
    obj = types.ModuleType(name)
    obj.__dict__.update(attrs)
    sys.modules[name] = obj
    return obj


class Entry:
    def __init__(self, name, kind, **data):
        self.entry_id = self.title = name
        self.data = {"device_type": kind, **data}
        self.options = {}
        self.listeners = []
        self.unload_callbacks = []

    def add_update_listener(self, listener):
        self.listeners.append(listener)
        return lambda: self.listeners.remove(listener)

    def async_on_unload(self, callback):
        self.unload_callbacks.append(callback)


class ConfigFlow:
    def __init_subclass__(cls, **kwargs):
        pass

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}


class Registry:
    def __init__(self):
        self.devices = {}

    def async_get_or_create(self, config_entry_id, identifiers, **kwargs):
        key = frozenset(identifiers)
        if key not in self.devices:
            self.devices[key] = types.SimpleNamespace(
                id=str(len(self.devices)), config_entries={config_entry_id},
                via_device_id=None, identifiers=identifiers,
            )
        return self.devices[key]

    def async_update_device(self, device_id, **kwargs):
        device = next(d for d in self.devices.values() if d.id == device_id)
        device.__dict__.update(kwargs)


class Entity:
    def async_write_ha_state(self):
        self.state_writes = getattr(self, "state_writes", 0) + 1

    async def async_will_remove_from_hass(self):
        pass


class Coordinator:
    @classmethod
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, hass, logger, **kwargs):
        self.last_update_success = True
        self.callbacks = []
        self.stopped = False
        if kwargs.get("config_entry"):
            kwargs["config_entry"].async_on_unload(self.async_shutdown)

    def async_set_updated_data(self, data):
        self.data = data
        for callback in list(self.callbacks):
            callback()

    def async_add_listener(self, callback):
        self.callbacks.append(callback)
        return lambda: self.callbacks.remove(callback)

    async def async_request_refresh(self):
        if not self.stopped:
            self.data = await self._async_update_data()

    async def async_shutdown(self):
        self.stopped = True


def track(hass, source, callback):
    subscription = [source, callback, True]
    hass.subscriptions.append(subscription)
    return lambda: subscription.__setitem__(2, False)


class Client:
    instances = []
    operations = []
    active_io = 0
    max_active_io = 0
    connect_calls = 0
    gate = None
    entered = None

    def __init__(self, host, **kwargs):
        self.host, self.kwargs = host, kwargs
        self.connected = False
        self.closed = False
        self.instances.append(self)

    async def connect(self):
        type(self).connect_calls += 1
        await asyncio.sleep(0)
        self.connected = self.host != "offline.proxy"
        return self.connected

    def close(self):
        self.closed = True
        self.connected = False

    async def _operate(self, kind, address, value, device_id):
        cls = type(self)
        cls.active_io += 1
        cls.max_active_io = max(cls.max_active_io, cls.active_io)
        try:
            if cls.entered:
                cls.entered.set()
            if cls.gate:
                await cls.gate.wait()
            await asyncio.sleep(.001)
            cls.operations.append((self.host, self.kwargs["port"], kind, device_id, address, value))
            return types.SimpleNamespace(address=address,
                                         registers=list(range(value)) if kind == "read" else [value],
                                         isError=lambda: False)
        finally:
            cls.active_io -= 1

    async def read_holding_registers(self, address, *, count, device_id):
        return await self._operate("read", address, count, device_id)

    async def write_register(self, address, *, value, device_id):
        return await self._operate("write", address, value, device_id)


module("homeassistant")
module("homeassistant.core", HomeAssistant=object, callback=lambda f: f)
module("homeassistant.config_entries", ConfigEntry=Entry, ConfigFlow=ConfigFlow, OptionsFlow=ConfigFlow)
module("homeassistant.exceptions", ConfigEntryNotReady=type("ConfigEntryNotReady", (Exception,), {}),
       HomeAssistantError=type("HomeAssistantError", (Exception,), {}))
module("homeassistant.const", EVENT_COMPONENT_LOADED="component_loaded", CONF_HOST="host", CONF_PORT="port", CONF_SLAVE="slave", CONF_SCAN_INTERVAL="scan_interval",
       STATE_ON="on", UnitOfTemperature=types.SimpleNamespace(CELSIUS="Â°C"),
       Platform=types.SimpleNamespace(SENSOR="sensor", NUMBER="number", SELECT="select", BUTTON="button", SWITCH="switch"))
module("homeassistant.helpers")
module("homeassistant.helpers.update_coordinator", DataUpdateCoordinator=Coordinator)
module("homeassistant.helpers.device_registry", DeviceInfo=dict, async_get=lambda hass: hass.registry,
       async_entries_for_config_entry=lambda registry, entry_id: [d for d in registry.devices.values() if entry_id in d.config_entries])
module("homeassistant.helpers.event", async_track_state_change_event=track, async_track_time_interval=track)
module("homeassistant.helpers.selector", selector=lambda value: value)
module("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
module("homeassistant.components")
module("homeassistant.components.frontend", DATA_PANELS="frontend_panels",
       async_register_built_in_panel=lambda *args, **kwargs: None)
module("homeassistant.components.sensor", SensorEntity=Entity, SensorDeviceClass=types.SimpleNamespace(TEMPERATURE="temperature"))
module("homeassistant.components.button", ButtonEntity=Entity)
module("pymodbus")
module("pymodbus.client", AsyncModbusTcpClient=Client)
module("pymodbus.exceptions", ModbusIOException=Exception, ConnectionException=Exception, ModbusException=Exception)
module("pymodbus.framer", FramerType=types.SimpleNamespace(RTU="rtu", SOCKET="socket"))
module("voluptuous", Schema=lambda value: value, Required=lambda key, **kwargs: key,
       Optional=lambda key, **kwargs: key, In=lambda value: value, All=lambda *args: args,
       Coerce=lambda value: value, Range=lambda **kwargs: kwargs)

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components/r290_heatpump"
module("r290_under_test.dashboard", async_setup_dashboard=AsyncMock())
spec = importlib.util.spec_from_file_location("r290_under_test", COMPONENT / "__init__.py", submodule_search_locations=[str(COMPONENT)])
integration = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = integration
spec.loader.exec_module(integration)
connection = importlib.import_module("r290_under_test.connection")
hub_module = importlib.import_module("r290_under_test.hub")
flow_module = importlib.import_module("r290_under_test.config_flow")
curve_module = importlib.import_module("r290_under_test.temperature_curve")
button_module = importlib.import_module("r290_under_test.button")


class ConfigEntries:
    def __init__(self, hass, entries):
        self.hass, self.entries = hass, entries
        self.reloads = []
        self.unload_ok = True
        self.setup_failure = None

    def async_entries(self, domain):
        return self.entries

    def async_update_entry(self, entry, *, data=None, options=None, title=None):
        changed = False
        if title is not None:
            entry.title = title
        for name, value in (("data", data), ("options", options)):
            if value is not None and getattr(entry, name) != value:
                setattr(entry, name, dict(value))
                changed = True
        if changed:
            for listener in entry.listeners:
                self.hass.async_create_task(listener(self.hass, entry))
        return changed

    async def async_forward_entry_setups(self, entry, platforms):
        if self.setup_failure == entry.entry_id:
            raise RuntimeError("platform setup failed")
        if entry.data["device_type"] != "modbus_bridge":
            self.hass.registry.async_get_or_create(config_entry_id=entry.entry_id, identifiers={("test", entry.entry_id)})

    async def async_unload_platforms(self, entry, platforms):
        return self.unload_ok

    async def async_reload(self, entry_id):
        self.reloads.append(entry_id)


class Hass:
    def __init__(self, entries):
        self.data = {}
        self.registry = Registry()
        self.config_entries = ConfigEntries(self, entries)
        self.tasks = set()
        self.states = {}
        self.subscriptions = []
        self.bus = types.SimpleNamespace(async_listen=lambda *args: lambda: None)
        self.services = types.SimpleNamespace(async_call=AsyncMock())

    def async_create_task(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def flush(self):
        async with asyncio.timeout(3):
            while self.tasks:
                await asyncio.gather(*list(self.tasks))


class SharedConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        Client.instances, Client.operations = [], []
        Client.active_io = Client.max_active_io = Client.connect_calls = 0
        Client.gate = Client.entered = None
        self.bridge = Entry("bridge", "modbus_bridge", host="gateway", port=502, block_size=49,
                            block_pause=.02, request_timeout=7, connect_retries=0)
        self.pump1 = Entry("pump1", "heat_pump", host="gateway", slave=1, scan_interval=10)
        self.pump2 = Entry("pump2", "heat_pump", host="gateway", slave=2, scan_interval=30)
        self.curve = Entry("curve", "heating_curve", host="gateway", slave=1, outdoor_sensor="sensor.out")
        self.curve.options = {"t_flow_max": 45, "heatcurve_active": True, "pv_power_sensor": "sensor.pv"}
        self.entries = [self.bridge, self.pump1, self.pump2, self.curve]
        self.hass = Hass(self.entries)
        self.loaded = []

    async def setup_entries(self, entries=None):
        for entry in entries or self.entries:
            await integration.async_setup_entry(self.hass, entry)
            self.loaded.append(entry)

    def runtime(self, entry):
        return self.hass.data["r290_heatpump"][entry.entry_id]

    async def asyncTearDown(self):
        Client.gate = None
        for entry in reversed(self.loaded):
            if entry.entry_id in self.hass.data.get("r290_heatpump", {}):
                self.hass.config_entries.unload_ok = True
                await integration.async_unload_entry(self.hass, entry)
        await self.hass.flush()

    async def test_all_entries_share_one_client_and_serialized_io(self):
        await self.setup_entries()
        hubs = [self.runtime(e)["hub"] for e in self.entries]
        self.assertEqual(len({id(h) for h in hubs}), 1)
        await asyncio.gather(*(h.async_read_block(i % 2 + 1, 0x40, 2) for i, h in enumerate(hubs * 3)))
        self.assertEqual(Client.connect_calls, 1)
        self.assertEqual(len(Client.instances), 1)
        self.assertEqual(Client.max_active_io, 1)
        self.assertEqual(self.runtime(self.pump1)["batch"]._block_size, 49)
        self.assertEqual(Client.instances[0].kwargs["timeout"], 7)

    async def test_reconnect_resets_old_error_and_probes_every_linked_slave(self):
        await self.setup_entries()
        hub = self.runtime(self.bridge)["hub"]
        await hub.async_pb_call(1, 0, 1, "bad_kind")
        self.assertEqual(hub.communication_status, "Error")
        old = Client.instances[-1]
        for pump in (self.pump1, self.pump2):
            self.runtime(pump)["batch"].register(0x40, pump.data["scan_interval"])
        statuses = []

        async def publish():
            statuses.append(hub.communication_status)

        self.hass.data["r290_heatpump"]["sensor.r290_heatpump_bridge_status"] = types.SimpleNamespace(
            _hub=hub, async_update=publish, async_write_ha_state=lambda: None,
        )
        button = button_module.R290HeatPumpModbusReconnectButton(self.hass, hub, {})
        await button.async_press()
        self.assertTrue(old.closed)
        self.assertEqual(Client.connect_calls, 2)
        self.assertEqual(statuses, ["Not checked", "Connected"])
        self.assertEqual(button.extra_state_attributes["verified_slaves"], [1, 2])
        self.assertIsNone(button.extra_state_attributes["last_reconnect_error"])
        self.assertFalse(button.extra_state_attributes["reconnecting"])
        self.assertTrue(self.runtime(self.pump1)["batch"]._startup_tasks)
        self.assertEqual([(op[2], op[3], op[4], op[5]) for op in Client.operations],
                         [("read", 1, 0x40, 1), ("read", 2, 0x40, 1)])

    async def test_reconnect_with_no_registered_sensors_stays_unverified(self):
        await self.setup_entries([self.bridge])
        hub = self.runtime(self.bridge)["hub"]
        button = button_module.R290HeatPumpModbusReconnectButton(self.hass, hub, {})
        await button.async_press()
        self.assertEqual(hub.communication_status, "Not checked")
        self.assertEqual(Client.operations, [])
        self.assertEqual(button.extra_state_attributes["verified_slaves"], [])

    async def test_reconnect_failure_is_raised_to_home_assistant(self):
        self.bridge.data["host"] = "offline.proxy"
        await self.setup_entries([self.bridge])
        hub = self.runtime(self.bridge)["hub"]
        button = button_module.R290HeatPumpModbusReconnectButton(self.hass, hub, {})
        with self.assertRaises(button_module.HomeAssistantError):
            await button.async_press()
        self.assertEqual(hub.communication_status, "Error")
        self.assertIn("Failed to connect", button.extra_state_attributes["last_reconnect_error"])
        self.assertFalse(button.extra_state_attributes["reconnecting"])

    async def test_reconnect_modbus_probe_failure_is_not_hidden(self):
        await self.setup_entries()
        hub = self.runtime(self.bridge)["hub"]
        self.runtime(self.pump1)["batch"].register(0x40, 10)
        hub.async_read_block = AsyncMock(side_effect=TimeoutError("No register response"))
        button = button_module.R290HeatPumpModbusReconnectButton(self.hass, hub, {})
        with self.assertRaisesRegex(button_module.HomeAssistantError, "Slave 1, register 0x0040"):
            await button.async_press()
        self.assertEqual(button.extra_state_attributes["verified_slaves"], [])

    async def test_reconnect_waits_for_inflight_write_and_coalesces_double_clicks(self):
        await self.setup_entries([self.bridge])
        hub = self.runtime(self.bridge)["hub"]
        Client.entered, Client.gate = asyncio.Event(), asyncio.Event()
        write = asyncio.create_task(hub.async_pb_write_register(1, 0x301, 35))
        await Client.entered.wait()
        old = Client.instances[-1]
        button = button_module.R290HeatPumpModbusReconnectButton(self.hass, hub, {})
        press = asyncio.create_task(button.async_press())
        await asyncio.sleep(0)
        self.assertTrue(button.extra_state_attributes["reconnecting"])
        self.assertFalse(old.closed)
        await button.async_press()
        self.assertEqual(Client.connect_calls, 1)
        Client.gate.set()
        await asyncio.gather(write, press)
        self.assertTrue(old.closed)
        self.assertEqual(Client.connect_calls, 2)
        self.assertEqual(Client.operations[-1][2], "write")

    async def test_reconnect_does_not_touch_another_bridge(self):
        await self.setup_entries()
        other = Entry("other_bridge", "modbus_bridge", host="other", connect_retries=0)
        self.entries.append(other)
        await self.setup_entries([other])
        hub = self.runtime(self.bridge)["hub"]
        other_hub = self.runtime(other)["hub"]
        await other_hub.async_connect()
        other_client = other_hub._client
        self.runtime(other)["batch"].register(0x40, 30)
        button = button_module.R290HeatPumpModbusReconnectButton(self.hass, hub, {})
        await button.async_press()
        self.assertFalse(other_client.closed)
        self.assertEqual(Client.operations, [])

    async def test_proxy_mode_propagates_to_all_entries_and_retires_each_socket(self):
        await self.setup_entries()
        flow = flow_module.R290HeatPumpOptionsFlow(self.bridge)
        flow.hass = self.hass
        result = await flow.async_step_init(dict(host="proxy", port=504, connection_type="tcp_proxy"))
        self.assertEqual(result["type"], "create_entry")
        await self.hass.flush()
        hub = self.runtime(self.bridge)["hub"]
        self.assertEqual(hub.communication_status, "Not checked")
        for entry in self.entries:
            self.assertEqual(entry.data["connection_type"], "tcp_proxy")
            self.assertIs(self.runtime(entry)["hub"], hub)
        await asyncio.gather(
            hub.async_read_block(1, 0, 3), hub.async_read_block(2, 0x4a, 1),
            hub.async_pb_write_register(2, 0x301, 35),
        )
        self.assertEqual(Client.max_active_io, 1)
        self.assertTrue(all(c.closed for c in Client.instances))
        self.assertIsNone(hub._client)
        self.assertEqual(hub.communication_status, "Connected")
        self.assertFalse(hub.diagnostics["socket_connected"])
        self.assertIsNotNone(hub.diagnostics["last_response"])
        self.assertTrue(all(c.kwargs["retries"] == 0 for c in Client.instances))
        self.assertTrue(all(c.kwargs["framer"] == "socket" for c in Client.instances))

    async def test_cancelled_proxy_request_closes_socket_without_retry(self):
        self.bridge.data["connection_type"] = "tcp_proxy"
        await self.setup_entries()
        hub = self.runtime(self.bridge)["hub"]
        Client.entered, Client.gate = asyncio.Event(), asyncio.Event()
        task = asyncio.create_task(hub.async_pb_write_register(1, 0x301, 35))
        await Client.entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertIsNone(hub._client)
        self.assertTrue(Client.instances[-1].closed)
        self.assertEqual(hub.communication_status, "Error")

    async def test_options_flow_moves_reads_and_writes_and_persists_every_entry(self):
        await self.setup_entries()
        refs = [self.runtime(e)["hub"] for e in self.entries]
        await refs[0].async_connect()
        old = Client.instances[0]
        opts = dict(self.curve.options)
        flow = flow_module.R290HeatPumpOptionsFlow(self.bridge)
        flow.hass = self.hass
        result = await flow.async_step_init(dict(host="proxy", port=1502, connection_type="tcp", block_size=12, block_pause=.15))
        self.assertEqual(result["type"], "create_entry")
        await self.hass.flush()
        self.assertTrue(old.closed)
        self.assertEqual(self.hass.config_entries.reloads, [])
        for entry, ref in zip(self.entries, refs):
            self.assertIs(self.runtime(entry)["hub"], ref)
            self.assertEqual((entry.data["host"], entry.data["port"]), ("proxy", 1502))
            self.assertEqual(self.runtime(entry)["batch"]._block_size, 12)
            await ref.async_pb_write_register(1, 0x301, 35)
            await ref.async_read_block(1, 0x301, 1)
        self.assertTrue(all(op[:2] == ("proxy", 1502) for op in Client.operations))
        self.assertEqual(Client.instances[-1].kwargs["framer"], "socket")
        self.assertEqual(self.curve.options, opts)
        self.assertEqual(self.pump1.data["scan_interval"], 10)
        self.assertEqual(self.pump2.data["scan_interval"], 30)

    async def test_startup_migrates_stale_gateway_copies_using_bridge(self):
        self.bridge.data.update(host="proxy", port=1502)
        await self.setup_entries([self.pump2, self.curve, self.pump1, self.bridge])
        for entry in self.entries:
            self.assertEqual(entry.data["host"], "proxy")
            self.assertEqual(self.runtime(entry)["hub"]._host, "proxy")
        self.assertEqual(self.curve.data["bridge_entry_id"], "bridge")

    async def test_new_runtime_after_restart_still_uses_proxy(self):
        await self.setup_entries()
        await connection.async_update_bridge_connection(self.hass, self.bridge, {**self.bridge.data, "host": "proxy", "port": 1502})
        await self.hass.flush()
        for entry in self.entries:
            await integration.async_unload_entry(self.hass, entry)
        self.loaded.clear()
        fresh_entries = [Entry(e.entry_id, **{k: v for k, v in e.data.items() if k != "device_type"}, kind=e.data["device_type"]) for e in self.entries]
        self.hass = Hass(fresh_entries)
        await self.setup_entries(fresh_entries)
        await self.runtime(fresh_entries[1])["hub"].async_read_block(1, 0x40, 1)
        self.assertEqual(Client.operations[-1][0:2], ("proxy", 1502))

    async def test_failed_proxy_validation_rolls_back_all_settings(self):
        await self.setup_entries()
        hub = self.runtime(self.bridge)["hub"]
        await hub.async_connect()
        before = [dict(e.data) for e in self.entries]
        flow = flow_module.R290HeatPumpOptionsFlow(self.bridge)
        flow.hass = self.hass
        result = await flow.async_step_init({"host": "offline.proxy", "port": 1502, "connection_type": "tcp"})
        self.assertEqual(result["errors"]["base"], "cannot_connect")
        self.assertEqual([e.data for e in self.entries], before)
        await hub.async_read_block(1, 0x40, 1)
        self.assertEqual(Client.operations[-1][0], "gateway")
        self.assertTrue(all(c.closed for c in Client.instances if c.host == "offline.proxy"))

    async def test_unloaded_and_cop_entries_are_handled_without_touching_cop(self):
        disabled = Entry("disabled", "floor_heating_curve", host="gateway", outdoor_sensor="sensor.other")
        cop = Entry("cop", "cop_calculator", heat_meter="sensor.q", power_meter="sensor.p")
        self.entries.extend([disabled, cop])
        await self.setup_entries([self.bridge, self.pump1])
        await connection.async_update_bridge_connection(self.hass, self.bridge, {**self.bridge.data, "host": "proxy"})
        await self.hass.flush()
        self.assertEqual(disabled.data["host"], "proxy")
        self.assertNotIn("host", cop.data)

    async def test_other_explicit_bridge_is_not_changed(self):
        other = Entry("other", "modbus_bridge", host="other.gateway")
        child = Entry("other_pump", "heat_pump", host="other.gateway", bridge_entry_id="other")
        self.entries.extend([other, child])
        await self.setup_entries()
        await connection.async_update_bridge_connection(self.hass, self.bridge, {**self.bridge.data, "host": "proxy"})
        self.assertEqual(child.data["host"], "other.gateway")
        self.assertEqual(self.runtime(child)["hub"]._host, "other.gateway")

    async def test_unloading_one_entry_keeps_connection_until_last_user(self):
        await self.setup_entries()
        hub = self.runtime(self.bridge)["hub"]
        await hub.async_connect()
        client = Client.instances[0]
        for entry in self.entries[:-1]:
            await integration.async_unload_entry(self.hass, entry)
            self.assertFalse(client.closed)
        await integration.async_unload_entry(self.hass, self.entries[-1])
        self.assertTrue(client.closed)
        result = await hub.async_pb_call(1, 0x40, 1, "holding")
        self.assertTrue(result.isError())
        self.assertEqual(len(Client.instances), 1)

    async def test_failed_unload_keeps_runtime_and_client(self):
        await self.setup_entries()
        hub = self.runtime(self.pump1)["hub"]
        await hub.async_connect()
        self.hass.config_entries.unload_ok = False
        self.assertFalse(await integration.async_unload_entry(self.hass, self.pump1))
        self.assertIs(self.runtime(self.pump1)["hub"], hub)
        self.assertFalse(Client.instances[0].closed)

    async def test_platform_setup_failure_releases_only_failed_owner(self):
        await self.setup_entries([self.bridge])
        self.hass.config_entries.setup_failure = self.pump1.entry_id
        with self.assertRaisesRegex(RuntimeError, "platform setup"):
            await integration.async_setup_entry(self.hass, self.pump1)
        shared = self.hass.data["r290_heatpump"]["_connections"][("bridge", "bridge")]
        self.assertEqual(shared["users"], {"bridge"})
        self.assertNotIn("pump1", self.hass.data["r290_heatpump"])

    async def test_reconfigure_waits_for_inflight_request(self):
        await self.setup_entries()
        hub = self.runtime(self.bridge)["hub"]
        Client.gate, Client.entered = asyncio.Event(), asyncio.Event()
        read = asyncio.create_task(hub.async_read_block(1, 0x40, 1))
        await Client.entered.wait()
        change = asyncio.create_task(connection.async_update_bridge_connection(self.hass, self.bridge, {**self.bridge.data, "host": "proxy"}))
        await asyncio.sleep(0)
        self.assertFalse(change.done())
        Client.gate.set()
        await asyncio.gather(read, change)
        self.assertEqual(Client.operations[-1][0], "gateway")
        await hub.async_pb_write_register(1, 0x301, 35)
        self.assertEqual(Client.operations[-1][0], "proxy")

    async def test_batch_shutdown_cancels_startup_and_future_polling(self):
        await self.setup_entries()
        batch = self.runtime(self.pump1)["batch"]
        batch.register(0x40, 10)
        coord = batch._coordinators[10]
        await integration.async_unload_entry(self.hass, self.pump1)
        await coord._async_update_data()
        await self.hass.flush()
        self.assertEqual(Client.operations, [])
        self.assertEqual(coord.callbacks, [])

    async def test_batch_publishes_without_extra_poll_and_removes_entity_listeners(self):
        await self.setup_entries()
        batch = self.runtime(self.pump1)["batch"]
        batch.register(0x40, 10)
        batch.register(0x301, 600)
        updates, cleanup = [], []
        entity = types.SimpleNamespace(
            async_schedule_update_ha_state=lambda force: updates.append((force, batch.get_cached(0x40, 10))),
            async_on_remove=cleanup.append,
        )
        batch.subscribe(entity, 10)
        updates.clear()
        batch._coordinators[600].async_set_updated_data({0x301: 35})
        self.assertEqual(updates, [])
        batch._coordinators[10].async_set_updated_data({0x40: 123})
        self.assertEqual(updates, [(True, 123)])
        self.assertEqual(Client.operations, [])
        cleanup[0]()
        batch._coordinators[10].async_set_updated_data({0x40: 124})
        self.assertEqual(updates, [(True, 123)])
        # Either HA entity removal or manager unload may happen first.
        batch.subscribe(entity, 10)
        await batch.async_shutdown()
        cleanup[-1]()
        self.assertEqual(batch._coordinators[10].callbacks, [])

    async def test_setup_during_bridge_change_uses_committed_settings(self):
        await self.setup_entries([self.bridge])
        hub = self.runtime(self.bridge)["hub"]
        await hub._lock.acquire()
        change = asyncio.create_task(connection.async_update_bridge_connection(
            self.hass, self.bridge, {**self.bridge.data, "host": "proxy"}
        ))
        await asyncio.sleep(0)
        setup = asyncio.create_task(integration.async_setup_entry(self.hass, self.pump1))
        await asyncio.sleep(0)
        hub._lock.release()
        await asyncio.gather(change, setup)
        self.loaded.append(self.pump1)
        self.assertIs(self.runtime(self.pump1)["hub"], hub)
        self.assertEqual(hub._host, "proxy")
        self.assertEqual(self.pump1.data["host"], "proxy")

    async def test_queued_listener_does_not_restore_stale_settings(self):
        await self.setup_entries()
        hub = self.runtime(self.bridge)["hub"]
        await hub._lock.acquire()
        change = asyncio.create_task(connection.async_update_bridge_connection(
            self.hass, self.bridge, {**self.bridge.data, "host": "proxy"}
        ))
        await asyncio.sleep(0)
        listener = asyncio.create_task(integration._async_update_listener(self.hass, self.bridge))
        await asyncio.sleep(0)
        hub._lock.release()
        await asyncio.gather(change, listener)
        await self.hass.flush()
        self.assertEqual(hub._host, "proxy")
        self.assertTrue(all(e.data["host"] == "proxy" for e in self.entries))

    async def test_curves_unregister_every_listener_and_cannot_write_after_removal(self):
        await self.setup_entries()
        self.hass.states["sensor.out"] = types.SimpleNamespace(state="0", attributes={})
        hub = self.runtime(self.curve)["hub"]
        curve = curve_module.R290HeatPumpTemperatureCurveSensor(self.hass, self.curve, {}, hub)
        await curve.async_added_to_hass()
        await curve._pv_callback()
        await curve.async_will_remove_from_hass()
        before = len(Client.operations)
        curve._last_written = None
        await curve._pv_callback()
        self.assertEqual(len(Client.operations), before)
        self.assertFalse(any(s[2] for s in self.hass.subscriptions))
        self.assertIsNone(curve._post_write_handle)

    async def test_device_hierarchy_preserves_separate_entries(self):
        await self.setup_entries()
        bridge_device = self.hass.registry.devices[frozenset({("r290_heatpump", "r290_heatpump_bridge")})]
        for entry in self.entries[1:]:
            child = self.hass.registry.devices[frozenset({("test", entry.entry_id)})]
            self.assertEqual(child.via_device_id, bridge_device.id)
            self.assertEqual(child.config_entries, {entry.entry_id})


if __name__ == "__main__":
    unittest.main()

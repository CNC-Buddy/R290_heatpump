"""Profile changes and consumers using the existing HA lifecycle doubles."""

import asyncio
import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch

import test_shared_connection as base
from test_polling_nextgen import Clock, Scheduler

batch_module = importlib.import_module("r290_under_test.polling.batch")
consumers = importlib.import_module("r290_under_test.polling.consumers")


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bridge = base.Entry(
            "bridge", "modbus_bridge", host="gateway", connect_retries=0
        )
        self.pump = base.Entry(
            "pump",
            "heat_pump",
            host="gateway",
            slave=2,
            scan_interval=30,
            long_scan_interval=600,
        )
        self.hass = base.Hass([self.bridge, self.pump])
        er = sys.modules.get("homeassistant.helpers.entity_registry")
        if er is None:
            er = base.module("homeassistant.helpers.entity_registry")
        self.registry = types.SimpleNamespace(async_get=lambda entity_id: None)
        self.registry_patch = patch.object(
            er, "async_get", return_value=self.registry, create=True
        )
        self.registry_patch.start()
        self.addCleanup(self.registry_patch.stop)
        base.Client.gate = base.Client.entered = None

    async def asyncTearDown(self):
        base.Client.gate = None
        for entry in (self.pump, self.bridge):
            if entry.entry_id in self.hass.data.get("r290_heatpump", {}):
                await base.integration.async_unload_entry(self.hass, entry)
        await self.hass.flush()

    async def test_profile_switch_reloads_once_and_preserves_saved_intervals(self):
        for entry in (self.bridge, self.pump):
            await base.integration.async_setup_entry(self.hass, entry)
        hub = self.hass.data["r290_heatpump"]["bridge"]["hub"]

        async def reload(entry_id):
            self.hass.config_entries.reloads.append(entry_id)
            entry = next(e for e in (self.bridge, self.pump) if e.entry_id == entry_id)
            await base.integration.async_unload_entry(self.hass, entry)
            for cleanup in entry.unload_callbacks:
                (
                    cleanup()
                    if not asyncio.iscoroutinefunction(cleanup)
                    else await cleanup()
                )
            entry.unload_callbacks.clear()
            await base.integration.async_setup_entry(self.hass, entry)

        self.hass.config_entries.async_reload = reload
        for profile in ("auto", "legacy"):
            await base.connection.async_update_bridge_connection(
                self.hass, self.bridge, {**self.bridge.data, "polling_profile": profile}
            )
            await self.hass.flush()
            runtime = self.hass.data["r290_heatpump"]["pump"]
            self.assertIs(runtime["hub"], hub)
            self.assertEqual(
                isinstance(runtime["batch"], batch_module.ScheduledBatchManager),
                profile == "auto",
            )
            self.assertEqual(self.pump.data["scan_interval"], 30)
            self.assertEqual(self.pump.data["long_scan_interval"], 600)
            self.assertEqual(self.pump.data["bridge_entry_id"], "bridge")
        self.assertEqual(
            self.hass.config_entries.reloads, ["bridge", "pump", "bridge", "pump"]
        )
        self.assertIsNone(hub.scheduler)
        self.assertEqual(len(self.hass.data["r290_heatpump"]["_connections"]), 1)

    async def test_cascade_bit_signals_tighten_both_slave_registers(self):
        self.bridge.data['polling_profile'] = 'auto'
        for entry in (self.bridge, self.pump):
            await base.integration.async_setup_entry(self.hass, entry)
        runtime = self.hass.data['r290_heatpump']
        scheduler = runtime['pump']['hub'].scheduler
        runtime['unit1'] = {'hub': runtime['pump']['hub'], 'slave': 1}
        records = {}
        for slave, owner in ((1, 'unit1'), (2, 'pump')):
            for name, fragment in (
                ('demand', 'relay_output_status_1_main_engine_circulating_water_pump_status'),
                ('defrost', 'running_status_1_system_defrost_status'),
            ):
                records[f'sensor.{name}{slave}'] = types.SimpleNamespace(
                    unique_id=f'r290_heatpump_{fragment}_slave_{slave}',
                    config_entry_id=owner, platform='r290_heatpump', disabled_by=None)
        self.registry.async_get = records.get
        runtime['control'] = {'controller': types.SimpleNamespace(config={
            'demand_entity': ['sensor.demand1', 'sensor.demand2'],
            'defrost_entities': ['sensor.defrost1', 'sensor.defrost2'],
            'max_age': 24, 'interval': 10,
        })}
        consumers.sync_requirements(self.hass, 'r290_heatpump')
        for slave in (1, 2):
            for address in (0x0000, 0x0019):
                demand = scheduler.demands[slave, address]
                self.assertEqual(demand.interval, 8)
                self.assertEqual(demand.max_age, 24)
                self.assertIn('consumer:control', demand.owners)
        runtime.pop('control')
        runtime.pop('unit1')
        consumers.sync_requirements(self.hass, 'r290_heatpump')
        self.assertFalse(any('consumer:control' in d.owners for d in scheduler.demands.values()))

    async def test_control_consumer_tightens_freshness_and_unload_removes_requirement(
        self,
    ):
        self.bridge.data["polling_profile"] = "auto"
        for entry in (self.bridge, self.pump):
            await base.integration.async_setup_entry(self.hass, entry)
        runtime = self.hass.data["r290_heatpump"]
        scheduler = runtime["pump"]["hub"].scheduler
        runtime["pump"]["batch"].register(0x4A, 600)
        self.registry.async_get = lambda entity_id: types.SimpleNamespace(
            unique_id="r290_heatpump_004a_slave_2",
            config_entry_id="pump",
            platform="r290_heatpump",
            disabled_by=None,
        )
        runtime["control"] = {
            "controller": types.SimpleNamespace(
                config={
                    "frequency_entities": ["sensor.feedback"],
                    "max_age": 24,
                    "interval": 10,
                }
            )
        }
        consumers.sync_requirements(self.hass, "r290_heatpump")
        demand = scheduler.demands[2, 0x4A]
        self.assertEqual(demand.interval, 8)
        self.assertEqual(demand.max_age, 24)
        runtime.pop("control")
        consumers.sync_requirements(self.hass, "r290_heatpump")
        self.assertEqual(demand.interval, 120)
        self.assertNotIn("consumer:control", demand.owners)

    async def test_reconfigure_waits_for_whole_write_and_readback(self):
        hub = base.hub_module.R290HeatPumpModbusHub("gateway", connect_retries=0)
        await hub.configure_polling({"polling_profile": "auto", "block_pause": 0})
        base.Client.gate, base.Client.entered = asyncio.Event(), asyncio.Event()
        before = len(base.Client.operations)
        write = asyncio.create_task(hub.async_pb_write_register(1, 0x301, 0))
        await base.Client.entered.wait()
        reconfigure = asyncio.create_task(
            hub.async_reconfigure(
                "new-gateway",
                502,
                "tcp_proxy",
                connect_timeout=8,
                connect_retries=0,
                request_timeout=5,
            )
        )
        await asyncio.sleep(0)
        self.assertFalse(reconfigure.done())
        base.Client.gate.set()
        await asyncio.gather(write, reconfigure)
        operations = base.Client.operations[before:]
        self.assertEqual(
            [(r[0], r[2]) for r in operations],
            [("gateway", "write"), ("gateway", "read")],
        )
        self.assertIsNone(hub.scheduler.get(1, 0x301))
        self.assertFalse(hub.scheduler.suspended)
        await hub.async_close()

    async def test_bad_profile_keeps_complete_setup_form_without_connecting(self):
        flow = base.flow_module.R290HeatPumpModbusConfigFlow()
        flow.hass = self.hass
        count = base.Client.connect_calls
        result = await flow.async_step_modbus_bridge(
            {
                "host": "gateway",
                "port": 502,
                "connection_type": "tcp_proxy",
                "poll_fast": 50,
                "poll_normal": 10,
            }
        )
        self.assertEqual(result["errors"]["base"], "invalid_polling_settings")
        self.assertIn("host", result["data_schema"])
        self.assertIn("poll_fast", result["data_schema"])
        self.assertEqual(base.Client.connect_calls, count)

    async def test_duplicate_bridge_rejected_before_auto_worker_is_created(self):
        duplicate = base.Entry("duplicate", "modbus_bridge", host="GATEWAY.", port=502)
        self.hass.config_entries.entries.append(duplicate)
        self.bridge.data["polling_profile"] = "auto"
        with self.assertRaisesRegex(Exception, "bridge already owns"):
            await base.connection.async_acquire_connection(self.hass, self.bridge)
        self.assertEqual(self.hass.data["r290_heatpump"].get("_connections", {}), {})


class FreshnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_reconnect_cancel_does_not_leave_scheduler_suspended(self):
        hub = base.hub_module.R290HeatPumpModbusHub("gateway", connect_retries=0)
        await hub.configure_polling({"polling_profile": "auto"})
        hub.scheduler._idle.clear()
        reconnect = asyncio.create_task(hub.async_reconnect())
        await asyncio.sleep(0)
        self.assertTrue(hub.scheduler.suspended)
        reconnect.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await reconnect
        self.assertFalse(hub.scheduler.suspended)
        hub.scheduler._idle.set()
        await hub.async_close()

    def test_transport_metrics_use_recent_window_and_nearest_rank_p95(self):
        metrics = importlib.import_module("r290_under_test.polling.metrics")
        clock = Clock()
        meter = metrics.TransportMetrics(clock)
        for duration in range(1, 21):
            start = clock()
            clock.advance(duration / 1000)
            meter.record(1, "holding", start, start, True)
        result = meter.snapshot()
        self.assertEqual(result["transactions_last_minute"], 20)
        self.assertAlmostEqual(result["latency_p95"], 0.019)
        clock.advance(61)
        self.assertEqual(meter.snapshot()["transactions_last_minute"], 0)
        self.assertIsNone(meter.snapshot()["latency_p95"])

    async def test_unrelated_reports_do_not_freshen_entity_and_constant_values_do(self):
        clock = Clock()

        async def read(unit, address, count):
            return [12] * count

        scheduler = Scheduler(
            read,
            None,
            {"polling_profile": "auto"},
            clock=clock,
            utc=lambda: str(clock()),
            start_worker=False,
        )
        batch = batch_module.ScheduledBatchManager(
            None,
            types.SimpleNamespace(scheduler=scheduler),
            1,
            config_entry=types.SimpleNamespace(entry_id="pump"),
        )
        entity = types.SimpleNamespace(
            _address=64, async_schedule_update_ha_state=Mock(), async_on_remove=Mock()
        )
        batch.register(64, 30)
        batch.register(70, 30)
        batch.subscribe(entity, 30)
        scheduler._success(1, 64, [12])
        count = entity.async_schedule_update_ha_state.call_count
        clock.advance(2)
        scheduler._success(1, 70, [20])
        self.assertEqual(entity.async_schedule_update_ha_state.call_count, count)
        clock.advance(2)
        scheduler._success(1, 64, [12])
        self.assertEqual(entity.async_schedule_update_ha_state.call_count, count + 1)
        await batch.async_shutdown()
        self.assertEqual(scheduler.demands, {})
        await scheduler.stop()

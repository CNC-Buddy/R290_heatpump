"""Offline control/safety/lifecycle tests; never talks to a real actuator."""
import asyncio
from datetime import datetime, timedelta, timezone
import importlib
import sys
import types
import unittest
from unittest.mock import AsyncMock

import test_shared_connection as fixture

sys.modules["homeassistant.core"].callback = lambda fn: fn


class Store:
    def __init__(self, *args):
        self.async_load = AsyncMock(return_value=None)
        self.async_save = AsyncMock()
        self.pending = None

    def async_delay_save(self, callback, delay):
        self.pending = callback


fixture.module("homeassistant.helpers.storage", Store=Store)
logic = importlib.import_module("r290_under_test.pump_logic")
config = importlib.import_module("r290_under_test.pump_config")
runtime = importlib.import_module("r290_under_test.pump_controller")
analytics = importlib.import_module("r290_under_test.analytics")


def sample(*, demand=True, dhw=False, defrost=False, flow=20, delta=5,
           frequency=40, speed=60, second=None):
    units = [logic.UnitReading(frequency, flow, None if delta is None else 30 + delta, 30)]
    if second:
        units.append(second)
    return logic.Snapshot(demand, dhw, defrost, tuple(units), speed)


class LogicTests(unittest.TestCase):
    def setUp(self):
        self.control = logic.PumpLogic({})

    def settled(self, reading, mode="auto"):
        self.control.decide(reading, 0, mode)
        return self.control.decide(reading, 61, mode)

    def test_startup_then_temperature_deadband(self):
        self.assertEqual(self.control.decide(sample(), 0).phase, "startup")
        self.assertEqual(self.control.decide(sample(), 61).speed, 60)

    def test_high_spread_increases_low_spread_reduces_with_bounds(self):
        self.assertEqual(self.settled(sample(delta=8)).speed, 62)
        self.control = logic.PumpLogic({})
        self.assertEqual(self.settled(sample(delta=3)).speed, 58)
        self.control = logic.PumpLogic({})
        self.assertEqual(self.settled(sample(delta=3, speed=30)).speed, 30)

    def test_largest_parallel_spread_controls_reduction(self):
        result = self.settled(sample(delta=3, second=logic.UnitReading(40, 20, 38, 30)))
        self.assertEqual(result.speed, 62)
        self.assertEqual(result.active_units, 2)

    def test_minimum_flow_per_active_unit_overrides_manual(self):
        result = self.control.decide(sample(second=logic.UnitReading(40, 10, 35, 30)), 0, "manual")
        self.assertEqual((result.phase, result.speed), ("flow_guard", 100))

    def test_inactive_unit_low_flow_does_not_block(self):
        result = self.settled(sample(second=logic.UnitReading(0, 0, None, None)))
        self.assertEqual(result.phase, "heating")

    def test_defrost_overrides_missing_data_and_zero_frequency(self):
        result = self.control.decide(sample(defrost=True, frequency=None, flow=None), 0)
        self.assertEqual((result.phase, result.speed), ("defrost", 100))
        self.assertEqual(self.control.decide(sample(), 10).phase, "startup")

    def test_zero_frequency_is_not_stop_permission(self):
        result = self.settled(sample(frequency=0))
        self.assertEqual((result.phase, result.speed), ("circulation", 60))

    def test_closed_valves_override_postrun_and_startup(self):
        idle = sample(demand=False, frequency=0)
        self.assertEqual(self.control.decide(idle, 0).phase, "idle")
        self.assertEqual(self.control.decide(idle, 119).speed, 0)
        self.assertEqual(self.control.decide(idle, 120).speed, 0)
        self.assertEqual(self.control.decide(sample(), 121).phase, "startup")
        self.assertEqual(self.control.decide(idle, 122).speed, 0)

    def test_closed_valves_override_defrost_compressor_and_invalid_data(self):
        for reading in (sample(demand=False, defrost=True), sample(demand=False),
                        sample(demand=False, frequency=None, dhw=None, flow=None)):
            with self.subTest(reading=reading):
                result = self.control.decide(reading, 0)
                self.assertEqual(result.speed, 0)
                self.assertTrue(result.command_allowed)

    def test_unknown_demand_cannot_start_or_raise_output(self):
        for speed in (0, 30, 80, None):
            result = self.control.decide(sample(demand=None, defrost=True, speed=speed), 0)
            self.assertEqual(result.speed, speed or 0)
            self.assertFalse(result.command_allowed)

    def test_lost_demand_never_causes_stop(self):
        result = self.control.decide(sample(demand=None, frequency=0, speed=80), 0)
        self.assertEqual((result.phase, result.speed), ("fallback", 80))

    def test_unknown_feedback_does_not_reapply_old_proposal(self):
        self.control.decide(sample(demand=None, speed=80), 0)
        result = self.control.decide(sample(demand=None, speed=None), 10)
        self.assertFalse(result.command_allowed)

    def test_missing_flow_and_invalid_delta_hold_safe_output(self):
        self.assertEqual(self.settled(sample(flow=None)).phase, "fallback")
        self.control = logic.PumpLogic({})
        self.assertEqual(self.settled(sample(delta=None)).phase, "fallback")
        self.control = logic.PumpLogic({})
        self.assertEqual(self.settled(sample(delta=-5)).phase, "fallback")

    def test_dhw_uses_separate_target(self):
        self.control = logic.PumpLogic({"dhw_delta": 3})
        d = self.settled(sample(delta=5, dhw=True))
        self.assertEqual((d.phase, d.speed, d.target_delta), ("dhw", 62, 3))

    def test_no_faster_adjustment_than_interval(self):
        self.assertEqual(self.settled(sample(delta=8)).speed, 62)
        self.assertEqual(self.control.decide(sample(delta=8, speed=62), 70).speed, 62)
        self.assertEqual(self.control.decide(sample(delta=8, speed=62), 92).speed, 64)

    def test_invalid_settings_rejected(self):
        for values in ({"min_speed": 90}, {"max_speed": 50}, {"safe_speed": float("nan")},
                       {"interval": 300, "max_age": 60}, {"output_min": 10, "output_max": 0},
                       {"commissioned": "yes"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                logic.PumpLogic(values)


def put(hass, entity_id, value, unit=None, age=0, **attributes):
    stamp = datetime.now(timezone.utc) - timedelta(seconds=age)
    if unit:
        attributes["unit_of_measurement"] = unit
    state = types.SimpleNamespace(entity_id=entity_id, state=str(value), attributes=attributes,
                                  last_reported=stamp, last_updated=stamp,
                                  last_changed=stamp - timedelta(days=1))
    hass.states[entity_id] = state
    return state


class ControllerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.entry = fixture.Entry("aux", "auxiliary_pump",
            speed_entity="number.pump", enable_entity="switch.enable",
            demand_entity="sensor.demand", dhw_entity="binary_sensor.dhw",
            defrost_entities=["sensor.defrost"], frequency_entities=["sensor.hz"],
            flow_entities=["sensor.flow"], supply_entities=["sensor.supply"],
            return_entities=["sensor.return"], legacy_automations=["automation.old"],
            commissioned=True, output_max=10)
        self.entry.data["name"] = "Aux"
        self.hass = fixture.Hass([self.entry])
        put(self.hass, "number.pump", 6, min=0, max=10, step=.1)
        put(self.hass, "switch.enable", "on")
        put(self.hass, "sensor.demand", "on")
        put(self.hass, "binary_sensor.dhw", "off")
        put(self.hass, "sensor.defrost", "off")
        put(self.hass, "sensor.hz", 40, "Hz")
        put(self.hass, "sensor.flow", 1.2, "m³/h")
        put(self.hass, "sensor.supply", 35, "°C")
        put(self.hass, "sensor.return", 86, "°F")
        put(self.hass, "automation.old", "off")
        self.controller = runtime.PumpController(self.hass, self.entry)
        await self.controller.async_start()

    async def asyncTearDown(self):
        await self.controller.async_stop()
        await self.hass.flush()

    async def test_observer_startup_and_reload_never_write(self):
        await self.controller.async_evaluate()
        self.assertEqual(self.controller.mode, "observe")
        self.hass.services.async_call.assert_not_awaited()
        other = runtime.PumpController(self.hass, self.entry)
        self.assertEqual(other.mode, "observe")

    async def test_service_recovery_blocks_automatic_and_manual_control(self):
        self.hass.data.setdefault('r290_heatpump',{})['_service']=types.SimpleNamespace(pending={'hp':{'state':'recovery_required'}})
        for mode in ['auto','manual']:
            with self.assertRaises(Exception):await self.controller.async_set_mode(mode)
        self.hass.services.async_call.assert_not_awaited()

    async def restart_saved(self, saved):
        await self.controller.async_stop()
        self.hass.services.async_call.reset_mock()
        self.controller = runtime.PumpController(self.hass, self.entry)
        self.controller._store.async_load.return_value = saved
        await self.controller.async_start()

    async def test_explicit_auto_ownership_survives_reload_and_stops_closed_path(self):
        await self.controller.async_set_mode('auto')
        saved = self.controller._storage_state()
        put(self.hass, 'sensor.demand', 'off')
        put(self.hass, 'sensor.hz', 0, 'Hz')
        await self.restart_saved(saved)
        self.assertEqual(self.controller.mode, 'auto')
        self.assertEqual(self.controller.decision.speed, 0)
        self.hass.services.async_call.assert_awaited_once_with('switch', 'turn_off', {'entity_id':'switch.enable'}, blocking=True)

    async def test_reload_waits_for_known_demand_without_starting(self):
        await self.controller.async_set_mode('auto')
        saved = self.controller._storage_state()
        put(self.hass, 'sensor.demand', 'unavailable')
        put(self.hass, 'switch.enable', 'off')
        await self.restart_saved(saved)
        self.assertEqual(self.controller.mode, 'observe')
        self.assertEqual(self.controller.diagnostics()['pending_mode'], 'auto')
        self.hass.services.async_call.assert_not_awaited()
        put(self.hass, 'sensor.demand', 'on')
        await self.controller.async_evaluate()
        self.assertEqual(self.controller.mode, 'auto')
        self.assertEqual(self.hass.services.async_call.await_count, 2)

    async def test_fault_and_explicit_observe_do_not_rearm_on_reload(self):
        for kind in ('observe','fault'):
            await self.controller.async_set_mode('auto')
            if kind == 'observe':
                await self.controller.async_set_mode('observe')
            else:
                put(self.hass, 'automation.old', 'on')
                await self.controller.async_evaluate()
                put(self.hass, 'automation.old', 'off')
            await self.restart_saved(self.controller._storage_state())
            self.assertEqual(self.controller.mode, 'observe')
            self.assertIsNone(self.controller._resume_mode)
            self.hass.services.async_call.assert_not_awaited()

    async def test_saved_ownership_cannot_transfer_to_changed_mapping(self):
        await self.controller.async_set_mode('auto')
        saved = self.controller._storage_state()
        put(self.hass, 'switch.new_enable', 'on')
        self.entry.options['enable_entity'] = 'switch.new_enable'
        await self.restart_saved(saved)
        self.assertEqual(self.controller.mode, 'observe')
        self.hass.services.async_call.assert_not_awaited()

    async def test_legacy_store_does_not_infer_permission_from_records(self):
        await self.restart_saved({'records':[{'kind':'mode','mode':'auto'}]})
        self.assertEqual(self.controller.mode, 'observe')
        self.hass.services.async_call.assert_not_awaited()

    async def test_false_demand_stops_immediately_despite_missing_dhw_and_postrun(self):
        await self.controller.async_set_mode('auto')
        self.hass.services.async_call.reset_mock()
        put(self.hass, 'sensor.demand', 'off')
        put(self.hass, 'binary_sensor.dhw', 'unavailable')
        await self.controller.async_evaluate()
        self.assertEqual(self.controller.decision.speed, 0)
        self.hass.services.async_call.assert_awaited_once_with('switch', 'turn_off', {'entity_id':'switch.enable'}, blocking=True)

    async def test_unknown_demand_does_not_send_start_command(self):
        await self.controller.async_set_mode('auto')
        self.hass.services.async_call.reset_mock()
        put(self.hass, 'sensor.demand', 'unavailable')
        put(self.hass, 'switch.enable', 'off')
        await self.controller.async_evaluate()
        self.assertFalse(self.controller.decision.command_allowed)
        self.hass.services.async_call.assert_not_awaited()

    async def test_conversion_and_last_reported_not_last_changed(self):
        s = self.controller.sample()
        self.assertEqual(s.actual_speed, 60)
        self.assertEqual(s.units[0].flow, 20)
        self.assertEqual(s.units[0].return_temperature, 30)
        self.assertEqual(s.units[0].frequency, 40)

    async def test_legacy_demand_scalar_is_normalized_without_changing_entry(self):
        self.assertEqual(self.controller.config['demand_entity'], ['sensor.demand'])
        self.assertEqual(self.entry.data['demand_entity'], 'sensor.demand')

    async def test_cascade_demand_three_valued_or(self):
        self.controller.config['demand_entity'] = ['sensor.demand', 'sensor.demand2']
        for a, b, expected in (
            ('off', 'off', False), ('on', 'off', True), ('off', 'on', True),
            ('off', 'unavailable', None), ('unknown', 'off', None),
            ('on', 'unavailable', True), ('unknown', 'on', True),
            ('unknown', 'unavailable', None), ('Heating', 'off', None),
        ):
            with self.subTest(a=a, b=b):
                put(self.hass, 'sensor.demand', a)
                put(self.hass, 'sensor.demand2', b)
                self.assertIs(self.controller.sample().demand, expected)
        self.hass.services.async_call.assert_not_awaited()

    async def test_second_unit_circulation_without_compressor_prevents_stop(self):
        await self.controller.async_stop()
        self.entry.data['demand_entity'] = ['sensor.demand', 'sensor.demand2']
        put(self.hass, 'sensor.demand', 'off')
        put(self.hass, 'sensor.demand2', 'on')
        put(self.hass, 'sensor.hz', 0, 'Hz')
        self.controller = runtime.PumpController(self.hass, self.entry)
        await self.controller.async_start()
        self.controller.logic = logic.PumpLogic(self.controller.config)
        self.controller.logic.decide(self.controller.sample(), 0)
        result = self.controller.logic.decide(self.controller.sample(), 61)
        self.assertEqual(result.phase, 'circulation')
        self.assertGreater(result.speed, 0)
        self.assertTrue(any('sensor.demand2' in sub[0] for sub in self.hass.subscriptions
                            if isinstance(sub[0], list) and sub[2]))
        ids = {item['entity_id'] for item in self.controller.diagnostics()['inputs']}
        self.assertIn('sensor.demand2', ids)
        self.hass.services.async_call.assert_not_awaited()

    async def test_missing_cascade_source_prevents_idle_after_postrun(self):
        self.controller.config['demand_entity'] = ['sensor.demand', 'sensor.missing']
        put(self.hass, 'sensor.demand', 'off')
        put(self.hass, 'sensor.hz', 0, 'Hz')
        result = self.controller.logic.decide(self.controller.sample(), 10000)
        self.assertEqual(result.phase, 'fallback')
        self.assertGreaterEqual(result.speed, self.controller.config['safe_speed'])

    async def test_second_unit_defrost_overrides_unavailable_first(self):
        self.controller.config['defrost_entities'] = ['sensor.defrost', 'sensor.defrost2']
        put(self.hass, 'sensor.defrost', 'unavailable')
        put(self.hass, 'sensor.defrost2', 'on')
        result = self.controller.logic.decide(self.controller.sample(), 10000)
        self.assertEqual(result.phase, 'defrost')
        self.assertEqual(result.speed, self.controller.config['defrost_speed'])

    async def test_active_command_sets_speed_before_enable(self):
        await self.controller.async_set_mode("auto")
        calls = self.hass.services.async_call.await_args_list
        self.assertEqual(calls[0].args[:2], ("number", "set_value"))
        self.assertEqual(calls[0].args[2]["value"], 6)
        self.assertEqual(calls[1].args[:2], ("switch", "turn_on"))

    async def test_repeated_evaluation_does_not_spam_commands(self):
        await self.controller.async_set_mode("auto")
        await self.controller.async_evaluate()
        await self.controller.async_evaluate()
        self.assertEqual(self.hass.services.async_call.await_count, 2)

    async def test_stale_or_unknown_critical_signals_block_arming(self):
        put(self.hass, "sensor.hz", 40, "Hz", age=1000)
        with self.assertRaises(Exception):
            await self.controller.async_set_mode("auto")
        self.hass.services.async_call.assert_not_awaited()

    async def test_active_stale_temperature_enters_fallback(self):
        await self.controller.async_set_mode("auto")
        self.controller.logic.running_since = 0
        put(self.hass, "sensor.supply", 35, "°C", age=1000)
        await self.controller.async_evaluate()
        self.assertEqual(self.controller.decision.phase, "fallback")
        self.assertGreaterEqual(self.controller.decision.speed, 60)

    async def test_non_boolean_status_is_not_treated_as_off(self):
        put(self.hass, "sensor.defrost", "Heating")
        self.assertIsNone(self.controller.sample().defrost)

    async def test_commissioning_and_automation_conflict_block_control(self):
        self.controller.config["commissioned"] = False
        with self.assertRaises(Exception):
            await self.controller.async_set_mode("auto")
        self.controller.config["commissioned"] = True
        put(self.hass, "automation.old", "on")
        with self.assertRaises(Exception):
            await self.controller.async_set_mode("manual")
        self.hass.services.async_call.assert_not_awaited()

    async def test_new_conflict_relinquishes_without_writing(self):
        await self.controller.async_set_mode("auto")
        self.hass.services.async_call.reset_mock()
        put(self.hass, "automation.old", "on")
        await self.controller.async_evaluate()
        self.assertEqual(self.controller.mode, "observe")
        self.assertEqual(self.controller.error, "automation_conflict")
        self.hass.services.async_call.assert_not_awaited()

    async def test_failed_write_latches_observer_and_is_not_retried(self):
        self.hass.services.async_call.side_effect = RuntimeError("timeout")
        await self.controller.async_set_mode("auto")
        self.assertEqual(self.controller.mode, "observe")
        self.assertEqual(self.controller.error, "timeout")
        await self.controller.async_evaluate()
        self.assertEqual(self.hass.services.async_call.await_count, 1)

    async def test_missing_actuator_feedback_latches_observer(self):
        await self.controller.async_set_mode("auto")
        self.controller._feedback_since = 0
        put(self.hass, "number.pump", 1, min=0, max=10, step=.1)
        await self.controller.async_evaluate()
        self.assertEqual(self.controller.mode, "observe")
        self.assertEqual(self.controller.error, "actuator_feedback")

    async def test_manual_value_cannot_write_before_failed_mode_change(self):
        await self.controller.async_set_mode("manual")
        self.hass.services.async_call.reset_mock()
        with self.assertRaises(Exception):
            await self.controller.async_set_mode("observe", manual_speed=80)
        self.assertEqual(self.controller.config["manual_speed"], 60)
        self.hass.services.async_call.assert_not_awaited()

    async def test_light_and_fan_actuators_use_native_services(self):
        for entity_id, attrs, service, expected in (
            ("light.pump", {"supported_color_modes": ["brightness"], "brightness": 153}, "turn_on", {"brightness_pct": 60}),
            ("fan.pump", {"supported_features": 1, "percentage": 60}, "set_percentage", {"percentage": 60}),
        ):
            put(self.hass, entity_id, "on", **attrs)
            values = {**self.entry.data, "speed_entity": entity_id, "enable_entity": ""}
            config.validate_config(self.hass, values, exclude_entry="aux")
            self.controller.config.update(values)
            self.hass.services.async_call.reset_mock()
            await self.controller._apply(60)
            self.hass.services.async_call.assert_awaited_once_with(entity_id.split('.')[0], service, {"entity_id": entity_id, **expected}, blocking=True)
            self.hass.services.async_call.reset_mock()
            await self.controller._apply(0)
            self.hass.services.async_call.assert_awaited_once_with(entity_id.split('.')[0], "turn_off", {"entity_id": entity_id}, blocking=True)

    async def test_flow_and_options_preserve_mapping_without_modbus(self):
        flow = fixture.flow_module.R290HeatPumpModbusConfigFlow()
        flow.hass = self.hass
        mappings = {k: v for k, v in self.entry.data.items() if k in config.ENTITY_FIELDS or k == "name"}
        first = await flow.async_step_auxiliary_pump(mappings)
        self.assertEqual(first["step_id"], "pump_limits")
        self.hass.config_entries.entries.clear()
        result = await flow.async_step_pump_limits({**logic.DEFAULTS, "output_max": 10})
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["device_type"], "auxiliary_pump")
        self.assertNotIn("host", result["data"])
        options = fixture.flow_module.R290HeatPumpOptionsFlow(self.entry)
        options.hass = self.hass
        mappings.pop("legacy_automations")
        await options.async_step_init(mappings)
        result = await options.async_step_pump_limits({**logic.DEFAULTS, "output_max": 10})
        self.assertEqual(result["data"]["legacy_automations"], [])

    async def test_observe_and_unload_do_not_issue_stop(self):
        await self.controller.async_set_mode("auto")
        self.hass.services.async_call.reset_mock()
        await self.controller.async_set_mode("observe")
        await self.controller.async_stop()
        self.controller._schedule()
        await self.controller.async_evaluate()
        self.hass.services.async_call.assert_not_awaited()
        self.assertTrue(all(not sub[2] for sub in self.hass.subscriptions))

    async def test_duplicate_actuator_and_misaligned_lists_rejected(self):
        other = fixture.Entry("other", "auxiliary_pump", speed_entity="number.pump")
        self.hass.config_entries.entries.append(other)
        with self.assertRaises(ValueError):
            config.validate_config(self.hass, self.entry.data, exclude_entry="aux")
        self.hass.config_entries.entries.remove(other)
        with self.assertRaises(ValueError):
            config.validate_config(self.hass, {**self.entry.data, "flow_entities": []}, exclude_entry="aux")

    async def test_number_without_enable_is_rejected(self):
        with self.assertRaises(ValueError):
            config.validate_config(self.hass, {**self.entry.data, "enable_entity": ""}, exclude_entry="aux")

    async def test_quantized_number_feedback_does_not_cause_repeated_writes(self):
        put(self.hass, "number.pump", 6, min=0, max=10, step=1)
        self.controller.config["max_step"] = 10
        await self.controller.async_set_mode("manual", manual_speed=65)
        self.controller.logic.running_since = 0
        await self.controller.async_evaluate()
        self.assertEqual(self.controller.last_command, 60)
        count = self.hass.services.async_call.await_count
        await self.controller.async_evaluate()
        self.assertEqual(self.hass.services.async_call.await_count, count)

    async def test_calibration_must_fit_native_output_step(self):
        put(self.hass, "number.pump", 6, min=0, max=10, step=1)
        with self.assertRaises(ValueError):
            config.validate_config(self.hass, {**self.entry.data, "output_min": .5, "max_step": 10}, exclude_entry="aux")

    async def test_auxiliary_entry_never_acquires_bridge(self):
        self.assertIsNone(fixture.connection.resolve_bridge(self.hass, self.entry))
        await fixture.integration.async_setup_entry(self.hass, self.entry)
        self.assertNotIn("hub", self.hass.data["r290_heatpump"]["aux"])
        await fixture.integration.async_unload_entry(self.hass, self.entry)


class AnalyticsTests(unittest.TestCase):
    def test_counter_delay_marked_uncertain_no_daily_interpolation(self):
        result = analytics.summarize([[0, 100], [3600, 110], [86400, 200]], 0, 86400, kind="energy")
        self.assertEqual(result["delta"], 100)
        self.assertTrue(result["uncertain"])
        self.assertEqual(result["increments"][-1]["value"], 90)

    def test_reset_excluded_and_flagged(self):
        r = analytics.summarize([[0, 100], [10, 105], [20, 0], [30, 2]], 0, 30, kind="energy")
        self.assertEqual((r["delta"], r["resets"]), (7, 1))
        self.assertTrue(r["uncertain"])

    def test_unknown_gap_not_runtime_or_start(self):
        r = analytics.summarize([[0, 0], [10, 40], [20, None], [40, 40], [50, 0]], 0, 60)
        self.assertEqual(r["starts"], 1)
        self.assertAlmostEqual(r["runtime_hours"], 20/3600)
        self.assertAlmostEqual(r["coverage"], 40/60)

    def test_power_integral_uses_irregular_state_durations(self):
        r = analytics.summarize([[0, 100], [1800, 0]], 0, 3600)
        self.assertEqual(r["integral"], 50)

    def test_downsampling_keeps_spike_and_missing_value(self):
        points = [[i, 0] for i in range(10000)]
        points[100][1], points[150][1] = 100, None
        reduced = analytics.thin(points)
        self.assertIn([100, 100], [list(p) for p in reduced])
        self.assertIn([150, None], [list(p) for p in reduced])
        self.assertLess(len(reduced), 1000)


if __name__ == "__main__":
    unittest.main()

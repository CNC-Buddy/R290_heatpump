"""Exercise real panel handlers with HA transport/registry doubles."""
import asyncio
from collections import deque
import importlib
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock

import test_shared_connection as fixture
from test_auxiliary_pump import Store, put

sys.modules["voluptuous"].Any = lambda *args: args
fixture.module("homeassistant.components.websocket_api",
               websocket_command=lambda schema: lambda fn: fn,
               async_response=lambda fn: fn, async_register_command=Mock())
fixture.module("homeassistant.components.http", StaticPathConfig=lambda *args: args)
fixture.module("homeassistant.components.panel_custom", async_register_panel=AsyncMock())
fixture.module("homeassistant.helpers.entity_registry", async_get=lambda hass: hass.entity_registry)
panel = importlib.import_module("r290_under_test.panel")


class PanelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.entry = fixture.Entry("hp", "heat_pump", slave=1)
        self.hass = fixture.Hass([self.entry])
        self.hass.data["r290_heatpump"] = {"_panel": {
            "store": Store(), "settings": {}, "audit": deque(maxlen=300),
            "write_lock": asyncio.Lock(), "history_lock": asyncio.Lock()}}
        self.hass.config = types.SimpleNamespace(components={"recorder"})
        self.hass.entity_registry = types.SimpleNamespace(entities={})
        for entity_id in ("number.p099", "select.mode", "switch.curve"):
            self.hass.entity_registry.entities[entity_id] = types.SimpleNamespace(
                entity_id=entity_id, config_entry_id="hp", platform="r290_heatpump",
                disabled_by=None, unique_id=entity_id, name=None, original_name="Parameter")
        put(self.hass, "number.p099", 3, min=1, max=15, step=1)
        put(self.hass, "select.mode", "heating", options=["heating", "dhw"])
        put(self.hass, "switch.curve", "off")
        self.connection = types.SimpleNamespace(
            subscriptions={},
            user=types.SimpleNamespace(is_admin=True, id="test-user"),
            send_result=Mock(), send_error=Mock(), context=lambda msg: "test-context")

    async def parameter(self, **values):
        msg = dict(id=1, entity_id="number.p099", expected="3", value="5", confirmed=True)
        msg.update(values)
        await panel.ws_parameter(self.hass, self.connection, msg)

    def error_code(self):
        return self.connection.send_error.call_args.args[1]

    async def test_non_admin_cannot_read_or_write(self):
        self.connection.user.is_admin = False
        await panel.ws_panel(self.hass, self.connection, {"id": 1})
        self.assertEqual(self.error_code(), "unauthorized")
        await self.parameter()
        self.hass.services.async_call.assert_not_awaited()

    async def test_panel_reports_are_scoped_and_not_faked_from_state_changes(self):
        energy = put(self.hass, "sensor.heat", 500, "kWh", age=7200)
        unrelated = put(self.hass, "sensor.private", 99)
        settings = self.hass.data["r290_heatpump"]["_panel"]["settings"]
        settings["heat_energy_entity"] = "sensor.heat"
        parameter = self.hass.states["number.p099"]
        del parameter.last_reported
        await panel.ws_panel(self.hass, self.connection, {"id": 1})
        result = self.connection.send_result.call_args.args[1]
        self.assertEqual(result["reports"]["sensor.heat"], energy.last_reported.isoformat())
        self.assertNotIn(unrelated.entity_id, result["reports"])
        self.assertNotIn(parameter.entity_id, result["reports"])
        self.hass.services.async_call.assert_not_awaited()

    async def test_confirmed_change_carries_context_and_audit(self):
        await self.parameter()
        call = self.hass.services.async_call.await_args
        self.assertEqual(call.args, ("number", "set_value", {"entity_id": "number.p099", "value": 5.0}))
        self.assertEqual(call.kwargs["context"], "test-context")
        record = self.hass.data["r290_heatpump"]["_panel"]["audit"][-1]
        self.assertEqual((record["before"], record["requested"], record["result"]), ("3", "5", "sent"))

    async def test_dhw_display_reuses_unambiguous_cop_signal_without_pump_controller(self):
        cop = fixture.Entry('cop', 'cop_calculator', cop_split_enabled=True,
                            cop_split_sensor='binary_sensor.dhw')
        self.hass.config_entries.entries.append(cop)
        put(self.hass, 'binary_sensor.dhw', 'on')
        await panel.ws_panel(self.hass, self.connection, {'id': 1})
        result = self.connection.send_result.call_args.args[1]
        self.assertEqual(result['sources']['dhw_entity'], 'binary_sensor.dhw')
        self.assertEqual(result['controllers'], [])
        self.assertIn('binary_sensor.dhw', result['reports'])
        other = fixture.Entry('other', 'cop_calculator', cop_split_enabled=True,
                              cop_split_sensor='binary_sensor.other')
        self.hass.config_entries.entries.append(other)
        await panel.ws_panel(self.hass, self.connection, {'id': 2})
        self.assertNotIn('dhw_entity', self.connection.send_result.call_args.args[1]['sources'])
        other.disabled_by = 'user'
        await panel.ws_panel(self.hass, self.connection, {'id': 3})
        self.assertEqual(self.connection.send_result.call_args.args[1]['sources']['dhw_entity'], 'binary_sensor.dhw')
        self.hass.services.async_call.assert_not_awaited()

    async def test_hydraulic_status_mappings_accept_switches_without_writing_them(self):
        put(self.hass, 'binary_sensor.dhw', 'on')
        put(self.hass, 'input_boolean.radiators', 'on')
        settings = {'dhw_entity': 'binary_sensor.dhw', 'buffer_charge_entity': 'switch.curve',
                    'radiator_pump_entity': 'input_boolean.radiators'}
        await panel.ws_settings(self.hass, self.connection, {'id': 1, 'settings': settings})
        self.connection.send_error.assert_not_called()
        self.assertEqual(self.hass.data['r290_heatpump']['_panel']['settings'], settings)
        self.assertTrue(set(settings.values()) <= panel._allowed_history(self.hass))
        for bad in ('number.p099', 'binary_sensor.missing'):
            await panel.ws_settings(self.hass, self.connection, {'id': 2, 'settings': {'dhw_entity': bad}})
            self.assertEqual(self.error_code(), 'invalid_entity')
        self.assertEqual(self.hass.data['r290_heatpump']['_panel']['settings'], settings)
        self.hass.services.async_call.assert_not_awaited()

    async def test_confirmation_and_stale_expected_value_are_enforced(self):
        await self.parameter(confirmed=False)
        self.assertEqual(self.error_code(), "confirmation_required")
        await self.parameter(expected="2")
        self.assertEqual(self.error_code(), "state_changed")
        self.hass.services.async_call.assert_not_awaited()

    async def test_unrelated_entities_cannot_be_written(self):
        put(self.hass, "number.unrelated", 1, min=0, max=10, step=1)
        await self.parameter(entity_id="number.unrelated", expected="1")
        self.assertEqual(self.error_code(), "invalid_entity")
        self.hass.services.async_call.assert_not_awaited()

    async def test_nan_range_and_step_are_validated(self):
        for value in ("nan", "inf", "16", "0", "3.1"):
            await self.parameter(value=value)
            self.assertEqual(self.error_code(), "invalid_value")
        self.hass.services.async_call.assert_not_awaited()

    async def test_select_option_and_switch_service_are_restricted(self):
        await self.parameter(entity_id="select.mode", expected="heating", value="invalid")
        self.assertEqual(self.error_code(), "invalid_value")
        await self.parameter(entity_id="select.mode", expected="heating", value="dhw")
        self.assertEqual(self.hass.services.async_call.await_args.args[:2], ("select", "select_option"))
        await self.parameter(entity_id="switch.curve", expected="off", value="on")
        self.assertEqual(self.hass.services.async_call.await_args.args[:2], ("switch", "turn_on"))

    async def test_service_failure_is_returned_and_audited(self):
        self.hass.services.async_call.side_effect = RuntimeError("device offline")
        await self.parameter()
        self.assertEqual(self.error_code(), "write_failed")
        self.assertEqual(self.hass.data["r290_heatpump"]["_panel"]["audit"][-1]["result"], "failed")

    async def test_auxiliary_controls_cannot_bypass_dedicated_endpoint(self):
        self.entry.data["device_type"] = "auxiliary_pump"
        await self.parameter()
        self.assertEqual(self.error_code(), "invalid_entity")
        self.hass.services.async_call.assert_not_awaited()

    async def test_settings_save_only_valid_sources_and_never_write_devices(self):
        put(self.hass, "sensor.energy", 100, "kWh")
        settings = {"name": "Plant", "tank_liters": 300, "buffer_liters": 1000, "heat_energy_entity": "sensor.energy"}
        await panel.ws_settings(self.hass, self.connection, {"id": 1, "settings": settings})
        self.assertEqual(self.hass.data["r290_heatpump"]["_panel"]["settings"], settings)
        self.hass.services.async_call.assert_not_awaited()
        await panel.ws_settings(self.hass, self.connection, {"id": 2, "settings": {"heat_energy_entity": "switch.curve"}})
        self.assertEqual(self.error_code(), "invalid_entity")

    async def test_history_scope_size_and_recorder_availability(self):
        await panel.ws_history(self.hass, self.connection, {"id": 1, "entity_ids": ["sensor.private"], "days": 1})
        self.assertEqual(self.error_code(), "invalid_entities")
        self.hass.config.components.clear()
        await panel.ws_history(self.hass, self.connection, {"id": 1, "entity_ids": ["number.p099"], "days": 1})
        self.assertEqual(self.error_code(), "recorder_unavailable")

    async def test_unavailable_pump_returns_error_without_action(self):
        await panel.ws_pump(self.hass, self.connection, {"id": 1, "entry_id": "missing", "confirmed": True, "mode": "auto"})
        self.assertEqual(self.error_code(), "not_loaded")
        self.hass.services.async_call.assert_not_awaited()

    async def test_plant_save_is_passive_and_legacy_client_keeps_configuration(self):
        config=panel.legacy_plant({'hp':self.entry})
        await panel.ws_settings(self.hass,self.connection,{'id':1,'settings':{'plant':config}})
        self.connection.send_error.assert_not_called()
        await panel.ws_settings(self.hass,self.connection,{'id':2,'settings':{'name':'Changed'}})
        self.assertEqual(self.hass.data['r290_heatpump']['_panel']['settings']['plant'],config)
        self.hass.services.async_call.assert_not_awaited()

    async def test_plant_save_rejects_active_controller_and_foreign_entities(self):
        config=panel.legacy_plant({'hp':self.entry})
        self.hass.data['r290_heatpump']['aux']={'controller':types.SimpleNamespace(mode='auto')}
        await panel.ws_settings(self.hass,self.connection,{'id':1,'settings':{'plant':config}})
        self.assertEqual(self.error_code(),'invalid_plant')
        self.assertNotIn('plant',self.hass.data['r290_heatpump']['_panel']['settings'])
        config['unit_ids']=['foreign']
        await panel.ws_settings(self.hass,self.connection,{'id':2,'settings':{'plant':config}})
        self.assertEqual(self.error_code(),'invalid_plant')

    async def test_service_requires_admin_and_failed_write_is_audited(self):
        engine=types.SimpleNamespace(inspect=AsyncMock(),start=AsyncMock(side_effect=ValueError('No flow')))
        self.hass.data['r290_heatpump']['_service']=engine
        self.connection.user.is_admin=False
        await panel.ws_service(self.hass,self.connection,{'id':1,'entry_id':'hp','action':'read'})
        self.assertEqual(self.error_code(),'unauthorized')
        engine.inspect.assert_not_awaited()
        self.connection.user.is_admin=True
        await panel.ws_service(self.hass,self.connection,{'id':2,'entry_id':'hp','action':'start','component':'compressor','value':30,'seconds':15,'confirmed':True,'qualified':True})
        self.assertEqual(self.error_code(),'service_failed')
        record=self.hass.data['r290_heatpump']['_panel']['audit'][-1]
        self.assertEqual((record['result'],record['component'],record['user_id']),('failed','compressor','test-user'))

    async def test_service_recovery_blocks_parameter_curve_and_topology_changes(self):
        self.hass.data['r290_heatpump']['_service']=types.SimpleNamespace(pending={'hp':{}})
        await self.parameter()
        self.assertEqual(self.error_code(),'service_active')
        await panel.ws_curve(self.hass,self.connection,{'id':2,'entry_id':'curve','confirmed':True})
        self.assertEqual(self.error_code(),'service_active')
        await panel.ws_settings(self.hass,self.connection,{'id':3,'settings':{'plant':panel.legacy_plant({'hp':self.entry})}})
        self.assertEqual(self.error_code(),'invalid_plant')
        self.hass.services.async_call.assert_not_awaited()

    async def test_pump_mode_and_manual_value_are_one_atomic_operation(self):
        controller = types.SimpleNamespace(async_set_mode=AsyncMock(), mode="manual", error=None,
                                           diagnostics=lambda: {"mode": "manual"})
        self.hass.data["r290_heatpump"]["aux"] = {"controller": controller}
        await panel.ws_pump(self.hass, self.connection, {"id": 1, "entry_id": "aux", "confirmed": True, "mode": "manual", "manual_speed": 65})
        controller.async_set_mode.assert_awaited_once_with("manual", manual_speed=65)


if __name__ == "__main__":
    unittest.main()

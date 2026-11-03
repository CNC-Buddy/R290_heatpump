"""Multi-point curves: configuration, real control callbacks and failure paths."""
import asyncio
import importlib
import types
import unittest
from unittest.mock import AsyncMock, Mock

import test_shared_connection as fixture
from test_panel_api import panel
import test_panel_api as panel_tests

maths = importlib.import_module("r290_under_test.curve_math")
POINTS = [{"outdoor": -15, "target": 50}, {"outdoor": 0, "target": 35}, {"outdoor": 20, "target": 25}]


class CurveMathTests(unittest.TestCase):
    def test_piecewise_interpolation_and_end_clamping(self):
        points = maths.validate_points(POINTS)
        for outdoor, target in [(-40, 50), (-15, 50), (-5, 40), (0, 35), (10, 30), (40, 25)]:
            self.assertEqual(maths.interpolate(points, outdoor), target)

    def test_legacy_curve_matches_every_previous_formula_value(self):
        for low, high in [(25, 50), (40, 25), (30, 30)]:
            points = maths.points_from_options(dict(t_flow_min=low, t_flow_max=high))
            for i in range(-400, 401):
                x = i / 10
                old = high if x <= -15 else low if x >= 20 else low + (high-low)/-35*(x-20)
                self.assertAlmostEqual(maths.interpolate(points, x), old)

    def test_invalid_points_do_not_fall_back_to_a_default_curve(self):
        cases = [[], POINTS[:1], POINTS*4, list(reversed(POINTS)),
                 [POINTS[0], POINTS[0]], [{"outdoor": 0, "target": 30}, {"outdoor": 0.01, "target": 30}],
                 [{"outdoor": -31, "target": 30}, POINTS[-1]],
                 [{"outdoor": 0, "target": 81}, POINTS[-1]],
                 [{"outdoor": True, "target": 35}, POINTS[-1]],
                 [{"outdoor": 0, "target": "nan"}, POINTS[-1]],
                 [{"outdoor": 0, "target": float("inf")}, POINTS[-1]],
                 [{"outdoor": 0}, POINTS[-1]], None]
        for points in cases:
            with self.subTest(points=points), self.assertRaises(ValueError):
                maths.points_from_options({"curve_points": points})

    def test_ten_points_and_rising_cooling_curve(self):
        points = maths.validate_points([dict(outdoor=i, target=6+i/10) for i in range(10)])
        self.assertEqual(maths.interpolate(points, 4.5), 6.45)


class CurvePointApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        panel_tests.PanelTests.setUp(self)
        self.curve = fixture.Entry('curve', 'heating_curve', outdoor_sensor='sensor.out', pv_enabled=True)
        self.curve.options = {"inertia_hours": 2, "stepsize_c": 1}
        self.hass.config_entries.entries.append(self.curve)
        self.update = Mock(wraps=self.hass.config_entries.async_update_entry)
        self.hass.config_entries.async_update_entry = self.update

    async def change(self, **overrides):
        snap = panel.curve_snapshot(self.curve, [])
        msg = dict(id=2, entry_id='curve', revision=snap['revision'], changes=[], points=POINTS, confirmed=True)
        msg.update(overrides)
        await panel.ws_curve(self.hass, self.connection, msg)

    async def test_all_four_types_commit_points_and_aliases_once_preserving_other_options(self):
        for kind in ('heating_curve','floor_heating_curve','hot_water_curve','cooling_curve'):
            self.curve.data['device_type'] = kind
            self.update.reset_mock()
            await self.change()
            self.update.assert_called_once()
            self.assertEqual(self.curve.options['curve_points'], POINTS)
            self.assertEqual(self.curve.options['t_flow_max'], 50)
            self.assertEqual(self.curve.options['t_flow_min'], 25)
            self.assertEqual(self.curve.options['inertia_hours'], 2)
            self.assertTrue(self.curve.data['pv_enabled'])
            self.assertTrue(panel.curve_snapshot(self.curve, [])['custom_points'])
        self.hass.services.async_call.assert_not_awaited()

    async def test_point_saves_still_require_admin_confirmation_and_revision(self):
        self.connection.user.is_admin = False
        await self.change()
        self.connection.user.is_admin = True
        await self.change(confirmed=False)
        await self.change(revision='old')
        await self.change(points=[POINTS[0]])
        self.update.assert_not_called()

    async def test_default_snapshot_is_non_mutating_and_corrupt_curve_is_visible(self):
        snap = panel.curve_snapshot(self.curve, [])
        self.assertEqual(len(snap['points']), 2)
        self.assertFalse(snap['custom_points'])
        self.assertNotIn('curve_points', self.curve.options)
        self.curve.options['curve_points'] = []
        snap = panel.curve_snapshot(self.curve, [])
        self.assertEqual(snap['points'], [])
        self.assertTrue(snap['point_error'])
        await self.change()  # Explicit valid replacement repairs it.
        self.assertEqual(self.curve.options['curve_points'], POINTS)

    async def test_legacy_helper_edit_preserves_intermediate_points_and_rejects_crossing(self):
        from test_parameter_error_reporting import method
        setter = method('number.py', 'HeatCurveParamNumber', 'async_set_native_value')
        setter.__globals__.update({name: getattr(maths, name) for name in ('ENDPOINT_KEYS','replace_endpoints','endpoint_options')})
        self.curve.options['curve_points'] = POINTS
        obj = types.SimpleNamespace(_entry=self.curve, _hass=self.hass, _key='t_out_min', _legacy_keys=(), _attr_native_value=-15, async_write_ha_state=Mock())
        await setter(obj, -10)
        self.assertEqual(self.curve.options['curve_points'][1], POINTS[1])
        self.assertEqual(self.curve.options['curve_points'][0]['outdoor'], -10)
        self.update.assert_called_once()
        self.update.reset_mock()
        with self.assertRaises(Exception):
            await setter(obj, 1)
        self.update.assert_not_called()
        self.assertEqual(obj._attr_native_value, -10)


class CurvePointRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.entry = fixture.Entry('curve', 'heating_curve', slave=2, outdoor_sensor='sensor.out')
        self.entry.options = {'curve_points': POINTS, 'heatcurve_active': True, 'stepsize_c': 0.5}
        self.hass = fixture.Hass([self.entry])
        self.hub = types.SimpleNamespace(async_pb_write_register=AsyncMock())
        self.sensor = fixture.curve_module.R290HeatPumpTemperatureCurveSensor(self.hass, self.entry, {}, self.hub)
        self.outdoor(10)
        await self.sensor.async_added_to_hass()

    def outdoor(self, value):
        self.hass.states['sensor.out'] = types.SimpleNamespace(state=str(value), attributes={})

    async def asyncTearDown(self):
        await self.sensor.async_will_remove_from_hass()
        await self.hass.flush()

    async def test_real_callback_routes_interpolated_setpoint_to_configured_slave(self):
        await self.sensor._pv_callback()
        self.assertEqual(self.hub.async_pb_write_register.call_args.args, (2, 0x0301, 30, 'holding'))
        self.assertEqual(self.sensor.state, 30)
        self.assertEqual(self.sensor.extra_state_attributes['curve_points'], POINTS)

    async def test_invalid_missing_outdoor_and_invalid_configuration_never_write(self):
        for value in ['unknown', 'unavailable', 'nan', 'inf']:
            self.outdoor(value)
            await self.sensor._pv_callback()
            self.assertFalse(self.sensor.available)
        self.outdoor(10)
        self.entry.options['curve_points'] = []
        await self.sensor._pv_callback()
        self.hub.async_pb_write_register.assert_not_awaited()

    async def test_disconnect_does_not_claim_success_and_same_target_retries(self):
        await self.sensor._pv_callback()
        self.outdoor(0)
        self.hub.async_pb_write_register.side_effect = ConnectionError('offline')
        await self.sensor._pv_callback()
        await self.sensor.async_update()
        self.assertFalse(self.sensor.available)
        self.assertEqual(self.sensor._last_written, 30)
        self.hub.async_pb_write_register.side_effect = None
        await self.sensor._pv_callback()
        self.assertEqual(self.sensor.state, 35)
        self.assertIsNone(self.sensor.extra_state_attributes['control_error'])

    async def test_minimum_change_and_integer_rounding_avoid_repeated_writes(self):
        self.entry.options['stepsize_c'] = 2
        await self.sensor._pv_callback()  # 30
        self.outdoor(8)
        await self.sensor._pv_callback()  # 31, held back
        await self.sensor.async_update()
        self.assertEqual(self.sensor.state, 30)
        self.hub.async_pb_write_register.assert_awaited_once()
        self.outdoor(6)
        await self.sensor._pv_callback()  # 32
        self.assertEqual(self.sensor.state, 32)
        self.outdoor(5.8)
        await self.sensor._pv_callback()  # 32.1, same rounded target
        self.assertEqual(self.hub.async_pb_write_register.await_count, 2)

    async def test_smoothing_is_shared_and_attribute_reads_do_not_change_control_state(self):
        self.entry.options['inertia_hours'] = 1
        await self.sensor._pv_callback()
        self.outdoor(-15)
        self.sensor._last_ts = asyncio.get_running_loop().time() - 3600
        previous = (self.sensor._last_cmd, self.sensor._last_ts)
        for _ in range(5):
            self.sensor.extra_state_attributes
        self.assertEqual((self.sensor._last_cmd, self.sensor._last_ts), previous)
        await self.sensor._pv_callback()
        self.assertEqual(self.sensor.state, 43)

    async def test_pv_external_offset_and_final_target_limit(self):
        self.entry.options.update(pv_enabled=True, pv_power_sensor='sensor.pv', pv_grid_threshold_min_kw=1,
            pv_grid_threshold_max_kw=2, pv_grid_offset_max=10, external_offset_hold_minutes=0)
        self.hass.states['sensor.pv'] = types.SimpleNamespace(state='3', attributes={'unit_of_measurement':'kW'})
        self.hass.states[self.sensor._external_switch_ids[0]] = types.SimpleNamespace(state='on', attributes={})
        self.hass.states[self.sensor._external_number_id] = types.SimpleNamespace(state='10', attributes={})
        self.outdoor(0)
        await self.sensor._pv_callback()
        self.assertEqual(self.sensor.state, 55)
        self.hass.states[self.sensor._set_temp_entity_id] = types.SimpleNamespace(state='55', attributes={'min':20,'max':52})
        await self.sensor._pv_callback()
        self.assertEqual(self.sensor.state, 52)
        self.assertTrue(self.sensor.extra_state_attributes['target_limited'])

    async def test_disabled_curve_never_writes_and_cooling_direction_is_preserved(self):
        self.entry.options['heatcurve_active'] = False
        self.entry.options['curve_points'] = [dict(outdoor=0, target=6), dict(outdoor=20, target=12)]
        await self.sensor._pv_callback()
        await self.sensor.async_update()
        self.assertEqual(self.sensor.state, 9)
        self.hub.async_pb_write_register.assert_not_awaited()

    async def test_negative_target_is_encoded_as_signed_16_bit(self):
        self.entry.options['curve_points'] = [dict(outdoor=0, target=-10), dict(outdoor=20, target=0)]
        await self.sensor._pv_callback()
        self.assertEqual(self.sensor.state, -5)
        self.assertEqual(self.hub.async_pb_write_register.call_args.args[2], 65531)

    async def test_stored_points_survive_new_sensor_for_each_curve_type(self):
        for kind, address in [('heating_curve',0x0301),('floor_heating_curve',0x0303),('hot_water_curve',0x0302),('cooling_curve',0x0300)]:
            entry = fixture.Entry('restored', kind, slave=1, outdoor_sensor='sensor.out')
            entry.options = dict(self.entry.options)
            sensor = fixture.curve_module.R290HeatPumpTemperatureCurveSensor(self.hass, entry, {}, self.hub, modbus_address=address)
            await sensor.async_added_to_hass()
            await sensor._pv_callback()
            self.assertEqual(self.hub.async_pb_write_register.call_args.args[:3], (1,address,30))
            await sensor.async_will_remove_from_hass()


if __name__ == '__main__':
    unittest.main()

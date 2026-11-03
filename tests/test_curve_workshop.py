"""Curve changes must be scoped, reviewed and applied as one configuration."""
import types
import unittest
from unittest.mock import Mock

from test_panel_api import fixture, panel, put
import test_panel_api as panel_tests


class CurveWorkshopTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        panel_tests.PanelTests.setUp(self)
        self.curve = fixture.Entry('curve', 'heating_curve', t_out_min=-15, t_out_max=20,
                                   t_flow_min=25, t_flow_max=50, outdoor_sensor='sensor.outdoor')
        self.hass.config_entries.entries.append(self.curve)
        self.add('number.cold', 'r290_heatpump_heatcurve_curve_t_out_min', -15, min=-30, max=10, step=1)
        self.add('number.flow', 'r290_heatpump_heatcurve_curve_t_flow_max', 50, min=25, max=70, step=1)
        self.add('number.warm', 'r290_heatpump_heatcurve_curve_t_out_max', 20, min=0, max=35, step=1)
        self.add('switch.active', 'r290_heatpump_heating_curve_active_curve', 'off')
        self.add('select.offset', 'r290_heatpump_heating_pv_grid_offset_min_curve', '+0 degC', options=['+0 degC', '+2 degC'])
        self.update = Mock(wraps=self.hass.config_entries.async_update_entry)
        self.hass.config_entries.async_update_entry = self.update

    def add(self, entity_id, uid, state, **attrs):
        self.hass.entity_registry.entities[entity_id] = types.SimpleNamespace(
            entity_id=entity_id, config_entry_id='curve', platform='r290_heatpump',
            disabled_by=None, unique_id=uid, name=None, original_name=entity_id)
        put(self.hass, entity_id, state, **attrs)

    def snap(self):
        return panel.curve_snapshot(self.curve, panel._entities(self.hass))

    async def change(self, changes=None, **kwargs):
        msg=dict(id=2, entry_id='curve', revision=self.snap()['revision'], confirmed=True,
                 changes=changes or [dict(entity_id='number.cold', expected='-15', value='-12'),
                                     dict(entity_id='number.flow', expected='50', value='48')])
        msg.update(kwargs)
        await panel.ws_curve(self.hass, self.connection, msg)

    async def test_two_points_commit_once_without_intermediate_service_writes(self):
        await self.change()
        self.update.assert_called_once()
        self.assertEqual(self.curve.options, dict(t_out_min=-12, t_flow_max=48))
        self.assertEqual(self.curve.data['t_out_max'], 20)
        self.hass.services.async_call.assert_not_awaited()
        self.assertEqual(self.connection.send_result.call_args.args[1]['configured'], True)
        self.assertEqual([r['result'] for r in panel._store(self.hass)['audit']], ['configured']*2)

    async def test_admin_confirmation_revision_and_expected_values_gate_entire_batch(self):
        self.connection.user.is_admin = False
        await self.change()
        self.assertEqual(self.connection.send_error.call_args.args[1], 'unauthorized')
        self.connection.user.is_admin = True
        await self.change(confirmed=False)
        await self.change(revision='old')
        self.hass.states['number.flow'].state='51'
        await self.change()
        self.update.assert_not_called()
        self.assertEqual(self.curve.options, {})

    async def test_unrelated_duplicate_invalid_and_unavailable_values_never_commit(self):
        for changes in [
            [dict(entity_id='number.p099',expected='3',value='5')],
            [dict(entity_id='number.cold',expected='-15',value='-12')]*2,
            [dict(entity_id='number.cold',expected='-15',value='nan')],
            [dict(entity_id='number.cold',expected='-15',value='-12.5')],
            [dict(entity_id='number.cold',expected='-15',value='-31')],
            [dict(entity_id='number.cold',expected='-15',value='5'),dict(entity_id='number.warm',expected='20',value='4')],
        ]:
            await self.change(changes)
        self.hass.states['number.cold'].state='unavailable'
        await self.change()
        self.update.assert_not_called()

    async def test_switch_and_select_store_native_option_types(self):
        await self.change([dict(entity_id='switch.active',expected='off',value='on'),dict(entity_id='select.offset',expected='+0 degC',value='+2 degC')])
        self.assertIs(self.curve.options['heatcurve_active'], True)
        self.assertEqual(self.curve.options['pv_grid_offset_min'], 2)

    async def test_failed_update_is_reported_and_audited(self):
        self.update.side_effect=RuntimeError('Unable to store')
        await self.change()
        self.assertEqual(self.connection.send_error.call_args.args[1], 'write_failed')
        self.assertTrue(all(r['result']=='failed' for r in panel._store(self.hass)['audit']))

    async def test_all_curve_prefixes_and_disabled_entities(self):
        for kind,prefix in [('heating_curve','heating'),('hot_water_curve','hotwater'),('floor_heating_curve','floor_heating'),('cooling_curve','cooling')]:
            self.curve.data['device_type']=kind
            self.hass.entity_registry.entities['switch.active'].unique_id=f'r290_heatpump_{prefix}_curve_active_curve'
            self.assertIn('switch.active',[c['id'] for c in self.snap()['controls']])
        self.hass.entity_registry.entities['switch.active'].disabled_by='user'
        self.assertNotIn('switch.active',[c['id'] for c in self.snap()['controls']])
        self.curve.data['secret']='must-not-be-returned'
        self.assertNotIn('must-not-be-returned',str(self.snap()))


if __name__ == '__main__':
    unittest.main()

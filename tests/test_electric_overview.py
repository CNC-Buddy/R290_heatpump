"""Migration keeps hydraulic geometry; electricity settings never write devices."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import unittest
import test_panel_api as fixture

model = importlib.import_module('r290_under_test.electric_overview')
graphs = json.loads(Path(__file__).with_name('schematic-fixtures.json').read_text(encoding='utf-8'))


def legacy():
    graph = deepcopy(graphs['full_pv'])
    for n in graph['nodes']:
        if n['type'] in model.COMPONENTS:
            n['bindings'] = {'value': f'sensor.{n["type"]}'}
        if n['type'] == 'battery':
            n['bindings']['soc'] = 'sensor.soc'
    return {'schematic': {'revision': 7, 'draft': deepcopy(graph), 'published': graph}}


class MigrationTests(unittest.TestCase):
    def test_move_sources_without_moving_pipes_or_heaters(self):
        before = legacy()
        result = model.migrate(before)
        self.assertEqual(result['electric']['pv_power'], 'sensor.pv')
        self.assertEqual(result['electric']['battery_soc'], 'sensor.soc')
        self.assertTrue(result['electric']['enabled'])
        self.assertEqual(result['electric']['grid_positive'], 'unknown')
        for key in ('draft', 'published'):
            original, graph = before['schematic'][key], result['schematic'][key]
            ids = {n['id'] for n in graph['nodes']}
            self.assertEqual(graph['nodes'], [n for n in original['nodes'] if n['id'] in ids])
            self.assertEqual(graph['edges'], [e for e in original['edges'] if e['from']['node'] in ids and e['to']['node'] in ids])
            self.assertEqual(result['schematic']['electric_backup'][key], original)
            self.assertFalse(any(n['type'] in model.COMPONENTS for n in graph['nodes']))
        self.assertEqual(result['schematic']['revision'], 8)
        self.assertIs(model.migrate(result), result)
        self.assertEqual(before, legacy())

    def test_ambiguous_binding_not_guessed_and_existing_preferences_kept(self):
        old = legacy()
        next(n for n in old['schematic']['draft']['nodes'] if n['type'] == 'pv')['bindings']['value'] = 'sensor.other'
        self.assertEqual(model.migrate(old)['electric']['pv_power'], '')
        old['electric'] = {'enabled': False, 'pv_power': 'sensor.chosen'}
        self.assertEqual(model.migrate(old)['electric'], old['electric'])

    def test_empty_settings_stay_disabled_and_invalid_units_rejected(self):
        self.assertEqual(model.migrate({}), {})
        self.assertFalse(model.validate({}, {})['enabled'])
        for bad in ({'enabled': 1}, {'grid_positive': 'guess'}, {'pv_power': 'switch.x'}, {'extra': True}, {'battery_positive': []}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                model.validate(bad, {})

    def test_mounted_heater_remains_and_electric_only_graph_uses_standard_hydraulics(self):
        old = legacy()
        heater = {'id': 'heater', 'type': 'heater', 'tank': 'buffer', 'circuit': 'electric',
                  'leg': 'power', 'x': 1300, 'y': 700, 'bindings': {'value': 'sensor.heater'}}
        old['schematic']['published']['nodes'].append(heater)
        self.assertIn(heater, model.migrate(old)['schematic']['published']['nodes'])
        old = {'schematic': {'published': {'version': 1, 'nodes': [
            {'id': 'pv', 'type': 'pv', 'bindings': {'value': 'sensor.pv'}}], 'edges': []}}}
        result = model.migrate(old)
        self.assertIsNone(result['schematic']['published'])
        self.assertTrue(result['electric']['enabled'])


class ApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixture.PanelTests.setUp(self)

    async def test_save_read_history_old_client_and_disable_preserve_sources(self):
        fixture.put(self.hass, 'sensor.pv', 4000, 'W')
        await fixture.panel.ws_settings(self.hass, self.connection, {'id': 1, 'settings': {'electric': {'enabled': True, 'pv_power': 'sensor.pv'}}})
        self.connection.send_error.assert_not_called()
        self.assertIn('sensor.pv', fixture.panel._allowed_history(self.hass))
        await fixture.panel.ws_settings(self.hass, self.connection, {'id': 2, 'settings': {'name': 'old client'}})
        config = self.hass.data['r290_heatpump']['_panel']['settings']['electric']
        self.assertTrue(config['enabled'])
        await fixture.panel.ws_settings(self.hass, self.connection, {'id': 3, 'settings': {'electric': {**config, 'enabled': False}}})
        self.assertEqual(self.hass.data['r290_heatpump']['_panel']['settings']['electric']['pv_power'], 'sensor.pv')
        fixture.put(self.hass, 'sensor.energy', 12, 'kWh')
        await fixture.panel.ws_settings(self.hass, self.connection, {'id': 4, 'settings': {'electric': {'pv_power': 'sensor.energy'}}})
        self.assertEqual(self.connection.send_error.call_args.args[1], 'invalid_electric')
        self.hass.services.async_call.assert_not_awaited()

    async def test_import_legacy_and_repeat_save_preserve_backup_and_conflict_guard(self):
        graph = legacy()['schematic']['published']
        await fixture.panel.ws_schematic(self.hass, self.connection, {'id': 1, 'action': 'publish', 'expected_revision': 0, 'graph': graph})
        self.connection.send_error.assert_not_called()
        result = self.connection.send_result.call_args.args[1]
        self.assertEqual(result['electric']['house_power'], 'sensor.house')
        self.assertEqual(result['schematic']['revision'], 1)
        self.assertFalse(any(n['type'] in model.COMPONENTS for n in result['schematic']['published']['nodes']))
        await fixture.panel.ws_schematic(self.hass, self.connection, {'id': 2, 'action': 'draft', 'expected_revision': 1, 'graph': result['schematic']['draft']})
        updated = self.connection.send_result.call_args.args[1]
        self.assertEqual(updated['schematic']['electric_backup'], result['schematic']['electric_backup'])
        await fixture.panel.ws_schematic(self.hass, self.connection, {'id': 3, 'action': 'publish', 'expected_revision': 1, 'graph': graph})
        self.assertEqual(self.connection.send_error.call_args.args[1], 'conflict')
        self.hass.services.async_call.assert_not_awaited()

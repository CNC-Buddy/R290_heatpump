"""Live P183 verification, connection lifecycle and panel write boundary."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

import test_panel_api as base
from test_auxiliary_pump import put

panel = base.panel
access = panel.parameter_access


class AccessTests(unittest.IsolatedAsyncioTestCase):
    parameter = base.PanelTests.parameter
    error_code = base.PanelTests.error_code

    def setUp(self):
        base.PanelTests.setUp(self)
        self.hub = types.SimpleNamespace(async_read_block=AsyncMock(return_value=[2468]))
        self.hass.data['r290_heatpump']['hp'] = {'hub': self.hub}
        self.hass.entity_registry.entities['number.p099'].unique_id = 'r290_heatpump_p099_target_0163_slave_1_v2'

    async def unlock(self, password='2468', ids=None):
        await panel.ws_system_access(self.hass, self.connection,
            {'id': 1, 'action': 'unlock', 'entry_ids': ids or ['hp'], 'password': password})

    async def test_locked_endpoint_cannot_be_bypassed(self):
        await self.parameter()
        self.assertEqual(self.error_code(), 'system_locked')
        self.hass.services.async_call.assert_not_awaited()
        self.hub.async_read_block.assert_not_awaited()

    async def test_correct_password_reads_live_register_and_rechecks_on_write(self):
        await self.unlock()
        self.assertGreater(access.status(self.connection)['hp'], 590)
        self.assertEqual(self.hub.async_read_block.await_args.args, (1, 0x01B7, 1))
        await self.parameter()
        self.assertEqual(self.hub.async_read_block.await_count, 2)
        self.hass.services.async_call.assert_awaited_once()
        self.assertNotIn('2468', repr(access.grants(self.connection)))

    async def test_wrong_password_and_invalid_inputs_never_grant_or_write(self):
        for secret in ('998', '', '12a', '12345', 'ï¼’ï¼”ï¼–ï¼˜'):
            await self.unlock(secret)
            self.assertEqual(self.error_code(), 'system_locked')
            self.assertEqual(access.status(self.connection), {})
        self.hass.services.async_call.assert_not_awaited()

    async def test_current_zero_password_requires_explicit_zero(self):
        self.hub.async_read_block.return_value = [0]
        await self.parameter()
        self.hass.services.async_call.assert_not_awaited()
        await self.unlock('0000')
        await self.parameter()
        self.hass.services.async_call.assert_awaited_once()

    async def test_read_failure_or_invalid_register_fails_closed(self):
        for values in ([], [65535], [10000], [2468, 5]):
            self.hub.async_read_block.return_value = values
            await self.unlock()
            self.assertEqual(access.status(self.connection), {})
        self.hub.async_read_block.side_effect = RuntimeError('offline')
        await self.unlock()
        self.assertEqual(access.status(self.connection), {})
        self.hass.services.async_call.assert_not_awaited()

    async def test_password_change_and_connection_user_expiry_invalidate(self):
        await self.unlock()
        self.hub.async_read_block.return_value = [1357]
        await self.parameter()
        self.assertEqual(access.status(self.connection), {})
        self.hub.async_read_block.return_value = [2468]
        await self.unlock()
        access.grants(self.connection)['hp']['until'] = 0
        await self.parameter()
        self.assertEqual(self.error_code(), 'system_locked')
        await self.unlock()
        self.connection.user.id = 'another-admin'
        await self.parameter()
        self.assertEqual(access.status(self.connection), {})
        self.hass.services.async_call.assert_not_awaited()

    async def test_grant_is_scoped_to_connection_and_device(self):
        await self.unlock()
        old = self.connection
        self.connection = types.SimpleNamespace(**{**vars(old), 'subscriptions': {}})
        await self.parameter()
        self.assertEqual(self.error_code(), 'system_locked')
        self.assertIn('hp', access.status(old))
        self.assertNotIn('hp2', access.status(old))
        self.hass.services.async_call.assert_not_awaited()

    async def test_multiple_devices_are_all_or_none_and_lock_is_read_only(self):
        second = base.fixture.Entry('hp2', 'heat_pump', slave=2)
        self.hass.config_entries.entries.append(second)
        self.hass.data['r290_heatpump']['hp2'] = {'hub': self.hub}
        self.hub.async_read_block.side_effect = [[2468], [1357]]
        await self.unlock(ids=['hp', 'hp2'])
        self.assertEqual(access.status(self.connection), {})
        self.hub.async_read_block.side_effect = None
        await self.unlock(ids=['hp', 'hp2'])
        self.assertEqual(set(access.status(self.connection)), {'hp', 'hp2'})
        await panel.ws_system_access(self.hass, self.connection,
            {'id': 2, 'action': 'lock', 'entry_ids': ['hp', 'hp2']})
        self.assertEqual(access.status(self.connection), {})
        self.hass.services.async_call.assert_not_awaited()

    async def test_disconnect_cleans_grants_even_while_unlock_is_reading(self):
        # HA's ActiveConnection has slots; state lives in its subscription map.
        class Slotted:
            __slots__ = ('subscriptions', 'user')
        connection = Slotted()
        connection.subscriptions = {}
        connection.user = self.connection.user
        entered, release = asyncio.Event(), asyncio.Event()
        async def slow_read(*args):
            entered.set()
            await release.wait()
            return [2468]
        self.hub.async_read_block.side_effect = slow_read
        task = asyncio.create_task(access.unlock(self.hass, connection, [self.entry], '2468'))
        await entered.wait()
        unsubscribe = next(iter(connection.subscriptions.values()))
        unsubscribe()
        connection.subscriptions.clear()
        release.set()
        with self.assertRaisesRegex(ValueError, 'Connection closed'):
            await task
        self.assertEqual(unsubscribe.values, {})

    async def test_rate_limit_and_admin_boundary(self):
        for _ in range(5):
            await self.unlock('1')
        await self.unlock()
        self.assertIn('wait one minute', self.connection.send_error.call_args.args[2])
        self.assertEqual(self.hub.async_read_block.await_count, 5)
        self.connection.user.is_admin = False
        await self.unlock()
        self.assertEqual(self.error_code(), 'unauthorized')

    async def test_password_update_is_redacted_and_revokes_grant_even_on_failure(self):
        entity = self.hass.entity_registry.entities['number.p099']
        entity.unique_id = 'r290_heatpump_p183_password_01B7_slave_1_v2'
        put(self.hass, 'number.p099', 2468, min=0, max=9999, step=1)
        await self.unlock()
        self.hass.services.async_call.side_effect = RuntimeError('value 1357 failed; was 2468')
        await self.parameter(expected='2468', value='1357')
        audit = repr(self.hass.data['r290_heatpump']['_panel']['audit'])
        self.assertNotIn('1357', audit)
        self.assertNotIn('2468', audit)
        self.assertNotIn('1357', repr(self.connection.send_error.call_args))
        self.assertEqual(access.status(self.connection), {})

    async def test_user_parameters_keep_existing_confirmation_flow(self):
        self.hass.entity_registry.entities['number.p099'].unique_id = 'r290_heatpump_heating_set_temperature_slave_1'
        await self.parameter()
        self.hass.services.async_call.assert_awaited_once()
        self.hub.async_read_block.assert_not_awaited()


class CatalogLanguageTests(unittest.TestCase):
    def test_complete_localized_catalog_and_unknown_semantics(self):
        path = Path(__file__).resolve().parents[1] / 'custom_components/r290_heatpump/frontend/register-catalog.json'
        records = json.loads(path.read_text(encoding='utf-8'))['records']
        selected = [r for r in records if r['section'] in (1, 2, 3, 5)]
        self.assertEqual(len(selected), 255)
        for r in selected:
            for key in ('name_de', 'display_name_en', 'description_de', 'description_en'):
                self.assertTrue(r.get(key), (r['hex'], key))
            if r['unknown']:
                self.assertIn('nicht dokumentiert', r['description_de'].lower())
                self.assertIn('not documented', r['description_en'].lower())
        self.assertIn('firmware', next(r for r in selected if r['address'] == 0x53)['description_de'].lower())


class PhaseHistoryTests(unittest.TestCase):
    def read(self, rows, metadata):
        start = datetime(2026, 11, 1, tzinfo=timezone.utc)
        values = {key: [types.SimpleNamespace(state=value, last_updated=start+timedelta(seconds=i))
                       for i, value in enumerate(data)] for key, data in rows.items()}
        recorder = types.ModuleType('homeassistant.components.recorder')
        recorder.history = types.SimpleNamespace(get_significant_states=Mock(return_value=values))
        with patch.dict(sys.modules, {'homeassistant.components.recorder': recorder}):
            return panel._history_result(None, start, start+timedelta(days=1), list(rows), metadata)['series']

    def test_boolean_history_preserves_unknown_transitions_and_numeric_chart_gap(self):
        result = self.read({'sensor.dhw': ['off', 'off', 'on', 'unavailable', 'off']}, {})['sensor.dhw']
        self.assertEqual([e[1] for e in result['states']], ['off', 'on', 'unavailable', 'off'])
        self.assertFalse(result['states_truncated'])
        self.assertTrue(all(value is None for _, value in result['points']))

    def test_frequency_retains_events_but_temperature_uses_compact_chart(self):
        rows = {'sensor.freq': [str(i % 2 * 40) for i in range(7000)], 'sensor.temp': ['30'] * 7000}
        result = self.read(rows, {'sensor.freq': {'unit_of_measurement': 'Hz'}, 'sensor.temp': {'unit_of_measurement': '°C'}})
        self.assertEqual(len(result['sensor.freq']['states']), 6000)
        self.assertTrue(result['sensor.freq']['states_truncated'])
        self.assertNotIn('states', result['sensor.temp'])
        self.assertLess(len(result['sensor.temp']['points']), 1000)
        self.assertEqual(result['sensor.freq']['summary']['starts'], 3500)


if __name__ == '__main__':
    unittest.main()

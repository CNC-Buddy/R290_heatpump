"""Diagnostic transport boundaries, provenance, and lossless fault states."""
import asyncio
from datetime import datetime, timedelta, timezone
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

import test_panel_api as setup
from test_shared_connection import hub_module

d = setup.panel


class DiagnosticTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixture = setup.PanelTests()
        fixture.setUp()
        self.hass, self.connection, self.entry = fixture.hass, fixture.connection, fixture.entry
        self.hub = types.SimpleNamespace(async_read_block=AsyncMock(return_value=[65486, 0]))
        self.hass.data['r290_heatpump']['hp'] = {'hub': self.hub}

    async def read(self, **changes):
        msg = {'id': 1, 'entry_id': 'hp', 'addresses': [0x6e, 0x6f]}
        await d.ws_registers(self.hass, self.connection, {**msg, **changes})

    async def test_read_only_whitelisted_block_and_actual_reception_time(self):
        before = datetime.now(timezone.utc)
        await self.read()
        result = self.connection.send_result.call_args.args[1]
        self.assertEqual(result['values'], {0x6e:65486, 0x6f:0})
        self.assertGreaterEqual(datetime.fromisoformat(result['received_at']), before)
        self.hub.async_read_block.assert_awaited_once_with(1, 0x6e, 2)
        self.hass.services.async_call.assert_not_awaited()

    async def test_invalid_addresses_units_and_non_admin_never_read(self):
        for args in [{'addresses': []}, {'addresses':[0x6e,0x70]}, {'addresses':[0xffff]},
                     {'addresses':list(range(0x40,0x40+21))}, {'entry_id':'unknown'}, {'addresses':[True]}]:
            await self.read(**args)
            self.assertEqual(self.connection.send_error.call_args.args[1], 'diagnostic_read_failed')
        self.connection.user.is_admin = False
        await self.read()
        self.assertEqual(self.connection.send_error.call_args.args[1], 'unauthorized')
        self.hub.async_read_block.assert_not_awaited()

    async def test_parallel_requests_are_rejected_and_read_failure_is_not_zero(self):
        started, release = asyncio.Event(), asyncio.Event()
        async def wait(*args):
            started.set()
            await release.wait()
            raise TimeoutError('No response')
        self.hub.async_read_block.side_effect = wait
        first = asyncio.create_task(self.read())
        await started.wait()
        await self.read()
        self.assertIn('throttled',self.connection.send_error.call_args.args[2])
        release.set()
        await first
        self.connection.send_result.assert_not_called()
        self.assertFalse(self.hass.data['r290_heatpump']['hp']['_diagnostic_busy'])
        await self.read()
        self.hub.async_read_block.assert_awaited_once()

    async def test_catalog_associations_include_all_five_sections(self):
        from r290_under_test.panel_diagnostics import catalog, record_for
        self.assertEqual({r['section'] for r in catalog()['records']}, {1,2,3,4,5})
        self.assertEqual(record_for('r290_heatpump_heating_set_temperature_slave_1')['section'],3)
        self.assertEqual(record_for('r290_heatpump_p099_x_0163_slave_2_v2')['section'],4)
        self.assertEqual(record_for('r290_heatpump_fault_state_1_slave_1')['section'],1)
        self.assertIsNone(record_for('not_a_register'))

    async def test_raw_cache_keeps_age_previous_value_and_failure(self):
        coord=hub_module.ModbusBatchCoordinator(self.hass,self.hub,1,30,block_pause=0)
        coord.update_interval=timedelta(seconds=30)
        coord._addresses={0x6e,0x6f}
        await coord._async_update_data()
        first=coord.observations[0x6e].copy()
        await coord._async_update_data()
        self.assertEqual(first['changed_at'],coord.observations[0x6e]['changed_at'])
        self.hub.async_read_block.return_value=[65480,0]
        await coord._async_update_data()
        self.assertEqual(coord.observations[0x6e]['previous'],65486)
        last=coord.observations[0x6e].copy()
        self.hub.async_read_block.side_effect=TimeoutError('offline')
        self.assertEqual(await coord._async_update_data(),{})
        self.assertEqual(coord.observations[0x6e]['received_at'],last['received_at'])
        self.assertEqual(coord.observations[0x6e]['value'],65480)
        self.assertEqual(coord.observations[0x6e]['error'],'offline')

    async def test_fault_history_preserves_simultaneous_faults_and_unknown_gaps(self):
        now=datetime.now(timezone.utc)
        values=['None','Water flow, Phase error','Water flow, Phase error','unavailable','None']
        states=[types.SimpleNamespace(state=v,last_updated=now+timedelta(seconds=i)) for i,v in enumerate(values)]
        history=types.SimpleNamespace(get_significant_states=Mock(return_value={'sensor.fault':states}))
        recorder=types.ModuleType('homeassistant.components.recorder');recorder.history=history
        with patch.dict(sys.modules,{'homeassistant.components.recorder':recorder}):
            result=d.fault_history(self.hass,now,now+timedelta(days=1),['sensor.fault','sensor.empty'])
        self.assertEqual([e['state'] for e in result['events']],['None','unavailable','Water flow, Phase error','None'])
        self.assertTrue(result['events'][-1]['initial'])
        self.assertFalse(result['events'][0]['initial'])
        self.assertEqual(result['recorded_ids'],['sensor.fault'])
        self.hass.services.async_call.assert_not_awaited()

    async def test_fault_history_requires_admin_and_recorder(self):
        self.connection.user.is_admin=False
        await d.ws_faults(self.hass,self.connection,{'id':1,'days':7})
        self.assertEqual(self.connection.send_error.call_args.args[1],'unauthorized')
        self.connection.user.is_admin=True
        self.hass.config.components.clear()
        await d.ws_faults(self.hass,self.connection,{'id':1,'days':7})
        self.assertEqual(self.connection.send_error.call_args.args[1],'recorder_unavailable')

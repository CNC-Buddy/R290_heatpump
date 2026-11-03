"""Plant validation and real service engine exercised against an in-memory Modbus hub."""
import asyncio
import importlib
import types
import unittest
from unittest.mock import AsyncMock, patch
import test_shared_connection as fixture
from test_auxiliary_pump import Store, put

plant = importlib.import_module("r290_under_test.plant")
service = importlib.import_module("r290_under_test.service_tools")


class PlantTests(unittest.TestCase):
    def setUp(self):
        self.entries = {key: fixture.Entry(key, 'heat_pump', slave=n) for n,key in enumerate(['hp1','hp2'],1)}
        self.config = plant.legacy_plant(self.entries)

    def test_variants_and_count_validation(self):
        for heating in plant.CHOICES['heating']:
            for separation in plant.CHOICES['separation']:
                for dhw in plant.CHOICES['dhw']:
                    cfg={**self.config,'heating':heating,'separation':separation,'dhw':dhw}
                    self.assertEqual(plant.validate_plant(cfg,self.entries,{}),cfg)
        with self.assertRaises(ValueError):
            plant.validate_plant({**self.config,'mode':'single'},self.entries,{})
        with self.assertRaises(ValueError):
            plant.validate_plant({**self.config,'unit_ids':['hp1','missing']},self.entries,{})
        with self.assertRaises(ValueError):
            plant.validate_plant({**self.config,'unit_ids':['hp1','hp1']},self.entries,{})
        plant.validate_plant({**self.config,'mode':'single','unit_ids':['hp1']},self.entries,{})

    def test_valves_need_explicit_existing_feedback(self):
        with self.assertRaises(ValueError):
            plant.validate_plant({**self.config,'isolation':'feedback'},self.entries,{})
        valves={'hp1':'binary_sensor.v1','hp2':'binary_sensor.v2'}
        cfg={**self.config,'isolation':'feedback','valve_entities':valves}
        plant.validate_plant(cfg,self.entries,{eid:object() for eid in valves.values()})

    def test_controller_requires_matching_order_and_common_pump(self):
        registry=types.SimpleNamespace(entities={f'sensor.{u}':types.SimpleNamespace(config_entry_id=u) for u in self.entries})
        cfg={k:['sensor.hp1','sensor.hp2'] for k in ['frequency_entities','flow_entities','supply_entities','return_entities']}
        self.assertIsNone(plant.controller_problem(self.config,cfg,registry))
        self.assertIsNotNone(plant.controller_problem({**self.config,'aux_position':'heating_supply'},cfg,registry))
        cfg['flow_entities'].reverse()
        self.assertIsNotNone(plant.controller_problem(self.config,cfg,registry))


class Hub:
    def __init__(self):
        self.values={a:0 for a in range(0x400)}
        self.values.update({0x360:425,0x363:129,0x58:22,0x344:35,0x33e:30})
        self.writes=[]
        self.fail=False
        self.mismatch=False

    async def async_read_block(self,slave,address,count,**kwargs):
        if self.fail: raise OSError('offline')
        return [self.values[address+i] for i in range(count)]

    async def async_pb_write_register(self,slave,address,value,**kwargs):
        if self.fail: raise OSError('offline')
        self.writes.append((slave,address,value))
        if not self.mismatch:self.values[address]=value


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.hass=fixture.Hass([fixture.Entry('hp1','heat_pump',slave=1)])
        self.hub=Hub()
        self.hass.data['r290_heatpump']={'hp1':{'hub':self.hub}}
        self.store=Store()
        self.engine=service.ServiceTools(self.hass,self.store)

    async def asyncTearDown(self):
        self.hub.fail=False;self.hub.mismatch=False
        for entry in list(self.engine.pending):await self.engine.stop(entry)

    async def start(self,component='fan',value=25,**kwargs):
        return await self.engine.start('hp1',component,value,kwargs.get('seconds',15),kwargs.get('confirmed',True),kwargs.get('qualified',True))

    async def test_version_read_is_read_only_and_does_not_invent_display_version(self):
        result=await self.engine.inspect('hp1')
        self.assertEqual(result['program_version'],'4.25')
        self.assertEqual(result['values']['867'],129)
        self.assertIsNone(result['display_version'])
        self.assertFalse(self.hub.writes)
        with self.assertRaises(ValueError):await self.engine.inspect('hp1')

    async def test_tests_require_confirmation_ranges_standstill_and_no_faults(self):
        for arguments in ({'confirmed':False},{'qualified':False},{'seconds':1000}):
            with self.assertRaises(ValueError):await self.start(**arguments)
        for component,value in [('fan',81),('pfc',1),('pump',-1),('eev',501)]:
            with self.assertRaises(ValueError):await self.start(component,value)
        self.hub.values[1]=1024
        with self.assertRaises(ValueError):await self.start()
        self.hub.values[1]=0;self.hub.values[0x40]=40
        with self.assertRaises(ValueError):await self.start()
        self.hub.values[0x40]=0;self.hub.values[2]=1
        with self.assertRaises(ValueError):await self.start()
        self.assertFalse(self.hub.writes)

    async def test_start_stop_preserves_other_bits_and_restores_setpoint(self):
        self.hub.values[0x331]=256
        await self.start()
        self.assertEqual(self.hub.values[0x331],264)
        self.assertEqual(self.engine.pending['hp1']['state'],'running')
        with self.assertRaises(ValueError):await self.start()
        with self.assertRaises(ValueError):await self.engine.inspect('hp1')
        self.hub.values[0x331]|=512
        await self.engine.stop('hp1')
        self.assertEqual(self.hub.values[0x331],768)
        self.assertEqual(self.hub.values[0x33e],30)
        self.assertFalse(self.engine.pending)
        self.store.async_save.assert_awaited()

    async def test_external_override_and_low_flow_are_not_taken_over(self):
        self.hub.values[0x331]=1
        with self.assertRaises(ValueError):await self.start()
        self.hub.values[0x331]=0;self.hub.values[0x58]=0
        with self.assertRaises(ValueError):await self.start('compressor',30)
        self.assertFalse(self.hub.writes)

    async def test_frost_protection_and_other_service_commands_block_test_start(self):
        for address,value in [(0,2),(0,256),(0,16384),(0x330,16),(0x330,8192)]:
            self.hub.values[address]=value
            with self.assertRaises(ValueError):await self.start()
            self.hub.values[address]=0
        self.assertFalse(self.hub.writes)

    async def test_pump_restore_and_timer_survive_browser_absence(self):
        await self.start('pump',40)
        self.assertEqual(self.hub.values[0x343],1)
        task=self.engine.tasks.pop('hp1');task.cancel();await asyncio.gather(task,return_exceptions=True)
        await self.engine._watch('hp1',0)
        self.assertEqual(self.hub.values[0x343],0)
        self.assertEqual(self.hub.values[0x344],35)
        self.assertFalse(self.engine.pending)

    async def test_failed_restore_is_durable_and_recoverable(self):
        await self.start()
        self.hub.fail=True
        with self.assertRaises(ValueError):await self.engine.stop('hp1')
        saved=self.store.async_save.call_args.args[0]
        self.assertEqual(saved['hp1']['state'],'recovery_required')
        self.engine=service.ServiceTools(self.hass,self.store,saved)
        self.hub.fail=False
        with self.assertRaises(ValueError):await self.start()
        await self.engine.stop('hp1')
        self.assertEqual(self.hub.values[0x331],0)
        self.assertFalse(self.engine.pending)

    async def test_failed_readback_never_reports_running(self):
        self.hub.mismatch=True
        with self.assertRaises(ValueError):await self.start()
        self.assertFalse(self.engine.pending)

    async def test_restart_is_not_presented_as_supervised_running_test(self):
        await self.start()
        recovered=service.ServiceTools(self.hass,self.store,self.engine.pending)
        self.assertEqual(recovered.pending['hp1']['state'],'recovery_required')
        self.assertFalse(recovered.tasks)
        self.assertEqual(self.engine.pending['hp1']['state'],'running')

    async def test_address_change_never_restores_to_another_slave(self):
        await self.start()
        entry=self.hass.config_entries.async_entries('r290_heatpump')[0]
        entry.data['slave']=2
        before=len(self.hub.writes)
        with self.assertRaises(ValueError):await self.engine.stop('hp1')
        self.assertEqual(len(self.hub.writes),before)
        entry.data['slave']=1
        await self.engine.stop('hp1')
        self.assertFalse(self.engine.pending)

    async def test_changed_firmware_requires_local_inspection_before_restore(self):
        await self.start()
        before=len(self.hub.writes)
        self.hub.values[0x360]=443
        with self.assertRaises(ValueError):await self.engine.stop('hp1')
        self.assertEqual(len(self.hub.writes),before)
        self.assertEqual(self.engine.pending['hp1']['state'],'recovery_required')
        self.hub.values[0x360]=425

    async def test_start_guard_is_present_before_first_hardware_write(self):
        original=self.hub.async_read_block
        seen=[]
        async def read(*args,**kwargs):
            seen.append(self.engine.starting)
            return await original(*args,**kwargs)
        self.hub.async_read_block=read
        await self.start()
        self.assertTrue(all(seen))
        self.assertFalse(self.engine.starting)

    async def test_monitor_releases_on_fault_normal_start_or_lost_compressor_flow(self):
        for component,address,value in [('fan',2,1),('fan',0x40,30),('compressor',0x58,0)]:
            await self.start(component,25)
            task=self.engine.tasks.pop('hp1');task.cancel();await asyncio.gather(task,return_exceptions=True)
            old=self.hub.values[address];self.hub.values[address]=value
            with patch.object(service.asyncio,'sleep',new=AsyncMock()):
                await self.engine._watch('hp1',15)
            self.assertEqual(self.hub.values[0x331],0)
            self.assertFalse(self.engine.pending)
            self.hub.values[address]=old

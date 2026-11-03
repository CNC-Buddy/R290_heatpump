"""Optional sources remain read-only and scoped to explicitly mapped entities."""
import importlib
import unittest
from copy import deepcopy
from types import SimpleNamespace

import test_shared_connection as fixture
from test_auxiliary_pump import put
import test_panel_api as panel_fixture

panel = panel_fixture.panel
sources = importlib.import_module("r290_under_test.heat_sources")


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.entries = {'hp': fixture.Entry('hp', 'heat_pump', slave=1)}
        self.plant = panel.legacy_plant(self.entries)
        self.cfg = sources.defaults()
        self.states = {'sensor.power': SimpleNamespace(attributes={'unit_of_measurement': 'W'}),
                       'sensor.energy': SimpleNamespace(attributes={'unit_of_measurement': 'kWh'}),
                       'sensor.temp': SimpleNamespace(attributes={'unit_of_measurement': '°C'}),
                       'switch.dhw': SimpleNamespace(attributes={})}

    def test_missing_sources_disabled_and_no_implicit_bindings(self):
        self.assertEqual(sources.validate({}, self.entries, self.states, self.plant), self.cfg)
        self.assertEqual(sources.history_entities(self.cfg), set())

    def test_three_sources_with_explicit_sources(self):
        for c in self.cfg.values():
            c.update(enabled=True, managed_by='heat_pump', entry_id='hp', request_entity='switch.dhw',
                     energy_entity='sensor.energy', power_entity='sensor.power')
        self.cfg['secondary'].update(kind='wood', serves='both', dhw_temperature_entity='sensor.temp')
        self.assertEqual(sources.validate(self.cfg, self.entries, self.states, self.plant), self.cfg)
        self.assertEqual(sources.history_entities(self.cfg), set(self.states))

    def test_rejects_invalid_domains_units_and_unselected_controllers(self):
        self.cfg['dhw_heater']['enabled'] = True
        for changes in [{'power_entity':'switch.dhw'}, {'power_entity':'sensor.temp'},
                        {'energy_entity':'sensor.power'}, {'request_entity':'switch.missing'},
                        {'entry_id':'missing'}, {'managed_by':'heat_pump'}, {'kind':[]},
                        {'enabled':'yes'}, {'write_register':1}]:
            cfg=deepcopy(self.cfg); cfg['dhw_heater'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                sources.validate(cfg,self.entries,self.states,self.plant)

    def test_topology_must_have_assigned_store(self):
        for key,change in [('dhw_heater',{'dhw':'none'}),('buffer_heater',{'heating':'direct'}),
                           ('secondary',{'dhw':'none'})]:
            cfg=deepcopy(self.cfg);cfg[key]['enabled']=True
            if key=='secondary':cfg[key]['serves']='both'
            with self.subTest(key=key),self.assertRaises(ValueError):
                sources.validate(cfg,self.entries,self.states,{**self.plant,**change})

    def test_disabled_sources_keep_drafts_but_cannot_expand_history(self):
        self.cfg['secondary'].update(request_entity='switch.removed',entry_id='removed')
        sources.validate(self.cfg,self.entries,self.states,self.plant)
        self.assertEqual(sources.history_entities(self.cfg),set())

    def test_inline_heating_without_buffer_and_external_controller(self):
        for placement in ('supply', 'return'):
            cfg=deepcopy(self.cfg)
            cfg['buffer_heater'].update(enabled=True, placement=placement, managed_by='external',
                                        request_entity='switch.dhw')
            actual=sources.validate(cfg,self.entries,self.states,{**self.plant,'heating':'direct','dhw':'none'})
            self.assertEqual(actual['buffer_heater']['placement'],placement)
            self.assertEqual(actual['buffer_heater']['entry_id'],'')

    def test_legacy_heater_keeps_buffer_placement_and_rejects_unknown_locations(self):
        del self.cfg['buffer_heater']['placement']
        self.assertEqual(sources.validate(self.cfg,self.entries,self.states,self.plant)['buffer_heater']['placement'],'buffer')
        for value in ('tank',[],None):
            self.cfg['buffer_heater']['placement']=value
            with self.subTest(value=value),self.assertRaises(ValueError):
                sources.validate(self.cfg,self.entries,self.states,self.plant)

    def test_source_types_and_served_circuits_are_independent_of_r290_control(self):
        for kind in sources.KINDS:
            for serves in ('dhw','heating','both'):
                cfg=deepcopy(self.cfg)
                cfg['secondary'].update(enabled=True,kind=kind,serves=serves,managed_by='external')
                actual=sources.validate(cfg,self.entries,self.states,self.plant)
                self.assertEqual(actual['secondary']['entry_id'],'')


class SourcePanelTests(unittest.IsolatedAsyncioTestCase):
    setUp = panel_fixture.PanelTests.setUp
    error_code = panel_fixture.PanelTests.error_code

    async def test_passive_save_history_scope_and_old_client_preservation(self):
        put(self.hass,'switch.heater','on')
        put(self.hass,'sensor.heater_energy',20,'kWh')
        cfg=sources.defaults();cfg['dhw_heater'].update(enabled=True,request_entity='switch.heater',energy_entity='sensor.heater_energy')
        await panel.ws_settings(self.hass,self.connection,{'id':1,'settings':{'heat_sources':cfg}})
        self.connection.send_error.assert_not_called()
        self.assertIn('sensor.heater_energy',panel._allowed_history(self.hass))
        await panel.ws_settings(self.hass,self.connection,{'id':2,'settings':{'name':'legacy save'}})
        self.assertEqual(self.hass.data['r290_heatpump']['_panel']['settings']['heat_sources'],cfg)
        self.hass.services.async_call.assert_not_awaited()

    async def test_invalid_source_does_not_overwrite_settings(self):
        cfg=sources.defaults();cfg['dhw_heater'].update(enabled=True,power_entity='switch.curve')
        await panel.ws_settings(self.hass,self.connection,{'id':1,'settings':{'heat_sources':cfg}})
        self.assertEqual(self.error_code(),'invalid_heat_sources')
        self.assertEqual(self.hass.data['r290_heatpump']['_panel']['settings'],{})
        self.hass.services.async_call.assert_not_awaited()

    async def test_cached_b8_client_cannot_reset_inline_heater_placement(self):
        cfg=sources.defaults()
        cfg['buffer_heater'].update(enabled=True,managed_by='external',placement='supply')
        plant=panel.legacy_plant({'hp':self.entry});plant['heating']='direct'
        await panel.ws_settings(self.hass,self.connection,{'id':1,'settings':{'plant':plant,'heat_sources':cfg}})
        old_client=deepcopy(cfg);del old_client['buffer_heater']['placement']
        await panel.ws_settings(self.hass,self.connection,{'id':2,'settings':{'heat_sources':old_client}})
        self.connection.send_error.assert_not_called()
        saved=self.hass.data['r290_heatpump']['_panel']['settings']
        self.assertEqual(saved['heat_sources']['buffer_heater']['placement'],'supply')
        self.assertEqual(saved['plant']['heating'],'direct')
        self.hass.services.async_call.assert_not_awaited()

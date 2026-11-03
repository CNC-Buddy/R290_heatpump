"""Initial and options flows propose the right sources without plant changes."""
import importlib
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

import test_shared_connection as fixture
from test_auxiliary_pump import put

fixture.module('homeassistant.helpers.entity_registry', async_get=lambda hass: hass.entity_registry)
suggestions = importlib.import_module('r290_under_test.pump_suggestions')
pump_config = importlib.import_module('r290_under_test.pump_config')


class PumpSuggestionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bridge = fixture.Entry('bridge', 'modbus_bridge', host='proxy')
        self.hp1 = fixture.Entry('hp1', 'heat_pump', slave=1, bridge_entry_id='bridge')
        self.hp2 = fixture.Entry('hp2', 'heat_pump', slave=2, bridge_entry_id='bridge')
        self.hass = fixture.Hass([self.hp2, self.bridge, self.hp1])
        self.hass.entity_registry = types.SimpleNamespace(entities={})
        self.initial_operations = list(fixture.Client.operations)
        self.ids = {}
        for entry in (self.hp2, self.hp1):
            for key, fragment in suggestions.UNIT_SOURCES.items():
                unit = 'Hz' if key == 'frequency_entities' else 'l/min' if key == 'flow_entities' else '°C'
                self.add(entry, key, fragment, unit=unit)
            for key, fragment in suggestions.TEMPERATURE_SOURCES.items():
                self.add(entry, key, fragment, unit='°C')
            self.add(entry, 'defrost_entities', 'running_status_1_system_defrost_status', value='off')
            self.add(entry, 'demand_entity', 'relay_output_status_1_main_engine_circulating_water_pump_status', value='on')

    def add(self, entry, key, fragment, unit=None, value=30):
        # Deliberately unrelated entity ID and friendly name: use registry identity.
        entity_id=f'sensor.renamed_{entry.entry_id}_{key}'
        self.hass.entity_registry.entities[entity_id]=types.SimpleNamespace(
            entity_id=entity_id, config_entry_id=entry.entry_id, platform='r290_heatpump',
            unique_id=f'r290_heatpump_{fragment}_slave_{entry.data["slave"]}',
            disabled_by=None, name='Unrelated friendly name')
        put(self.hass, entity_id, value, unit)
        self.ids[(entry.entry_id,key)]=entity_id
        return entity_id

    def test_new_cascade_uses_renamed_entities_in_numeric_slave_order(self):
        result=suggestions.suggest_pump_entities(self.hass)
        for key in (*suggestions.UNIT_SOURCES, 'defrost_entities', 'demand_entity'):
            self.assertEqual(result[key],[self.ids[('hp1',key)],self.ids[('hp2',key)]])
        for key in suggestions.TEMPERATURE_SOURCES:
            self.assertEqual(result[key], self.ids[('hp1',key)])
        self.assertNotIn('speed_entity',result)
        self.assertNotIn('enable_entity',result)
        self.assertNotIn('dhw_entity',result)
        self.hass.services.async_call.assert_not_awaited()
        self.assertEqual(fixture.Client.operations, self.initial_operations)

    def test_missing_or_disabled_unit_source_never_shortens_a_column(self):
        self.hass.entity_registry.entities[self.ids[('hp2','defrost_entities')]].disabled_by='integration'
        del self.hass.states[self.ids[('hp2','flow_entities')]]
        result=suggestions.suggest_pump_entities(self.hass)
        self.assertNotIn('defrost_entities',result)
        self.assertNotIn('flow_entities',result)
        for key in ('frequency_entities','supply_entities','return_entities'):
            self.assertEqual(len(result[key]),2)
        self.assertEqual(self.hass.entity_registry.entities[self.ids[('hp2','defrost_entities')]].disabled_by,'integration')

    def test_wrong_measurement_units_and_duplicate_registry_matches_are_omitted(self):
        self.hass.states[self.ids[('hp2','flow_entities')]].attributes['unit_of_measurement']='W'
        original=self.hass.entity_registry.entities[self.ids[('hp1','supply_entities')]]
        self.hass.entity_registry.entities['sensor.duplicate']=types.SimpleNamespace(**{**vars(original),'entity_id':'sensor.duplicate'})
        put(self.hass,'sensor.duplicate',35,'°C')
        result=suggestions.suggest_pump_entities(self.hass)
        self.assertNotIn('flow_entities',result)
        self.assertNotIn('supply_entities',result)

    def test_saved_mappings_empty_fields_and_reverse_order_win(self):
        existing={'frequency_entities':[self.ids[('hp2','frequency_entities')],self.ids[('hp1','frequency_entities')]],
                  'tank_entity':'sensor.custom_tank','pump_power_entity':'','defrost_entities':[],
                  'speed_entity':'number.my_pump'}
        result=suggestions.suggest_pump_entities(self.hass, existing)
        for key,value in existing.items():self.assertEqual(result[key],value)
        self.assertEqual(result['flow_entities'],[self.ids[('hp2','flow_entities')],self.ids[('hp1','flow_entities')]])
        self.assertEqual(existing['pump_power_entity'],'')

    def test_custom_existing_lists_do_not_get_unrelated_r290_columns(self):
        existing={'frequency_entities':['sensor.template_frequency']}
        self.assertEqual(suggestions.suggest_pump_entities(self.hass,existing),existing)

    def test_two_bridges_and_duplicate_slave_numbers_do_not_mix_plants(self):
        self.hass.config_entries.entries.append(fixture.Entry('other','modbus_bridge',host='other'))
        self.hp2.data['bridge_entry_id']='other'
        self.assertEqual(suggestions.suggest_pump_entities(self.hass),{})
        self.hp2.data['bridge_entry_id']='bridge'
        self.hp2.data['slave']=1
        self.assertEqual(suggestions.suggest_pump_entities(self.hass),{})

    def test_single_unit_pump_relay_can_propose_circulation_demand(self):
        self.hass.config_entries.entries.remove(self.hp2)
        result=suggestions.suggest_pump_entities(self.hass)
        self.assertEqual(result['demand_entity'],[self.ids[('hp1','demand_entity')]])
        self.hass.states[result['demand_entity'][0]].state='heating'
        self.assertNotIn('demand_entity',suggestions.suggest_pump_entities(self.hass))

    def test_partial_demand_list_is_never_proposed_for_cascade(self):
        del self.hass.states[self.ids[('hp2', 'demand_entity')]]
        self.assertNotIn('demand_entity', suggestions.suggest_pump_entities(self.hass))

    def test_saved_common_demand_is_preserved_as_single_item_list(self):
        old = {'demand_entity': 'binary_sensor.my_combined_demand'}
        result = suggestions.suggest_pump_entities(self.hass, old)
        self.assertEqual(result['demand_entity'], ['binary_sensor.my_combined_demand'])
        self.assertEqual(old['demand_entity'], 'binary_sensor.my_combined_demand')

    def test_demand_schema_accepts_multiple_entities_and_normalizes_saved_scalar(self):
        schema = pump_config.pump_schema({'demand_entity': 'sensor.old_demand'})
        self.assertTrue(schema['demand_entity']['entity']['multiple'])

    def test_upgrade_enables_only_integration_disabled_pump_sources(self):
        from r290_under_test.pump_sources import async_enable_default_pump_sources
        er = sys.modules['homeassistant.helpers.entity_registry']
        registry = self.hass.entity_registry
        changes = []
        def update(entity_id, **kwargs):
            changes.append(entity_id)
            registry.entities[entity_id].__dict__.update(kwargs)
        registry.async_update_entity = update
        pump1 = self.ids[('hp1', 'demand_entity')]
        defrost1 = self.ids[('hp1', 'defrost_entities')]
        pump2 = self.ids[('hp2', 'demand_entity')]
        unrelated = self.ids[('hp1', 'flow_entities')]
        for entity_id in (pump1, pump2, unrelated):
            registry.entities[entity_id].disabled_by = 'integration'
        registry.entities[defrost1].disabled_by = 'user'
        with patch.object(er, 'RegistryEntryDisabler', types.SimpleNamespace(INTEGRATION='integration'), create=True):
            async_enable_default_pump_sources(self.hass, self.hp1, 1)
            async_enable_default_pump_sources(self.hass, self.hp1, 1)
        self.assertEqual(changes, [pump1])
        self.assertEqual(registry.entities[defrost1].disabled_by, 'user')
        self.assertEqual(registry.entities[pump2].disabled_by, 'integration')
        self.assertEqual(registry.entities[unrelated].disabled_by, 'integration')
        self.hass.services.async_call.assert_not_awaited()

    def test_pump_status_defaults_decode_the_actual_register_bits(self):
        from r290_under_test.pump_sources import PUMP_STATUS_REGISTERS
        # Execute the actual definitions, including the generated bit entities.
        # Keep the minimal HA imports local to this test.
        entity_module = types.ModuleType('homeassistant.helpers.entity')
        entity_module.EntityCategory = types.SimpleNamespace(DIAGNOSTIC='diagnostic')
        util_module = types.ModuleType('homeassistant.util')
        util_module.slugify = lambda value: re.sub(r'[^a-z0-9]+', '_', value.lower()).strip('_')
        path = Path(__file__).resolve().parents[1] / 'custom_components/r290_heatpump/main.py'
        spec = importlib.util.spec_from_file_location('r290_under_test._pump_main_defs', path)
        definitions = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'homeassistant.helpers.entity': entity_module,
                                     'homeassistant.util': util_module}):
            spec.loader.exec_module(definitions)
        sensors = {item['unique_id']: item for item in definitions.MAIN_SENSORS}
        for fragment, (address, bit) in PUMP_STATUS_REGISTERS.items():
            item = sensors[f'r290_heatpump_{fragment}']
            self.assertEqual((item['address'], item['bit']), (address, bit))
            self.assertTrue(item['enabled_by_default'])
            self.assertEqual(item['input_type'], 'holding')

    def test_panel_and_cop_sources_are_reused_with_units_and_explicit_dhw(self):
        cop=fixture.Entry('cop','cop_calculator',heat_meter='sensor.heat',power_meter='sensor.electric',cop_split_enabled=True,cop_split_sensor='binary_sensor.dhw')
        self.hass.config_entries.entries.append(cop)
        put(self.hass,'sensor.heat',800,'kWh');put(self.hass,'sensor.electric',200,'kWh')
        put(self.hass,'binary_sensor.dhw','off');put(self.hass,'sensor.display_heat',900,'kWh')
        put(self.hass,'sensor.aux_power',102,'W')
        self.hass.data['r290_heatpump']={'_panel':{'settings':{'heat_energy_entity':'sensor.display_heat','pump_power_entity':'sensor.aux_power'}}}
        result=suggestions.suggest_pump_entities(self.hass)
        self.assertEqual(result['heat_energy_entity'],'sensor.display_heat')
        self.assertEqual(result['electric_energy_entity'],'sensor.electric')
        self.assertEqual(result['pump_power_entity'],'sensor.aux_power')
        self.assertEqual(result['dhw_entity'],'binary_sensor.dhw')
        self.hass.states['sensor.electric'].attributes['unit_of_measurement']='W'
        cop.options['cop_split_enabled']=False
        result=suggestions.suggest_pump_entities(self.hass)
        self.assertNotIn('electric_energy_entity',result)
        self.assertNotIn('dhw_entity',result)

    async def test_flows_display_suggestions_but_save_submitted_choices(self):
        flow=fixture.flow_module.R290HeatPumpModbusConfigFlow();flow.hass=self.hass
        with patch.object(pump_config,'pump_schema',side_effect=lambda values=None,**kwargs:dict(values or {})):
            form=await flow.async_step_auxiliary_pump()
            self.assertEqual(form['data_schema']['frequency_entities'],[self.ids[('hp1','frequency_entities')],self.ids[('hp2','frequency_entities')]])
            custom={**form['data_schema'],'name':'Pump','speed_entity':'number.my_pump','tank_entity':'sensor.custom'}
            custom.pop('outdoor_entity')
            await flow.async_step_auxiliary_pump(custom)
            self.assertEqual(flow._pump_input['tank_entity'],'sensor.custom')
            self.assertNotIn('outdoor_entity',flow._pump_input)
            entry=fixture.Entry('aux','auxiliary_pump')
            entry.data.update(custom)
            entry.options={'pump_power_entity':''}
            options=fixture.flow_module.R290HeatPumpOptionsFlow(entry);options.hass=self.hass
            form=await options.async_step_auxiliary_pump()
            self.assertEqual(form['data_schema']['tank_entity'],'sensor.custom')
            self.assertEqual(form['data_schema']['pump_power_entity'],'')
            await options.async_step_auxiliary_pump({'name':'Pump', 'frequency_entities':custom['frequency_entities']})
            self.assertNotIn('tank_entity',options._pump_input)
        self.hass.services.async_call.assert_not_awaited()

    def test_entity_fields_are_removable_suggestions_not_schema_defaults(self):
        vol=sys.modules['voluptuous']
        markers=[]
        def marker(key,**kwargs):markers.append((key,kwargs));return key
        with patch.object(vol,'Required',side_effect=marker),patch.object(vol,'Optional',side_effect=marker):
            pump_config.pump_schema({'frequency_entities':['sensor.custom'],'tank_entity':'sensor.tank'})
        marked=dict(markers)
        self.assertEqual(marked['frequency_entities'],{'description':{'suggested_value':['sensor.custom']}})
        self.assertEqual(marked['tank_entity'],{'description':{'suggested_value':'sensor.tank'}})
        self.assertEqual(marked['speed_entity'],{})


if __name__=='__main__':unittest.main()

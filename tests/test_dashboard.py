from copy import deepcopy
import unittest
import test_panel_api as fixture
from test_auxiliary_pump import put
from test_schematic import model, FIXTURES
panel=fixture.panel

class ChartSettingsTests(unittest.IsolatedAsyncioTestCase):
    setUp=fixture.PanelTests.setUp
    error_code=fixture.PanelTests.error_code

    async def send(self, **overrides):
        put(self.hass, 'sensor.temperature', 35, '°C')
        msg=dict(id=1,key='operation-temperature',expected_revision=0,days=7,entity_ids=['sensor.temperature'])
        msg.update(overrides)
        await panel.ws_charts(self.hass,self.connection,msg)

    async def test_preferences_saved_and_legacy_settings_preserve_them(self):
        await self.send()
        self.connection.send_error.assert_not_called()
        expected=deepcopy(self.hass.data['r290_heatpump']['_panel']['settings']['charts'])
        self.assertEqual(expected['operation-temperature'],dict(revision=1,days=7,entity_ids=['sensor.temperature']))
        await panel.ws_settings(self.hass,self.connection,dict(id=2,settings={'name':'Updated'}))
        self.assertEqual(self.hass.data['r290_heatpump']['_panel']['settings']['charts'],expected)
        self.assertIn('sensor.temperature',panel._allowed_history(self.hass))
        self.hass.services.async_call.assert_not_awaited()

    async def test_admin_and_revision_conflicts(self):
        self.connection.user.is_admin=False
        await self.send()
        self.assertEqual(self.error_code(),'unauthorized')
        self.connection.user.is_admin=True
        await self.send()
        await self.send(days=30)
        self.assertEqual(self.error_code(),'conflict')
        self.assertEqual(self.hass.data['r290_heatpump']['_panel']['settings']['charts']['operation-temperature']['days'],7)
        await self.send(expected_revision=1,days=.25)
        self.assertEqual(self.hass.data['r290_heatpump']['_panel']['settings']['charts']['operation-temperature']['revision'],2)
        self.hass.services.async_call.assert_not_awaited()

    async def test_invalid_input_never_changes_preferences(self):
        invalid=[{'days':True},{'days':float('nan')},{'days':365},{'key':'../bad'}, {'key':'x'*65},
                 {'entity_ids':[]},{'entity_ids':['switch.curve']},{'entity_ids':['sensor.missing']},
                 {'entity_ids':['sensor.temperature']*2},{'entity_ids':[{}]}, {'entity_ids':['sensor.temperature']*25}]
        for case in invalid:
            with self.subTest(case=case):
                await self.send(**case)
                self.assertEqual(self.error_code(),'invalid_chart')
                self.assertNotIn('charts',self.hass.data['r290_heatpump']['_panel']['settings'])
        self.hass.services.async_call.assert_not_awaited()

    async def test_chart_limit_and_boolean_revision(self):
        self.hass.data['r290_heatpump']['_panel']['settings']['charts']={f'chart-{n}':{'revision':1,'days':1,'entity_ids':['sensor.temperature']} for n in range(100)}
        await self.send()
        self.assertEqual(self.error_code(),'invalid_chart')
        await self.send(key='chart-0',expected_revision=True)
        self.assertEqual(self.error_code(),'conflict')
        await self.send(key='chart-0',expected_revision=1)
        self.assertEqual(self.hass.data['r290_heatpump']['_panel']['settings']['charts']['chart-0']['days'],7)

class TankZoneTests(unittest.TestCase):
    def graph(self):
        graph=deepcopy(FIXTURES['full'])
        tank=next(n for n in graph['nodes'] if n['id']=='buffer')
        tank['temperature_zones']=[dict(entity=f'sensor.zone_{i}',height=h) for i,h in enumerate([15,38,62,85])]
        graph['nodes'].append(dict(id='heater_test',type='heater',label='',x=tank['x']+10,y=tank['y']+80,circuit='electric',leg='power',bindings={},tank='buffer'))
        return graph

    def test_four_zones_and_mounted_heater_keep_graph_complete(self):
        graph=model.validate_graph(self.graph())
        self.assertEqual(model.completeness(graph),[])
        self.assertTrue({f'sensor.zone_{i}' for i in range(4)}<=model.history_entities({'published':graph}))
        copy=model.validate_graph(graph);copy['nodes'][-1]['y']+=1
        self.assertNotEqual(copy['nodes'][-1]['y'],graph['nodes'][-1]['y'])

    def test_invalid_zone_heights_entities_count_and_mounts(self):
        for bad in [[],[dict(entity='',height=5)], [dict(entity='sensor.x',height=95)]]:
            graph=self.graph();next(n for n in graph['nodes'] if n['id']=='buffer')['temperature_zones']=bad
            model.validate_graph(graph)
        for zones in [[dict(entity='switch.test',height=50)], [dict(entity='sensor.x',height=True)],
                      [dict(entity='sensor.x',height=50),dict(entity='sensor.y',height=51)],
                      [dict(entity='',height=h) for h in [5,25,45,65,85]],
                      [dict(entity='',height=float('nan'))], [dict(entity='',height=96)],
                      [dict(entity='',height=30,unexpected=True)]]:
            with self.subTest(zones=zones):
                graph=self.graph();next(n for n in graph['nodes'] if n['id']=='buffer')['temperature_zones']=zones
                with self.assertRaises(ValueError): model.validate_graph(graph)
        for parent in ['missing','wp1','heater_test']:
            graph=self.graph();graph['nodes'][-1]['tank']=parent
            with self.assertRaises(ValueError):model.validate_graph(graph)
        graph=self.graph();graph['nodes'][0]['temperature_zones']=[]
        with self.assertRaises(ValueError):model.validate_graph(graph)

if __name__=='__main__':unittest.main()

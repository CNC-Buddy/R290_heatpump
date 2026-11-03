import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {inspect,nodePorts,connection,activeEdges,copy} from '../custom_components/r290_heatpump/frontend/schematic-model.js';
import {preset} from '../custom_components/r290_heatpump/frontend/schematic-presets.js';
const catalogue=JSON.parse(await readFile(new URL('../custom_components/r290_heatpump/frontend/schematic-catalog.json',import.meta.url)));
const templates=Object.fromEntries(['direct','cascade','full','full_pv'].map(k=>[k,preset(k,catalogue)]));
for(const [name,graph] of Object.entries(templates)){
  const report=inspect(graph,catalogue);assert.deepEqual(report.errors,[],name);assert.deepEqual(report.open,[],name);
}
const graph=templates.full;
assert.equal(Object.keys(nodePorts(graph.nodes.find(n=>n.id==='we2_valve'),catalogue)).length,3);
assert.ok(Object.values(nodePorts(graph.nodes.find(n=>n.id==='we2_valve'),catalogue)).every(p=>p.leg==='supply'));
assert.notEqual((await import('../custom_components/r290_heatpump/frontend/schematic-model.js')).colors.we2.supply,(await import('../custom_components/r290_heatpump/frontend/schematic-model.js')).colors.we2.return);
assert.throws(()=>connection({nodes:graph.nodes,edges:[]},catalogue,{node:'plate',port:'secondary_in'},{node:'ww',port:'wp_out'}),/incompatible/);
assert.throws(()=>connection({nodes:graph.nodes,edges:[]},catalogue,{node:'we2_valve',port:'common'},{node:'we2',port:'return'}),/incompatible/);
assert.throws(()=>connection(graph,catalogue,graph.edges[0].from,graph.edges[0].to),/occupied/);

// Cutting WMZ out of the graph must break all WP primary return routes, including
// DHW. A coil or exchanger cannot be a hidden hydraulic bypass around the meter.
const cut=copy(graph);cut.edges=cut.edges.filter(e=>e.from.node!=='wmz'&&e.to.node!=='wmz');
const cutReport=inspect(cut,catalogue);
assert.ok(cutReport.open.some(i=>i.node==='wp1'&&i.code==='loop'));
assert.ok(cutReport.open.some(i=>i.node==='wp2'&&i.code==='loop'));
const ring=copy(graph);ring.edges=ring.edges.filter(e=>e.to.node!=='turn');
assert.ok(inspect(ring,catalogue).open.some(i=>i.node==='circulation'&&i.code==='loop'));
// Taps are dead-end branches; removing them never breaks the circulation path.
const taps=copy(graph);taps.edges=taps.edges.filter(e=>!e.to.node.startsWith('tap'));
assert.ok(!inspect(taps,catalogue).open.some(i=>i.node==='circulation'&&i.code==='loop'));

const p={states:{},data:{entities:[],reports:{}},hass:{connected:true}};
for(const n of graph.nodes){
  if(['pump','heat_source','heat_pump'].includes(n.type))n.bindings.status=`binary_sensor.${n.id}`;
  if(n.type==='valve')n.bindings.phase=`binary_sensor.${n.id}`;
  for(const id of Object.values(n.bindings))p.states[id]={state:n.type==='valve'?'on':'on',attributes:{},last_reported:new Date().toISOString()};
}
const flow=activeEdges(graph,catalogue,p);
assert.ok(graph.edges.filter(e=>e.from.node==='ww'&&e.from.port==='wp_out'||e.to.node==='ww'&&e.to.port==='wp_in').every(e=>flow.has(e.id)));
assert.ok(!flow.has(graph.edges.find(e=>e.to.node==='plate'&&e.to.port==='primary_in').id));
assert.ok(!flow.has(graph.edges.find(e=>e.to.node==='tap1').id));
delete p.states['binary_sensor.wp_valve'];
assert.ok(!activeEdges(graph,catalogue,p).has(graph.edges.find(e=>e.from.node==='wmz').id));
p.hass.connected=false;assert.equal(activeEdges(graph,catalogue,p).size,0);
assert.deepEqual(inspect({...graph,version:2},catalogue).errors,['format']);
assert.ok(inspect({...graph,nodes:[{...graph.nodes[0],type:'constructor'}]},catalogue).errors.length);
// Shared golden fixture also exercises the independent Python validator.
await writeFile(new URL('./schematic-fixtures.json',import.meta.url),JSON.stringify(templates,null,2)+'\n');
console.log('PASS schematic templates, typed ports, WMZ placement, circulation, live paths and invalid input');

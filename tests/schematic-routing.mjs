import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {autoRoute,clearSegment,moveSegment,viaPoints,retainRoutes,validRoute} from '../custom_components/r290_heatpump/frontend/schematic-routing.js';
import {bindingsFor,bindingHelp} from '../custom_components/r290_heatpump/frontend/schematic-bindings.js';
import {paths,renderGraph} from '../custom_components/r290_heatpump/frontend/schematic-svg.js';
import {preset} from '../custom_components/r290_heatpump/frontend/schematic-presets.js';
import {inspect,createNode} from '../custom_components/r290_heatpump/frontend/schematic-model.js';
import {attachHeater,moveNode,temperature,tankReadings} from '../custom_components/r290_heatpump/frontend/schematic-tanks.js';
const catalog=JSON.parse(await readFile(new URL('../custom_components/r290_heatpump/frontend/schematic-catalog.json',import.meta.url)));
const boxes=[[180,80,300,300],[420,240,510,380]];
for(const [start,end] of [[[73,113],[600,420]],[[90,110],[90,500]],[[73,113],[600,113]]]){
  const route=autoRoute(start,end,boxes);assert.deepEqual(route[0],start);assert.deepEqual(route.at(-1),end);
  assert.ok(route.length<=7,JSON.stringify(route));
  for(let i=1;i<route.length;i++){assert.ok(route[i][0]===route[i-1][0]||route[i][1]===route[i-1][1]);assert.ok(clearSegment(route[i-1],route[i],boxes));}
}
const moved=moveSegment([[30,40],[220,40]],0,120);
assert.deepEqual(moved,[[30,120],[220,120]]);
assert.deepEqual(viaPoints([30,40],[220,40],moved),[[30,40],[30,120],[220,120],[220,40]]);
assert.throws(()=>moveSegment([[30,40],[220,40]],0,-20));
const graph=preset('full',catalog),line=graph.edges.find(e=>e.points?.length);
const saved=structuredClone(line.points),node=graph.nodes.find(n=>n.id===line.from.node);
moveNode(graph,node,node.x+40,node.y+30);assert.deepEqual(line.points,saved);
for(const path of Object.values(paths(graph,catalog)))assert.ok(!/NaN|Infinity/.test(path.d));
const heater=createNode('heater',catalog,'heater',0,0);graph.nodes.push(heater);attachHeater(graph,heater,'buffer');
const tank=graph.nodes.find(n=>n.id==='buffer'),dx=heater.x-tank.x,dy=heater.y-tank.y;
moveNode(graph,tank,tank.x+20,tank.y+40);assert.equal(heater.x-tank.x,dx);assert.equal(heater.y-tank.y,dy);
moveNode(graph,heater,0,0);assert.equal(heater.x,tank.x+10);assert.equal(heater.y,tank.y+20);
tank.temperature_zones=[{entity:'sensor.top',height:15},{entity:'sensor.bottom',height:85}];
assert.deepEqual(inspect(graph,catalog).errors,[]);
const p={language:'de',states:{'sensor.top':{state:'104',attributes:{unit_of_measurement:'°F'},last_reported:new Date().toISOString()}},data:{entities:[],reports:{}},hass:{connected:true},_animationPaused:true};
assert.equal(temperature(p,'sensor.top'),40);assert.equal(temperature(p,'sensor.bottom'),null);
assert.match(tankReadings(tank,p),/40/);assert.match(tankReadings(tank,p),/—/);
for(const editor of [false,true]){const svg=renderGraph(graph,catalog,p,{editor,geometry:paths(graph,catalog)});assert.match(svg,/sg-zones-buffer/);assert.match(svg,/sg-heater/);assert.ok(svg.indexOf('data-node="heater"')>svg.indexOf('data-node="buffer"'));}
const invalid=structuredClone(graph);invalid.nodes.find(n=>n.id==='heater').tank='wp1';assert.ok(inspect(invalid,catalog).errors.length);
// An unrelated obstacle must not change existing paths, including after JSON
// export/import. Moving an actual endpoint still adapts that connection.
const stable=preset('full',catalog),original=paths(stable,catalog);
retainRoutes(stable,original);
const battery=createNode('battery',catalog,'new_battery',710,360);stable.nodes.push(battery);
assert.deepEqual(paths(stable,catalog),original);
moveNode(stable,battery,850,650);assert.deepEqual(paths(stable,catalog),original);
assert.deepEqual(paths(JSON.parse(JSON.stringify(stable)),catalog),original);
const wp=stable.nodes.find(n=>n.id==='wp1');moveNode(stable,wp,wp.x+70,wp.y+50);
const adapted=paths(stable,catalog);
for(const e of stable.edges)assert.equal(adapted[e.id].d===original[e.id].d,e.from.node!=='wp1'&&e.to.node!=='wp1');
assert.deepEqual(inspect(stable,catalog).errors,[]);
for(const route of [null,[],[[1,1]],[[1,1],[2,2]],[[0,0],[Infinity,0]],[[0,0],[4001,0]],Array(257).fill([0,0])]){
 assert.equal(validRoute(route),false);const broken=structuredClone(stable);broken.edges[0].route=route;assert.ok(inspect(broken,catalog).errors.includes('pipe'));
}
for(const type of ['grid','pv','house','battery','heater']){
 const n=createNode(type,catalog,'electric',0,0),keys=bindingsFor(n).map(b=>b.key);
 assert.ok(!keys.some(k=>['flow','supply','return','phase','fan'].includes(k)));
 for(const en of [true,false])assert.doesNotMatch(bindingHelp(n,en),/Ventil|valve|Status\/Flow/);
}
assert.deepEqual(bindingsFor(battery).map(b=>b.key),['value','soc']);
const legacyElectric={...battery,bindings:{supply:'sensor.top',value:'sensor.top',soc:'sensor.top'}};
const electricSvg=renderGraph({version:1,nodes:[legacyElectric],edges:[]},catalog,p);
assert.doesNotMatch(electricSvg,/Vorlauf|Supply/);assert.match(electricSvg,/Ladezustand/);
console.log('PASS routing avoids staircases, manual segments retain anchors, mounted heaters follow tanks and temperature zones preserve missing values');
console.log('PASS independent routes survive placement, moves and reload; only connected routes adapt; electrical fields and saved-route validation');

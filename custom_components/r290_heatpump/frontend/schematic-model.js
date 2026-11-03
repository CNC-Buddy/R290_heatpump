// Display graph only. Catalogue is shared with the Python validator.
import {validRoute} from './schematic-routing.js?v=1.1.1';
export const copy = value => structuredClone(value);
export const emptyGraph = () => ({version:1,nodes:[],edges:[]});
export const circuits = {wp:['Wärmepumpenkreis','Heat-pump circuit'],heating:['Heizungswasser','Heating water'],we2:['Wärmeerzeuger 2','Heat source 2'],warmwater:['Warmwasser','Hot water'],electric:['Elektrisch','Electric']};
export const colors = {wp:{supply:'#f18a64',return:'#69b9df'},heating:{supply:'#efb251',return:'#53c9a9'},we2:{supply:'#c08ce9',return:'#959ff2'},warmwater:{supply:'#ffc15a',return:'#4fc5d3'},electric:{power:'#d6bd65'}};
export function nodePorts(node,catalog){
  return Object.fromEntries(Object.entries(catalog[node.type].ports).map(([key,p])=>{
    let side=p.side;
    if(node.flip)side={left:'right',right:'left'}[side]||side;
    if(node.flip_y)side={top:'bottom',bottom:'top'}[side]||side;
    return [key,{...p,circuit:p.circuit==='$'?node.circuit:p.circuit,leg:p.leg==='$'?node.leg:p.leg,x:node.flip?catalog[node.type].width-p.x:p.x,y:node.flip_y?catalog[node.type].height-p.y:p.y,side}];
  }));
}
export const endpointKey = ep => `${ep.node}:${ep.port}`;
export function compatible(a,b){return a.circuit===b.circuit&&a.leg===b.leg&&a.direction!=='in'&&b.direction!=='out';}
export function connection(graph,catalog,a,b){
  if(a.node===b.node)throw Error('same_node');
  if(graph.edges.some(e=>[e.from,e.to].some(p=>[endpointKey(a),endpointKey(b)].includes(endpointKey(p)))))throw Error('occupied');
  const pa=nodePorts(graph.nodes.find(n=>n.id===a.node),catalog)[a.port],pb=nodePorts(graph.nodes.find(n=>n.id===b.node),catalog)[b.port];
  if(!pa||!pb)throw Error('port');
  if(compatible(pa,pb))return {from:a,to:b};
  if(compatible(pb,pa))return {from:b,to:a};
  throw Error('incompatible');
}
export function inspect(graph,catalog){
  const errors=[],open=[],used=new Set(),adj=new Map(),nodes=new Map();
  const add=(a,b)=>{if(!adj.has(a))adj.set(a,[]);adj.get(a).push(b);};
  const coord=n=>typeof n==='number'&&Number.isFinite(n)&&n>=0&&n<=3600;
  const id=s=>typeof s==='string'&&/^[a-z][a-z0-9_-]{0,47}$/.test(s);
  const only=(v,keys)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).every(k=>keys.includes(k));
  const bindKeys=['value','supply','return','status','flow','phase','fan','soc'];
  if(!only(graph,['version','nodes','edges'])||graph.version!==1||!Array.isArray(graph.nodes)||!Array.isArray(graph.edges)||graph.nodes.length>80||graph.edges.length>160)return {errors:['format'],open:[]};
  for(const n of graph.nodes){
    const spec=Object.hasOwn(catalog,n?.type)?catalog[n.type]:null;
    if(!only(n,['id','type','label','x','y','circuit','leg','bindings','flip','flip_y','tank','temperature_zones'])||!id(n.id)||nodes.has(n.id)||!spec||!coord(n.x)||!coord(n.y)||typeof(n.label??'')!=='string'||(n.label||'').length>70||!spec.circuits.includes(n.circuit)||!spec.legs.includes(n.leg)||(n.circuit==='electric')!==(n.leg==='power')||['flip','flip_y'].some(k=>typeof(n[k]??false)!=='boolean')||!only(n.bindings||{},bindKeys)||Object.values(n.bindings||{}).some(v=>typeof v!=='string'||v&&!/^(sensor|binary_sensor|switch|input_boolean|number|input_number|select|input_select|fan|climate)\.[a-z0-9_]+$/.test(v))){errors.push('component');continue;}
    nodes.set(n.id,n);
  }
  if(errors.length)return {errors,open};
  for(const n of nodes.values()){
    if(Object.hasOwn(n,'tank')&&(n.type!=='heater'||typeof n.tank!=='string'||!['buffer','dhw_tank'].includes(nodes.get(n.tank)?.type)))errors.push('component');
    if(Object.hasOwn(n,'temperature_zones')){
      const zones=n.temperature_zones;if(!['buffer','dhw_tank'].includes(n.type)||!Array.isArray(zones)||zones.length>4||zones.some((z,i)=>!only(z,['entity','height'])||typeof z.entity!=='string'||z.entity&&!/^sensor\.[a-z0-9_]+$/.test(z.entity)||!coord(z.height)||z.height<5||z.height>95||i>0&&z.height-zones[i-1].height<8))errors.push('component');
    }
  }
  if(errors.length)return {errors,open};
  const edgeIds=new Set();
  for(const e of graph.edges){
    if(!only(e,['id','from','to','points','route'])||!id(e.id)||edgeIds.has(e.id)||!['from','to'].every(k=>only(e[k],['node','port'])&&typeof e[k].node==='string'&&typeof e[k].port==='string')||!Array.isArray(e.points||[])||(e.points||[]).length>16||(e.points||[]).some(p=>!Array.isArray(p)||p.length!==2||!p.every(coord))||Object.hasOwn(e,'route')&&!validRoute(e.route)){errors.push('pipe');continue;}
    edgeIds.add(e.id);
    const na=nodes.get(e.from.node),nb=nodes.get(e.to.node),a=na&&nodePorts(na,catalog)[e.from.port],b=nb&&nodePorts(nb,catalog)[e.to.port];
    if(!a||!b||na===nb||used.has(endpointKey(e.from))||used.has(endpointKey(e.to))||!compatible(a,b)){errors.push('incompatible');continue;}
    used.add(endpointKey(e.from));used.add(endpointKey(e.to));add(endpointKey(e.from),endpointKey(e.to));
  }
  if(!nodes.size)open.push({node:'',code:'empty'});
  for(const n of nodes.values()){
    const spec=catalog[n.type],ports=nodePorts(n,catalog);
    for(const group of spec.groups){
      const count=group.filter(k=>used.has(`${n.id}:${k}`)).length;
      if(count&&count!==group.length)open.push({node:n.id,code:'open',ports:group.filter(k=>!used.has(`${n.id}:${k}`))});
      for(const a of group)for(const b of group)if(a!==b&&ports[a].direction!=='out'&&ports[b].direction!=='in')add(`${n.id}:${a}`,`${n.id}:${b}`);
    }
    if(!n.tank&&!Object.keys(ports).some(k=>used.has(`${n.id}:${k}`)))open.push({node:n.id,code:'isolated'});
    if(spec.require_all&&Object.keys(ports).some(k=>!used.has(`${n.id}:${k}`)))open.push({node:n.id,code:'required'});
  }
  for(const n of nodes.values())if(catalog[n.type].closed_loop){
    for(const [key,p] of Object.entries(nodePorts(n,catalog)))if(p.direction==='out'){
      const start=`${n.id}:${key}`,queue=[...(adj.get(start)||[])],seen=new Set();let closed=false;
      while(queue.length){const at=queue.pop();if(at===start){closed=true;break;}if(!seen.has(at)){seen.add(at);queue.push(...(adj.get(at)||[]));}}
      if(!closed){open.push({node:n.id,code:'loop'});break;}
    }
  }
  return {errors:[...new Set(errors)],open,adj};
}
export function createNode(type,catalog,id,x=60,y=60){const s=catalog[type];return {id,type,label:'',x,y,circuit:s.circuits[0],leg:s.legs[0],bindings:{},flip:false};}
export function freshValue(p,id){
  const s=p.states[id];if(!s||p.hass?.connected===false||s.attributes?.restored||['unknown','unavailable',''].includes(s.state))return null;
  const at=p.data?.reports?.[id]||s.last_reported;
  // Boolean external devices may legitimately report only state changes.
  const integrated=p.data?.entities?.some(e=>e.id===id);
  if((integrated||!['on','off','true','false'].includes(s.state))&&(!at||!Number.isFinite(Date.parse(at))||Date.now()-Date.parse(at)>180000))return null;
  return s.state;
}
export function isOn(p,id){const v=freshValue(p,id);if(v===null)return null;return ['on','true'].includes(v)||Number.isFinite(Number(v))&&Number(v)>0?true:['off','false'].includes(v)||Number(v)===0?false:null;}

// Only animate complete, proven live cycles. A compressor signal alone does not
// establish water flow; heat pumps require an assigned flow/pump-status source.
export function activeEdges(graph,catalog,p){
  if(p._animationPaused||p.hass?.connected===false)return new Set();
  const adj=new Map(),enabledSources=[];
  const add=(a,b,edge=null)=>{if(!adj.has(a))adj.set(a,[]);adj.get(a).push({to:b,edge});};
  for(const e of graph.edges)add(endpointKey(e.from),endpointKey(e.to),e.id);
  for(const n of graph.nodes){
    const ports=nodePorts(n,catalog),spec=catalog[n.type],b=n.bindings||{};
    let allowed=true,branch=null;
    if(['heat_pump','heat_source','pump'].includes(n.type))allowed=isOn(p,b.flow||b.status)===true;
    if(n.type==='valve'){
      const v=freshValue(p,b.phase);branch=['on','true','1','dhw','warmwater'].includes(v)?'a':['off','false','0','heating'].includes(v)?'b':null;allowed=branch!==null;
    }
    if(!allowed)continue;
    for(const g of spec.groups)for(const a of g)for(const z of g){
      if(a===z||ports[a].direction==='out'||ports[z].direction==='in'||branch&&z!==branch)continue;
      add(`${n.id}:${a}`,`${n.id}:${z}`);
    }
    if(spec.closed_loop&&allowed)for(const [k,v] of Object.entries(ports))if(v.direction==='out')enabledSources.push(`${n.id}:${k}`);
  }
  const result=new Set();
  for(const start of enabledSources){
    // Edges in the start node's strongly connected region belong to a closed
    // live circuit; open taps and inactive branches are excluded.
    const reachable=new Set([start]),queue=[start];
    while(queue.length){const k=queue.pop();for(const link of adj.get(k)||[])if(!reachable.has(link.to)){reachable.add(link.to);queue.push(link.to);}}
    const back=new Set([start]);let changed=true;
    while(changed){changed=false;for(const [a,list] of adj)if(reachable.has(a)&&!back.has(a)&&list.some(l=>back.has(l.to))){back.add(a);changed=true;}}
    for(const [a,list] of adj)if(reachable.has(a)&&back.has(a))for(const link of list)if(link.edge&&back.has(link.to))result.add(link.edge);
  }
  return result;
}

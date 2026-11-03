import "/r290_heatpump_static/r290-panel.js";

const now=Date.now(), stamp=new Date(now).toISOString();
const states={}, entities=[], entries=[
  {id:"hp1",title:"R290 Heat Pump (Slave 1)",type:"heat_pump",slave:1},
  {id:"hp2",title:"R290 Heat Pump (Slave 2)",type:"heat_pump",slave:2},
  {id:"heatcurve",title:"Heizkurve",type:"heating_curve"},
  {id:"pump",title:"Wilo · gemeinsame Zusatzpumpe",type:"auxiliary_pump"}
];
function add(id,value,unit,name,entryId,uniqueId,extra={}){
  states[id]={entity_id:id,state:String(value),attributes:{friendly_name:name,...(unit?{unit_of_measurement:unit}:{}),...extra},last_changed:stamp,last_updated:stamp,last_reported:stamp};
  if(entryId)entities.push({id,name,entry_id:entryId,unique_id:uniqueId||id,disabled:false});
  return id;
}
for(let n=1;n<=2;n++){
  const names={compressor_operating_frequency:[n===1?40:0,"Hz",`WP ${n} · Verdichter`],water_outlet_temperature_t7:[n===1?35:32,"°C",`WP ${n} · Vorlauf`],return_water_temperature_t6:[30,"°C",`WP ${n} · Rücklauf`],water_flow:[n===1?22:0,"L/min",`WP ${n} · Durchfluss`]};
  for(const [key,[value,unit,name]] of Object.entries(names))add(`sensor.${key}_${n}`,value,unit,name,`hp${n}`,`r290_heatpump_${key}_slave_${n}`);
  add(`binary_sensor.defrost_${n}`,'off',null,'System defrost status',`hp${n}`,`r290_heatpump_running_status_1_system_defrost_status_slave_${n}`);
  add(`sensor.power_${n}`,n===1?2400:0,'W',`WP ${n} · Leistung`,`hp${n}`,`r290_heatpump_device_input_power_slave_${n}`);
  add(`sensor.fan_${n}`,n===1?620:0,'rpm',`WP ${n} · Lüfter`,`hp${n}`,`r290_heatpump_fan_operating_frequency_rotational_speed_slave_${n}`);
  add(`sensor.pump_pwm_${n}`,35,'','Pump speed PWM',`hp${n}`,`r290_heatpump_pump_speed_pwm_slave_${n}`);
  add(`sensor.pump_percent_${n}`,65,'%','Pump speed',`hp${n}`,`r290_heatpump_pump_speed_percent_slave_${n}`);
  add(`number.p099_${n}`,n===1?3:8,"K","P099 - Target temperature difference",`hp${n}`,`r290_heatpump_p099_target_0163_slave_${n}_v2`,{min:1,max:15,step:1});
  add(`number.p100_${n}`,50,"%","P100 - Minimum pump speed",`hp${n}`,`r290_heatpump_p100_minimum_pump_0164_slave_${n}_v2`,{min:20,max:100,step:1});
  for(let p=101;p<150;p++)add(`number.p${p}_${n}`,(p===116?0:p%10),"",`P${p} - Parameter ${p}`,`hp${n}`,`r290_heatpump_p${p}_slave_${n}_v2`,{min:0,max:100,step:1});
}
add("sensor.tank",52.4,"°C","Warmwasserspeicher");add("sensor.buffer",32.1,"°C","Heizungspuffer");
add("sensor.outdoor",11.6,"°C","Außentemperatur");add("sensor.radiator_supply",31.3,"°C","Heizkörper Vorlauf");add("sensor.radiator_return",26.4,"°C","Heizkörper Rücklauf");
add("sensor.pump_power",102,"W","Zusatzpumpe Leistung");add("sensor.heat",47990,"kWh","Wärmemengenzähler",null,null,{device_class:"energy"});
states["sensor.heat"].last_updated=new Date(now-1000*3600*3).toISOString();
add("sensor.electric",572.4,"kWh","Stromzähler",null,null,{device_class:"energy"});
const curves=[];
for(const [type,prefix,title] of [['heating_curve','heating','Heizkörper'],['hot_water_curve','hotwater','Warmwasser'],['floor_heating_curve','floor_heating','Fußbodenheizung'],['cooling_curve','cooling','Kühlung']]){
  const id=type==='heating_curve'?'heatcurve':prefix;
  if(id!=='heatcurve')entries.push({id,title,type});
  const snap={entry_id:id,revision:'revision-'+id,outdoor_entity:'sensor.outdoor',controls:[],custom_points:false,
    points:[{outdoor:-15,target:50},{outdoor:20,target:25}],point_error:null,
    point_limits:{outdoor_min:-30,outdoor_max:35,target_min:-20,target_max:80,step:.1,max_points:10}};
  function field(key,label,section,value,domain,attrs,suffix){
    const eid=`${domain}.${prefix}_${key}`;
    add(eid,value,domain==='number'?'°C':null,label,id,suffix?`r290_heatpump_${prefix}_${suffix}_${id}`:`r290_heatpump_heatcurve_${id}_${key}`,attrs);
    snap.controls.push({key,label,section,id:eid});
  }
  for(const [key,label,value,min,max,step,section] of [
    ['t_out_min','Außen · kalter Stützpunkt',-15,-30,10,1,'basis'],['t_flow_max','Soll · am kalten Stützpunkt',50,25,70,1,'basis'],
    ['t_out_max','Außen · warmer Stützpunkt',20,0,35,1,'basis'],['t_flow_min','Soll · am warmen Stützpunkt',25,20,60,1,'basis'],
    ['inertia_hours','Sollwert glätten · Stunden',0,0,24,.1,'fine'],['stepsize_c','Mindeständerung · °C',.5,0,2,.1,'fine'],
    ['pv_grid_threshold_min_kw','PV-Schwelle 1 · kW',2,0,50,.1,'pv'],['pv_grid_threshold_max_kw','PV-Schwelle 2 · kW',3,0,50,.1,'pv'],
    ['pv_offset_reset_kw','Rücksetzschwelle · kW',.25,0,50,.05,'pv'],['pv_battery_threshold_pct','Batterieschwelle · %',80,0,100,1,'pv'],
    ['pv_hold_minutes','PV-Haltezeit · min',15,0,240,1,'pv'],['external_offset_value','Externer Offset · °C',0,-10,10,1,'pv'],
    ['external_offset_hold_minutes','Externe Haltezeit · min',5,0,240,1,'pv']
  ])field(key,label,section,value,'number',{min,max,step},section==='pv'?key:null);
  for(const [key,label,section,suffix] of [['heatcurve_active','Kurvenregelung','basis','curve_active'],['pv_enabled','PV-Optimierung','pv','pv_optimization'],['external_offset_enabled','Externe Anhebung','pv','external_heating_offset']])field(key,label,section,key==='heatcurve_active'?'on':'off','switch',{},suffix);
  for(const [key,label] of [['pv_grid_offset_min','Offset ab Schwelle 1'],['pv_grid_offset_max','Offset ab Schwelle 2'],['pv_battery_offset','Batterie-Offset']])field(key,label,'pv','+0 degC','select',{options:Array.from({length:21},(_,i)=>`${i-10>=0?'+':''}${i-10} degC`)},key);
  curves.push(snap);
}
const config={min_speed:30,max_speed:100,safe_speed:60,defrost_speed:100,manual_speed:60,heating_delta:5,dhw_delta:5,min_flow:15,max_step:2,interval:30,startup_seconds:60,postrun_seconds:120,max_age:180,commissioned:true,legacy_automations:[]};
Object.assign(config,{speed_entity:'light.pump',frequency_entities:[1,2].map(n=>`sensor.compressor_operating_frequency_${n}`),supply_entities:[1,2].map(n=>`sensor.water_outlet_temperature_t7_${n}`),return_entities:[1,2].map(n=>`sensor.return_water_temperature_t6_${n}`)});
for(const [key,value,unit] of [['actual_speed',60,'%'],['suggested_speed',58,'%'],['target_delta',5,'K'],['status','heating',null]])add(`sensor.pump_${key}`,value,unit,key,'pump',`r290_pump_pump_${key}`);
add('binary_sensor.dhw','on',null,'Warmwasserladung');
add('switch.buffer_charge','off',null,'Pufferladepumpe');
add('switch.radiators','off',null,'Heizkreispumpe');
const settings={name:"Beispielanlage",tank_liters:300,buffer_liters:1000,tank_entity:"sensor.tank",buffer_entity:"sensor.buffer",outdoor_entity:"sensor.outdoor",pump_power_entity:"sensor.pump_power",heat_energy_entity:"sensor.heat",electric_energy_entity:"sensor.electric",radiator_supply_entity:"sensor.radiator_supply",radiator_return_entity:"sensor.radiator_return"};
const controller={entry_id:"pump",name:"Wilo · gemeinsame Zusatzpumpe",mode:"observe",config,decision:{phase:"heating",speed:58,reason:"reduce_flow",target_delta:5,deltas:[3.8],active_units:1,issues:[]},actual_speed:60,last_command:null,last_command_at:null,error:null,conflicts:[],records:[{at:stamp,kind:"decision",mode:"observe",reason:"reduce_flow",speed:58},{at:new Date(now-600000).toISOString(),kind:"lifecycle",mode:"observe",reason:"started_in_observe"}]};
add('sensor.fault_1','Water flow, Phase error',null,'Fault State 1','hp1','r290_heatpump_fault_state_1_slave_1');
add('sensor.fault_2','None',null,'Fault State 1','hp2','r290_heatpump_fault_state_1_slave_2');
add('sensor.user_temp',42,'°C','Heating set temperature','hp1','r290_heatpump_heating_set_temperature_slave_1');
add('sensor.disabled',3,null,'Disabled raw status','hp1','r290_heatpump_unmapped_status_slave_1');entities.at(-1).disabled=true;
add('sensor.extra','ready',null,'Unmapped status','hp1','r290_heatpump_extra_slave_1',{diagnostic_detail:'available attribute'});
const polling=[{entry_id:"bridge",title:"Modbus Bridge",profile:"auto",running:true,queue_depth:1,overdue_registers:0,verified_writes:2,transport:{transactions_last_minute:20,errors_last_minute:0,latency_p95:.12,transport_time_fraction:.15},settings:{poll_fast:10,poll_normal:30,poll_slow:120,poll_config:600,poll_budget:.6},slaves:{1:{requests:20,errors:0,latency_ewma:.1,backoff_remaining:0,block_limit:20}}}];
const data={polling,version:"1.1.0",settings,entries,entities,curves,controllers:[controller],audit:[],recorder:true};
data.service={tests:{},snapshots:{}};data.system_access={};
config.flow_entities=[1,2].map(n=>`sensor.water_flow_${n}`);
window.fixture={data,states,calls:[],writes:[],failNext:false};
const panel=document.createElement("r290-control-panel");window.panel=panel;
const hass={states,connected:true,config:{time_zone:"Europe/Berlin"},callWS:async msg=>{
  window.fixture.calls.push(msg);
  if(window.fixture.failNext){window.fixture.failNext=false;throw new Error("Simulierter Kommunikationsfehler");}
  const type=msg.type.split("/")[1];
  if(type==='service'){
    if(msg.action==='read')return data.service.snapshots[msg.entry_id]={received_at:stamp,program_version:'4.25',display_version:null,errors:{},values:{864:425,865:1,866:130,867:129,817:0,818:30,822:150,826:0,830:30,835:0,836:35}};
    if(msg.action==='start'){
      if(!msg.confirmed||!msg.qualified)throw new Error('Confirm on-site supervision');
      window.fixture.writes.push(msg);return data.service.tests[msg.entry_id]={component:msg.component,value:msg.value,state:'running',ends_at:new Date(Date.now()+msg.seconds*1000).toISOString()};
    }
    window.fixture.writes.push(msg);delete data.service.tests[msg.entry_id];return {released:true};
  }
  if(type==='registers'){fixture.readCounter=(fixture.readCounter||0)+1;return {entry_id:msg.entry_id,received_at:new Date().toISOString(),values:Object.fromEntries(msg.addresses.map(a=>[a,65000+fixture.readCounter]))};}
  if(type==='faults')return {events:[{entity_id:'sensor.fault_1',at:stamp,state:'Water flow, Phase error',initial:false},{entity_id:'sensor.fault_1',at:stamp,state:'unavailable',initial:true}],entity_ids:['sensor.fault_1','sensor.fault_2'],recorded_ids:['sensor.fault_1'],total:2,truncated:false};
  if(type==="panel")return structuredClone(data);
  if(type==="settings"){data.settings={...msg.settings,...(data.settings.schematic?{schematic:data.settings.schematic}:{}),...(data.settings.charts?{charts:data.settings.charts}:{})};return {saved:true};}
  if(type==='charts'){const current=data.settings.charts?.[msg.key]||{};if(msg.expected_revision!==(current.revision||0))throw Error('Chart changed; reload');const chart={revision:(current.revision||0)+1,days:msg.days,entity_ids:msg.entity_ids};data.settings.charts={...data.settings.charts,[msg.key]:chart};return {chart};}
  if(type==='schematic'){
    const current=data.settings.schematic||{revision:0,draft:null,published:null};
    if(msg.expected_revision!==current.revision)throw new Error('Schematic changed; reload before saving');
    const next={...current,revision:current.revision+1};
    if(msg.action==='disable')next.published=null;
    else {next.draft=structuredClone(msg.graph);if(msg.action==='publish')next.published=structuredClone(msg.graph);}
    data.settings.schematic=next;return {schematic:structuredClone(next),issues:[]};
  }
  if(type==="pump"){window.fixture.writes.push(msg);controller.mode=msg.mode;return structuredClone(controller);}
  if(type==='system_access'){
    if(msg.action==='unlock'&&msg.password!=='2468')throw Error('Password does not match P183');
    for(const id of msg.entry_ids){if(msg.action==='lock')delete data.system_access[id];else data.system_access[id]=600;}
    return {system_access:{...data.system_access}};
  }
  if(type==="parameter"){
    const e=entities.find(e=>e.id===msg.entity_id);if(/^number.p\d/.test(msg.entity_id)&&!data.system_access[e.entry_id])throw Error('System parameters locked: enter P183');
    if(states[msg.entity_id].state!==msg.expected)throw new Error("Value changed since preview; review again");
    window.fixture.writes.push(msg);data.audit.unshift({at:stamp,entity_id:msg.entity_id,before:msg.expected,requested:msg.value,result:"sent"});
    states[msg.entity_id].state=String(msg.value);return {sent:true,verification_pending:true};
  }
  if(type==='curve'){
    const snap=curves.find(c=>c.entry_id===msg.entry_id);
    if(msg.revision!==snap.revision||msg.changes.some(c=>states[c.entity_id].state!==c.expected))throw new Error('Konfiguration geändert. Entwurf verwerfen und neu prüfen.');
    window.fixture.writes.push(msg);
    for(const c of msg.changes){states[c.entity_id].state=String(c.value);data.audit.unshift({at:stamp,entity_id:c.entity_id,before:c.expected,requested:c.value,result:'configured'});}
    if(msg.points){
      snap.points=structuredClone(msg.points);snap.custom_points=true;
      const values={t_out_min:msg.points[0].outdoor,t_out_max:msg.points.at(-1).outdoor,t_flow_max:msg.points[0].target,t_flow_min:msg.points.at(-1).target};
      for(const [key,value] of Object.entries(values)){const c=snap.controls.find(c=>c.key===key);if(c)states[c.id].state=String(value);}
    }else if(!snap.custom_points){
      const value=key=>Number(states[snap.controls.find(c=>c.key===key).id].state);
      snap.points=[{outdoor:value('t_out_min'),target:value('t_flow_max')},{outdoor:value('t_out_max'),target:value('t_flow_min')}];
    }
    snap.revision+='-next';return {configured:true};
  }
  if(type==="history"){
    const start=now-msg.days*86400000,series={};
    for(const id of msg.entity_ids){const s=states[id];if(!s)continue;const energy=s.attributes.device_class==="energy";
      const points=Array.from({length:200},(_,i)=>[(start+i*(now-start)/199)/1000,energy?1000+i*.5:s.attributes.unit_of_measurement==="Hz"?(i%27<21?40:0):Number(s.state)+Math.sin(i/9)*(s.attributes.unit_of_measurement==="W"?8:1.6)]);
      series[id]={unit:s.attributes.unit_of_measurement,kind:energy?"energy":"value",points,states:['on','off'].includes(s.state)?[[(start/1000),s.state]]:points,samples:200,summary:{delta:id==="sensor.heat"?719:199.6,resets:0,uncertain:id==="sensor.heat",max_increment_gap:86400,coverage:.997,runtime_hours:18.6,starts:16,integral:1900}};
    }
    return {start:new Date(start).toISOString(),end:stamp,series};
  }
  throw new Error(`Unknown fixture command ${type}`);
}};
panel.hass=hass;document.body.append(panel);

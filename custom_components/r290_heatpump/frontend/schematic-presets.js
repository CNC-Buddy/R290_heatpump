import {createNode,emptyGraph} from './schematic-model.js?v=1.1.0';

// These are explicit graph connections, not coordinates masquerading as pipes.
// Both coils, exchanger sides and the circulation return have distinct ports.
export function preset(kind,catalog,p){
  const g=emptyGraph();if(kind==='empty')return g;
  const add=(type,id,x,y,extra={})=>{const n={...createNode(type,catalog,id,x,y),...extra};g.nodes.push(n);return n;};
  const wire=(a,b,points=[])=>{const ep=s=>{const [node,port]=s.split('.');return {node,port};};g.edges.push({id:`pipe_${g.edges.length+1}`,from:ep(a),to:ep(b),points});};
  const hp=(id,x,y,i)=>{const u=p?.units?.[i];return add('heat_pump',id,x,y,{label:`WP ${i+1}`,bindings:u?Object.fromEntries([['value','compressor_operating_frequency'],['supply','water_outlet_temperature_t7'],['return','return_water_temperature_t6'],['flow','water_flow'],['fan','fan_operating_frequency_rotational_speed']].map(([key,part])=>[key,p.entity(part,u.id)||''])):{}});};
  const mapped=key=>p?.mapping?.(key)||'';
  if(kind==='direct'){
    hp('wp1',80,160,0);add('radiator','heating',720,160);g.nodes.at(-1).circuit='wp';
    add('heat_meter','wmz',420,340,{flip:true,leg:'return',bindings:{value:mapped('heat_energy_entity')}});
    wire('wp1.supply','heating.in',[[300,190],[680,190]]);
    wire('heating.out','wmz.in',[[680,250],[680,380]]);wire('wmz.out','wp1.return',[[300,380],[300,250]]);
    return g;
  }
  hp('wp1',40,240,0);hp('wp2',40,520,1);
  add('junction','wp_supply',300,390);add('junction','wp_return',300,600,{leg:'return'});
  add('pump','aux',420,370,{label:'Zusatzpumpe',bindings:{value:p?.pumpEntity?.('actual_speed')||'',status:mapped('pump_power_entity')}});
  add('valve','wp_valve',620,360,{label:'Umschaltventil WP',bindings:{phase:mapped('dhw_entity')}});
  add('dhw_tank','ww',1280,280,{label:'Warmwasser',bindings:{value:mapped('tank_entity')}});
  add('plate','plate',900,690);
  add('heat_meter','wmz',500,600,{flip:true,leg:'return',bindings:{value:mapped('heat_energy_entity')}});
  add('junction','wp_merge',740,620,{leg:'return'});
  add('pump','charge',1100,680,{circuit:'heating',label:'Pufferladepumpe',bindings:{status:mapped('buffer_charge_entity')}});
  add('buffer','buffer',1280,670,{circuit:'heating',bindings:{value:mapped('buffer_entity')}});
  add('pump','heating_pump',1560,680,{circuit:'heating',label:'Heizkreispumpe',bindings:{status:mapped('radiator_pump_entity')}});
  add('radiator','heating',1800,690,{circuit:'heating',bindings:{supply:mapped('radiator_supply_entity'),return:mapped('radiator_return_entity')}});
  wire('wp1.supply','wp_supply.a',[[260,270],[260,410]]);wire('wp2.supply','wp_supply.c',[[260,550],[320,550]]);
  wire('wp_supply.b','aux.in');wire('aux.out','wp_valve.common');
  wire('wp_valve.a','ww.wp_in',[[800,380],[800,340],[1220,340]]);
  wire('wp_valve.b','plate.primary_in',[[820,440],[820,720]]);
  wire('ww.wp_out','wp_merge.b',[[1160,390],[1160,600],[840,600],[840,640]]);
  wire('plate.primary_out','wp_merge.c',[[760,800]]);wire('wp_merge.a','wmz.in');
  wire('wmz.out','wp_return.b',[[400,640],[400,620]]);
  wire('wp_return.a','wp1.return',[[280,620],[280,330]]);wire('wp_return.c','wp2.return',[[320,680],[240,680],[240,610]]);
  wire('plate.secondary_out','charge.in');wire('charge.out','buffer.charge_in');wire('buffer.charge_out','plate.secondary_in',[[1240,780],[1240,800]]);
  wire('buffer.heating_out','heating_pump.in');wire('heating_pump.out','heating.in');wire('heating.out','buffer.heating_in');
  // Drinking-water circulation continues beyond the tap branches and closes
  // through its own return pump, independent of whether a tap is open.
  add('junction','ww_branch1',1600,320,{circuit:'warmwater',flip_y:true});add('junction','ww_branch2',1800,320,{circuit:'warmwater',flip_y:true});
  add('tap','tap1',1560,140,{label:'Zapfstelle 1'});add('tap','tap2',1760,140,{label:'Zapfstelle 2'});
  add('circulation_end','turn',1940,320);
  add('pump','circulation',1600,470,{circuit:'warmwater',leg:'return',flip:true,label:'Zirkulationspumpe'});
  wire('ww.hot','ww_branch1.a');wire('ww_branch1.b','ww_branch2.a');
  wire('ww_branch1.c','tap1.in');wire('ww_branch2.c','tap2.in');
  wire('ww_branch2.b','turn.hot');wire('turn.return','circulation.in',[[1880,420],[1880,510]]);wire('circulation.out','ww.circulation');
  if(kind==='full'||kind==='full_pv'){
    add('heat_source','we2',40,900);add('valve','we2_valve',520,880,{circuit:'we2',label:'Umschaltventil WE2'});
    add('junction','we2_merge',760,1030,{circuit:'we2',leg:'return'});
    wire('we2.supply','we2_valve.common');
    wire('we2_valve.a','ww.we2_in',[[680,900],[680,560],[1220,560],[1220,460]]);
    wire('we2_valve.b','buffer.we2_in',[[1180,960],[1180,860]]);
    wire('ww.we2_out','we2_merge.b',[[1240,510],[1240,1050]]);
    wire('buffer.we2_out','we2_merge.c',[[1200,910],[1200,1090],[780,1090]]);
    wire('we2_merge.a','we2.return',[[380,1050],[380,990]]);
  }
  if(kind==='full_pv'){
    add('pv','pv',80,60);add('house','house',440,60);add('battery','battery',800,60);add('grid','grid',1160,60);
    add('junction','electric1',360,160,{circuit:'electric',leg:'power'});add('junction','electric2',720,160,{circuit:'electric',leg:'power'});
    wire('pv.power','electric1.a',[[150,180]]);wire('electric1.c','house.power',[[380,220],[510,220]]);
    wire('electric1.b','electric2.a');wire('electric2.c','battery.power',[[740,220],[870,220]]);wire('electric2.b','grid.power',[[1230,180]]);
  }
  return g;
}

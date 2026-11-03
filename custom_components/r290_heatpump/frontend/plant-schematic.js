import {esc} from './model.js?v=1.1.1';
import {outdoorUnit,tank} from './visuals.js?v=1.1.1';
import {choiceLabel} from './plant.js?v=1.1.1';

// Every loop is drawn from explicit ports; animation reuses the same path.
export function plantSchematic(p,m,units,state,readings){
 const tr=(de,en)=>p.language==='en'?en:de, height=Math.max(510,units.length*155+55), join=Math.min(230,height/2), heatY=height-160, ret=height-60;
 const base=[], inner=[], motion=[], art=[];
 const pipe=(key,d,hot,running,branch='')=>{const target=/exchanger|coil|tank|^emitter$|^series-buffer$|^dhw-secondary/.test(key)?inner:base;target.push(`<path class="${hot?'hot-pipe':'cold-pipe'}" data-pipe="${key}" d="${d}"/>`);if(running)motion.push(`<path data-key="${key}" data-flow="${key}" data-branch="${branch}" class="flow-motion ${hot?'hot-motion':'cold-motion'}" d="${d}"/>`);};
 const text=(x,y,value,cls='svg-muted',id)=>`<text x="${x}" y="${y}" class="${cls}" ${id?`data-history="${esc(id)}" tabindex="0" role="button" aria-label="${tr('Verlauf','History')}: ${esc(id)}"`:''}>${esc(value)}</text>`;
 const pump=(x,y,label,running,id,value)=>`<g class="schematic-pump ${running?'running':''}" transform="translate(${x-23} ${y-23})"><circle class="pump-halo" cx="23" cy="23" r="25" fill="none" stroke="#659d79"/><circle cx="23" cy="23" r="23" fill="#b8d5bd" stroke="#2d6e50" stroke-width="2"/><path d="M16 9v28l23-14Z" fill="#286948"/></g>${text(x-48,y-29,label,'svg-muted')}${text(x-30,y+47,value||'','svg-title',id)}`;
 const exchanger=(x,y)=>`<rect x="${x}" y="${y-10}" width="60" height="80" rx="6" fill="#ecebe4" stroke="#526671" stroke-width="2"/>${Array.from({length:6},(_,i)=>`<path d="M${x+8+i*9} ${y}v60" stroke="${i%2?'#7997a3':'#b97254'}" stroke-width="3"/>`).join('')}`;
 const hasDhw=m.dhw!=='none', flow=units.some(u=>u.flowing), heat=flow&&(!hasDhw||state.phase==='heating'), dhw=flow&&state.phase==='dhw'&&hasDhw;
 units.forEach((u,i)=>{
   const y=45+i*155;
   pipe(`unit-${i}-supply`,`M260 ${y+66}H310V${join}`,true,u.flowing);
   pipe(`unit-${i}-return`,`M340 ${ret}V${y+94}H260`,false,u.flowing);
   art.push(`<g class="schematic-unit" data-unit="${esc(u.slave)}">${text(20,y-12,`${tr('Wärmepumpe','Heat pump')} ${u.slave}`,'svg-title')}${outdoorUnit(20,y,u.fanRunning)}${text(160,y+4,tr('Verdichter','Compressor'))}${text(160,y+28,u.frequency,'svg-value',u.frequencyId)}${text(160,y+52,tr('Vorlauf','Supply'))}${text(160,y+70,u.supply,'hot-text',u.supplyId)}${text(160,y+88,tr('Rücklauf','Return'))}${text(160,y+106,u.return,'cold-text',u.returnId)}</g>`);
   if(m.isolation!=='none')art.push(`<g data-isolation="${esc(u.id)}"><path d="M278 ${y+58}l16 16v-16l-16 16Z" stroke="#526671" fill="${u.valveOpen===true?'#b8d5bd':u.valveOpen===false?'#e1b3a0':'#e0dfd9'}"/>${text(160,y+126,u.valveOpen===true?tr('Ventil offen','Valve open'):u.valveOpen===false?tr('Ventil geschlossen','Valve closed'):tr('Ventilstatus unbekannt','Valve state unknown'),'svg-muted')}</g>`);
 });
 pipe('common-supply',`M310 ${join}H550`,true,flow);
 pipe('common-return',`M550 ${ret}H340`,false,flow);
 if(m.aux_position==='common_supply')art.push(pump(430,join,tr('Zusatzpumpe','Auxiliary pump'),readings.pumpRunning,readings.speedId,readings.speed));
 if(m.aux_position==='common_return')art.push(pump(430,ret,tr('Zusatzpumpe','Auxiliary pump'),readings.pumpRunning,readings.speedId,readings.speed));
 if(hasDhw){
   art.push(`<path d="M540 ${join-10}l20 20v-20l-20 20Z" fill="#c1c8c9" stroke="#526671"/>${text(510,join-24,tr('Umschaltventil','Diverter valve'))}`);
   pipe('dhw-supply',`M550 ${join}V110H${m.dhw==='plate'?640:760}`,true,dhw,'dhw');
   art.push(tank(760,42,75,150),text(850,60,tr('Warmwasser','Domestic hot water'),'svg-title'),text(850,86,readings.tankVolume),text(850,120,readings.tankTemp,'svg-temp hot-text',readings.tankId));
   if(m.dhw==='plate'){
     art.push(exchanger(640,100),text(610,205,tr('WW-Wärmetauscher','DHW exchanger')));
     pipe('dhw-primary-exchanger','M640 110H660V160H640',true,dhw,'dhw');
     pipe('dhw-return',`M640 160H570V${ret}H550`,false,dhw,'dhw');
     pipe('dhw-secondary-supply','M680 110H760H795V162H760',true,state.dhwCharging,'dhw-charge');
     pipe('dhw-secondary-return','M760 162H700V160H680V110',false,state.dhwCharging,'dhw-charge');
     art.push(pump(727,162,tr('WW-Ladepumpe','DHW charge pump'),state.dhwCharging,null,''));
   }else{
     pipe('dhw-coil','M760 110H810Q820 110 810 120H780Q770 120 780 130H810Q820 130 810 140H795V192',true,dhw,'dhw');
     pipe('dhw-return',`M795 192H570V${ret}H550`,false,dhw,'dhw');
   }
 }
 const plate=m.separation==='plate', parallel=m.heating==='buffer_parallel', series=m.heating==='buffer_series';
 let secondary=plate?state.bufferCharging:heat;
 pipe('heating-supply',`M550 ${join}V${heatY}H${plate?640:parallel?760:940}`,true,heat,'heating');
 if(m.aux_position==='heating_supply')art.push(pump(590,heatY,tr('Zusatzpumpe','Auxiliary pump'),readings.pumpRunning,readings.speedId,readings.speed));
 if(plate){
   art.push(exchanger(640,heatY-10),text(600,heatY+100,tr('Systemtrennung','System separation')));
   pipe('heating-primary-exchanger',`M640 ${heatY}H660V${heatY+50}H640`,true,heat,'heating');
   pipe('heating-return',`M640 ${heatY+50}H550V${ret}`,false,heat,'heating');
   pipe('charge-exchanger',`M700 ${heatY+50}H680V${heatY}H700`,false,secondary,'buffer-charge');
   pipe('secondary-supply',`M700 ${heatY}H${parallel?760:940}`,true,secondary,'buffer-charge');
 }
 if(parallel){
   art.push(tank(760,heatY-45,75,135),text(750,heatY-95,tr('Heizungspuffer','Heating buffer'),'svg-title'),text(850,heatY-76,readings.bufferVolume),text(850,heatY-53,readings.bufferTemp,'svg-temp hot-text',readings.bufferId));
   pipe('charge-tank',`M760 ${heatY}H780V${heatY+50}H760`,true,secondary,'buffer-charge');
   pipe('charge-return',`M760 ${heatY+50}H${plate?700:550}${plate?'':`V${ret}`}`,false,secondary,'buffer-charge');
   pipe('emitter-tank',`M835 ${heatY+50}H815V${heatY}H835`,false,state.radiatorRunning,'radiators');
   pipe('emitter-supply',`M835 ${heatY}H940`,true,state.radiatorRunning,'radiators');
   pipe('emitter-return',`M940 ${heatY+50}H835`,false,state.radiatorRunning,'radiators');
   art.push(pump(884,heatY,tr('Heizkreispumpe','Heating pump'),state.radiatorRunning,null,''));
 }else if(series){
   art.push(tank(760,heatY+20,75,85),text(760,heatY-60,tr('Reihenpuffer','Series buffer'),'svg-title'),text(760,heatY-40,readings.bufferTemp,'svg-muted',readings.bufferId));
   pipe('series-buffer',`M940 ${heatY+50}H835H800V${heatY+80}H760`,false,secondary,'radiators');
   pipe('series-return',`M760 ${heatY+80}H${plate?720:550}V${plate?heatY+50:ret}${plate?'H700':''}`,false,secondary,'radiators');
 }else pipe('direct-return',`M940 ${heatY+50}H${plate?700:550}${plate?'':`V${ret}`}`,false,secondary,'radiators');
 if(plate)art.push(pump(725,heatY,tr('Sekundärpumpe','Secondary pump'),secondary,null,''));
 art.push(`<rect x="940" y="${heatY-12}" width="65" height="78" rx="5" fill="#f4f3ef" stroke="#607581" stroke-width="2"/><text x="1005" y="${heatY+98}" text-anchor="end" class="svg-muted">${esc(choiceLabel(p,'emitters',m.emitters))}</text>`);
 const emitterPath=m.emitters==='radiators'?`M940 ${heatY}H985V${heatY+50}H940`:`M940 ${heatY}H990V${heatY+16}H955V${heatY+32}H990V${heatY+50}H940`;
 pipe('emitter',emitterPath,true,parallel?state.radiatorRunning:secondary,'radiators');
 return `<div class="adaptive-schematic"><svg class="plant-svg" viewBox="0 0 1070 ${height}" role="group" aria-label="${tr('Konfiguriertes Hydraulikschema','Configured hydraulic schematic')}"><defs><linearGradient id="case"><stop stop-color="#fcfcf9"/><stop offset="1" stop-color="#dbdeda"/></linearGradient><linearGradient id="water" x2="0" y2="1"><stop stop-color="#e9b69a"/><stop offset="1" stop-color="#abc8d9"/></linearGradient></defs><g fill="none">${base.join('')}</g>${art.join('')}<g fill="none">${inner.join('')}${motion.join('')}</g></svg></div>`;
}

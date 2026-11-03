import {esc,fmt} from './model.js?v=1.1.1';
import {freshValue} from './schematic-model.js?v=1.1.1';

export const isTank=n=>['buffer','dhw_tank'].includes(n?.type);
export const zoneHeights={1:[50],2:[20,80],3:[15,50,85],4:[15,38,62,85]};
export function zoneName(index,count,english=false){
  const names=english?{1:['Temperature'],2:['Top','Bottom'],3:['Top','Middle','Bottom'],4:['Top','Upper middle','Lower middle','Bottom']}:{1:['Temperatur'],2:['Oben','Unten'],3:['Oben','Mitte','Unten'],4:['Oben','Mitte oben','Mitte unten','Unten']};
  return names[count]?.[index]||'';
}
export function temperature(p,id){
  const raw=freshValue(p,id);if(raw===null||!raw.trim())return null;
  const n=Number(raw),unit=p.states[id]?.attributes?.unit_of_measurement;
  if(!Number.isFinite(n)||!['°C','°F','K'].includes(unit))return null;
  return unit==='°F'?(n-32)*5/9:unit==='K'?n-273.15:n;
}
export function zoneColor(value){
  if(value===null)return '#dfe5e5';
  const t=Math.max(0,Math.min(1,(value-20)/40)),cold=[163,201,218],hot=[230,146,111];
  return `rgb(${cold.map((v,i)=>Math.round(v+(hot[i]-v)*t)).join(',')})`;
}
export function tankLayers(n,p){
  if(!isTank(n)||!n.temperature_zones?.length)return {defs:'',fill:''};
  const zones=n.temperature_zones,stops=zones.flatMap((z,i)=>{
    const start=i?(zones[i-1].height+z.height)/2:0,end=i+1<zones.length?(z.height+zones[i+1].height)/2:100,color=zoneColor(temperature(p,z.entity));
    return `<stop offset="${start+(i?2:0)}%" stop-color="${color}"/><stop offset="${end-(i+1<zones.length?2:0)}%" stop-color="${color}"/>`;
  }).join('');
  return {defs:`<defs><linearGradient id="sg-zones-${n.id}" x1="0" y1="${n.flip_y?1:0}" x2="0" y2="${n.flip_y?0:1}">${stops}</linearGradient></defs>`,fill:`url(#sg-zones-${n.id})`};
}
export function tankReadings(n,p){
  if(!isTank(n)||!n.temperature_zones?.length)return '';
  const english=p.language==='en',zones=n.temperature_zones;
  return `<g class="sg-tank-zones"><path d="M179 24V256" stroke="var(--line)" stroke-width="4"/>${zones.map((z,i)=>{
    const value=temperature(p,z.entity),y=24+z.height*2.32,color=zoneColor(value),name=zoneName(i,zones.length,english),label=value===null?'—':`${fmt(value,1)} °C`;
    return `<g data-key="zone-${n.id}-${i}" ${z.entity?`data-reading="${esc(z.entity)}" tabindex="0" role="button" aria-label="${english?'History':'Verlauf'}: ${name}"`:''}><title>${esc(z.entity|| (english?'No sensor assigned':'Kein Fühler zugeordnet'))}${value===null?english?' · No current temperature':' · Keine aktuelle Temperatur':''}</title><path d="M133 ${y}H179" stroke="${color}" stroke-width="2"/><circle cx="134" cy="${y}" r="5" fill="${color}" stroke="#fff" stroke-width="2"/><circle cx="179" cy="${y}" r="4" fill="${color}"/><rect x="190" y="${y-17}" width="175" height="34" rx="8" fill="var(--surface)" stroke="var(--line)"/><text x="199" y="${y+4}" font-size="12" fill="var(--muted)">${name}</text><text x="355" y="${y+5}" text-anchor="end" font-size="16" font-weight="600" fill="var(--ink)">${label}</text></g>`;
  }).join('')}</g>`;
}
export function heaterArt(){
  return '<g class="sg-heater"><path d="M32 39H111Q121 39 121 48Q121 57 111 57H32" fill="none" stroke="#71858b" stroke-width="7"/><path d="M32 39H111Q121 39 121 48Q121 57 111 57H32" fill="none" stroke="#e9e6d9" stroke-width="3"/><rect x="24" y="32" width="12" height="32" rx="3" fill="url(#sg-brass)" stroke="#8a795a"/><path d="M24 48H12V78H70V100" fill="none" stroke="#b49624" stroke-width="3"/></g>';
}
// A heater is an independent electrical component with an optional visual mount.
// Its mount does not introduce a hydraulic connection or a switching action.
export function attachHeater(graph,heater,tankId){
  if(!tankId){delete heater.tank;return;}
  const tank=graph.nodes.find(n=>n.id===tankId);if(heater.type!=='heater'||!isTank(tank)||tank.x+10>3600||tank.y+80>3600)throw Error('component');
  heater.tank=tankId;heater.x=tank.x+10;heater.y=tank.y+80;
}
export function moveNode(graph,node,x,y){
  const tank=node.tank&&graph.nodes.find(n=>n.id===node.tank);
  if(tank){x=tank.x+10;y=Math.max(tank.y+20,Math.min(tank.y+170,y));}
  const children=graph.nodes.filter(n=>n.tank===node.id),group=[node,...children];
  const dx=Math.max(-Math.min(...group.map(n=>n.x)),Math.min(3600-Math.max(...group.map(n=>n.x)),x-node.x));
  const dy=Math.max(-Math.min(...group.map(n=>n.y)),Math.min(3600-Math.max(...group.map(n=>n.y)),y-node.y));
  for(const n of group){n.x+=dx;n.y+=dy;}
}

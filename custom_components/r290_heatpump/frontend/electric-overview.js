import {esc,numeric} from './model.js?v=1.1.1';
import {electricArt} from './electric-art.js?v=1.1.1';
import {patchHTML} from './dom.js?v=1.1.1';

const t=(p,de,en)=>p.language==='en'?en:de;
// Keep hp_power as the storage key so b18 assignments retain their history.
const fields={pv_power:['PV-Leistung','PV power'],house_power:['Hausgesamtverbrauch · inklusive Wärmeerzeuger','Total house consumption · including heat generators'],battery_power:['Batterie · Lade-/Entladeleistung','Battery · charge/discharge power'],battery_soc:['Batterie · Ladezustand','Battery · state of charge'],grid_power:['Netz · Bezug/Einspeisung','Grid · import/export'],hp_power:['Wärmeerzeuger · gemeinsame Leistungsaufnahme','Heat generators · shared power meter']};
export const electricModel=p=>({enabled:false,battery_positive:'unknown',grid_positive:'unknown',...Object.fromEntries(Object.keys(fields).map(k=>[k,''])),...p.data?.settings?.electric});
const label=(p,key)=>fields[key][p.language==='en'?1:0];
const units=key=>key==='battery_soc'?['%']:['W','kW','MW'];

export function electricForm(p,config=electricModel(p)){
 const select=(key,title,choices)=>`<label>${title}<select data-electric="${key}">${choices.map(([value,de,en])=>`<option value="${value}" ${config[key]===value?'selected':''}>${t(p,de,en)}</option>`).join('')}</select></label>`;
 return `<section class="card electric-setup" data-key="electric-setup"><div class="card-header"><div><h2>${t(p,'PV & Stromübersicht','PV & electricity overview')}</h2><p>${t(p,'Ein eigener Bereich oberhalb des Hydraulikschemas.','A separate section above the hydraulic schematic.')}</p></div><label class="electric-enable"><input type="checkbox" data-electric="enabled" ${config.enabled?'checked':''}>${t(p,'In der Anlagenübersicht anzeigen','Show in plant overview')}</label></div>
 <p class="small muted">${t(p,'Momentane Leistung in W oder kW zuordnen, keine Energiezähler in kWh. Hausgesamtverbrauch umfasst das gesamte Haus einschließlich Wärmeerzeuger. Für gemeinsam gemessene Wärmepumpen und Heizstäbe einmal die Gesamtleistung des Shelly zuordnen. Dieser Wert wird nicht nochmals zum Hausverbrauch addiert und nicht auf einzelne Geräte aufgeteilt.','Assign instantaneous power in W or kW, not energy counters in kWh. Total house consumption includes the heat generators. For heat pumps and immersion heaters on a shared Shelly, assign its total power once. This reading is not added to house consumption again or split between individual devices.')}</p>
 <div class="form-grid">${Object.keys(fields).map(key=>`<label>${label(p,key)}<r290-entity-picker data-electric="${key}"></r290-entity-picker>${key==='house_power'?`<small>${t(p,'Leer lassen: aus PV-, Netz- und Batterieleistung berechnen.','Leave empty to calculate from PV, grid and battery power.')}</small>`:''}</label>`).join('')}
 ${select('battery_positive',t(p,'Positiver Batteriewert bedeutet','Positive battery value means'),[['unknown','Noch nicht festgelegt','Not defined yet'],['charge','Laden','Charging'],['discharge','Entladen','Discharging']])}
 ${select('grid_positive',t(p,'Positiver Netzwert bedeutet','Positive grid value means'),[['unknown','Noch nicht festgelegt','Not defined yet'],['import','Netzbezug','Grid import'],['export','Einspeisung','Grid export']])}</div>
 <p class="small muted">${t(p,'Hausberechnung: PV + Netzbezug + Batterieentladung − Einspeisung − Batterieladung. Alle drei Leistungsquellen müssen aktuelle Werte liefern. Ein zugeordneter Haussensor hat Vorrang; sein Ausfall wird nicht durch eine Berechnung verdeckt.','House calculation: PV + grid import + battery discharge − grid export − battery charge. All three power sources must provide current readings. An assigned house sensor takes priority; calculation does not hide its failure.')}</p>
 <p class="small muted">${t(p,'Negative Werte bedeuten jeweils die Gegenrichtung. Ohne festgelegte Richtung erscheinen keine Flusspfeile. Bei fehlenden oder über 5 Minuten alten Meldungen wird kein aktueller Fluss dargestellt.','Negative values mean the opposite direction. Flow arrows require a defined direction. Missing reports or reports older than 5 minutes do not show a current flow.')}</p>
 <div class="button-row"><button class="secondary" data-action="discard-settings">${t(p,'Änderungen verwerfen','Discard changes')}</button><button class="primary" data-action="save-settings">${t(p,'Einstellungen speichern','Save settings')}</button></div></section>`;
}
export function configureElectricPicker(p,picker,items,config=electricModel(p)){
 const key=picker.dataset.electric;if(!fields[key])return false;
 picker.configure(items.filter(s=>s.id===config[key]||s.id.startsWith('sensor.')&&units(key).includes(s.unit)),config[key],label(p,key),p.language);return true;
}
export function readElectricForm(p){
 const result=electricModel(p);
 for(const el of p.shadowRoot.querySelectorAll('[data-electric]'))result[el.dataset.electric]=el.type==='checkbox'?el.checked:el.value;
 return result;
}
export function refreshElectricLanguage(p){
 const old=p.shadowRoot.querySelector('.electric-setup');if(!old)return;
 const config=readElectricForm(p);old.outerHTML=electricForm(p,config);
 const items=Object.values(p.states).map(s=>({id:s.entity_id,name:p.name(s.entity_id),unit:s.attributes.unit_of_measurement||''})).sort((a,b)=>a.name.localeCompare(b.name,p.language));
 for(const el of p.shadowRoot.querySelectorAll('r290-entity-picker[data-electric]'))configureElectricPicker(p,el,items,config);
}

// Freshness is based on receipt, never last_changed. Unknown units are not W.
export function electricReading(p,key,config=electricModel(p)){
 if(key==='house_power'&&!config.house_power)return calculatedHouseReading(p,config);
 const id=config[key],s=p.states[id],raw=numeric(s?.state),unit=s?.attributes?.unit_of_measurement;
 const at=p.data?.reports?.[id]||s?.last_reported,age=at?(Date.now()-Date.parse(at))/1000:NaN;
 const valid=raw!==null&&units(key).includes(unit)&&!s?.attributes?.restored&&
   (key==='battery_soc'?raw>=0&&raw<=100:!['pv_power','house_power','hp_power'].includes(key)||raw>=0);
 const reason=p.hass?.connected===false?'offline':!id?'unassigned':!valid?'unavailable':!Number.isFinite(age)?'unknown':age>300||age < -60?'stale':'';
 return {id,value:valid?raw*(key==='battery_soc'?1:{W:.001,kW:1,MW:1000}[unit]):null,reason,fresh:!reason};
}
function direction(kind,reading,config){
 if(!reading.fresh||reading.value===0)return '';
 if(kind==='pv')return 'out';if(kind==='house'||kind==='heat')return 'in';
 const convention=config[`${kind}_positive`];if(convention==='unknown')return '';
 const positiveOut=kind==='battery'?convention==='discharge':convention==='import';
 return (reading.value>0)===positiveOut?'out':'in';
}
function powerInjection(kind,reading,config){
 const flow=direction(kind,reading,config);
 return reading.fresh&&(flow||reading.value===0)?Math.abs(reading.value)*(flow==='out'?1:-1):null;
}
function calculatedHouseReading(p,config){
 const inputs=['pv','grid','battery'].map(kind=>({kind,reading:electricReading(p,`${kind}_power`,config)}));
 const sources=inputs.map(({reading})=>reading.id).filter(Boolean),base={id:'',sources:[...new Set(sources)],calculated:true,value:null,fresh:false};
 const missing=inputs.find(({reading})=>!reading.fresh);
 if(missing)return {...base,reason:missing.reading.reason};
 const injections=inputs.map(({kind,reading})=>powerInjection(kind,reading,config));
 if(injections.includes(null))return {...base,reason:'direction'};
 if(base.sources.length!==inputs.length)return {...base,reason:'inconsistent'};
 const sum=injections.reduce((total,value)=>total+value,0),value=Math.abs(sum)<1e-9?0:sum;
 // Negative consumption is inconsistent input, not export and not a real zero.
 if(!Number.isFinite(value)||value<0)return {...base,reason:'inconsistent'};
 return {...base,value,fresh:true,reason:''};
}
const reasonText=(p,reason)=>({offline:t(p,'Verbindung getrennt','Disconnected'),unassigned:t(p,'Nicht zugeordnet','Not assigned'),unavailable:t(p,'Nicht verfügbar','Unavailable'),unknown:t(p,'Meldezeit unbekannt','Report time unknown'),stale:t(p,'Meldung veraltet','Stale report'),direction:t(p,'Richtung nicht festgelegt','Direction not defined'),inconsistent:t(p,'Messwerte widersprüchlich','Conflicting readings')})[reason]||'';
const formatted=(p,value,unit='kW')=>`${new Intl.NumberFormat(p.language==='en'?'en-GB':'de-DE',{maximumFractionDigits:unit==='%'?0:2}).format(Math.abs(value))} ${unit}`;
function readingValue(p,r,unit='kW'){
 return p.historyValue(r.sources||r.id,r.fresh?esc(formatted(p,r.value,unit)):'—');
}
export function electricOverview(p){
 const config=electricModel(p);if(!config.enabled)return '';
 const names={pv:t(p,'Photovoltaik','Photovoltaics'),house:t(p,'Haus gesamt','Whole house'),battery:t(p,'Batteriespeicher','Battery storage'),grid:t(p,'Netz','Grid')};
 const heat=electricReading(p,'hp_power',config),soc=electricReading(p,'battery_soc',config);
 const parts=['pv','house','battery','grid'].map(kind=>{
   const r=electricReading(p,`${kind}_power`,config),flow=direction(kind,r,config);
   const state=r.reason?reasonText(p,r.reason):r.value===0?t(p,'Kein Leistungsfluss','No power flow'):kind==='pv'||kind==='house'?'':!flow?t(p,'Richtung nicht festgelegt','Direction not defined'):kind==='battery'?(flow==='in'?t(p,'Laden','Charging'):t(p,'Entladen','Discharging')):(flow==='in'?t(p,'Einspeisung','Export'):t(p,'Netzbezug','Import'));
   const status=r.calculated?(r.reason?`${t(p,'Berechnung','Calculation')}: ${state}`:`${t(p,'Berechnet','Calculated')}${state?' · '+state:''}`):state;
   const main=kind==='battery'?soc:r;
   const heating=kind==='house'?`<div class="electric-heat" title="${t(p,'Wärmepumpen und Heizstäbe gemeinsam gemessen; im Hausverbrauch enthalten.','Heat pumps and immersion heaters measured together; included in the house total.')}"><span>${t(p,'davon Wärmeerzeuger','of which heat generators')}</span><b>${readingValue(p,heat)}</b>${heat.reason?`<small>${reasonText(p,heat.reason)}</small>`:''}</div>`:'';
   return `<article class="electric-item" data-key="electric-${kind}" data-electric-item="${kind}"><div class="electric-item-main"><div class="electric-art-wrap">${electricArt(kind,soc)}<span class="electric-port" aria-hidden="true"></span></div><div class="electric-readings"><h3>${names[kind]}</h3><strong>${readingValue(p,main,kind==='battery'?'%':'kW')}</strong>${status?`<span class="electric-status">${esc(status)}${kind==='battery'?` · ${readingValue(p,r)}`:''}</span>`:''}${heating}${kind==='battery'&&soc.reason?`<small>${esc(reasonText(p,soc.reason))} · ${t(p,'Ladezustand','state of charge')}</small>`:''}</div></div></article>`;
 });
 const pause=t(p,p._animationPaused?'Animation starten':'Animation pausieren',p._animationPaused?'Resume animation':'Pause animation'),settings=t(p,'Einrichten','Configure');
 const control=(attrs,title,paths)=>`<button class="secondary electric-control" ${attrs} title="${title}" aria-label="${title}"><svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" stroke-linecap="round">${paths}</svg></button>`;
 return `<section class="card electric-overview ${p._animationPaused?'is-paused':''}" data-key="electric-overview" aria-label="${t(p,'PV & Stromübersicht','PV & electricity overview')}"><header class="electric-header"><h2>${t(p,'Strom','Electricity')}</h2><div class="electric-actions">${control('data-action="toggle-motion"',pause,p._animationPaused?'<path d="M8 5l11 7-11 7Z"/>':'<path d="M8 5v14M16 5v14"/>')}${control('data-view="settings"',settings,'<circle cx="12" cy="12" r="3"/><path d="m10 3 4 0 .7 3 2 .9 2.8-.9 2 3.5-2.2 2v2l2.2 2-2 3.5-2.8-.9-2 .9-.7 3h-4l-.7-3-2-.9-2.8.9-2-3.5 2.2-2v-2l-2.2-2 2-3.5 2.8.9 2-.9Z"/>')}</div></header><div class="electric-flow-grid">${parts.join('')}<div class="electric-connections" data-key="electric-connections" data-preserve-children></div></div></section>`;
}

export function electricFlowState(p){
 const config=electricModel(p),result={};
 for(const kind of ['pv','house','heat','battery','grid']){
   const r=electricReading(p,kind==='heat'?'hp_power':`${kind}_power`,config),flow=direction(kind,r,config);
   result[kind]={...r,flow,injection:powerInjection(kind,r,config)};
 }
 return result;
}

// Heat generation is included in the house meter and displayed beneath it.
// Every main-bus end terminates at a component; row turns avoid the readings.
export function electricRoutes(ports,width,readings){
 const rows=[];
 for(const key of Object.keys(ports).sort((a,b)=>ports[a].y-ports[b].y)){
   const row=rows.at(-1);if(row&&Math.abs(ports[row[0]].y-ports[key].y)<2)row.push(key);else rows.push([key]);
 }
 const main=rows.flatMap((row,i)=>row.sort((a,b)=>(ports[a].x-ports[b].x)*(i%2?-1:1))),routes=[];
 const values=main.map(k=>readings[k].injection);
 const balanced=values.every(v=>v!==null)&&Math.abs(values.reduce((a,b)=>a+b,0))<=Math.max(.15,values.reduce((a,b)=>a+Math.abs(b),0)*.025);
 const busY=a=>Math.max(...Object.values(ports).filter(b=>Math.abs(a.y-b.y)<2).map(b=>Math.max(b.y+18,b.clearY+12)));
 let cumulative=0,rowTransition=0;
 for(let i=0;i<main.length;i++){
   const key=main[i],a=ports[key],b=ports[main[i+1]],v=readings[key].injection,ay=busY(a);
   routes.push({id:`branch-${key}`,points:[[a.x,a.y],[a.x,ay]],flow:Math.sign(v||0)});
   cumulative+=v||0;
   if(b){const by=busY(b),sameRow=Math.abs(a.y-b.y)<2,gutter=rowTransition%2===0?width-5:5;if(!sameRow)rowTransition++;
     routes.push({id:`bus-${key}`,points:sameRow?[[a.x,ay],[b.x,by]]:[[a.x,ay],[gutter,ay],[gutter,by],[b.x,by]],flow:balanced?Math.sign(Math.abs(cumulative)<.005?0:cumulative):0});}
 }
 return routes;
}
function flowPath(route){
 const d=route.points.map(([x,y],i)=>`${i?'L':'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
 const length=route.points.slice(1).reduce((sum,p,i)=>sum+Math.hypot(p[0]-route.points[i][0],p[1]-route.points[i][1]),0);
 const count=Math.max(1,Math.ceil(length/120)),duration=Math.max(1.2,length/55);
 const markers=route.flow?Array.from({length:count},(_,i)=>`<g class="electric-motion" style="offset-path:path('${d}');animation-duration:${duration}s;animation-delay:${-duration*i/count}s"><circle r="6.5"/><path class="electric-chevron" d="M-2.2 -3l3.4 3-3.4 3"/></g>`).join(''):'';
 return `<g data-key="${route.id}" data-electric-route="${route.id}" class="electric-route ${route.flow?'has-flow':''} ${route.flow<0?'reverse':''}"><path class="electric-wire" d="${d}"/>${markers}</g>`;
}
export function stopElectricFlows(p){p._electricObserver?.disconnect();p._electricObserver=null;p._electricGrid=null;}
export function refreshElectricFlows(p){
 const grid=p.shadowRoot.querySelector('.electric-flow-grid');
 if(p._electricGrid!==grid){stopElectricFlows(p);if(grid){p._electricGrid=grid;p._electricObserver=new ResizeObserver(()=>refreshElectricFlows(p));p._electricObserver.observe(grid);for(const port of grid.querySelectorAll('.electric-port'))p._electricObserver.observe(port.closest('.electric-item'));}}
 if(!grid)return;
 const box=grid.getBoundingClientRect();if(!box.width||!box.height)return;
 const ports=Object.fromEntries([...grid.querySelectorAll('[data-electric-item]')].map(el=>{const port=el.querySelector('.electric-port').getBoundingClientRect(),text=el.querySelector('.electric-readings').getBoundingClientRect();return [el.dataset.electricItem,{x:port.left-box.left,y:port.top-box.top,clearY:text.bottom-box.top}];}));
 const routes=electricRoutes(ports,box.width,electricFlowState(p));
 patchHTML(grid.querySelector('.electric-connections'),`<svg width="100%" height="100%" viewBox="0 0 ${box.width} ${box.height}" aria-hidden="true">${routes.map(flowPath).join('')}</svg>`);
}

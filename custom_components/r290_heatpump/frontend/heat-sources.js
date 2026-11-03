import {esc,numeric,fmt,energyFactor} from './model.js?v=1.1.1';
import {patchElement} from './dom.js?v=1.1.1';

const t=(p,de,en)=>p.language==='en'?en:de;
const TITLES={dhw_heater:['Heizstab · Warmwasser','DHW immersion heater'],buffer_heater:['Elektrische Zusatzheizung · Heizung','Electric auxiliary heating'],secondary:['Zweiter Wärmeerzeuger','Additional heat source']};
const PLACEMENTS=[['buffer','Im Heizungspuffer','In heating buffer'],['supply','Im Heizungsvorlauf','In heating supply'],['return','Im Heizungsrücklauf','In heating return']];
const KINDS=[['gas','Gas','Gas'],['oil','Öl','Oil'],['pellet','Pellets','Pellets'],['wood','Holz / Kamin','Wood / stove'],['solar','Solarthermie','Solar thermal'],['district','Fernwärme','District heating'],['other','Sonstiger','Other']];
const FIELDS={request_entity:['Anforderung / Reglerausgang','Request / controller output'],feedback_entity:['Eigene Betriebsrückmeldung','Independent running feedback'],power_entity:['Elektrische Leistung','Electrical power'],energy_entity:['Stromzähler · kumuliert','Electricity meter · cumulative'],heat_entity:['Wärmezähler · kumuliert','Heat meter · cumulative'],dhw_temperature_entity:['Wärmequelle · Temperatur WW','Heat-source temperature · DHW'],heating_temperature_entity:['Wärmequelle · Temperatur Heizen','Heat-source temperature · heating'],dhw_pump_entity:['Ladepumpe · Warmwasser','Charge pump · DHW'],heating_pump_entity:['Ladepumpe · Heizen','Charge pump · heating']};
const STATUS=new Set(['request_entity','feedback_entity','dhw_pump_entity','heating_pump_entity']);
const title=(p,id)=>TITLES[id][p.language==='en'?1:0];
const label=(p,key)=>FIELDS[key][p.language==='en'?1:0];
export function sourceModel(p){return Object.fromEntries(Object.keys(TITLES).map(id=>[id,{enabled:false,kind:'other',serves:id==='dhw_heater'?'dhw':'heating',managed_by:'observe',entry_id:'',electricity_scope:'unknown',...(id==='buffer_heater'?{placement:'buffer'}:{}),...Object.fromEntries(Object.keys(FIELDS).map(k=>[k,''])),...p.data?.settings?.heat_sources?.[id]}]));}
const select=(p,id,key,name,options,value)=>`<label class="field">${name}<select data-source="${id}" data-source-field="${key}">${options.map(([v,de,en])=>`<option value="${esc(v)}" ${value===v?'selected':''}>${esc(t(p,de,en))}</option>`).join('')}</select></label>`;
export function sourcesForm(p){
 const models=sourceModel(p), units=p.allUnits||[];
 return `<section class="card heat-source-setup"><div class="card-header"><div><h2>${t(p,'Heizstäbe & zweiter Wärmeerzeuger','Immersion heaters & additional heat source')}</h2><p>${t(p,'Vorhandene Geräte und Messquellen zuordnen. Speichern aktiviert keine Heizung und erstellt keine Schaltautomatik.','Map installed devices and measurements. Saving does not activate heating or create switching automation.')}</p></div></div>
 ${Object.entries(models).map(([id,c])=>`<details data-detail-id="source-setup-${id}" ${c.enabled?'open':''}><summary>${title(p,id)}</summary><div class="source-settings-body"><label class="source-enabled"><input type="checkbox" data-source="${id}" data-source-field="enabled" ${c.enabled?'checked':''}> ${t(p,'Gerät ist eingebaut / anzeigen','Device installed / display')}</label><div class="form-grid">
 ${id==='secondary'?select(p,id,'kind',t(p,'Art des Wärmeerzeugers','Heat-source type'),KINDS,c.kind)+select(p,id,'serves',t(p,'Versorgt','Supplies'),[['heating','Heizung','Heating'],['dhw','Warmwasser','DHW'],['both','Heizung und Warmwasser','Heating and DHW']],c.serves):''}
 ${id==='buffer_heater'?select(p,id,'placement',t(p,'Einbauort der Zusatzheizung','Auxiliary heater location'),PLACEMENTS,c.placement):''}
 ${select(p,id,'managed_by',t(p,'Bestehende Ansteuerung','Existing control'),[['observe','Nur Messung / unbekannt','Measurement only / unknown'],['heat_pump','Wärmepumpensteuerung','Heat-pump controller'],['external','Externe Regelung / Home Assistant','External control / Home Assistant']],c.managed_by)}
 ${select(p,id,'entry_id',t(p,'Wärmepumpe für Signale und Parameter','Heat pump for signals and parameters'),[['','Nicht zugeordnet','Unassigned'],...units.map(u=>[u.id,u.title,u.title])],c.entry_id)}
 ${select(p,id,'electricity_scope',t(p,'Strom im Anlagen-Gesamtzähler','Electricity in the overall plant meter'),[['unknown','Messgrenze unbekannt','Boundary unknown'],['included','Bereits enthalten','Already included'],['separate','Separat / nicht enthalten','Separate / not included']],c.electricity_scope)}
 ${Object.keys(FIELDS).filter(key=>id==='secondary'||!['dhw_pump_entity','heating_pump_entity','dhw_temperature_entity','heating_temperature_entity'].includes(key)).map(key=>`<label class="field">${label(p,key)}<r290-entity-picker data-source="${id}" data-source-field="${key}"></r290-entity-picker></label>`).join('')}</div>
 <button class="secondary" data-source-suggest="${id}">${t(p,'Eindeutige R290-Signale vorschlagen','Suggest unambiguous R290 signals')}</button><p class="small muted">${t(p,'Bei externer Regelung ist keine steuernde R290-Wärmepumpe erforderlich. Die WP-Ausgänge werden nur für die Ansteuerung „Wärmepumpensteuerung“ vorgeschlagen; externe Schalter bleiben frei zuordenbar.','External control does not require a controlling R290 heat pump. R290 request outputs are suggested only for heat-pump control; external switches can be mapped independently.')}</p><p class="small muted">${t(p,'Die Betriebsrückmeldung sollte vom Gerät oder Schütz kommen. Ein Reglerausgang bestätigt keine Wärmeerzeugung. Leere Felder bleiben unzugeordnet; Strom- und Wärmezähler werden nicht automatisch zur Gesamtbilanz addiert.','Running feedback should come from the device or contactor. A controller output does not confirm heat production. Empty fields remain unassigned; electricity and heat meters are not automatically added to the overall balance.')}</p></div></details>`).join('')}
 <p class="notice">${t(p,'EH1 kann laut Handbuch bei P139/P140 = 2 als Gasfreigabe dienen. WW-Heizstab und Gasfreigabe dürfen dann nicht als unabhängig schaltbare Geräte angenommen werden. EH2 bezeichnet einen Heizungsausgang; seine Zuordnung zum Puffer muss zur Verdrahtung passen.','According to the manual, EH1 can serve as a gas request with P139/P140 = 2. DHW heating and gas requests must then not be assumed to be independent outputs. EH2 is a heating output; its buffer assignment must match the wiring.')}</p>
 <div class="settings-actions"><button class="primary" data-action="save-settings">${t(p,'Wärmeerzeuger speichern','Save heat sources')}</button></div></section>`;
}
export function readSourcesForm(p){const result=sourceModel(p);for(const el of p.shadowRoot.querySelectorAll('[data-source][data-source-field]'))result[el.dataset.source][el.dataset.sourceField]=el.type==='checkbox'?el.checked:el.value;return result;}
export function configureSourcePicker(p,picker,items){
 if(!picker.dataset.source)return false;
 const field=picker.dataset.sourceField, allowed=STATUS.has(field)?['sensor','binary_sensor','switch','input_boolean']:['sensor'];
 const units=field==='power_entity'?['W','kW']:['energy_entity','heat_entity'].includes(field)?['Wh','kWh','MWh']:STATUS.has(field)?null:['°C','°F'];
 picker.configure(items.filter(s=>allowed.includes(s.id.split('.')[0])&&(!units||units.includes(s.unit))),sourceModel(p)[picker.dataset.source][field],label(p,field),p.language);return true;
}
export function refreshSourcesLanguage(p){
 const root=p.shadowRoot.querySelector('.heat-source-setup');if(!root)return;
 const saved=readSourcesForm(p), template=document.createElement('template');template.innerHTML=sourcesForm(p);patchElement(root,template.content.firstElementChild);
 for(const el of root.querySelectorAll('[data-source][data-source-field]')){const value=saved[el.dataset.source][el.dataset.sourceField];if(el.tagName==='R290-ENTITY-PICKER')el.setValue(value);else if(el.type==='checkbox')el.checked=value;else el.value=value;}
}
const relay=n=>`relay_output_status_${n}_`;
export const NATIVE_SOURCES={
 dhw_heater:{request_entity:[relay(1)+'hot_water_electric_heating_status']},
 buffer_heater:{request_entity:[relay(1)+'air_conditioner_electric_heating_status',relay(1)+'floor_heating_electric_heating_status']},
 secondary:{request_entity:[relay(3)+'gas_output_status'],dhw_pump_entity:[relay(3)+'auxiliary_heat_source_hot_water_pump_status'],heating_pump_entity:[relay(3)+'auxiliary_heat_source_heating_pump_status'],dhw_temperature_entity:['auxiliary_heating_source_hot_water_temperature_value'],heating_temperature_entity:['auxiliary_heating_source_heating_temperature_value']}
};
function parameter(p,uid,code){return p.data.entities.find(e=>e.entry_id===uid&&!e.disabled&&e.unique_id.includes(`_p${code}_`))?.id;}
function nativeControl(p,id,c){
 if(c.managed_by==='heat_pump')return true;
 const request=p.data.entities.find(e=>e.id===c.request_entity&&e.entry_id===c.entry_id);
 return !!request&&NATIVE_SOURCES[id].request_entity.some(s=>new RegExp(`^r290_heatpump_${s}_slave_\\d+$`).test(request.unique_id));
}
export function suggestSources(p,id){
 const c=readSourcesForm(p)[id];if(!c.entry_id){p.toast(t(p,'Zuerst die zuständige Wärmepumpe auswählen.','First select the responsible heat pump.'),true);return;}
 let count=0;
 for(const [field,slugs] of Object.entries(NATIVE_SOURCES[id])){
   if(c[field])continue;
   if(field==='request_entity'&&c.managed_by!=='heat_pump')continue;
   if(id==='dhw_heater'&&p.raw(parameter(p,c.entry_id,'140'))!==0)continue;
   if(id==='secondary'&&field==='request_entity'&&c.kind!=='gas')continue;
   if(c.serves==='heating'&&field.startsWith('dhw_')||c.serves==='dhw'&&field.startsWith('heating_'))continue;
   const matches=p.data.entities.filter(e=>!e.disabled&&e.entry_id===c.entry_id&&p.states[e.id]&&slugs.some(s=>new RegExp(`^r290_heatpump_${s}_slave_\\d+$`).test(e.unique_id)));
   if(matches.length!==1)continue;
   p.shadowRoot.querySelector(`[data-source="${id}"][data-source-field="${field}"]`)?.setValue(matches[0].id);count++;
 }
 if(count)p._editingSettings=true;
 p.toast(count?t(p,`${count} eindeutige Quellen vorgeschlagen. Verdrahtung prüfen und speichern.`,`${count} unambiguous sources suggested. Check wiring and save.`):t(p,'Keine eindeutige neue Quelle. Entitäten gegebenenfalls in Home Assistant aktivieren und passend zur Verdrahtung zuordnen.','No unambiguous new source. Enable entities in Home Assistant if necessary and map them to the actual wiring.'));
}
function usable(p,id){const s=p.states[id];if(!s||s.attributes?.restored||p.hass?.connected===false||['unknown','unavailable'].includes(s.state))return null;if(p.data.entities.some(e=>e.id===id)){const at=p.data.reports?.[id]||s.last_reported;if(!at||!Number.isFinite(Date.parse(at))||Date.now()-Date.parse(at)>180000)return null;}return s;}
function signal(p,id){const s=usable(p,id);return !s?null:['on','true','1'].includes(s.state)?true:['off','false','0'].includes(s.state)?false:null;}
export function sourceStatus(p,c){
 if(c.feedback_entity&&c.feedback_entity!==c.request_entity){const on=signal(p,c.feedback_entity);return {active:on,ids:[c.feedback_entity],text:on===null?t(p,'Rückmeldung unbekannt','Feedback unknown'):on?t(p,'Betriebsrückmeldung an','Running feedback on'):t(p,'Betriebsrückmeldung aus','Running feedback off')};}
 if(c.power_entity){const s=usable(p,c.power_entity),n=numeric(s?.state);const valid=n!==null&&n>=0&&['W','kW'].includes(s?.attributes?.unit_of_measurement);return {active:valid?n>0:null,ids:[c.power_entity],text:!valid?t(p,'Leistung unbekannt','Power unknown'):n>0?t(p,'Leistungsaufnahme','Drawing power'):t(p,'Keine Leistungsaufnahme','No power draw')};}
 const on=signal(p,c.request_entity);return {active:null,ids:[c.request_entity],text:on===null?t(p,'Status unbekannt','State unknown'):on?t(p,'Angefordert · Betrieb unbestätigt','Requested · operation unconfirmed'):t(p,'Nicht angefordert','Not requested')};
}
function warnings(p,id,c,all){
 const warnings=[];
 if(nativeControl(p,id,c)&&id==='dhw_heater'&&p.raw(parameter(p,c.entry_id,'140'))===2)warnings.push(t(p,'P140 = 2: Ausgang ist als Gasfreigabe konfiguriert. Heizstab-Zuordnung prüfen.','P140 = 2: output configured as gas request. Check heater assignment.'));
 if(nativeControl(p,id,c)&&id==='buffer_heater'&&p.raw(parameter(p,c.entry_id,'139'))===2)warnings.push(t(p,'P139 = 2: Gasbetrieb ausgewählt. Heizstab-Zuordnung prüfen.','P139 = 2: gas operation selected. Check heater assignment.'));
 if(c.feedback_entity&&c.feedback_entity===c.request_entity)warnings.push(t(p,'Anforderung und Rückmeldung sind dieselbe Quelle; keine unabhängige Bestätigung.','Request and feedback use the same source; no independent confirmation.'));
 if(Object.entries(all).some(([key,other])=>key!==id&&other.enabled&&['request_entity','power_entity','energy_entity','heat_entity'].some(field=>c[field]&&c[field]===other[field])))warnings.push(t(p,'Quelle mit einem weiteren Wärmeerzeuger geteilt; keine getrennte Verbrauchsmessung / Ansteuerung belegt.','Source shared with another heat source; independent metering / control is not established.'));
 return warnings;
}
export function sourcesOverview(p){
 const all=sourceModel(p), enabled=Object.entries(all).filter(([,c])=>c.enabled);
 if(!enabled.length)return '';
 return `<section class="heat-sources"><div class="card-header"><div><h2>${t(p,'Weitere Wärmeerzeuger','Additional heat sources')}</h2><p>${t(p,'Anforderung und tatsächliche Rückmeldung getrennt betrachten.','Distinguish requests from actual feedback.')}</p></div><button class="secondary" data-view="settings">${t(p,'Zuordnung ändern','Edit assignments')}</button></div>${(p.data.heat_source_issues||[]).map(s=>`<p class="notice error">${esc(s)}</p>`).join('')}<div class="heat-source-grid">${enabled.map(([id,c])=>{
  const status=sourceStatus(p,c),codes=!nativeControl(p,id,c)?[]:id==='dhw_heater'?['022','096','140']:id==='buffer_heater'?['022','026','139']:['139','140','151','152','153','154'];
  const context=c.serves==='dhw'?t(p,'Warmwasser','DHW'):c.serves==='both'?t(p,'Heizung + Warmwasser','Heating + DHW'):t(p,'Heizung','Heating');
  const value=key=>STATUS.has(key)?p.historyValue(c[key],esc(signal(p,c[key])===null?t(p,'Unbekannt','Unknown'):signal(p,c[key])?t(p,'An','On'):t(p,'Aus','Off'))):p.val(c[key]);
  return `<article class="card heat-source-card" data-heat-source="${id}"><div class="card-header"><div><h3>${title(p,id)}</h3><p>${esc(id==='secondary'?KINDS.find(k=>k[0]===c.kind)?.[p.language==='en'?2:1]||'':t(p,'Elektrisch','Electric'))} · ${context}</p></div><span class="source-glyph ${status.active===true&&!p._animationPaused?'active':''}" aria-hidden="true">♨</span></div>${p.historyValue(status.ids,p.badge(status.text,status.active===true?'warm':status.active===null?'amber':''))}
  <p class="small muted">${c.managed_by==='heat_pump'?t(p,'Ansteuerung: Wärmepumpensteuerung','Control: heat-pump controller'):c.managed_by==='external'?t(p,'Ansteuerung: externe Regelung','Control: external controller'):t(p,'Ansteuerung: nicht zugeordnet','Control: unassigned')}${id==='buffer_heater'?` · ${esc(PLACEMENTS.find(v=>v[0]===c.placement)?.[p.language==='en'?2:1]||'')}`:''}</p>
  ${Object.keys(FIELDS).filter(key=>c[key]).map(key=>`<div class="status-row"><span>${label(p,key)}</span><strong>${value(key)}</strong></div>`).join('')||`<p>${t(p,'Noch keine Messquellen zugeordnet.','No measurement sources assigned yet.')}</p>`}
  ${warnings(p,id,c,all).map(s=>`<p class="notice">${esc(s)}</p>`).join('')}
  ${codes.length?`<details data-detail-id="source-parameters-${id}"><summary>${t(p,'Zugehörige Geräteparameter','Related device parameters')}</summary>${codes.map(code=>{const eid=parameter(p,c.entry_id,code);return eid?`<div class="status-row"><span>P${code} · ${esc(p.name(eid))}</span>${p.val(eid)}</div>`:'';}).join('')||`<p>${t(p,'Zuständige Wärmepumpe und aktive Parameter-Entitäten zuordnen.','Assign the responsible heat pump and enable its parameter entities.')}</p>`}<p class="small muted">${t(p,'Änderungen im Bereich Parameter prüfen. Diese Anzeige schaltet keine Komponenten.','Review changes in Parameters. This display does not switch components.')}</p></details>`:''}</article>`;
 }).join('')}</div></section>`;
}
export function sourceHistoryIds(p){return [...new Set(Object.values(sourceModel(p)).filter(c=>c.enabled).flatMap(c=>Object.keys(FIELDS).map(k=>c[k])).filter(Boolean))];}
export function sourcesEnergy(p){
 const enabled=Object.entries(sourceModel(p)).filter(([,c])=>c.enabled);if(!enabled.length)return '';
 const reading=(id)=>{const s=p.history?.series[id],factor=energyFactor(s?.unit),delta=numeric(s?.summary?.delta);return p.historyValue(id,`${s&&factor!==null&&delta!==null?`${s.summary.uncertain?'≈ ':''}${fmt(delta*factor,2)} kWh`:'—'}`);};
 return `<section class="card source-energy"><h2>${t(p,'Energie der weiteren Wärmeerzeuger','Energy from additional heat sources')}</h2><p>${t(p,'Zählerzuwächse im ausgewählten Zeitraum. Keine automatische Addition zur Anlagenbilanz und keine COP-Berechnung für Gas-, Öl- oder Holzgeräte.','Meter increments for the selected period. No automatic addition to plant totals or COP calculation for gas, oil or wood appliances.')}</p>${enabled.map(([id,c])=>`<div class="source-energy-row"><strong>${title(p,id)}</strong><span>${t(p,'Strom','Electricity')}: ${reading(c.energy_entity)}</span><span>${t(p,'Wärme','Heat')}: ${reading(c.heat_entity)}</span><small>${c.electricity_scope==='included'?t(p,'Strom im Gesamtzähler enthalten · nicht doppelt addieren','Electricity included in overall meter · do not add twice'):c.electricity_scope==='separate'?t(p,'Strom separat erfasst','Electricity metered separately'):t(p,'Strom-Messgrenze unbekannt','Electricity boundary unknown')}</small></div>`).join('')}<p class="small muted">${t(p,'Fehlende Zähler bleiben leer. Datenlücken, Rücksetzungen und verzögerte Meldungen begrenzen die zeitliche Zuordnung. Die Wärmeabgabe wird nicht aus Heizstab-Nennleistung oder Schaltzustand errechnet.','Missing meters remain blank. Gaps, resets and delayed reports limit time allocation. Heat output is not inferred from nominal heater power or switching state.')}</p></section>`;
}

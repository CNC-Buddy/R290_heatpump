import {esc} from './model.js?v=1.1.0';
import {patchElement} from './dom.js?v=1.1.0';

export const OPTIONS={
 mode:[['single','Einzelgerät','Single unit'],['cascade','Parallele Kaskade','Parallel cascade']],
 heating:[['direct','Direkter Heizkreis','Direct heating circuit'],['buffer_parallel','Parallelpuffer / hydraulische Weiche','Parallel buffer / hydraulic separator'],['buffer_series','Reihenpuffer im Rücklauf','Series buffer in return']],
 separation:[['none','Keine zusätzliche Trennung','No additional separation'],['plate','Plattenwärmetauscher','Plate heat exchanger']],
 dhw:[['none','Kein Warmwasserspeicher','No DHW tank'],['coil','Speicher mit interner Heizschlange','Tank with internal coil'],['plate','Speicher über Plattenwärmetauscher','Tank via plate heat exchanger']],
 aux_position:[['none','Keine Zusatzpumpe','No auxiliary pump'],['common_supply','Gemeinsamer Vorlauf vor Umschaltventil','Common supply before diverter'],['common_return','Gemeinsamer Rücklauf','Common return'],['heating_supply','Nur im Heizungsvorlauf nach Umschaltventil','Heating supply after diverter only']],
 emitters:[['radiators','Heizkörper','Radiators'],['floor','Fußbodenheizung','Underfloor heating'],['mixed','Heizkörper und Fußbodenheizung','Radiators and underfloor heating']],
 isolation:[['none','Keine Absperrventile','No isolation valves'],['pump_linked','Kugelhähne an interne Pumpen gekoppelt','Ball valves linked to internal pumps'],['feedback','Kugelhähne mit Offen-Rückmeldung','Ball valves with open feedback']],
};
const LABELS={mode:['Anlagenart','Plant type'],heating:['Heizungseinbindung','Heating connection'],separation:['Systemtrennung Heizung','Heating system separation'],dhw:['Warmwasser','Domestic hot water'],aux_position:['Position der Zusatzpumpe','Auxiliary pump position'],emitters:['Wärmeabgabe','Heat emitters'],isolation:['Absperrventile je Wärmepumpe','Isolation valves per heat pump']};
const t=(p,de,en)=>p.language==='en'?en:de;
export const choiceLabel=(p,key,value)=>OPTIONS[key]?.find(o=>o[0]===value)?.[p.language==='en'?2:1]||value;
export function plantModel(p){
 const all=(p.data?.entries||[]).filter(e=>e.type==='heat_pump'&&!e.disabled);
 return p.data?.settings?.plant||p.data?.plant||{mode:all.length===1?'single':'cascade',unit_ids:all.map(e=>e.id),heating:'buffer_parallel',separation:'plate',dhw:'coil',aux_position:'common_supply',emitters:'radiators',isolation:'none',valve_entities:{},controller_id:p.data?.controllers?.length===1?p.data.controllers[0].entry_id:''};
}
export function plantDescription(p){const m=plantModel(p);return `${choiceLabel(p,'mode',m.mode)} · ${choiceLabel(p,'heating',m.heating)} · ${choiceLabel(p,'dhw',m.dhw)}`;}
export function plantForm(p){
 const m=plantModel(p), all=(p.data?.entries||[]).filter(e=>e.type==='heat_pump');
 return `<section class="card plant-setup"><div class="card-header"><div><h2>${t(p,'Anlagenaufbau','Plant configuration')}</h2><p>${t(p,'Beschreibt Verrohrung und Gerätezuordnung. Ändert keine Kaskadenparameter der Wärmepumpen.','Describes plumbing and device assignments. Does not change heat-pump cascade parameters.')}</p></div></div>
 ${!p.data.settings.plant?`<p class="notice">${t(p,'Bisheriges Schema als Vorgabe. Bitte den tatsächlichen Aufbau auswählen und speichern.','The previous schematic is prefilled. Select and save the actual installation.')}</p>`:''}
 ${(p.data.plant_issues||[]).map(issue=>`<p class="notice error">${esc(issue)}</p>`).join('')}
 <div class="form-grid">${Object.entries(OPTIONS).map(([key,options])=>`<label class="field">${LABELS[key][p.language==='en'?1:0]}<select data-plant="${key}">${options.map(([value,de,en])=>`<option value="${value}" ${m[key]===value?'selected':''}>${t(p,de,en)}</option>`).join('')}</select></label>`).join('')}
 <label class="field">${t(p,'Zugeordneter Zusatzpumpenregler','Assigned auxiliary-pump controller')}<select data-plant="controller_id"><option value="">${t(p,'Keiner / nur Anzeige','None / display only')}</option>${(p.data.controllers||[]).map(c=>`<option value="${esc(c.entry_id)}" ${m.controller_id===c.entry_id?'selected':''}>${esc(c.name)}</option>`).join('')}</select></label></div>
 <h3>${t(p,'Zugehörige Wärmepumpen','Heat pumps in this plant')}</h3><p class="small muted">${t(p,'Die Reihenfolge folgt der Liste. Dieselbe Reihenfolge muss in den Sensorlisten des Reglers gelten. Offen-Rückmeldung: an = offen. Ein Schaltbefehl allein ist keine Positionsmessung.','List order is used for controller sensor bindings. Open feedback: on = open. A switch command alone is not a position measurement.')}</p>
 <div class="plant-unit-list">${all.map(u=>`<div class="plant-unit-row"><label><input type="checkbox" data-plant-unit="${esc(u.id)}" ${m.unit_ids.includes(u.id)?'checked':''} ${u.disabled?'disabled':''}> ${esc(u.title)} <small>· ${t(p,'Busadresse','Bus address')} ${esc(u.slave)}</small></label><label class="field">${t(p,'Kugelhahn · Offen-Rückmeldung','Ball valve · open feedback')}<r290-entity-picker data-valve-unit="${esc(u.id)}"></r290-entity-picker></label></div>`).join('')}</div>
 <p class="small muted">${t(p,'Die Automatik des Zusatzpumpenreglers unterstützt die gemeinsame Pumpe im Vor- oder Rücklauf. Eine Pumpe nur im Heizungszweig wird dargestellt; ihre automatische Regelung ist hier nicht freigegeben. Bestehende Sensorlisten bleiben unverändert.','Automatic auxiliary control supports a common supply or return pump. A pump in the heating branch is displayed; its automatic control is not enabled here. Existing sensor bindings remain unchanged.')}</p>
 <div class="settings-actions"><button class="primary" data-action="save-settings">${t(p,'Anlagenaufbau speichern','Save plant configuration')}</button></div></section>`;
}
export function readPlantForm(p){
 const previous=plantModel(p), result={...previous};
 for(const el of p.shadowRoot.querySelectorAll('[data-plant]'))result[el.dataset.plant]=el.value;
 result.unit_ids=[...p.shadowRoot.querySelectorAll('[data-plant-unit]:checked')].map(el=>el.dataset.plantUnit);
 result.valve_entities=Object.fromEntries([...p.shadowRoot.querySelectorAll('[data-valve-unit]')].filter(el=>result.unit_ids.includes(el.dataset.valveUnit)).map(el=>[el.dataset.valveUnit,el.value||'']));
 if((result.mode==='single'&&result.unit_ids.length!==1)||(result.mode==='cascade'&&result.unit_ids.length<2))throw new Error(t(p,'Geräteauswahl passt nicht zu Einzelgerät / Kaskade.','Device selection does not match single unit / cascade.'));
 if(result.aux_position==='none'&&result.controller_id)throw new Error(t(p,'Ohne Zusatzpumpe bitte keinen Regler zuordnen.','Do not assign a controller when no auxiliary pump is present.'));
 if(result.isolation==='feedback'&&result.unit_ids.some(id=>!result.valve_entities[id]))throw new Error(t(p,'Bitte Offen-Rückmeldung für jeden Kugelhahn zuordnen.','Assign open feedback to every ball valve.'));
 return result;
}

// Translate this form without committing or losing an incomplete plant draft.
export function refreshPlantLanguage(p){
 const root=p.shadowRoot.querySelector('.plant-setup');if(!root)return;
 const values=[...root.querySelectorAll('[data-plant],[data-plant-unit]')].map(el=>({key:el.dataset.plant,unit:el.dataset.plantUnit,value:el.value,checked:el.checked}));
 const template=document.createElement('template');template.innerHTML=plantForm(p);patchElement(root,template.content.firstElementChild);
 for(const saved of values){const el=[...root.querySelectorAll('[data-plant],[data-plant-unit]')].find(e=>e.dataset.plant===saved.key&&e.dataset.plantUnit===saved.unit);if(el){el.value=saved.value;if(saved.unit)el.checked=saved.checked;}}
}

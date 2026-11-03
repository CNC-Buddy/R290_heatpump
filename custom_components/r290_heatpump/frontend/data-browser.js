import {renderBusHealth} from './bus-health.js?v=1.1.1';
import {esc, numeric, fmt} from './model.js?v=1.1.1';
import {patchHTML} from './dom.js?v=1.1.1';
import {tr, translateTree} from './i18n.js?v=1.1.1';

export const sections={main:'Maschineninfo',realtime:'Echtzeitwerte',user:'Benutzerparameter',devices:'Systemparameter',user2:'Benutzerparameter 2',all:'Alle Entitäten'};
const HELP={P099:['Ziel-Temperaturdifferenz für die interne Pumpendrehzahlregelung der Wärmepumpe. Dieser Parameter regelt nicht die separate Zusatzpumpe.','Target temperature difference for the internal pump-speed control. This parameter does not control the separate auxiliary pump.'],P100:['Untere PWM-Grenze der internen Wasserpumpe. Die separate Zusatzpumpe hat eigene Betriebsgrenzen.','Lower PWM limit for the internal water pump. The separate auxiliary pump has its own operating limits.']};
const sectionNumbers={main:1,realtime:2,user:3,devices:4,user2:5};
export const text=(p,de,en)=>p.language==='en'?en:de;
export const records=p=>p._registerCatalog?.records||[];
export function recordFor(p,e){
  const base=e.unique_id.replace(/_slave_\d+(?:_v2)?$/,'');
  const address=e.register??(e.unique_id.match(/_([0-9a-f]{4})_slave_/i)?.[1] ? parseInt(e.unique_id.match(/_([0-9a-f]{4})_slave_/i)[1],16):null);
  return records(p).find(r=>address!==null?r.address===address:r.entities?.some(v=>v.unique_id===base));
}
export const title=(p,r)=>p.language==='en'?r.display_name_en||r.name:r.name_de||r.name;
function unitDifferences(p,entities){
  // Compare the same interpretation across units, never raw PWM against %
  // (or a register bit against the parent status) within a single unit.
  const groups=new Map();
  for(const e of entities){
    const value=p.states[e.id]?.state;
    if(e.disabled||value===undefined||['unknown','unavailable'].includes(value))continue;
    const key=e.unique_id.replace(/_slave_\d+(?:_v2)?$/,'');
    if(!groups.has(key))groups.set(key,new Map());
    groups.get(key).set(e.entry_id,value);
  }
  return [...groups.values()].some(values=>values.size>1&&new Set(values.values()).size>1);
}
export function sample(p,entry,address){
  const a=p.data.registers?.[entry]?.[address],b=p._registerSamples?.[entry]?.[address];
  return !a?b:!b?a:Math.max(Date.parse(b.received_at)||0,Date.parse(b.attempted_at)||0)>=Math.max(Date.parse(a.received_at)||0,Date.parse(a.attempted_at)||0)?b:a;
}
export function rawValue(s){return s?.value==null?'—':`${s.value} / ${s.value>32767?s.value-65536:s.value} / 0x${Number(s.value).toString(16).toUpperCase().padStart(4,'0')}`;}
function rawLink(p,entry,address,s){return `<button class="value-history" data-raw-history="${esc(entry)}" data-address="${address}" title="${text(p,'Sitzungsverlauf anzeigen','Show session history')}"><code>${rawValue(s)}</code></button>`;}
export function showRawHistory(p,entry,address){
  const values=(p._registerLog||[]).filter(s=>s.entry_id===entry&&s.address===address);
  const latest=sample(p,entry,address);
  if(latest?.received_at&&!values.some(v=>v.received_at===latest.received_at))values.push({...latest,address,entry_id:entry});
  values.sort((a,b)=>Date.parse(b.received_at)-Date.parse(a.received_at));
  p.readOnlyDialog(`${text(p,'Rohregister','Raw register')} 0x${address.toString(16).toUpperCase().padStart(4,'0')}`,`<p>${text(p,'Nur empfangene Sitzungsmessungen, kein dauerhafter Recorder-Verlauf. Die Live-Abfrage sammelt Werte, solange die Diagnoseansicht geöffnet ist.','Received session readings only, not permanent Recorder history. Live polling collects values while the diagnostics view is open.')}</p><div class="table-wrap"><table><thead><tr><th>${text(p,'Empfangen','Received')}</th><th>uint16 / int16 / hex</th></tr></thead><tbody>${values.map(s=>`<tr><td>${p.date(s.received_at)}</td><td><code>${rawValue(s)}</code></td></tr>`).join('')||`<tr><td colspan="2">${text(p,'Noch keine Messungen.','No readings yet.')}</td></tr>`}</tbody></table></div>`);
}
function freshness(p,s){
  if(!s?.received_at)return text(p,'Noch kein Empfang','No reception yet');
  if(s.error)return text(p,'Lesefehler · letzter Empfang','Read error · last reception');
  const stale=(Date.now()-Date.parse(s.received_at))/1000>Math.max(90,(s.interval||30)*2);
  return text(p,stale?'Veraltet · letzter Empfang':'Empfangen',stale?'Stale · last reception':'Received');
}
function entityValue(p,e){
  const lockedPassword=recordFor(p,e)?.code==='P183'&&!p.systemUnlocked(e.entry_id);
  if(lockedPassword)return `<div><strong>••••</strong><small>${text(p,'Passwort geschützt','Password protected')}</small></div>`;
  const state=p.states[e.id],available=!e.disabled&&state&&!['unavailable','unknown'].includes(state.state);
  const pumpLabel=/r290_heatpump_pump_speed_percent(?:_slave_\d+)?$/.test(e.unique_id||'')?text(p,'Pumpendrehzahl (%)','Pump speed (%)'):/r290_heatpump_pump_speed_pwm(?:_slave_\d+)?$/.test(e.unique_id||'')?text(p,'PWM-Rohwert','Raw PWM'):'';
  const editable=/^(number|select|switch)\./.test(e.id)&&p.data.entries.find(v=>v.id===e.entry_id)?.type!=='auxiliary_pump';
  return `<div data-key="${esc(e.id)}">${pumpLabel?`<small>${esc(pumpLabel)}</small>`:''}${e.disabled?`<span class="muted">${text(p,'Deaktiviert','Disabled')}</span>`:`<strong>${p.val(e.id)}</strong>`}${editable&&p.canEditParameter(e.id)?` <button class="param-value editable" data-edit="${esc(e.id)}" aria-label="${text(p,'Bearbeiten','Edit')}: ${esc(e.name)}" ${available&&p.hass?.connected!==false?'':'disabled'}>✎</button>`:''}
    ${p.pending.has(e.id)?`<small>${text(p,String(p.pending.get(e.id).value)===state?.state?'Rückmeldung stimmt überein':'Rückmeldung ausstehend',String(p.pending.get(e.id).value)===state?.state?'Feedback matches':'Awaiting feedback')}</small>`:''}<small>${esc(e.id)}${!available&&!e.disabled?` · ${text(p,'Nicht verfügbar','Unavailable')}`:''}</small>
    <details data-detail-id="entity-${esc(e.id)}"><summary>${text(p,'Entitätsdetails','Entity details')}</summary><p>${esc(e.name)}<br>${esc(e.unique_id)}</p><p>${text(p,'Zustand geändert','State changed')}: ${p.date(state?.last_changed)}<br>${text(p,'HA-Meldung','HA report')}: ${p.date(p.data.reports?.[e.id]||state?.last_reported)}</p><pre data-no-translate>${esc(JSON.stringify(state?.attributes||{},null,2))}</pre></details></div>`;
}
function explanation(p,r){
  const desc=p.language==='en'?(r.description_en||r.description):(r.description_de||r.description);
  const def=r.default_observed??r.default_manual;
  const bits=p.language==='en'?(r.bits_en||r.bits):(r.bits_de||r.bits);
  return `<strong>${esc(r.code?`${r.code} · ${title(p,r)}`:title(p,r))}</strong><small>${esc(r.hex)} · ${esc(r.access||text(p,'Zugriff unbekannt','Access unknown'))}${r.min!=null?` · ${text(p,'Bereich laut Dokumentation','Documented range')} ${esc(r.min)} ${text(p,'bis','to')} ${esc(r.max)} ${esc(r.unit||'')}`:''}</small><details data-detail-id="reg-${r.section}-${r.address}"><summary>${text(p,'Erklärung','Explanation')}</summary><p class="parameter-description" data-no-translate>${esc(desc||text(p,'Keine dokumentierte Erklärung.','No documented explanation.'))}</p>${HELP[r.code]?`<p>${text(p,...HELP[r.code])}</p>`:''}${bits?`<pre data-no-translate>${esc(bits)}</pre>`:''}${r.issues?.length?`<p>${text(p,'Hinweise zur Registerzuordnung:','Register mapping notes:')}<br>${r.issues.map(issue=>esc(p.language==='en'?issue.replace(/Bit (\d+) nicht einzeln beschriftet:/,'Bit $1 has no individual label:').replace('Nur Schalter 0/1 implementiert; Modi 2 und 3 aus Excel fehlen.','Only a 0/1 switch is implemented; spreadsheet modes 2 and 3 are missing.'):issue)).join('<br>')}</p>`:''}</details>${r.code==='P183'||def===undefined||def===null?'':`<span class="sr-only">Default ${esc(def)}</span>`}`;
}
export function renderCatalogTable(p){
  const target=p.shadowRoot.querySelector('#parameter-table');if(!target)return;
  const tab=p.view==='system'?'devices':p.view==='machine'?'main':p._parameterTab||'devices',query=p.query.toLowerCase().trim(),entries=p.data.entries;
  const codeQuery=/^p\d{1,3}$/.test(query)?`P${query.slice(1).padStart(3,'0')}`:null;
  const entityRecords=new Map(p.data.entities.map(e=>[e.id,recordFor(p,e)]));
  let body, count;
  if(tab==='all'){
    const entities=p.data.entities.filter(e=>`${e.name} ${e.id} ${e.unique_id} ${entries.find(v=>v.id===e.entry_id)?.title}`.toLowerCase().includes(query));count=entities.length;
    body=`<thead><tr><th>${text(p,'Entität & Information','Entity & information')}</th><th>${text(p,'Eintrag','Entry')}</th><th>${text(p,'Zustand & Attribute','State & attributes')}</th></tr></thead><tbody>${entities.map(e=>`<tr data-key="${esc(e.id)}"><td>${esc(e.name)}<small>${esc(entityRecords.get(e.id)?.hex||'')}</small></td><td>${esc(entries.find(v=>v.id===e.entry_id)?.title||e.entry_id)}</td><td>${entityValue(p,e)}</td></tr>`).join('')}</tbody>`;
  }else{
    const rows=records(p).filter(r=>r.section===sectionNumbers[tab]).map(r=>({r,entities:p.data.entities.filter(e=>entityRecords.get(e.id)===r)})).filter(({r,entities})=>{
      return (!p.differences||unitDifferences(p,entities))&&(codeQuery?r.code===codeQuery:`${r.display_name_en} ${r.name} ${r.name_de} ${r.description} ${r.description_de} ${r.description_en} ${r.code} ${r.hex} ${entities.map(e=>`${e.id} ${e.name}`).join(' ')}`.toLowerCase().includes(query));
    });count=rows.length;
    body=`<thead><tr><th>${text(p,'Parameter & Erklärung','Parameter & explanation')}</th><th>Default</th>${p.units.map(u=>`<th>${text(p,'WP','HP')} ${esc(u.slave)}</th>`).join('')}</tr></thead><tbody>${rows.map(({r,entities})=>`<tr data-key="register-${r.section}-${r.address}" class="${unitDifferences(p,entities)?'diff':''}"><td>${explanation(p,r)}</td><td class="default-value">${r.code==='P183'?'••••':esc(r.default_observed??r.default_manual??'—')}<small>${esc(r.unit||'')}</small></td>${p.units.map(unit=>{
      const cells=entities.filter(e=>e.entry_id===unit.id).sort((a,b)=>Number(b.unique_id.includes('pump_speed_percent'))-Number(a.unique_id.includes('pump_speed_percent'))),s=sample(p,unit.id,r.address);
      return `<td>${cells.map(e=>entityValue(p,e)).join('')||`<span class="muted">${text(p,'Keine Entität','No entity')}</span>`}${s&&r.code!=='P183'?`<details data-detail-id="raw-${unit.id}-${r.address}"><summary>${text(p,'Rohwert','Raw value')}</summary>${rawLink(p,unit.id,r.address,s)}<small>${freshness(p,s)} · ${p.date(s.received_at)}</small></details>`:''}</td>`;
    }).join('')}</tr>`).join('')}</tbody>`;
  }
  p.shadowRoot.querySelector('#parameter-count').textContent=`${count} ${text(p,'Einträge','entries')}`;
  patchHTML(target,`${p._catalogError?`<div class="notice">${esc(p._catalogError)}</div>`:''}<div class="table-wrap device-parameters"><table>${body}</table></div>`);
  translateTree(target,p.language);
}
function registerSelection(p){const scope=p._diagnosticScope||'';return records(p).filter(r=>r.kind==='holding'&&(scope==='all'||(scope?r.section===Number(scope):r.unknown)));}
export function renderDiagnostics(p){
  if(!p._registerNotes){try{const notes=JSON.parse(localStorage.getItem('r290.register.notes')||'{}');p._registerNotes=notes&&typeof notes==='object'&&!Array.isArray(notes)?notes:{};}catch{p._registerNotes={};}}
  const rows=registerSelection(p),query=(p._diagnosticQuery||'').toLowerCase();
  const filtered=rows.filter(r=>`${r.hex} ${r.code||''} ${r.name} ${r.name_de||''}`.toLowerCase().includes(query));
  return p.heading(text(p,'Register live untersuchen.','Inspect live registers.'),text(p,'Rohwerte ohne angenommene Skalierung. Jede Messung trägt ihren tatsächlichen Empfangszeitpunkt.','Raw values without assumed scaling. Every reading carries its actual reception time.'),`<button class="${p._diagnosticLive?'primary':'secondary'}" data-diagnostic-action="toggle" ${p.hass?.connected===false&&!p._diagnosticLive?'disabled':''}>${p._diagnosticLive?text(p,'Live-Abfrage stoppen','Stop live reads'):text(p,'Live-Abfrage starten','Start live reads')}</button><button class="secondary" data-diagnostic-action="export">JSON ↓</button>`)+
    renderBusHealth(p)+`<div class="notice info">${text(p,'Die laufende Integration liefert vorhandene Rohwerte. „Live-Abfrage starten“ liest zusätzlich die gewählte Registergruppe reihum über die bestehende Modbus-Verbindung: höchstens 20 Register pro Anfrage, 3 Sekunden Pause. Stoppt beim Verlassen dieser Seite. Es werden keine Register beschrieben.','Existing raw readings come from normal integration polling. “Start live reads” additionally reads the selected register group in turn via the existing Modbus connection: up to 20 registers per request, with a 3 second pause. Stops when leaving this page. No registers are written.')}</div>
    <section class="card"><div class="filters"><label>${text(p,'Registergruppe','Register group')}<select data-diagnostic-scope>${[['','Unbekannte Register','Unknown registers'],['all','Alle Register','All registers'],...Object.entries(sectionNumbers).map(([key,id])=>[String(id),sections[key],tr(sections[key],'en')])].map(([id,de,en])=>`<option value="${id}" ${(p._diagnosticScope||'')===id?'selected':''}>${text(p,de,en)}</option>`).join('')}</select></label><input type="search" data-diagnostic-query aria-label="${text(p,'Register suchen','Search registers')}" placeholder="${text(p,'Adresse oder Name','Address or name')}" value="${esc(p._diagnosticQuery||'')}"><span>${filtered.length} / ${rows.length}</span><span role="status">${p._diagnosticLive?text(p,'Live-Abfrage läuft','Live reads running'):text(p,'Zusätzliche Abfrage gestoppt','Additional reads stopped')}</span></div>
    ${p._diagnosticError?`<div class="notice error">${esc(p._diagnosticError)}</div>`:''}
    <div class="table-wrap register-table"><table><thead><tr><th>${text(p,'Register','Register')}</th><th>${text(p,'Gerät','Device')}</th><th>uint16 / int16 / hex</th><th>${text(p,'Vorher / Änderung','Previous / change')}</th><th>${text(p,'Empfang / Änderung','Reception / change')}</th></tr></thead><tbody>${filtered.flatMap(r=>p.units.map(u=>{
      const s=sample(p,u.id,r.address);
      return `<tr data-key="diagnostic-${u.id}-${r.address}" class="${s?.error?'diagnostic-error':''}"><td><strong>${esc(r.hex)}</strong> ${esc(r.code||'')}<small>${esc(title(p,r))}</small><details data-detail-id="bits-${u.id}-${r.address}"><summary>${text(p,'Bits & Beschreibung','Bits & description')}</summary><code>${s?.value==null?'—':Number(s.value).toString(2).padStart(16,'0')}</code><pre data-no-translate>${esc((p.language==='en'?r.bits_en:r.bits_de)||r.bits||'')}</pre><p>${esc(p.language==='en'?r.description_en||r.description:r.description_de||r.description)}</p><label class="field">${text(p,'Vermutete Bedeutung / Notiz','Suspected meaning / note')}<textarea data-register-note="${r.address}" aria-label="${text(p,'Notiz','Note')} ${r.hex} ${text(p,'WP','HP')} ${u.slave}">${esc(p._registerNotes[r.address]||'')}</textarea></label></details></td><td>${text(p,'WP','HP')} ${esc(u.slave)}</td><td>${rawLink(p,u.id,r.address,s)}</td><td>${s?.previous==null?'—':`${s.previous} / ${s.value-s.previous>0?'+':''}${s.value-s.previous}`}</td><td>${freshness(p,s)}<small>${p.date(s?.received_at)}<br>Δ ${p.date(s?.changed_at)}${s?.error?`<br>${esc(s.error)}`:''}</small></td></tr>`;
    })).join('')}</tbody></table></div><p class="small muted">${text(p,'Der Export ist eine Momentaufnahme mit bis zu 2.000 Sitzungsmessungen; live ist nur diese verbundene Ansicht. Fehlende Werte sind keine Nullen.','The export is a snapshot with up to 2,000 session readings; only this connected view is live. Missing readings are not zeros.')}</p></section>`;
}
export function stopDiagnostics(p){p._diagnosticGeneration=(p._diagnosticGeneration||0)+1;p._diagnosticLive=false;clearTimeout(p._diagnosticTimer);}
async function poll(p,generation=p._diagnosticGeneration){
  if(generation!==p._diagnosticGeneration)return;
  if(!p._diagnosticLive||!p.isConnected||p.view!=='diagnostics'){stopDiagnostics(p);return;}
  if(p.hass?.connected===false||document.hidden){p._diagnosticTimer=setTimeout(()=>poll(p,generation),3000);return;}
  const jobs=[];
  for(const u of p.units){let job;
    for(const r of registerSelection(p).sort((a,b)=>a.address-b.address)){
      if(!job||job.addresses.length>=20||r.address!==job.addresses.at(-1)+1){job={entry_id:u.id,addresses:[]};jobs.push(job);}job.addresses.push(r.address);
    }
  }
  if(!jobs.length){stopDiagnostics(p);p.render();return;}
  const job=jobs[(p._diagnosticCursor||0)%jobs.length];p._diagnosticCursor=(p._diagnosticCursor||0)+1;
  p._registerSamples??={};const bucket=p._registerSamples[job.entry_id]??={};
  try{
    const result=await p.ws('registers',job);if(generation!==p._diagnosticGeneration)return;p._diagnosticError='';
    for(const [address,value] of Object.entries(result.values)){
      const old=sample(p,job.entry_id,address),changed=old?.value!==value;
      bucket[address]={value,received_at:result.received_at,changed_at:changed?result.received_at:old?.changed_at,previous:changed?old?.value:old?.previous,interval:Math.max(30,jobs.length*3),error:null};
      p._registerLog??=[];p._registerLog.push({entry_id:job.entry_id,address:Number(address),value,received_at:result.received_at});
    }
    p._registerLog=p._registerLog.slice(-2000);
  }catch(err){if(generation!==p._diagnosticGeneration)return;p._diagnosticError=err.message||String(err);for(const address of job.addresses)bucket[address]={...sample(p,job.entry_id,address),error:p._diagnosticError,attempted_at:new Date().toISOString()};}
  if(p._diagnosticLive&&p.isConnected&&p.view==='diagnostics'){p.render();p._diagnosticTimer=setTimeout(()=>poll(p,generation),3000);}
}
export function diagnosticAction(p,action){
  if(action==='toggle'){if(p._diagnosticLive)stopDiagnostics(p);else {p._diagnosticLive=true;p._diagnosticCursor=0;poll(p);}p.render();}
  if(action==='export'){
    const content={exported_at:new Date().toISOString(),live:false,version:p.data.version,polling:p.data.polling||[],entries:p.units,notes:p._registerNotes||{},registers:p.data.registers,session_registers:p._registerSamples||{},samples:p._registerLog||[],sample_limit:2000};
    const url=URL.createObjectURL(new Blob([JSON.stringify(content,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='r290-register-snapshot.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
}
export async function loadFaults(p){
  if(p._faultLoading)return;p._faultLoading=true;p._faultError='';
  try{p._faultHistory=await p.ws('faults',{days:p._faultDays||7});}catch(err){p._faultError=err.message||String(err);}finally{p._faultLoading=false;p.render();}
}
function faultState(p,value){return value==='None'||value==='0'?text(p,'Keine aktiven Meldungen','No active faults'):!value||['unknown','unavailable'].includes(value)?text(p,'Status unbekannt','Status unknown'):esc(value);}
function currentFault(p,e){
  const r=recordFor(p,e),s=sample(p,e.entry_id,r?.address);
  if(e.disabled)return null;
  if(s?.error)return 'unavailable';
  if(s?.value!=null){
    const labels=new Map([...String(r?.bits||'').matchAll(/^Bit(\d+)[ \t]+([^\r\n]+)/gm)].map(m=>[Number(m[1]),m[2].trim()]));
    const active=Array.from({length:16},(_,i)=>i).filter(i=>s.value&(1<<i));
    return active.map(i=>labels.get(i)||`Bit ${i} · ${text(p,'Bedeutung unbekannt','meaning unknown')}`).join(', ')||'None';
  }
  return p.states[e.id]?.state;
}
export function renderFaults(p){
  const entities=p.data.entities.filter(e=>e.fault||recordFor(p,e)?.section===1&&/fault/i.test(recordFor(p,e)?.name||''));
  const available=entities.filter(e=>currentFault(p,e)&&!['unknown','unavailable'].includes(currentFault(p,e)));
  const active=available.filter(e=>!['None','0'].includes(currentFault(p,e)));
  const history=p._faultHistory;
  return p.heading(text(p,'Fehlerspeicher & Status.','Fault history & status.'),text(p,'Aktuelle Fehlermeldungen und aufgezeichnete Zustände aus Home Assistant.','Current fault reports and recorded states from Home Assistant.'),`<button class="secondary" data-fault-refresh ${p._faultLoading?'disabled':''}>${text(p,'Verlauf aktualisieren','Refresh history')}</button>`)+
    `<div class="notice info">${text(p,'Der Verlauf stammt aus dem Home-Assistant-Recorder, nicht aus einem nachgewiesenen internen Fehlerspeicher. Deaktivierte, ausgeschlossene oder fehlende Entitäten haben möglicherweise keinen Verlauf. „Status unbekannt“ bestätigt keine Entstörung.','History comes from Home Assistant Recorder, not a verified internal device fault log. Disabled, excluded or missing entities may have no history. “Status unknown” does not confirm a fault has cleared.')}</div>
    <div class="metrics-grid">${p.metric(text(p,'Register mit aktiven Meldungen','Registers with active reports'),active.length)}${p.metric(text(p,'Verfügbare Fehlerregister','Available fault registers'),`${available.length} / ${entities.length}`)}</div>
    <section class="card"><h2>${text(p,'Aktuelle Fehlermeldungen','Current fault reports')}</h2><div class="table-wrap"><table><thead><tr><th>${text(p,'Gerät / Fehlerregister','Device / fault register')}</th><th>Status</th><th>${text(p,'HA-Meldung','HA report')}</th></tr></thead><tbody>${entities.map(e=>`<tr data-key="fault-${esc(e.id)}"><td>${esc(p.data.entries.find(u=>u.id===e.entry_id)?.title)}<small>${esc(e.name)} · ${esc(recordFor(p,e)?.hex||'')}</small></td><td>${e.disabled?text(p,'Deaktiviert','Disabled'):p.historyValue(e.id,faultState(p,currentFault(p,e)))}</td><td>${p.date(p.data.reports?.[e.id]||p.states[e.id]?.last_reported)}${sample(p,e.entry_id,recordFor(p,e)?.address)?`<small>Modbus: ${freshness(p,sample(p,e.entry_id,recordFor(p,e)?.address))} · ${p.date(sample(p,e.entry_id,recordFor(p,e)?.address)?.received_at)}</small>`:''}</td></tr>`).join('')||`<tr><td colspan="3">${text(p,'Keine Fehlerentitäten vorhanden.','No fault entities present.')}</td></tr>`}</tbody></table></div></section>
    <section class="card"><div class="filters"><h2>${text(p,'Aufgezeichnete Zustände','Recorded states')}</h2><select data-fault-days aria-label="${text(p,'Zeitraum','Period')}">${[1,7,30].map(n=>`<option value="${n}" ${(p._faultDays||7)===n?'selected':''}>${n} ${text(p,'Tage','days')}</option>`).join('')}</select><span>${history?.events?.length||0} ${text(p,'Einträge','entries')}</span></div>${p._faultError?`<div class="notice error">${esc(p._faultError)}</div>`:''}${history?.truncated?`<div class="notice">${text(p,'Anzeige auf die letzten 2.000 Zustandswechsel begrenzt. Zeitraum verkürzen.','Showing the last 2,000 state changes. Select a shorter period.')}</div>`:''}<p class="small muted">${text(p,'Entitäten mit Aufzeichnungen','Entities with recorded data')}: ${history?.recorded_ids?.length||0} / ${history?.entity_ids?.length||0}</p><div class="table-wrap"><table><thead><tr><th>${text(p,'Zeit','Time')}</th><th>${text(p,'Fehlerregister','Fault register')}</th><th>Status</th></tr></thead><tbody>${(history?.events||[]).map((event,i)=>`<tr data-key="event-${i}"><td>${p.date(event.at)}${event.initial?`<small>${text(p,'Erster bekannter Zustand im Zeitraum','Initial known state in period')}</small>`:''}</td><td>${esc(p.name(event.entity_id))}</td><td>${p.historyValue(event.entity_id,faultState(p,event.state))}</td></tr>`).join('')||`<tr><td colspan="3">${p._faultLoading?text(p,'Verlauf wird geladen …','Loading history …'):text(p,'Keine Aufzeichnungen im gewählten Zeitraum.','No recorded data in this period.')}</td></tr>`}</tbody></table></div></section>`;
}

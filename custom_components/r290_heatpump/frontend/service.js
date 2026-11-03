import {esc} from './model.js?v=1.1.1';

const COMPONENTS={compressor:['Verdichter 1','Compressor 1',0x332,120,'Hz'],fan:['Lüfter','Fan',0x33e,80,'Hz'],eev:['Expansionsventil EEV 1','Expansion valve EEV 1',0x336,500,'steps'],evi:['Einspritzventil EVI 1','Injection valve EVI 1',0x33a,500,'steps'],pump:['Interne Wasserpumpe','Internal water pump',0x344,100,'raw %']};
const t=(p,de,en)=>p.language==='en'?en:de;
const unitText=(p,u)=>u==='steps'?t(p,'Schritte','steps'):u==='raw %'?t(p,'% (Rohwert)','% (raw)'):u;
const unitId=p=>p._serviceUnit||p.units[0]?.id||p.allUnits[0]?.id;
export function serviceBanner(p){
 const tests=p.data?.service?.tests||{};
 return Object.entries(tests).map(([id,test])=>`<div class="notice error" role="status"><strong>${esc(p.allUnits.find(u=>u.id===id)?.title||id)} · ${test.state==='running'?t(p,'Servicetest aktiv','Service test running'):t(p,'Servicetest: Rücksetzung prüfen','Service test: check recovery')}</strong><p>${test.state==='running'?`${t(p,'Automatische Rücksetzung vorgesehen bis','Automatic release scheduled by')} ${esc(p.date(test.ends_at))}`:esc(test.error||t(p,'Nach Neustart oder Unterbrechung Rücksetzung erforderlich.','Recovery required after restart or interruption.'))}</p><button class="secondary" data-service-stop="${esc(id)}">${t(p,'Test beenden / Automatik wiederherstellen','End test / restore automatic mode')}</button></div>`).join('');
}
export function renderService(p,factory=false){
 const id=unitId(p), snap=p.data?.service?.snapshots?.[id], vals=snap?.values||{}, errors=snap?.errors||{};
 const val=a=>vals[a]===undefined?'—':String(vals[a]), busy=p._serviceBusy;
 return p.heading(factory?t(p,'Werkstestmodus','Factory test mode'):t(p,'Geräteinfo','Device information'),t(p,'Dokumentierte Serviceregister pro Wärmepumpe. Tests sind unabhängig von normalen Geräteparametern.','Documented service registers per heat pump. Tests are separate from normal device parameters.'))+
 `<div class="card service-toolbar"><label class="field">${t(p,'Wärmepumpe','Heat pump')}<select data-service-unit>${p.allUnits.map(u=>`<option value="${esc(u.id)}" ${id===u.id?'selected':''}>${esc(u.title)}</option>`).join('')}</select></label><button class="secondary" data-service-action="read" ${busy||!id?'disabled':''}>${busy?t(p,'Register werden gelesen …','Reading registers …'):t(p,'Geräteinfo und Testwerte lesen','Read device info and test values')}</button><span class="small muted">${snap?`${t(p,'Letzte Abfrage','Last read')}: ${esc(p.date(snap.received_at))}`:t(p,'Noch nicht abgefragt','Not read yet')}</span></div>
 ${p._serviceError?`<p class="notice error" role="alert">${esc(p._serviceError)}</p>`:''}
 ${!factory?`<div class="grid equal"><section class="card"><h2>${t(p,'Firmware & Protokoll','Firmware & protocol')}</h2>
 <div class="status-row"><span>${t(p,'Programmversion · Hauptplatine','Program version · mainboard')}<small>0x0360 · ${t(p,'Rohwert','Raw value')} ${val(0x360)}</small></span><strong>${esc(snap?.program_version||'—')}</strong></div>
 <div class="status-row"><span>${t(p,'Controller-/Displayversion','Controller/display version')}</span><strong>—</strong></div>
 <p class="small muted">${t(p,'Für die Displayversion ist keine Modbus-Adresse belegt. Die Programmversion wird gemäß Protokoll als Rohwert ÷ 100 angezeigt; bitte einmal am Geräte-Display vergleichen.','No Modbus address is documented for the display version. Program version uses raw value ÷ 100 according to the protocol; compare it with the device display once.')}</p>
 <div class="status-row"><span>${t(p,'Produkttyp / Typ-ID','Product type / type ID')}</span><strong>${val(0x361)} / ${val(0x362)}</strong></div><div class="status-row"><span>${t(p,'Protokollversion · Rohwert','Protocol version · raw value')}</span><strong>${val(0x363)}</strong></div>
 ${Object.keys(errors).length?`<details><summary>${t(p,'Nicht lesbare Register','Unreadable registers')} (${Object.keys(errors).length})</summary>${Object.entries(errors).map(([a,e])=>`<p class="small muted">0x${Number(a).toString(16).toUpperCase()} · ${esc(e)}</p>`).join('')}</details>`:''}</section></div>`:''}${factory?`<div class="grid equal">
 <section class="card"><h2>${t(p,'Vor einem Komponententest','Before a component test')}</h2><p>${t(p,'Gerät ausschalten und Verdichterstillstand abwarten. Zusatzpumpenregler auf Beobachten stellen. Vor Ort bleiben und sicherstellen, dass die gewählte Komponente zur Geräteausführung gehört.','Switch the device off and wait for the compressor to stop. Set auxiliary controllers to Observe. Stay on site and ensure the selected component exists on this device.')}</p>
 <p class="small muted">${t(p,'Ein Test läuft 15–120 Sekunden. Home Assistant setzt danach den Testmodus zurück und prüft die Registerrückmeldung. Bei Strom-, Netzwerk- oder HA-Ausfall ist das nicht garantiert: dann am Gerät beenden. Ein Register-Readback bestätigt keinen mechanischen Betrieb.','Tests run for 15–120 seconds. Home Assistant releases the override and checks register feedback afterward. Power, network or HA failure can prevent release: stop at the device in that case. Register readback does not confirm mechanical operation.')}</p><p class="small muted">${t(p,'Interne Pumpenvorgabe: roher Protokollwert, keine bestätigte Drehrichtung der PWM-Skala. PFC, Kältemittelrückgewinnung, Evakuierung, Werksreset und IPLV sind hier nicht als Testbefehle freigegeben.','Internal pump target: raw protocol value; PWM direction is not confirmed. PFC, refrigerant recovery, evacuation, factory reset and IPLV are not enabled as test commands here.')}</p></section></div>
 <section class="card"><div class="card-header"><div><h2>${t(p,'Komponenten gezielt testen','Test individual components')}</h2><p>${t(p,'Immer nur ein Test gleichzeitig. Start erst nach Vorschau und ausdrücklicher Bestätigung.','One test at a time. Starting requires a preview and explicit confirmation.')}</p></div></div>
 <div class="service-components">${Object.entries(COMPONENTS).map(([key,[de,en,address,max,unit]])=>`<div class="service-component"><h3>${t(p,de,en)}</h3><p class="small muted">0x${address.toString(16).toUpperCase()} · 0–${max} ${unitText(p,unit)}</p><div class="status-row"><span>${t(p,'Gespeicherte Testvorgabe','Stored test target')}</span><strong>${val(address)} ${unitText(p,unit)}</strong></div><button class="secondary" data-service-test="${key}" ${busy||!snap||vals[address]===undefined||Object.keys(p.data?.service?.tests||{}).length?'disabled':''}>${t(p,'Test vorbereiten','Prepare test')}</button></div>`).join('')}</div>
 <p class="small muted">${t(p,'Zwangssteuerung 0x0331 / Pumpenmodus 0x0343','Forced control 0x0331 / pump mode 0x0343')}: ${val(0x331)} / ${val(0x343)}. ${t(p,'Grundlage: Modbus-Protokoll V1.2.9, Seiten 25–27. Vorhandene Übersteuerungen werden nicht übernommen.','Source: Modbus protocol V1.2.9, pages 25–27. Existing overrides are not taken over.')}</p></section>`:''}`;
}
export function serviceChange(p,el){if(!el.hasAttribute('data-service-unit'))return false;p._serviceUnit=el.value;p._serviceError='';el.blur();p.render();return true;}
export async function serviceClick(p,button){
 if(button.dataset.serviceStop){
   button.disabled=true;
   try{await p.ws('service',{action:'stop',entry_id:button.dataset.serviceStop});p._serviceError='';}
   catch(err){p._serviceError=err.message;p.toast(err.message,true);}
   await p.load();button.disabled=false;return true;
 }
 if(button.dataset.serviceAction==='read'){
   const id=unitId(p);p._serviceBusy=true;p._serviceError='';button.blur();p.render();
   try{await p.ws('service',{action:'read',entry_id:id});}
   catch(err){p._serviceError=err.message;}
   finally{p._serviceBusy=false;await p.load();}return true;
 }
 const component=button.dataset.serviceTest;if(!component)return false;
 const [de,en,address,max,unit]=COMPONENTS[component], id=unitId(p);
 p.openModal(t(p,'Komponententest prüfen','Review component test'),`${esc(p.allUnits.find(u=>u.id===id)?.title||id)} · ${t(p,de,en)}`,
 `<label class="field">${t(p,'Testvorgabe','Test target')} (${unitText(p,unit)})<input name="target" type="number" min="0" max="${max}" step="1" value="${p.data?.service?.snapshots?.[id]?.values[address]??0}" required></label><label class="field">${t(p,'Dauer in Sekunden','Duration in seconds')}<input name="duration" type="number" min="15" max="120" step="1" value="30" required></label><p>${t(p,'Dieser Befehl kann die Komponente sofort bewegen oder starten. Bei Kommunikationsausfall am Gerät beenden.','This command may immediately move or start the component. Stop at the device if communication fails.')}</p><label class="service-confirm"><input name="qualified" type="checkbox" required> ${t(p,'Ich prüfe vor Ort die passende Geräteausführung und beaufsichtige den Test.','I have checked the device configuration and will supervise the test on site.')}</label>`,async dialog=>{
  await p.ws('service',{action:'start',entry_id:id,component,value:Number(dialog.querySelector('[name=target]').value),seconds:Number(dialog.querySelector('[name=duration]').value),qualified:dialog.querySelector('[name=qualified]').checked,confirmed:true});
  return t(p,'Test gestartet. Rücksetzung am Gerät überprüfen.','Test started. Check release at the device.');
 });return true;
}

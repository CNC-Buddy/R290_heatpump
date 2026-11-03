import {electricOverview} from './electric-overview.js?v=1.1.0';
import {esc, numeric, fmt, ageLabel, phaseNames, modeNames, chartPaths} from './model.js?v=1.1.0';
import {icon, pumpIcon, schematic} from './visuals.js?v=1.1.0';
import {plantModel,plantDescription} from './plant.js?v=1.1.0';
import {plantSchematic} from './plant-schematic.js?v=1.1.0';
import {sourcesOverview} from './heat-sources.js?v=1.1.0';

import {renderChart} from './chart-ui.js?v=1.1.0';

export function overviewSeries(p) {
  const chosen=p.data?.settings?.charts?.['overview-temperature']?.entity_ids;if(chosen)return chosen.map((id,i)=>({id,label:p.name(id),color:`var(--plot-${i%6+1})`}));
  const first=p.units[0], common=p.entity('total_water_outlet_temperature',first?.id);
  const plant=plantModel(p);
  return [
    {id:common||p.entity('water_outlet_temperature_t7',first?.id),label:common?'Vorlauf · gemeinsam':`Vorlauf · WP ${first?.slave??'—'}`,color:'var(--plot-1)'},
    {id:p.entity('return_water_temperature_t6',first?.id),label:`Rücklauf · WP ${first?.slave??'—'}`,color:'var(--plot-2)'},
    {id:p.mapping('tank_entity'),label:'Warmwasser',color:'var(--plot-3)'},
    {id:p.mapping('buffer_entity'),label:'Heizungspuffer',color:'var(--plot-4)'},
    {id:p.mapping('outdoor_entity'),label:'Außentemperatur',color:'var(--plot-5)'},
  ].filter(s=>s.label!=='Warmwasser'||plant.dhw!=='none').filter(s=>s.label!=='Heizungspuffer'||plant.heating!=='direct');
}

const sourceKey=p=>overviewSeries(p).map(s=>s.id||'').join('|')+'|'+(p.data?.settings?.charts?.['overview-temperature']?.days||1);
export function overviewNeedsHistory(p) {
  return !p._overviewLoading&&!p._overviewError&&(!p.overviewHistory||p._overviewKey!==sourceKey(p)||Date.now()-p._overviewLoadedAt>300000);
}
export async function loadOverviewHistory(p) {
  if(p._overviewLoading||!p.data)return;
  const key=sourceKey(p), ids=[...new Set(overviewSeries(p).map(s=>s.id).filter(Boolean))];
  p._overviewLoading=true;p._overviewError='';p.render();
  try {
    if(!ids.length)throw new Error('Für den Temperaturverlauf sind noch keine Quellen zugeordnet.');
    const result=await p.ws('history',{entity_ids:ids,days:p.data?.settings?.charts?.['overview-temperature']?.days||1});
    if(key===sourceKey(p)){p.overviewHistory=result;p._overviewKey=key;p._overviewLoadedAt=Date.now();}
  } catch(error){p._overviewError=error.message||String(error);}
  finally {p._overviewLoading=false;p.render();}
}

// A HA report is not proof that a physical radio packet arrived. Never infer it
// from last_updated (which changes only when a state or its attributes change).
function report(p,id) {
  const s=p.states[id], at=p.data?.reports?.[id]||s?.last_reported;
  const time=at?Date.parse(at):NaN;
  return {id,valid:numeric(s?.state)!==null,time,age:Number.isFinite(time)?Math.max(0,(Date.now()-time)/1000):null};
}
function activeSignal(p,id){
  const source=report(p,id);
  return p.hass?.connected!==false&&!p._animationPaused&&source.valid&&source.age!==null&&source.age<=180&&p.raw(id)>0;
}

export function booleanSignal(p,id){
  const state=p.states[id];
  if(!state||state.attributes?.restored||p.hass?.connected===false)return null;
  // R290 status sensors are polled; switches/helpers may legitimately remain
  // unchanged for hours. Their source integration must mark failures unavailable.
  if(p.data?.entities?.some(e=>e.id===id)){
    const at=p.data?.reports?.[id]||state.last_reported;
    if(!at||!Number.isFinite(Date.parse(at))||Date.now()-Date.parse(at)>180000)return null;
  }
  const value=String(state.state).toLowerCase();
  return ['on','true','1'].includes(value)?true:['off','false','0'].includes(value)?false:null;
}

export function hydraulicState(p){
  const dhwId=p.mapping('dhw_entity');
  const dhw=booleanSignal(p,dhwId);
  // A mapped but unavailable signal must not be concealed by an old decision.
  const phase=plantModel(p).dhw==='none'?'heating':dhwId?(dhw===null?null:dhw?'dhw':'heating'):
    (['dhw','heating'].includes(p.controller?.decision?.phase)?p.controller.decision.phase:null);
  const enabled=p.hass?.connected!==false&&!p._animationPaused;
  const bufferChargeState=booleanSignal(p,p.mapping('buffer_charge_entity'));
  const radiatorState=booleanSignal(p,p.mapping('radiator_pump_entity'));
  return {phase:p.hass?.connected===false?null:phase,
    bufferChargeState,radiatorState,
    bufferCharging:enabled&&bufferChargeState===true,
    radiatorRunning:enabled&&radiatorState===true,
    dhwCharging:enabled&&booleanSignal(p,p.mapping('dhw_charge_entity'))===true};
}

export function qualityModel(p) {
  const sources=p.units.map(u=>report(p,p.entity('water_outlet_temperature_t7',u.id)));
  const heat=report(p,p.mapping('heat_energy_entity'));
  const missing=sources.length===0||sources.some(s=>!s.valid)||!heat.valid||overviewSeries(p).some(s=>numeric(p.states[s.id]?.state)===null);
  const old=sources.some(s=>s.age!==null&&s.age>180)||heat.age!==null&&heat.age>900;
  const unknown=sources.some(s=>s.age===null)||heat.age===null;
  const disconnected=p.hass?.connected===false;
  const times=sources.map(s=>s.time).filter(Number.isFinite);
  return {sources,heat,missing,old,unknown,lanTime:times.length?Math.min(...times):NaN,
    label:disconnected?'Verbindung getrennt':missing?'Quellen unvollständig':old?'Meldealter prüfen':unknown?'Meldezeit unbekannt':'HA-Meldungen aktuell',
    tone:disconnected?'red':missing||old||unknown?'amber':'green'};
}

function qualityCard(p) {
  const q=qualityModel(p);
  const time=t=>Number.isFinite(t)?p.date(t,{hour:'2-digit',minute:'2-digit',second:'2-digit'}):'—';
  const delta=Number.isFinite(q.lanTime)&&Number.isFinite(q.heat.time)?Math.abs(q.lanTime-q.heat.time)/1000:null;
  return `<section class="card quality-card" aria-labelledby="quality-title"><h2 id="quality-title">Datenqualität</h2>${p.badge(q.label,q.tone)}
    <p>${q.missing?'Mindestens eine Messquelle fehlt oder liefert keinen Zahlenwert.':q.old?'Einige HA-Meldungen liegen länger zurück. WM-Bus-Zähler getrennt bewerten.':q.unknown?'Nicht alle Quellen stellen einen Meldezeitpunkt bereit.':'Die zugeordneten Quellen haben zuletzt zeitnah an HA gemeldet.'}</p>
    <div class="quality-times"><span class="section-label">Letzte HA-Meldung</span><dl><div><dt>Wärmepumpen¹</dt><dd title="${esc(Number.isFinite(q.lanTime)?p.date(q.lanTime):'Nicht bekannt')}">${time(q.lanTime)}</dd></div><div><dt>Wärmezähler</dt><dd title="${esc(Number.isFinite(q.heat.time)?p.date(q.heat.time):'Nicht bekannt')}">${time(q.heat.time)}</dd></div><div><dt>Zeitversatz</dt><dd>${delta===null?'—':esc(ageLabel(delta).replace(/^vor /,''))}</dd></div></dl></div>
    <p class="quality-note">¹ Älteste Vorlaufmeldung. HA-Meldezeiten belegen keinen WM-Bus-Empfang. Unveränderte Zählerstände sind kein Ausfallnachweis.</p>
    <button class="text-button" data-view="analysis">Messgrenzen ansehen ${icon('arrow')}</button></section>`;
}

function temperatureChart(p,series) {
  const width=p.shadowRoot.querySelector('.temperature-plot')?.clientWidth||680;
  return renderChart(p,'overview-temperature',{ids:series.map(s=>s.id),unit:'°C',title:p.language==='en'?'Temperature history':'Temperaturverläufe',legend:false,width,height:220,history:p._overviewKey===sourceKey(p)?p.overviewHistory:null,synced:true,managed:true,error:p._overviewError,labels:Object.fromEntries(series.map(s=>[s.id,s.label])),colors:Object.fromEntries(series.map(s=>[s.id,s.color]))});
}

function temperatures(p) {
  const series=overviewSeries(p), h=p.overviewHistory;
  return `<section class="card temperatures" aria-labelledby="temperatures-title"><div class="card-header"><div><h2 id="temperatures-title">Temperaturverläufe</h2><p>Wichtige Temperaturen der Anlage</p></div><button class="icon-button" data-action="overview-history-refresh" aria-label="Temperaturverlauf aktualisieren" ${p._overviewLoading?'disabled':''}>${icon('refresh')}</button></div>
    <div class="temperature-content"><div class="temperature-plot">${temperatureChart(p,series)}<p class="chart-caption">${h&&p._overviewKey===sourceKey(p)?`${p.date(h.start,{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})} – ${p.date(h.end,{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})} · Recorder`:'Home Assistant Recorder'} · Datenlücken unterbrechen die Linie.</p></div>
    <div class="current-values"><div class="current-heading"><h3>Aktuelle Werte</h3><span class="small muted">${p.date(Date.now(),{hour:'2-digit',minute:'2-digit'})}</span></div>${series.map(s=>`<div class="current-value ${p._hiddenTemperatures?.has(s.id)?'is-hidden':''}" ><button class="temperature-toggle" data-temperature="${esc(s.id||'')}" aria-pressed="${!p._hiddenTemperatures?.has(s.id)}" ${!s.id?'disabled':''} title="Kurve ein- oder ausblenden"><span class="temperature-dot" style="--series:${s.color}"></span><span>${esc(s.label)}</span></button><strong>${p.val(s.id)}</strong></div>`).join('')}<span class="small muted toggle-hint">Name: Kurve ausblenden · Wert: Verlauf öffnen.</span></div></div></section>`;
}

function pumpCard(p) {
  const c=p.controller,d=c?.decision, power=p.raw(p.mapping('pump_power_entity'));
  const running=power!==null?power>0:null;
  const moving=activeSignal(p,p.mapping("pump_power_entity"));
  return `<section class="card pump-summary"><div class="card-header"><h2>Zusatzpumpe</h2>${p.badge(running===null?'Status unbekannt':running?'Leistungsaufnahme':'Keine Leistung',running?'green':'')}</div>
    <div class="pump-hero">${pumpIcon(moving?"running":"")}<div><span class="label">Aktuelle Ansteuerung</span><div class="pump-readings"><strong>${p.historyValue(p.pumpEntity('actual_speed')||c?.config.speed_entity,`${fmt(c?.actual_speed,0)} <small>%</small>`)}</strong><span>${p.val(p.mapping('pump_power_entity'),0)}</span></div></div></div>
    <div class="mode-summary"><div><span class="label">Regelungsmodus</span><strong>${icon('eye')} ${esc(c?modeNames[c.mode]:'Nicht eingerichtet')}</strong></div><div><strong>${c?.mode==='observe'?'Keine Stellbefehle':c?'Regelung freigegeben':'Zuordnung fehlt'}</strong><p>${c?.mode==='observe'?'Der Regler beobachtet die Anlage und berechnet Vorschläge.':c?'Betriebsgrenzen und Freigaben gelten für jeden Stellbefehl.':'Sensoren und Stellglied in der Integration verbinden.'}</p></div></div>
    <div class="pump-targets"><div><span>Vorgeschlagene<br>Ansteuerung</span><strong>${p.historyValue(p.pumpEntity('suggested_speed'),`${fmt(d?.speed,0)} <small>%</small>`)}</strong></div><div><span>Ziel<br>Spreizung</span><strong>${p.historyValue(p.pumpEntity('target_delta'),`${fmt(d?.target_delta)} <small>K</small>`)}</strong></div><div><span>Gemessene<br>Spreizung${d?.deltas?.length>1?'en':''}</span><strong>${p.historyValue([...(c?.config.supply_entities||[]),...(c?.config.return_entities||[])],`${d?.deltas?.length?d.deltas.map(v=>fmt(v)).join(' / '):'—'} <small>K</small>`)}</strong></div></div>
    <button class="primary pump-link" data-view="pump">Regelung ansehen ${icon('arrow')}</button></section>`;
}

export function renderHydraulics(p) {
  if(p.data.settings.schematic?.published)return '<r290-schematic data-mode="live" data-preserve-children></r290-schematic>';
  const c=p.controller, pumpRunning=activeSignal(p,p.mapping("pump_power_entity"));
  const hydraulic=hydraulicState(p);
  const reading=id=>{const state=p.states[id];return numeric(state?.state)===null?'—':`${fmt(state.state,1)} ${state.attributes.unit_of_measurement||''}`;};
  const units=p.units.map(u=>({slave:u.slave,frequencyId:p.entity('compressor_operating_frequency',u.id),supplyId:p.entity('water_outlet_temperature_t7',u.id),returnId:p.entity('return_water_temperature_t6',u.id),fanRunning:activeSignal(p,p.entity("fan_operating_frequency_rotational_speed",u.id)),flowing:activeSignal(p,p.entity("water_flow",u.id)),frequency:reading(p.entity('compressor_operating_frequency',u.id)),supply:reading(p.entity('water_outlet_temperature_t7',u.id)),return:reading(p.entity('return_water_temperature_t6',u.id))}));
  if(p.data.settings.plant){
    const plant=plantModel(p), volume=key=>p.data.settings[key]?`${fmt(p.data.settings[key],0)} l`:'—';
    units.forEach((u,i)=>{
      u.id=p.units[i].id;
      if(plant.isolation==='feedback')u.valveOpen=booleanSignal(p,plant.valve_entities[u.id]);
      else if(plant.isolation==='pump_linked'){
        const source=p.data.entities.find(e=>e.entry_id===u.id&&e.unique_id.includes('relay_output_status_1_main_engine_circulating_water_pump_status'));
        u.valveOpen=source?booleanSignal(p,source.id):null;
      }
      if(plant.isolation==='feedback'&&u.valveOpen!==true)u.flowing=false;
      if(plant.isolation==='pump_linked'&&u.valveOpen===false)u.flowing=false;
    });
    return (p.data.plant_issues||[]).map(issue=>`<p class="notice error">${esc(issue)}</p>`).join('')+plantSchematic(p,plant,units,hydraulic,{pumpRunning,speedId:p.pumpEntity('actual_speed')||c?.config.speed_entity,speed:`${fmt(c?.actual_speed,0)} %`,tankId:p.mapping('tank_entity'),bufferId:p.mapping('buffer_entity'),tankTemp:reading(p.mapping('tank_entity')),bufferTemp:reading(p.mapping('buffer_entity')),tankVolume:volume('tank_liters'),bufferVolume:volume('buffer_liters')})+
      `<div class="schematic-footer"><span class="pipe-key hot">Vorlauf</span><span class="pipe-key cold">Rücklauf</span><span>${p.language==='en'?'Configured plumbing · animation uses fresh flow and status signals':'Konfigurierte Verrohrung · Animation nach aktuellen Durchfluss- und Statuswerten'}</span><button class="text-button" data-action="toggle-motion">${p._animationPaused?'Animation starten':'Animation pausieren'}</button><button class="text-button" data-view="settings">${p.language==='en'?'Edit plant':'Anlagenaufbau ändern'}</button></div>`;
  }
  if(units.length!==2)return `<div class="empty"><h3>${units.length} Wärmepumpen eingerichtet</h3><p>${p.language==='en'?'Choose the actual plumbing in Setup.':'Bitte den tatsächlichen Anlagenaufbau unter Einrichtung auswählen.'}</p><button class="primary" data-view="settings">${p.language==='en'?'Configure plant':'Anlagenaufbau einrichten'}</button></div>${p.unitTable()}`;
  const volume=key=>p.data.settings[key]?`${fmt(p.data.settings[key],0)} l`:'Volumen nicht hinterlegt';
  return `<div class="desktop-schematic">${schematic({units,historyLabel:p.language==='en'?'Show history':'Verlauf anzeigen',speedId:p.pumpEntity('actual_speed')||c?.config.speed_entity,powerId:p.mapping('pump_power_entity'),tankId:p.mapping('tank_entity'),bufferId:p.mapping('buffer_entity'),pumpRunning,...hydraulic,speed:`${fmt(c?.actual_speed,0)} %`,power:reading(p.mapping('pump_power_entity')),tankTemp:reading(p.mapping('tank_entity')),bufferTemp:reading(p.mapping('buffer_entity')),tankVolume:volume('tank_liters'),bufferVolume:volume('buffer_liters')})}</div>
    <div class="mobile-schematic"><div class="mobile-units">${units.map(u=>`<div class="mobile-unit"><span class="eyebrow">Wärmepumpe ${esc(u.slave)}</span><strong>${p.historyValue(u.frequencyId,esc(u.frequency))}</strong><dl><div><dt>Vorlauf</dt><dd class="hot-text">${p.historyValue(u.supplyId,esc(u.supply))}</dd></div><div><dt>Rücklauf</dt><dd class="cold-text">${p.historyValue(u.returnId,esc(u.return))}</dd></div></dl></div>`).join('')}</div><div class="flow-join"><span></span><small>Parallele Kaskade</small><span></span></div><div class="mobile-flow-pump">${pumpIcon(pumpRunning?"running":"")}<span>Gemeinsame Zusatzpumpe<strong>${p.historyValue(p.pumpEntity('actual_speed')||c?.config.speed_entity,`${fmt(c?.actual_speed,0)} %`)} <small>· ${p.val(p.mapping('pump_power_entity'))}</small></strong></span></div><div class="flow-divider">↓ <span>3/2-Wege-Umschaltventil</span></div><div class="mobile-stores"><div><span>Warmwasser</span><strong>${p.val(p.mapping('tank_entity'))}</strong><small>${esc(volume('tank_liters'))} · interner Wärmetauscher</small></div><div><span>Heizungspuffer</span><strong>${p.val(p.mapping('buffer_entity'))}</strong><small>${esc(volume('buffer_liters'))} · Plattenwärmetauscher → Heizkörper</small></div></div></div>
    <div class="schematic-status"><span>${hydraulic.phase==='dhw'?'Speicherzweig: Warmwasser':hydraulic.phase==='heating'?'Speicherzweig: Heizungspuffer':'Speicherzweig unbekannt · Warmwassersignal zuordnen'}</span><span>${hydraulic.bufferChargeState===true?'Pufferladekreis: an':hydraulic.bufferChargeState===false?'Pufferladekreis: aus':'Pufferladekreis: Status unbekannt'}</span><span>${hydraulic.radiatorState===true?'Heizkörperkreis: an':hydraulic.radiatorState===false?'Heizkörperkreis: aus':'Heizkörperkreis: Status unbekannt'}</span></div>
    <div class="schematic-footer"><span class="pipe-key hot">Vorlauf</span><span class="pipe-key cold">Rücklauf</span><span>Schema · Flussrichtung schematisch · Ventilposition nicht rückgemeldet</span><button class="text-button" data-action="toggle-motion" aria-pressed="${!p._animationPaused}">${p._animationPaused?"Animation starten":"Animation pausieren"}</button><button class="text-button" data-view="operation">Betriebsdetails ${icon('arrow')}</button></div>`;
}

export function renderOverview(p) {
  const c=p.controller,d=c?.decision, active=p.units.filter(u=>(p.raw(p.entity('compressor_operating_frequency',u.id))||0)>0).length;
  const phase=hydraulicState(p).phase;
  return `<div class="overview-heading" data-key="overview-heading"><div class="overview-title"><div><h1>Anlagenübersicht</h1>${p.historyValue(p.mapping('dhw_entity')||p.pumpEntity('status'),p.badge(phaseNames[phase]||'Status unbekannt',phase==='heating'?'warm':''))}</div><p>${esc(plantDescription(p))}</p></div><div class="overview-context"><div class="outdoor">${icon('cloud')}<div><span>Außentemperatur</span><strong>${p.val(p.mapping('outdoor_entity'))}</strong></div></div><div class="operating-context"><span>Betriebszustand</span><strong>${p.historyValue(p.pumpEntity('control_mode'),esc(c?`Regler: ${modeNames[c.mode]}`:'Regler nicht eingerichtet'))}</strong><small>${p.historyValue(p.units.map(u=>p.entity('compressor_operating_frequency',u.id)),`${active} von ${p.units.length} Verdichtern aktiv`)}</small></div></div></div>
    ${electricOverview(p)}<div data-key="overview-main" class="overview-main ${plantModel(p).aux_position==='none'||p.data.settings.schematic?.published?'without-aux':''}" style="--motion-offset:-${(p._motionOffset??=0).toFixed(3)}s"><section data-key="plant-card" class="card plant-card" aria-label="Hydraulische Anlagenübersicht">${renderHydraulics(p)}</section>${plantModel(p).aux_position==='none'||p.data.settings.schematic?.published?'':pumpCard(p)}</div>
    ${sourcesOverview(p)}<div class="overview-bottom" data-key="overview-bottom">${temperatures(p)}${qualityCard(p)}</div>`;
}

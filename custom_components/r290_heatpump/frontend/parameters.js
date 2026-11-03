import {sections, renderCatalogTable} from './data-browser.js?v=1.1.0';
import {translateTree} from './i18n.js?v=1.1.0';
import {esc, numeric, fmt} from './model.js?v=1.1.0';
import {curveValue, pointsOf, pointError, insertPoint, ENDPOINT_KEYS} from './curve-model.js?v=1.1.0';
export {curveValue} from './curve-model.js?v=1.1.0';

export const CURVES = {heating_curve:'Heizkörper',hot_water_curve:'Warmwasser',floor_heating_curve:'Fußbodenheizung',cooling_curve:'Kühlung'};
const TABS = {basis:'Basis',pv:'PV & Anhebung',fine:'Feinabstimmung'};
export function defaultValue(record){return record?.default_observed ?? record?.default_manual ?? null;}
function current(p){
  const type=p._parameterTab||'heating_curve';
  const entries=p.data.entries.filter(e=>e.type===type);
  const entry=entries.find(e=>e.id===p._curveEntry)||entries[0];
  const snap=p.data.curves?.find(c=>c.entry_id===entry?.id);
  return {type,entries,entry,snap,draft:p._curveDrafts?.get(entry?.id)};
}
function valuesFor(p,snap,draft){
  const values=Object.fromEntries((snap?.controls||[]).map(c=>[c.key,draft?.values[c.id]??draft?.base[c.id]??p.states[c.id]?.state]));
  if(draft?.points!==undefined||snap?.custom_points)values.points=draft?.points??snap.points;
  return values;
}
function changeList(draft){return Object.entries(draft?.values||{}).filter(([id,v])=>String(v)!==String(draft.base[id])).map(([entity_id,value])=>({entity_id,value,expected:draft.base[entity_id]}));}
function pointsChanged(draft){return draft?.points!==undefined&&JSON.stringify(draft.points)!==JSON.stringify(draft.basePoints);}
function changeCount(draft){return changeList(draft).length+(pointsChanged(draft)?1:0);}
function canEdit(p,snap){return p.unlocked&&p.hass?.connected!==false&&(!p._curveDrafts?.get(snap?.entry_id)||p._curveDrafts.get(snap.entry_id).revision===snap.revision);}
function ensureDraft(p,snap){
  p._curveDrafts??=new Map();
  if(!p._curveDrafts.has(snap.entry_id))p._curveDrafts.set(snap.entry_id,{revision:snap.revision,base:Object.fromEntries(snap.controls.map(c=>[c.id,p.states[c.id]?.state])),values:{},basePoints:structuredClone(snap.points??pointsOf(valuesFor(p,snap,null)))});
  return p._curveDrafts.get(snap.entry_id);
}
function editPoints(p,snap,points){
  const draft=ensureDraft(p,snap);draft.points=structuredClone(points);
  for(const c of snap.controls)if(ENDPOINT_KEYS.includes(c.key))delete draft.values[c.id];
  return draft;
}
// The master (slave 1) controls the shared heating curves.
export function curveEstimates(p,type){
  if(!['heating_curve','floor_heating_curve','cooling_curve'].includes(type))return [];
  const find=(unit,address,code)=>p.data.entities.find(e=>e.entry_id===unit.id&&!e.disabled&&e.id?.startsWith('number.')&&(Number(e.register)===address||new RegExp(`(?:_${address.toString(16).padStart(4,'0')}_slave_|_p${code}_)`,'i').test(e.unique_id||'')));
  const master=(p.allUnits||[]).find(unit=>Number(unit.slave)===1);
  if(!master)return [{available:false}];
  return [master].map(unit=>{
    const modeEntity=find(unit,0x0174,'116'),spreadEntity=find(unit,0x0163,'099');
    const mode=numeric(p.states[modeEntity?.id]?.state),spread=numeric(p.states[spreadEntity?.id]?.state);
    const available=(mode===0||mode===1)&&spread!==null&&spread>=0;
    return {unit,mode,spread,available,offset:available?(mode===0?spread:-spread)*(type==='cooling_curve'?-1:1):null};
  });
}
function estimateLabel(e,en){return e.mode===0?(en?'Flow forecast':'Vorlauf · Prognose'):(en?'Return forecast':'Rücklauf · Prognose');}
function baseLabel(p,type,draft){
  const mode=curveEstimates(p,type)[0]?.mode,en=p.language==='en';
  const side=mode===0?(en?'Return':'Rücklauf'):mode===1?(en?'Flow':'Vorlauf'):'';
  return `${en?'Base setpoint':'Basissoll'}${side?` · ${side}`:''}${draft?(en?' · preview':' · Vorschau'):''}`;
}
function estimateMetrics(p,type,values,outside){
  const rows=curveEstimates(p,type);if(!rows.length)return '';
  const en=p.language==='en',target=curveValue(values,outside);
  return `<div class="curve-estimates">${rows.map(e=>`<div><span>${e.available?estimateLabel(e,en):(en?'Forecast unavailable':'Prognose nicht verfügbar')}</span><strong>${e.available&&target!==null?`${fmt(target+e.offset,1)} <small>°C</small>`:'—'}</strong><small>${e.available?`${e.mode===0?(en?'Return control':'Rücklaufregelung'):(en?'Flow control':'Vorlaufregelung')} · P099 ${fmt(e.spread,1)} K`:(en?'P116 or P099 unavailable':'P116 oder P099 nicht verfügbar')}</small></div>`).join('')}</div>`;
}
function graph(p,snap,draft){
  const live=valuesFor(p,snap,null), values=valuesFor(p,snap,draft), outside=p.raw(snap?.outdoor_entity);
  const valid=curveValue(values,0)!==null;
  if(!valid)return `<div class="curve-no-data" role="alert">${esc(pointError(pointsOf(values)))}</div>`;
  const points=pointsOf(values),livePoints=pointsOf(live),editable=!!snap.point_limits&&canEdit(p,snap);
  const width=620,height=245,left=42,right=600,top=20,bottom=210;
  const xmin=Math.min(-20,...points.map(p=>Number(p.outdoor)-5)),xmax=Math.max(30,...points.map(p=>Number(p.outdoor)+5));
  const estimates=curveEstimates(p,current(p).type).filter(e=>e.available);
  const temperatures=[...points,...livePoints].flatMap(pt=>[Number(pt.target),...estimates.map(e=>Number(pt.target)+e.offset)]).filter(Number.isFinite);
  const ymin=Math.floor((Math.min(...temperatures)-5)/5)*5,ymax=Math.ceil((Math.max(...temperatures)+5)/5)*5;
  const x=t=>left+(t-xmin)/(xmax-xmin)*(right-left),y=t=>bottom-(t-ymin)/(ymax-ymin)*(bottom-top);
  const path=(v,offset=0)=>[xmin,...pointsOf(v).map(p=>Number(p.outdoor)),xmax].map((t,i)=>`${i?'L':'M'}${x(t).toFixed(1)},${y(curveValue(v,t)+offset).toFixed(1)}`).join(' ');
  return `<svg class="curve-chart" data-xmin="${xmin}" data-xmax="${xmax}" data-ymin="${ymin}" data-ymax="${ymax}" viewBox="0 0 ${width} ${height}" role="group" aria-label="Kurvenvorschau: Solltemperatur in Abhängigkeit von der Außentemperatur">
    ${[0,1,2,3,4].map(i=>{const v=ymin+i*(ymax-ymin)/4;return `<line class="grid-line" x1="${left}" x2="${right}" y1="${y(v)}" y2="${y(v)}"/><text x="32" y="${y(v)+4}" text-anchor="end">${fmt(v,0)}°</text>`;}).join('')}
    ${Array.from({length:6},(_,i)=>xmin+i*(xmax-xmin)/5).map(v=>`<text x="${x(v)}" y="233" text-anchor="middle">${fmt(v,0)}°</text>`).join('')}
    ${curveValue(live,0)!==null?`<path class="curve-live" style="display:${p._curveHidden?.has('live')?'none':''}" d="${path(live)}"/>`:''}
    ${estimates.map((e,i)=>`<path class="curve-estimate curve-estimate-${i%4}" d="${path(values,e.offset)}"><title>${estimateLabel(e,p.language==='en')}</title></path>`).join('')}
    ${changeCount(draft)?`<path class="curve-draft" style="display:${p._curveHidden?.has('draft')?'none':''}" d="${path(values)}"/>`:''}
    ${outside!==null&&outside>=xmin&&outside<=xmax?`<line class="curve-guide" x1="${x(outside)}" x2="${x(outside)}" y1="${top}" y2="${bottom}"/><circle cx="${x(outside)}" cy="${y(curveValue(values,outside))}" r="4.5" fill="var(--accent)"/>`:''}
    <g class="curve-control-points" style="display:${p._curveHidden?.has(changeCount(draft)?'draft':'live')?'none':''}">${points.map((pt,i)=>`<g class="curve-point ${editable?'editable':''}" transform="translate(${x(Number(pt.outdoor))},${y(Number(pt.target))})" ${editable?`data-point-handle="${i}" tabindex="0" role="button" aria-label="Stützpunkt ${i+1} verschieben"`:''}><circle r="12" fill="transparent"/><circle class="point-dot" r="4"/><title>${fmt(pt.outdoor,1)} °C → ${fmt(pt.target,1)} °C</title></g>`).join('')}</g>
  </svg><div class="curve-legend"><button type="button" data-curve-series="live" aria-pressed="${!p._curveHidden?.has('live')}"><i></i>Gespeicherte Basiskurve</button>${changeCount(draft)?`<button type="button" data-curve-series="draft" aria-pressed="${!p._curveHidden?.has('draft')}"><i class="draft-key"></i>Entwurf</button>`:''}${estimates.map((e,i)=>`<span class="curve-estimate-legend"><i class="estimate-key estimate-key-${i%4}"></i>${estimateLabel(e,p.language==='en')}</span>`).join('')}<span>Außentemperatur →</span></div><div class="curve-hover-tooltip chart-tooltip" hidden></div>`;
}
function actions(draft){const n=changeCount(draft);return `<span class="small muted">${n?`${n} Änderung${n===1?'':'en'} im Entwurf`:'Keine ungespeicherten Änderungen'}</span><div class="buttons"><button class="secondary" data-parameter-action="discard" ${n?'':'disabled'}>Verwerfen</button><button class="primary" data-parameter-action="review" ${n?'':'disabled'}>Änderung prüfen →</button></div>`;}
function pointEditor(p,snap,draft){
  if(!snap.point_limits)return '';
  const values=valuesFor(p,snap,draft),points=pointsOf(values),custom=values.points!==undefined,limits=snap.point_limits,disabled=!canEdit(p,snap),error=pointError(points,limits);
  return `<div class="curve-points" id="curve-points"><div class="curve-point-heading"><strong>Stützpunkte</strong><span class="small muted">${points.length} / ${limits.max_points}</span></div>
    ${custom?`<div class="curve-point-list"><div class="point-row point-labels"><span>#</span><span>Außen · °C</span><span>Soll · °C</span><span></span></div>${points.map((pt,i)=>`<div class="point-row" data-point-row="${i}"><span class="point-index">${i+1}</span>${['outdoor','target'].map(k=>`<input type="number" required data-point-index="${i}" data-point-field="${k}" aria-label="${k==='outdoor'?'Außen':'Soll'} · Stützpunkt ${i+1}" min="${limits[k+'_min']}" max="${limits[k+'_max']}" step="0.1" value="${esc(pt[k])}" ${disabled?'disabled':''}>`).join('')}<button class="point-remove" data-parameter-action="remove-point" data-point-index="${i}" aria-label="Stützpunkt ${i+1} entfernen" ${disabled||points.length<=2?'disabled':''}>×</button></div>`).join('')}</div>`:''}
    <p class="curve-point-error small" role="alert" id="curve-point-error">${esc(error)}</p>
    <button class="secondary" data-parameter-action="add-point" ${disabled||!insertPoint(points)?'disabled':''}>+ Stützpunkt hinzufügen</button>
    <p class="curve-note">2–10 Punkte. Zwischenwerte werden linear berechnet; außerhalb gelten die Endwerte. Punkte ziehen oder mit den Pfeiltasten verschieben.</p></div>`;
}
function workshop(p){
  const {type,entries,entry,snap,draft}=current(p);
  if(!entry)return p.empty(`${CURVES[type]} einrichten`,'Für diese Kurve ist noch kein Integrationseintrag vorhanden.');
  if(!snap)return '<div class="card empty">Kurvendaten werden von dieser Backend-Version noch nicht bereitgestellt. Integration aktualisieren und neu laden.</div>';
  const section=p._curveSection||'basis',values=valuesFor(p,snap,draft),outside=p.raw(snap.outdoor_entity);
  const controls=snap.controls.filter(c=>c.section===section&&!(values.points!==undefined&&ENDPOINT_KEYS.includes(c.key)));
  const activeValue=valuesFor(p,snap,null).heatcurve_active,active=activeValue==='on';
  return `${entries.length>1?`<label class="field curve-entry">Kurveneintrag<select data-curve-entry>${entries.map(e=>`<option value="${esc(e.id)}" ${e.id===entry.id?'selected':''}>${esc(e.title)}</option>`).join('')}</select></label>`:''}
    <div class="curve-workshop"><section class="card curve-visual"><div class="card-header"><div><h2>${CURVES[type]} · Basiskurve</h2><p>${esc(entry.title)}</p></div>${p.historyValue(snap.controls.find(c=>c.key==='heatcurve_active')?.id,p.badge(active?'Regelung aktiv':activeValue==='off'?'Regelung aus':'Status unbekannt',active?'green':''))}</div>
      <div id="curve-graph">${graph(p,snap,draft)}</div>
      <div class="curve-metrics"><div><span>Außen · zugeordnete Quelle</span><strong>${p.val(snap.outdoor_entity)}</strong></div><div><span id="curve-target-label">${baseLabel(p,type,!!draft)}</span><strong id="curve-target">${p.historyValue([snap.outdoor_entity,...snap.controls.filter(c=>c.section==="basis").map(c=>c.id)],`${fmt(curveValue(values,outside),1)} <small>°C</small>`)}</strong></div></div>
      <div id="curve-estimates">${estimateMetrics(p,type,values,outside)}</div>
      <p class="curve-note">Die Vorschau zeigt die Basiskurve. PV-Offset, externe Anhebung, Sollwertglättung und Rundung können den ausgegebenen Sollwert verändern.</p>
      ${type==='cooling_curve'?'<p class="curve-note">Auch die Kühlkurve folgt den konfigurierten Stützpunkten. Die Vorschau kehrt deren Richtung nicht automatisch um.</p>':''}
      <small class="muted">Quelle außen: ${esc(snap.outdoor_entity||'Nicht zugeordnet')}</small></section>
    <section class="card curve-editor"><div class="curve-subtabs" role="tablist" aria-label="Kurveneinstellungen">${Object.entries(TABS).map(([key,label])=>`<button role="tab" aria-selected="${section===key}" class="${section===key?'selected':''}" data-curve-section="${key}">${label}</button>`).join('')}</div>
      <div class="curve-fields">${controls.map(c=>{
        const state=p.states[c.id],a=state?.attributes||{},v=draft?.values[c.id]??draft?.base[c.id]??state?.state;
        const disabled=!p.unlocked||!state||['unknown','unavailable'].includes(state.state)||p.hass?.connected===false;
        const common=`id="curve-field-${esc(c.id)}" data-curve-field="${esc(c.id)}" ${disabled?'disabled':''}`;
        const control=c.id.startsWith('number.')?`<input type="number" required ${common} min="${esc(a.min)}" max="${esc(a.max)}" step="${esc(a.step||1)}" value="${numeric(v)===null?'':esc(v)}">`:`<select ${common}>${!state||["unknown","unavailable"].includes(state.state)?'<option value="" selected>Nicht verfügbar</option>':''}${(c.id.startsWith('switch.')?['off','on']:a.options||[]).map(option=>`<option value="${esc(option)}" ${option===v?'selected':''}>${c.id.startsWith('switch.')?(option==='on'?'Aktiv':'Aus'):esc(option)}</option>`).join('')}</select>`;
        return `<div class="field"><label for="curve-field-${esc(c.id)}">${esc(c.label)}</label>${control}<small>${p.historyValue(c.id,p.language==='en'?'History':'Verlauf')}</small>${section==='fine'?`<small>${c.key==='inertia_hours'?'0 = aus. Glättet den Sollwert zeitlich.':'0 = keine Mindeständerung. Kleine Sollwertänderungen werden zurückgehalten.'}</small>`:''}</div>`;
      }).join('')||'<p class="muted">Für diesen Bereich sind keine verfügbaren Steuerentitäten zugeordnet.</p>'}</div>
      ${section==='basis'?pointEditor(p,snap,draft):''}
      ${section==='pv'?'<p class="curve-note">Offsets und Freigaben gehören nur zu dieser Kurve. Haltezeiten können die Wirkung über den Auslöser hinaus verlängern.</p>':''}
      ${!p.unlocked?'<p class="curve-note">Zum Bearbeiten oben „Bearbeitung freigeben“ wählen.</p>':''}
      ${draft&&draft.revision!==snap.revision?'<div class="notice">Konfiguration inzwischen geändert. Bitte Entwurf verwerfen und neu prüfen.</div>':''}
      <div class="curve-actions" id="curve-actions">${actions(draft)}</div></section></div>`;
}
function audit(p){return `<details class="card parameter-audit" data-detail-id="audit"><summary>Änderungsprotokoll <span class="muted">${p.data.audit.length} Einträge</span></summary><p class="small muted">„Gesendet“ bestätigt einen Dienstaufruf; „Konfiguriert“ bestätigt die gespeicherte Kurve. Beides ersetzt keine Geräterückmeldung.</p><button class="secondary" data-export="audit">CSV ↓</button><div class="table-wrap"><table><thead><tr><th>Zeit</th><th>Parameter</th><th>Alt → Neu</th><th>Ergebnis</th></tr></thead><tbody>${p.data.audit.slice(0,100).map(a=>`<tr><td>${p.date(a.at,{hour:'2-digit',minute:'2-digit'})}</td><td>${esc(p.name(a.entity_id))}</td><td>${esc(a.before)} → ${esc(a.requested)}</td><td>${esc({sent:'Gesendet',configured:'Konfiguriert',failed:'Fehlgeschlagen'}[a.result]||a.result)}${a.error?`<small>${esc(a.error)}</small>`:''}</td></tr>`).join('')||'<tr><td colspan="4">Noch keine Änderungen über diese Oberfläche.</td></tr>'}</tbody></table></div></details>`;}
export function renderParameters(p,section=false){
  const system=section===true,machine=section==='main',en=p.language==='en',special=system||machine;
  const tab=system?'devices':machine?'main':p._parameterTab&&!['devices','all','main'].includes(p._parameterTab)?p._parameterTab:'heating_curve';if(!special)p._parameterTab=tab;
  const access=system?`<div class="buttons"><button class="secondary" data-action="system-unlock">${en?'Unlock with P183':'Mit P183 entsperren'}</button>${p.units.some(u=>p.systemUnlocked(u.id))?`<button class="secondary" data-action="system-lock">${en?'Lock now':'Jetzt sperren'}</button>`:''}</div>`:machine?'':`<button class="${p.unlocked?'primary':'secondary'}" data-action="unlock">${p.unlocked?'Bearbeitung freigegeben':'Bearbeitung freigeben'}</button>`;
  return p.heading(system?'Systemparameter':machine?'Maschineninfo':'Parameter & Kurven.',special?(en?'Device values and documented explanations.':'Gerätewerte und dokumentierte Erklärungen.'):'Vier Kurven, klare Stützpunkte und Gerätewerte mit dokumentierten Defaults.',access)+
    (system?`<div class="system-access-status">${p.units.map(u=>`<span>${esc(u.title)} · ${p.systemUnlocked(u.id)?(en?'Unlocked':'Freigegeben'):(en?'Locked':'Gesperrt')}</span>`).join('')}<small>${en?'Unlock applies per heat pump for 10 minutes. Reading remains available.':'Die Freigabe gilt je Wärmepumpe für 10 Minuten. Lesen ist jederzeit möglich.'}</small></div>`:'')+
    (special?'':`<div class="parameter-tabs" role="tablist" aria-label="Parameterbereich">${Object.entries({...CURVES,...sections}).filter(([key])=>!['devices','all','main'].includes(key)).map(([key,label])=>`<button role="tab" aria-selected="${tab===key}" data-parameter-tab="${key}" class="${tab===key?'selected':''}">${label}</button>`).join('')}</div>`)+
    (sections[tab]?`<section class="card"><div class="card-header"><div><h2>${sections[tab]}</h2><p>Default: „Real Default“, falls hinterlegt, sonst Handbuchwert. Aktuelle Werte stammen aus Home Assistant.</p></div></div><div class="filters"><input type="search" class="search" data-control="search" aria-label="Parameter suchen" placeholder="Code, Adresse oder Beschreibung suchen …" value="${esc(p.query)}"><label class="check"><input type="checkbox" data-control="differences" ${p.differences?'checked':''}>Nur Unterschiede</label><span id="parameter-count" class="small muted"></span></div><div id="parameter-table" data-preserve-children></div></section>`:workshop(p))+(machine?'':audit(p));
}
function refreshDraft(p,snap,draft){
  p.shadowRoot.querySelector('#curve-graph').innerHTML=graph(p,snap,draft);
  p.shadowRoot.querySelector('#curve-target-label').textContent=baseLabel(p,current(p).type,true);
  translateTree(p.shadowRoot.querySelector('.curve-metrics'),p.language);
  p.shadowRoot.querySelector('#curve-target').innerHTML=p.historyValue([snap.outdoor_entity,...snap.controls.filter(c=>c.section==="basis").map(c=>c.id)],`${fmt(curveValue(valuesFor(p,snap,draft),p.raw(snap.outdoor_entity)),1)} <small>°C</small>`);
  p.shadowRoot.querySelector('#curve-estimates').innerHTML=estimateMetrics(p,current(p).type,valuesFor(p,snap,draft),p.raw(snap.outdoor_entity));
  p.shadowRoot.querySelector('#curve-actions').innerHTML=actions(draft);
  const error=p.shadowRoot.querySelector('#curve-point-error');if(error)error.textContent=pointError(pointsOf(valuesFor(p,snap,draft)));
  const add=p.shadowRoot.querySelector('[data-parameter-action="add-point"]');if(add)add.disabled=!canEdit(p,snap)||!insertPoint(pointsOf(valuesFor(p,snap,draft)));
  translateTree(p.shadowRoot.querySelector('#curve-graph'),p.language);translateTree(p.shadowRoot.querySelector('#curve-actions'),p.language);
  translateTree(p.shadowRoot.querySelector('#curve-point-error'),p.language);
}
export function curveInput(p,el){
  const {snap}=current(p);if(!snap||!canEdit(p,snap))return;
  let draft;
  if(el.dataset.pointField){
    const points=structuredClone(pointsOf(valuesFor(p,snap,current(p).draft))),index=Number(el.dataset.pointIndex),key=el.dataset.pointField;
    if(!points[index]||!['outdoor','target'].includes(key))return;
    points[index][key]=el.value===''?'':Number(el.value);draft=editPoints(p,snap,points);
  }else{
    if(!snap.controls.some(c=>c.id===el.dataset.curveField))return;
    draft=ensureDraft(p,snap);draft.values[el.dataset.curveField]=el.value;
  }
  refreshDraft(p,snap,draft);
}
export function hasCurveDraft(p){return [...(p._curveDrafts?.values()||[])].some(d=>changeCount(d));}
function movedPoint(points,index,outdoor,target,limits){
  const next=structuredClone(points),round=v=>Math.round(v*10)/10;
  const lo=index?Number(points[index-1].outdoor)+0.1:limits.outdoor_min,hi=index<points.length-1?Number(points[index+1].outdoor)-0.1:limits.outdoor_max;
  next[index]={outdoor:round(Math.min(hi,Math.max(lo,outdoor))),target:round(Math.min(limits.target_max,Math.max(limits.target_min,target)))};
  return next;
}
export function curveKey(p,event){
  const handle=event.target.closest('[data-point-handle]');if(!handle||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;
  const {snap,draft}=current(p);if(!canEdit(p,snap))return;event.preventDefault();
  const points=pointsOf(valuesFor(p,snap,draft)),i=Number(handle.dataset.pointHandle),step=event.shiftKey?1:0.1;
  if(pointError(points))return;
  editPoints(p,snap,movedPoint(points,i,Number(points[i].outdoor)+(event.key==='ArrowRight'?step:event.key==='ArrowLeft'?-step:0),Number(points[i].target)+(event.key==='ArrowUp'?step:event.key==='ArrowDown'?-step:0),snap.point_limits));
  p.render();p.shadowRoot.querySelector(`[data-point-handle="${i}"]`)?.focus({preventScroll:true});
}
export function curvePointer(p,event){
  const handle=event.target.closest('[data-point-handle]');if(!handle||event.button!==0)return;
  const {snap,draft}=current(p);if(!canEdit(p,snap))return;
  const original=structuredClone(pointsOf(valuesFor(p,snap,draft)));if(pointError(original))return;
  event.preventDefault();const i=Number(handle.dataset.pointHandle),svg=handle.closest('svg'),matrix=svg.getScreenCTM()?.inverse();if(!matrix)return;
  const start=new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix),range={...svg.dataset},controller=new AbortController();
  const beforeDraft=draft?structuredClone(draft):null;
  p._curveDrag?.abort();p._curveDrag=controller;
  const end=cancel=>{
    controller.abort();p._curveDrag=null;
    if(cancel){if(beforeDraft)p._curveDrafts.set(snap.entry_id,beforeDraft);else p._curveDrafts?.delete(snap.entry_id);}
    p.render();p.shadowRoot.querySelector(`[data-point-handle="${i}"]`)?.focus({preventScroll:true});
  };
  window.addEventListener('pointermove',e=>{
    if(e.pointerId!==event.pointerId)return;
    if(!canEdit(p,snap)){end(true);return;}
    const loc=new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix);
    const points=movedPoint(original,i,Number(original[i].outdoor)+(loc.x-start.x)*(range.xmax-range.xmin)/558,Number(original[i].target)-(loc.y-start.y)*(range.ymax-range.ymin)/190,snap.point_limits);
    const d=editPoints(p,snap,points);refreshDraft(p,snap,d);
    const container=p.shadowRoot.querySelector('#curve-points');if(container){container.outerHTML=pointEditor(p,snap,d);translateTree(p.shadowRoot.querySelector('#curve-points'),p.language);}
  },{signal:controller.signal});
  window.addEventListener('pointerup',e=>{if(e.pointerId===event.pointerId)end(false);},{signal:controller.signal});
  window.addEventListener('pointercancel',()=>end(true),{signal:controller.signal});
  window.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();end(true);}},{signal:controller.signal});
}
export async function parameterClick(p,button){
  if(button.dataset.parameterTab){if(p._parameterTab!==button.dataset.parameterTab){p.query="";p.differences=false;}p._parameterTab=button.dataset.parameterTab;p._curveEntry=null;p.render();return true;}
  if(button.dataset.curveSection){p._curveSection=button.dataset.curveSection;p.render();return true;}
  if(!button.dataset.parameterAction)return false;
  const {entry,snap,draft}=current(p);
  if(button.dataset.parameterAction==='discard'){p._curveDrafts?.delete(entry.id);await p.load();p.render();return true;}
  if(!canEdit(p,snap))return true;
  if(['add-point','remove-point'].includes(button.dataset.parameterAction)){
    const points=pointsOf(valuesFor(p,snap,draft));let next;
    if(button.dataset.parameterAction==='add-point')next=insertPoint(points);
    else if(points.length>2)next=points.filter((_,i)=>i!==Number(button.dataset.pointIndex));
    if(next){editPoints(p,snap,next);p.shadowRoot.activeElement?.blur();p.render();}return true;
  }
  if(!draft)return true;
  if([...p.shadowRoot.querySelectorAll('[data-curve-field],[data-point-field]')].some(el=>!el.reportValidity()))return true;
  const problem=pointError(pointsOf(valuesFor(p,snap,draft)));if(problem){p.toast(problem,true);return true;}
  const changes=changeList(draft);if(!changeCount(draft))return true;
  const pointChanges=pointsChanged(draft)?{points:structuredClone(draft.points)}:{};
  const pointSummary=points=>points.map(pt=>`${fmt(pt.outdoor,1)} °C → ${fmt(pt.target,1)} °C`).join('<br>');
  const pointReview=pointChanges.points?`<div class="table-wrap point-review"><table><thead><tr><th>Stützpunkte</th><th>Aktuell</th><th>Entwurf</th></tr></thead><tbody><tr><td>Außen → Soll</td><td>${pointSummary(draft.basePoints)}</td><td>${pointSummary(draft.points)}</td></tr></tbody></table></div>`:'';
  p.openModal('Kurvenänderung prüfen',esc(entry.title),`<div class="table-wrap"><table><thead><tr><th>Einstellung</th><th>Aktuell</th><th>Entwurf</th></tr></thead><tbody>${changes.map(c=>`<tr><td>${esc(snap.controls.find(f=>f.id===c.entity_id)?.label)}</td><td>${esc(c.expected)}</td><td>${esc(c.value)}</td></tr>`).join('')}</tbody></table></div><p class="small muted">Die Änderungen werden gemeinsam gespeichert. Bei aktiver Kurvenregelung können sie anschließend den Sollwert der Wärmepumpe ändern.</p>`,async()=>{
    await p.ws('curve',{entry_id:entry.id,revision:draft.revision,changes,...pointChanges,confirmed:true});p._curveDrafts.delete(entry.id);
    return 'Kurve gespeichert. Der Integrationseintrag wird neu geladen; ausgegebenen Sollwert anschließend prüfen.';
  });
  if(pointReview){const review=p.shadowRoot.querySelector('dialog .table-wrap');review.insertAdjacentHTML('afterend',pointReview);if(!changes.length)review.remove();translateTree(p.shadowRoot.querySelector('dialog'),p.language);}
  return true;
}

export const renderDevices=renderCatalogTable;

export function curveHover(p,event){
  const svg=event.target.closest?.('.curve-chart');if(!svg||p._curveDrag)return;
  const tip=p.shadowRoot.querySelector('.curve-hover-tooltip');if(!tip)return;
  const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(svg.getScreenCTM().inverse());
  if(point.x<42||point.x>600||point.y<20||point.y>210){delete svg._curvePointer;tip.hidden=true;return;}
  svg._curvePointer={clientX:event.clientX,clientY:event.clientY};
  const outside=Number(svg.dataset.xmin)+(point.x-42)/558*(Number(svg.dataset.xmax)-Number(svg.dataset.xmin));
  const {snap,draft}=current(p),en=p.language==='en';
  const values=[['live',en?'Saved':'Gespeichert',valuesFor(p,snap,null)],...(changeCount(draft)?[['draft',en?'Draft':'Entwurf',valuesFor(p,snap,draft)]]:[])].filter(([key])=>!p._curveHidden?.has(key));
  const estimates=curveEstimates(p,current(p).type).filter(e=>e.available),v=valuesFor(p,snap,draft);
  tip.innerHTML=`<strong>${en?'Outside':'Außen'}: ${fmt(outside,1)} °C</strong>${values.map(([,label,v])=>`<div><span>${label}</span><b>${fmt(curveValue(v,outside),1)} °C</b></div>`).join('')}${estimates.map(e=>`<div><span>${estimateLabel(e,en)}</span><b>${fmt(curveValue(v,outside)+e.offset,1)} °C</b></div>`).join('')}`;tip.hidden=false;
  const rect=svg.parentElement.getBoundingClientRect();tip.style.left=`${Math.max(0,Math.min(event.clientX-rect.left+12,rect.width-tip.offsetWidth))}px`;tip.style.top=`${Math.max(0,event.clientY-rect.top-tip.offsetHeight-8)}px`;
}

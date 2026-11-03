import {electricForm,readElectricForm,configureElectricPicker,refreshElectricLanguage,refreshElectricFlows,stopElectricFlows} from './electric-overview.js?v=1.1.0';
import {renderOperating,chart as operatingChart,operatingIds} from './operating-data.js?v=1.1.0';
import {recordFor,renderDiagnostics, renderFaults, loadFaults, stopDiagnostics, diagnosticAction, showRawHistory} from './data-browser.js?v=1.1.0';
import {patchHTML, patchElement, preserveScroll} from './dom.js?v=1.1.0';
import {esc, numeric, fmt, setLocale, ageLabel, phaseNames, modeNames, reasons} from "./model.js?v=1.1.0";

import "./entity-picker.js?v=1.1.0";
import {icon} from "./visuals.js?v=1.1.0";
import {brandLogo} from "./branding.js?v=1.1.0";
import {renderOverview, loadOverviewHistory, overviewNeedsHistory} from "./overview.js?v=1.1.0";
import {renderParameters, renderDevices, parameterClick, curveInput, hasCurveDraft, curveKey, curvePointer, curveHover} from "./parameters.js?v=1.1.0";
import {tr, translateTree} from './i18n.js?v=1.1.0';
import {plantModel, plantForm, readPlantForm, refreshPlantLanguage} from './plant.js?v=1.1.0';
import {renderService, serviceClick, serviceChange, serviceBanner} from './service.js?v=1.1.0';
import {sourcesForm,readSourcesForm,configureSourcePicker,refreshSourcesLanguage,suggestSources,sourceHistoryIds} from './heat-sources.js?v=1.1.0';
import {schematicView,configureSchematics} from './schematic-editor.js?v=1.1.0';

import {chartClick,chartHover,chartLeave,chartSearch,chartStyles,refreshChartHover} from './chart-ui.js?v=1.1.0';

const NAV = [["overview","◈","Anlage"],["operating","↗","Betriebsdaten"],["parameters","≡","Parameter"],["service","⚒","Service"],["settings","⚙","Einstellungen"]];
const SUBNAV={settings:[['settings','Einrichtung'],['schematic','Schaubild'],['pump','Zusatzpumpe']],service:[['service','Geräteinfo'],['machine','Maschineninfo'],['factory','Werkstestmodus'],['diagnostics','Diagnose'],['faults','Fehlerspeicher'],['system','Systemparameter']]};
const mainView=view=>Object.keys(SUBNAV).find(key=>SUBNAV[key].some(([id])=>id===view))||view;
const canonical=view=>['operation','analysis'].includes(view)?'operating':view;
const validView=view=>NAV.some(([id])=>id===view)||Object.values(SUBNAV).flat().some(([id])=>id===view);

const COLORS = Array.from({length:6},(_,i)=>`var(--plot-${i+1})`);
const MAPPINGS = {
  pump_power_entity:"Stromaufnahme Zusatzpumpe", heat_energy_entity:"Wärmemenge · kumulierter Zähler",
  electric_energy_entity:"Stromverbrauch · kumulierter Zähler", tank_entity:"Warmwasserspeicher",
  buffer_entity:"Heizungspuffer", outdoor_entity:"Außentemperatur",
  radiator_supply_entity:"Heizkörper · Vorlauf", radiator_return_entity:"Heizkörper · Rücklauf",
  dhw_entity:"Warmwasserladung · Status (on/off)",
  buffer_charge_entity:"Pufferladekreis · Pumpenstatus (on/off)",
  radiator_pump_entity:"Heizkörperkreis · Pumpenstatus (on/off)",
  dhw_charge_entity:"WW-Ladekreis · Pumpenstatus (on/off)"
};
const STATUS_MAPPINGS=new Set(['dhw_entity','buffer_charge_entity','radiator_pump_entity','dhw_charge_entity']);
const STATUS_HINTS={dhw_entity:'An = Warmwasserzweig, aus = Pufferzweig. Ein vorhandenes COP-Warmwassersignal wird automatisch verwendet.',buffer_charge_entity:'Separate Umwälzung zwischen Plattenwärmetauscher und Puffer. Nur Anzeige, keine Steuerung.',radiator_pump_entity:'Separate Umwälzung zwischen Puffer und Heizkörpern. Nur Anzeige, keine Steuerung.'};
const CURVES = {heating_curve:"Heizkurve",hot_water_curve:"Warmwasserkurve",floor_heating_curve:"Fußbodenheizung",cooling_curve:"Kühlkurve"};

class R290ControlPanel extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:"open"});
    this.language='de';try{this.language=localStorage.getItem('r290.control.language')==='en'?'en':'de';}catch{}
    // Keep styles mounted across state updates, avoiding unstyled intermediate
    // frames and repeated stylesheet loads when the panel refreshes.
    this.shadowRoot.innerHTML='<link rel="stylesheet" href="/r290_heatpump_static/panel.css?v=1.1.0"><link rel="stylesheet" href="/r290_heatpump_static/overview.css?v=1.1.0"><link rel="stylesheet" href="/r290_heatpump_static/parameters.css?v=1.1.0"><link rel="stylesheet" href="/r290_heatpump_static/theme.css?v=1.1.0"><link rel="stylesheet" href="/r290_heatpump_static/electric-overview.css?v=1.1.0"><div id="panel-root"></div>';
    const chartStyle=document.createElement('style');chartStyle.textContent=chartStyles;this.shadowRoot.append(chartStyle);
    this.shadowRoot.addEventListener('pointermove',e=>{chartHover(this,e);curveHover(this,e);});
    this.shadowRoot.addEventListener('pointerout',e=>{const svg=e.target.closest?.('.curve-chart');if(svg&&!svg.contains(e.relatedTarget)){delete svg._curvePointer;this.shadowRoot.querySelector('.curve-hover-tooltip')?.setAttribute('hidden','');}});this.shadowRoot.addEventListener('pointerout',chartLeave);
    this.view="overview"; this.data=null; this.error=""; this.days=1; this.history=null;
    this.query=""; this.group="all"; this.differences=false; this.unlocked=false;
    this.controllerId=null; this.pending=new Map(); this._renderTimer=null;
    this.shadowRoot.addEventListener("click",event=>this.onClick(event));
    this.shadowRoot.addEventListener("change",event=>this.onChange(event));
    this.shadowRoot.addEventListener("input",event=>this.onInput(event));
    this.shadowRoot.addEventListener("pointerdown",event=>curvePointer(this,event));
    this.shadowRoot.addEventListener("keydown",event=>curveKey(this,event));
    this.shadowRoot.addEventListener("keydown",event=>{const el=event.target.closest('[data-history]');if(el&&el.tagName.toLowerCase()!=='button'&&['Enter',' '].includes(event.key)){event.preventDefault();this.showHistory(el.dataset.history);}});
    this._hashHandler=()=>{const slug=canonical(location.hash.slice(1));if(validView(slug)){if(this.view!==slug)stopDiagnostics(this);this.view=slug;this.render();}};
  }
  set hass(value) {
    this._hass=value;
    if(!this.data && !this._loading && this.isConnected) this.load();
    if(!this._renderTimer) this._renderTimer=setTimeout(()=>{this._renderTimer=null;this.render();},1000);
  }
  get hass(){return this._hass;}
  set narrow(value){this._narrow=value;}
  set panel(value){this._panel=value;}
  connectedCallback(){
    this._hashHandler(); window.addEventListener("hashchange",this._hashHandler);
    this._resizeObserver=new ResizeObserver(entries=>{const width=Math.round(entries[0].contentRect.width);if(width===this._observedWidth)return;this._observedWidth=width;clearTimeout(this._resizeTimer);this._resizeTimer=setTimeout(()=>this.render(),80);});
    this._resizeObserver.observe(this);
    this._interval=setInterval(()=>this.load(true),15000);
    this.render(); if(this._hass && !this.data) this.load();
  }
  disconnectedCallback(){
    this._curveDrag?.abort();this._curveDrag=null;
    stopDiagnostics(this);stopElectricFlows(this);
    clearInterval(this._interval);clearTimeout(this._renderTimer);clearTimeout(this._toastTimer);
    this._resizeObserver?.disconnect();clearTimeout(this._resizeTimer);
    this._renderTimer=null;window.removeEventListener("hashchange",this._hashHandler);
  }
  async ws(type,extra={}) {
    if(!this._hass || this._hass.connected===false) throw new Error("Keine Verbindung zu Home Assistant.");
    return this._hass.callWS({type:`r290_heatpump/${type}`,...extra});
  }
  async load(silent=false){
    if(this._loading || !this._hass || !this.isConnected) return;
    this._loading=true;
    try {this.data=await this.ws("panel");this.error="";this._loadedAt=Date.now();
      if(!this._registerCatalog){try{const response=await fetch('/r290_heatpump_static/register-catalog.json?v=1.1.0');if(!response.ok)throw new Error('Registerkatalog konnte nicht geladen werden.');this._registerCatalog=await response.json();this._catalogError='';}catch(err){this._catalogError=err.message;}}
      if(!this._schematicCatalog){try{const response=await fetch('/r290_heatpump_static/schematic-catalog.json?v=1.1.0');if(!response.ok)throw new Error('Bauteilkatalog nicht verfügbar / Component catalogue unavailable');this._schematicCatalog=await response.json();this._schematicCatalogError='';}catch(err){this._schematicCatalogError=err.message;}}
    }
    catch(err){this.error=err.message||String(err);}
    finally{this._loading=false;this.render();}
  }
  get states(){return this._hass?.states||{};}
  get controller(){const plant=this.data?.settings?.plant;return plant?this.data?.controllers.find(c=>c.entry_id===plant.controller_id):this.data?.controllers.find(c=>c.entry_id===this.controllerId)||this.data?.controllers[0];}
  get allUnits(){return (this.data?.entries||[]).filter(e=>e.type==="heat_pump"&&!e.disabled).sort((a,b)=>(a.slave||0)-(b.slave||0));}
  get units(){const plant=this.data?.settings?.plant;return plant?plant.unit_ids.map(id=>this.allUnits.find(e=>e.id===id)).filter(Boolean):this.allUnits;}
  entity(fragment,entryId){return this.data?.entities.find(e=>(!entryId||e.entry_id===entryId)&&e.id.startsWith("sensor.")&&e.unique_id.includes(fragment)&&!e.disabled)?.id;}
  mapping(key){
    if(this.data?.settings[key]) return this.data.settings[key];
    if(this.controller?.config[key]) return this.controller.config[key];
    if(this.data?.sources?.[key]) return this.data.sources[key];
    const fragments={tank_entity:"water_tank_temperature",buffer_entity:"buffer_tank_temperature_t10",outdoor_entity:"external_ambient_temperature_t1"};
    return fragments[key]?this.entity(fragments[key],this.units[0]?.id):null;
  }
  val(id,digits=1){const s=this.states[id];const value=s && !["unknown","unavailable"].includes(s.state)?`${numeric(s.state)===null?esc(s.state):fmt(s.state,digits)}${s.attributes.unit_of_measurement?` <span class="unit">${esc(s.attributes.unit_of_measurement)}</span>`:""}`:"—";return this.historyValue(id,value);}
  pumpEntity(key){return this.data?.entities.find(e=>e.unique_id===`r290_pump_${this.controller?.entry_id}_${key}`)?.id;}
  historyValue(ids,value){const list=(Array.isArray(ids)?ids:[ids]).filter(Boolean);return list.length?`<button type="button" class="value-history" data-history="${esc(list.join(','))}" title="${this.language==='en'?'Show history':'Verlauf anzeigen'}" aria-label="${esc(`${this.language==='en'?'Show history':'Verlauf anzeigen'}: ${list.map(id=>this.name(id)).join(' / ')}`)}">${value}</button>`:value;}
  readOnlyDialog(title,body){
    this._modal=()=>{};const dialog=document.createElement('dialog');dialog.className='dialog history-dialog';
    dialog.setAttribute('aria-label',title);dialog.innerHTML=`<h2>${esc(title)}</h2>${body}<footer><button class="secondary" data-action="close-dialog">${this.language==='en'?'Close':'Schließen'}</button></footer>`;
    dialog.addEventListener('cancel',event=>{event.preventDefault();this.closeModal();});this.shadowRoot.append(dialog);dialog.showModal();
  }
  showHistory(value){
    const ids=[...new Set(String(value||'').split(',').filter(id=>/^[a-z_]+\.[a-z0-9_]+$/.test(id)))];
    if(!ids.length)return;
    if(this._modal)this.closeModal();
    // Open the root view with its embedded history so X closes the dialog directly.
    if(ids.length===1){this.dispatchEvent(new CustomEvent('hass-more-info',{detail:{entityId:ids[0],view:'info'},bubbles:true,composed:true}));return;}
    this.readOnlyDialog(this.language==='en'?'History of source values':'Verlauf der Ausgangswerte',`<p>${this.language==='en'?'This value is calculated from several sources. Select a source to view its recorded history.':'Dieser Wert wird aus mehreren Quellen berechnet. Wähle eine Quelle für ihren aufgezeichneten Verlauf.'}</p><div class="history-sources">${ids.map(id=>this.historyValue(id,esc(this.name(id)))).join('')}</div>`);
  }
  raw(id){return numeric(this.states[id]?.state);}
  date(value,options={}){const d=new Date(value);return Number.isNaN(d.valueOf())?"—":d.toLocaleString(this.language==='en'?'en-GB':'de-DE',{timeZone:this._hass?.config?.time_zone||"Europe/Berlin",...options});}
  metric(label,value,foot="",glyph=""){return `<div class="metric">${glyph?`<span class="metric-glyph">${icon(glyph)}</span>`:""}<div class="label">${esc(label)}</div><div class="value mono">${value}</div><div class="foot">${foot}</div></div>`;}
  badge(text,tone=""){return `<span class="badge ${tone}"><span class="dot"></span>${esc(text)}</span>`;}
  heading(title,subtitle,actions=""){return `<div class="page-heading"><div><p class="eyebrow">R290 / ${esc(NAV.find(n=>n[0]===mainView(this.view))?.[2]||"")}</p><h1>${title}</h1><p>${subtitle}</p></div><div class="buttons">${actions}</div></div>`;}
  empty(title,text,link=true){return `<div class="card empty"><div class="empty-icon">◎</div><h2>${esc(title)}</h2><div>${text}</div>${link?'<a class="primary" href="/config/integrations/integration/r290_heatpump">Integration einrichten ↗</a>':""}</div>`;}
  render(){
    if(!this.isConnected || this._modal || this._editingSettings || this._curveDrag) return;
    const focus=this.shadowRoot.activeElement;
    if(focus?.matches("input,select,textarea,r290-entity-picker")&&!focus.matches("[data-diagnostic-query],[data-control=search],[data-register-note]")) return;
    setLocale(this.language);this.setAttribute('lang',this.language);
    const sameView=this._renderedView===this.view;
    const restoreScroll=sameView?preserveScroll(this):()=>{};
    const toast=this.shadowRoot.querySelector(".toast");
    const navScroll=this.shadowRoot.querySelector(".app-header nav")?.scrollLeft||0;
    const tabScroll=new Map(['.parameter-tabs','.curve-subtabs'].map(selector=>[selector,this.shadowRoot.querySelector(selector)?.scrollLeft||0]));
    const temperatureFocus=focus?.dataset.temperature;
    const oldScroll=sameView?(this.shadowRoot.querySelector(".table-wrap")?.scrollTop||0):0;
    const openDetails=new Set([...this.shadowRoot.querySelectorAll('details[open][data-detail-id]')].map(el=>el.dataset.detailId));
    const views={overview:()=>this.overview(),pump:()=>this.pump(),operating:()=>renderOperating(this),parameters:()=>this.parameters(),settings:()=>this.settings(),faults:()=>renderFaults(this),diagnostics:()=>renderDiagnostics(this),service:()=>renderService(this),factory:()=>renderService(this,true),system:()=>renderParameters(this,true),machine:()=>renderParameters(this,'main'),schematic:()=>schematicView(this)};
    let body=this.data?views[this.view]():`<div class="empty"><span class="loading-dot"></span><h2>Anlagendaten werden geladen</h2><p>Verbindung zur R290-Integration wird hergestellt.</p><button class="secondary" data-action="refresh">Erneut laden</button></div>`;
    const disconnected=this._hass?.connected===false;
    patchHTML(this.shadowRoot.getElementById("panel-root"),`<div class="shell">
      <header class="app-header"><div class="header-brand"><button class="icon-button menu-ha" data-action="ha-menu" aria-label="Home Assistant Menü öffnen">${icon('menu')}</button></div>
      <nav aria-label="Anlagenbereiche">${NAV.map(([id,_,name])=>`<button class="nav ${mainView(this.view)===id?"active":""}" data-view="${id}" ${mainView(this.view)===id?'aria-current="page"':""}>${name}</button>`).join("")}</nav>
      <div class="header-meta"><div class="language-switch" role="group" aria-label="Sprache"><button data-language="de" aria-pressed="${this.language==='de'}" lang="de">DE</button><button data-language="en" aria-pressed="${this.language==='en'}" lang="en">EN</button></div><span class="connection-indicator ${disconnected?'offline':''}" title="${disconnected?'Verbindung getrennt':'Verbunden mit Home Assistant'}"><span class="dot"></span><span>${disconnected?'Offline':'Lokal verbunden'}</span></span><button class="icon-button" data-action="refresh" aria-label="Daten aktualisieren">${icon('refresh')}</button></div><div class="brand">${brandLogo()}</div></header>
      <main class="content" data-key="view-${this.view}"><div class="site-context"><span>${esc(this.data?.settings.name||"Heizungsanlage")}</span><span>R290 NextGen <span class="muted">/</span> v${esc(this.data?.version||"1.1.0")}</span></div>
      ${this.error?`<div role="alert" class="notice error">${esc(this.error)}</div>`:""}${serviceBanner(this)}
      ${disconnected?'<div data-key="connection-notice" role="alert" class="notice error">Die Verbindung ist getrennt. Angezeigte Werte können veraltet sein. Änderungen sind nicht verfügbar.</div>':""}${SUBNAV[mainView(this.view)]?`<nav class="section-tabs" aria-label="${this.language==='en'?'Subpages':'Unterseiten'}">${SUBNAV[mainView(this.view)].map(([id,label])=>`<button data-view="${id}" class="${this.view===id?'active':''}" ${this.view===id?'aria-current="page"':''}>${label}</button>`).join('')}</nav>`:''}${body}</main></div>`);
    if(toast)this.shadowRoot.append(toast);
    const nav=this.shadowRoot.querySelector(".app-header nav");
    if(nav){nav.scrollLeft=navScroll;const active=nav.querySelector('[aria-current="page"]');if(active){const n=nav.getBoundingClientRect(),a=active.getBoundingClientRect();if(a.right>n.right)nav.scrollLeft+=a.right-n.right+8;else if(a.left<n.left)nav.scrollLeft-=n.left-a.left+8;}}
    for(const [selector,scroll] of tabScroll){const tabs=this.shadowRoot.querySelector(selector);if(!tabs)continue;tabs.scrollLeft=scroll;const selected=tabs.querySelector('[aria-selected="true"]');if(selected){const t=tabs.getBoundingClientRect(),s=selected.getBoundingClientRect();if(s.right>t.right)tabs.scrollLeft+=s.right-t.right;else if(s.left<t.left)tabs.scrollLeft-=t.left-s.left;}}
    if(temperatureFocus)[...this.shadowRoot.querySelectorAll('[data-temperature]')].find(el=>el.dataset.temperature===temperatureFocus)?.focus({preventScroll:true});
    if(["parameters","system","machine"].includes(this.view)) this.renderParameterTable();
    if(this.view==="settings"){
      const items=Object.values(this.states).map(s=>({id:s.entity_id,name:this.name(s.entity_id),unit:s.attributes.unit_of_measurement||""})).sort((a,b)=>a.name.localeCompare(b.name,"de"));
      for(const picker of this.shadowRoot.querySelectorAll("r290-entity-picker")){
        if(configureElectricPicker(this,picker,items)||configureSourcePicker(this,picker,items))continue;
        if(picker.dataset.valveUnit){picker.configure(items.filter(s=>['sensor','binary_sensor','switch','input_boolean'].includes(s.id.split('.')[0])),plantModel(this).valve_entities[picker.dataset.valveUnit],this.language==='en'?'Valve open feedback':'Ventil offen',this.language);continue;}
        const key=picker.dataset.setting,domains=STATUS_MAPPINGS.has(key)?['sensor','binary_sensor','switch','input_boolean']:['sensor'];
        picker.configure(items.filter(s=>domains.includes(s.id.split('.')[0])),this.data.settings[key],MAPPINGS[key],this.language);
      }
    }
    for(const plot of this.shadowRoot.querySelectorAll(".operating-chart")){const width=Math.max(220,Math.round(plot.getBoundingClientRect().width));const template=document.createElement("template");template.innerHTML=operatingChart(this,plot.dataset.operatingChart,width);patchElement(plot,template.content.firstElementChild);}
    const table=this.shadowRoot.querySelector(".table-wrap");if(table)table.scrollTop=oldScroll;
    for(const detail of this.shadowRoot.querySelectorAll('details[data-detail-id]'))detail.open=openDetails.has(detail.dataset.detailId);
    translateTree(this.shadowRoot,this.language);
    configureSchematics(this);refreshElectricFlows(this);
    restoreScroll();this._renderedView=this.view;refreshChartHover(this);
    const curve=this.shadowRoot.querySelector('.curve-chart');if(curve?._curvePointer)curveHover(this,{...curve._curvePointer,target:curve});
    if(this.data&&this.view==="faults"&&!this._faultHistory&&!this._faultLoading&&!this._faultError)loadFaults(this);
    if(this.data&&this.view==="overview"&&overviewNeedsHistory(this))loadOverviewHistory(this);
    if(this.view==="operating"&&!this.history&&!this._historyLoading&&!this._historyError)this.loadHistory();
  }
  overview(){return renderOverview(this);}
  volume(key){const n=this.data?.settings[key];return n?`${fmt(n,0)} Liter Speichervolumen`:"Speichervolumen noch nicht hinterlegt";}
  unitTable(){return `<div style="overflow:auto"><table><thead><tr><th>Gerät</th><th>Verdichter</th><th>Vorlauf / Rücklauf</th><th>Durchfluss</th></tr></thead><tbody>${this.units.map(u=>`<tr><td>WP ${esc(u.slave)}<small>${esc(u.title)}</small></td><td>${this.val(this.entity("compressor_operating_frequency",u.id),0)}</td><td>${this.val(this.entity("water_outlet_temperature_t7",u.id))} / ${this.val(this.entity("return_water_temperature_t6",u.id))}</td><td>${this.val(this.entity("water_flow",u.id))}</td></tr>`).join("")}</tbody></table></div>`;}
  healthRows(){
    return ["heat_energy_entity","electric_energy_entity","pump_power_entity"].map(key=>{
      const id=this.mapping(key),state=this.states[id],label=MAPPINGS[key];
      const at=state?.last_updated, age=at?(Date.now()-new Date(at))/1000:Infinity;
      const valid=state&&!['unavailable','unknown'].includes(state.state);
      return `<div class="status-row"><div class="name">${esc(label)}<small>${id?`${esc(id)}<br>${esc(tr("Letzte Zustandsänderung",this.language))} ${esc(tr(ageLabel(age),this.language))}`:"Noch nicht zugeordnet"}</small></div>${this.badge(!valid?"Fehlt":key==="heat_energy_entity"&&age>900?"Zeitbezug prüfen":"Verfügbar",!valid?"amber":key==="heat_energy_entity"&&age>900?"amber":"green")}</div>`;
    }).join("")+`<p class="small muted">Ein unveränderter Zählerstand beweist keinen Empfangsausfall. WM-Bus-Werte werden ausschließlich für zeitlich gekennzeichnete Auswertungen genutzt.</p>`;
  }
  pump(){
    const c=this.controller;
    const header=this.heading("Umwälzung mit Überblick.","Stellwert, Grenzen und die Begründung jeder Regelentscheidung.",'<a class="secondary" href="/config/integrations/integration/r290_heatpump">Eintrag & Optionen ↗</a>');
    if(!c)return header+this.empty("Zusatzpumpenregelung einrichten","In der R290-Integration einen Eintrag „Auxiliary Pump Controller“ hinzufügen.<br>Messwerte, Stellglied und bestehende Automationen werden dort zugeordnet.");
    const d=c.decision,s=c.config;
    return header+`${this.data.controllers.length>1?`<select class="controller-select" data-control="controller" aria-label="Pumpenregler">${this.data.controllers.map(v=>`<option value="${esc(v.entry_id)}" ${v.entry_id===c.entry_id?'selected':""}>${esc(v.name)}</option>`).join("")}</select>`:""}
      ${c.error?`<div class="notice error">${esc(reasons[c.error]||c.error)}</div>`:""}
      ${c.pending_mode?`<div class="notice">${esc(reasons.waiting_to_resume)}</div>`:""}
      ${c.mode==="observe"&&!c.pending_mode&&numeric(c.actual_speed)>0?'<div class="notice">Beobachten aktiv: Der Pumpenausgang ist eingeschaltet und wird hier derzeit nicht geregelt.</div>':""}
      <div class="grid equal"><section class="card"><div class="card-header"><div><h2>${esc(c.name)}</h2><p>${esc(phaseNames[d?.phase]||"Initialisierung")}</p></div>${this.badge(modeNames[c.mode],c.mode==="observe"?"":"green")}</div>
      <div class="ring-wrap"><div class="ring" style="--percentage:${numeric(c.actual_speed)??0}"><div class="ring-inner"><strong>${this.historyValue(this.pumpEntity('actual_speed')||c.config.speed_entity,`${fmt(c.actual_speed,0)} %`)}</strong><small>Ansteuerung aktuell</small></div></div><div><div class="eyebrow">Berechneter Stellwert</div><div class="suggestion mono">${this.historyValue(this.pumpEntity('suggested_speed'),`${fmt(d?.speed,0)} %`)}</div><div class="small muted">${this.val(this.mapping("pump_power_entity"),0)} Stromaufnahme</div></div></div>
      <div class="reason">${esc(reasons[d?.reason]||d?.reason||"Warte auf Betriebsdaten.")}</div>
      <div class="values-grid"><div><div class="label">Aktive Wärmepumpen</div><div class="v">${this.historyValue(c.config.frequency_entities,esc(d?.active_units??'—'))}</div></div><div><div class="label">Spreizungen</div><div class="v">${this.historyValue([...(c.config.supply_entities||[]),...(c.config.return_entities||[])],d?.deltas?.length?d.deltas.map(v=>fmt(v)).join(" / ")+" K":"—")}</div></div><div><div class="label">Zielspreizung</div><div class="v">${this.historyValue(this.pumpEntity('target_delta'),`${fmt(d?.target_delta)} K`)}</div></div></div></section>
      <section class="card"><div class="card-header"><div><h2>Regelung bedienen</h2><p>Eine freigegebene Regelung wird nach Neustart mit geprüften Eingangssignalen fortgesetzt.</p></div></div>
      <div class="pill-row">${Object.entries(modeNames).map(([key,name])=>`<button class="pill ${c.mode===key?'selected':""}" data-mode="${key}" ${this._hass?.connected===false?'disabled':""}>${name}</button>`).join("")}</div>
      <p class="small muted">Die interne Pumpenfreigabe hat Vorrang. Nur bei offenem Pumpenkreis wirken Anlauf, Abtauung und Mindestdurchfluss.</p>
      <div class="status-row"><span>Inbetriebnahme bestätigt</span>${this.badge(s.commissioned?"Ja":"Ausstehend",s.commissioned?"green":"amber")}</div>
      <div class="status-row"><span>Bestehende Automationen</span><span>${c.conflicts.length?this.badge(`${c.conflicts.length} Konflikt(e)`,"red"):this.badge(s.legacy_automations?.length?"Kein gemeldeter Konflikt":"Keine Automationen zur Konfliktprüfung zugeordnet",s.legacy_automations?.length?"green":"amber")}</span></div>
      <div class="status-row"><span>Letzter Stellbefehl</span><span>${c.last_command===null?"Noch keiner":`${fmt(c.last_command,0)} %`}</span></div>
      <div class="status-row"><span>Zeitpunkt</span><span>${c.last_command_at?this.date(c.last_command_at,{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}):"—"}</span></div>
      <p class="small muted">Beobachten sendet keine Stellbefehle und schaltet die Pumpe nicht aus. Eine bisherige Automation wird hier weder ein- noch ausgeschaltet.</p></section>
      <section class="card"><div class="card-header"><div><h2>Konfigurierte Betriebsgrenzen</h2><p>Diese Werte müssen zur Hydraulik und zur Pumpenansteuerung passen.</p></div></div>
      ${[["Stellbereich",`${fmt(s.min_speed,0)}–${fmt(s.max_speed,0)} %`],["Ersatzwert / Abtauung",`${fmt(s.safe_speed,0)} / ${fmt(s.defrost_speed,0)} %`],["Mindestdurchfluss je aktiver WP",`${fmt(s.min_flow)} L/min`],["Spreizung Heizen / Warmwasser",`${fmt(s.heating_delta)} / ${fmt(s.dhw_delta)} K`],["Schritt / Intervall",`${fmt(s.max_step)} % / ${fmt(s.interval,0)} s`],["Anlauf",`${fmt(s.startup_seconds,0)} s`],["Nachlauf","Folgt der internen Pumpenfreigabe"],["Maximales Alter numerischer Messwerte",`${fmt(s.max_age,0)} s`]].map(([k,v])=>`<div class="status-row"><span>${k}</span><strong>${v}</strong></div>`).join("")}</section>
      <section class="card"><div class="card-header"><div><h2>Entscheidungsprotokoll</h2><p>Vorschläge, Stellbefehle und Fehler getrennt nachvollziehen.</p></div><button class="secondary" data-export="pump">CSV ↓</button></div>${this.timeline(c.records)}</section>
      <section class="card wide"><div class="card-header"><div><h2>Eingangssignale der Regelung</h2><p>Numerische Werte werden auf Einheiten, Plausibilität und Meldealter geprüft.</p></div></div><div class="table-wrap"><table><thead><tr><th>Quelle</th><th>Wert</th><th>Letzte Meldung</th><th>Verwendbar</th></tr></thead><tbody>${(c.inputs||[]).map(input=>`<tr><td>${esc(this.name(input.entity_id))}<small>${esc(input.entity_id)}</small></td><td>${this.historyValue(input.entity_id,`${esc(input.state??"—")} ${esc(input.unit||"")}`)}</td><td>${input.age_checked?esc(ageLabel(input.age_seconds)):"Ereignisbasiertes Statussignal"}</td><td>${this.badge(input.valid?"Ja":"Nein",input.valid?"green":"red")}</td></tr>`).join("")||'<tr><td colspan="4">Warte auf Signaldetails.</td></tr>'}</tbody></table></div></section></div>`;
  }
  timeline(records){return `<div class="timeline">${records?.length?records.slice(0,100).map(r=>`<div class="timeline-row"><time>${this.date(r.at,{hour:"2-digit",minute:"2-digit",second:"2-digit"})}<br>${this.date(r.at,{day:"2-digit",month:"2-digit"})}</time><div><strong>${esc(({decision:"Berechnung",command:"Stellbefehl",fault:"Fehler",mode:"Betriebsart",lifecycle:"System",manual_target:"Fester Stellwert"}[r.kind])||r.kind)}</strong><p>${esc(reasons[r.reason]||modeNames[r.reason]||r.reason)}</p>${r.detail?`<p>${esc(r.detail)}</p>`:""}</div><span>${r.speed===undefined?"":`${fmt(r.speed,0)} %`}</span></div>`).join(""):'<p class="muted small">Noch keine Ereignisse.</p>'}</div>`;}
  historyIds(){
    const plant=plantModel(this);
    const ids=[...Object.keys(MAPPINGS).filter(k=>!STATUS_MAPPINGS.has(k)&&!(k==='tank_entity'&&plant.dhw==='none')&&!(k==='buffer_entity'&&plant.heating==='direct')&&!(k==='pump_power_entity'&&plant.aux_position==='none')).map(k=>this.mapping(k))];
    for(const unit of this.units) for(const fragment of ["compressor_operating_frequency","water_outlet_temperature_t7","return_water_temperature_t6","water_flow"]) ids.push(this.entity(fragment,unit.id));
    ids.push(...sourceHistoryIds(this),...operatingIds(this));
    return [...new Set(ids.filter(Boolean))];
  }
  async loadHistory(){
    if(this._historyLoading||!this.data)return;
    const ids=this.historyIds();
    if(!ids.length){this._historyError="Keine Quellen für die Auswertung zugeordnet.";this.render();return;}
    this._historyLoading=true;this._historyError="";this.render();
    const requestedDays=this.days;
    try{let result;for(let i=0;i<ids.length;i+=24){const part=await this.ws("history",{entity_ids:ids.slice(i,i+24),days:requestedDays});result=result?{...result,series:{...result.series,...part.series}}:part;}if(requestedDays===this.days)this.history=result;}
    catch(err){this._historyError=err.message||String(err);}
    finally{this._historyLoading=false;this.render();if(requestedDays!==this.days)this.loadHistory();}
  }
  historyPeriod(){return `${this.date(this.history.start,{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"})} – ${this.date(this.history.end,{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"})}`;}
  chartName(id){
    for(const [key,name] of Object.entries({tank_entity:"Warmwasser",buffer_entity:"Heizungspuffer",outdoor_entity:"Außen",radiator_supply_entity:"Heizkörper · Vorlauf",radiator_return_entity:"Heizkörper · Rücklauf",pump_power_entity:"Zusatzpumpe"}))if(this.mapping(key)===id)return name;
    const entity=this.data.entities.find(e=>e.id===id),unit=this.units.find(u=>u.id===entity?.entry_id);
    if(unit)for(const [fragment,label] of Object.entries({compressor_operating_frequency:"Verdichter",water_outlet_temperature_t7:"Vorlauf",return_water_temperature_t6:"Rücklauf",water_flow:"Durchfluss",device_input_power:"Leistung"}))if(entity.unique_id.includes(fragment))return `WP ${unit.slave} · ${label}`;
    return this.name(id);
  }
  name(id){return this.states[id]?.attributes?.friendly_name||this.data?.entities.find(e=>e.id===id)?.name||id;}
  pumpEnergy(){const series=this.history?.series[this.mapping("pump_power_entity")],factor=series?.unit==="W"?.001:series?.unit==="kW"?1:null;return `<div class="split"><strong style="font-size:28px">${this.historyValue(this.mapping("pump_power_entity"),`${fmt(series&&factor!==null?series.summary.integral*factor:null,2)} <small class="muted">kWh</small>`)}</strong><span class="small muted">${series?fmt(series.summary.coverage*100,1):"—"} % Zustandsabdeckung</span></div>`;}
  parameters(){return renderParameters(this);}
  renderParameterTable(){renderDevices(this);translateTree(this.shadowRoot.querySelector('#parameter-table'),this.language);}
  settings(){
    const settings=this.data.settings;
    return this.heading("Die Anlage zuordnen.","Anzeigedaten und Speichergrößen. Die Pumpenregelung wird über ihren Integrationseintrag eingerichtet.")+
      `<section class="card"><h2>${this.language==='en'?'Plant schematic editor':'Schaubild-Baukasten'}</h2><p>${this.language==='en'?'Place components, connect their ports and assign live readings. The saved diagram changes the display only.':'Bauteile platzieren, Anschlüsse verbinden und Livewerte zuordnen. Der gespeicherte Plan verändert nur die Anzeige.'}</p><button class="primary" data-view="schematic">${this.language==='en'?'Open editor':'Baukasten öffnen'}</button></section>`+electricForm(this)+plantForm(this)+sourcesForm(this)+`<div class="grid equal"><section class="card wide"><div class="card-header"><div><h2>Anzeige & Messquellen</h2><p>Diese Zuordnungen verändern keine Geräteparameter.</p></div></div><div class="form-grid">
      <label class="field">Anlagenname<input data-setting="name" maxlength="100" value="${esc(settings.name||"Heizungsanlage")}"></label><div></div>
      <label class="field">Warmwasserspeicher · Liter<input type="number" min="0" max="50000" data-setting="tank_liters" value="${settings.tank_liters||0}"><small>0 = nicht hinterlegt</small></label>
      <label class="field">Heizungspuffer · Liter<input type="number" min="0" max="50000" data-setting="buffer_liters" value="${settings.buffer_liters||0}"><small>0 = nicht hinterlegt</small></label>
      ${Object.entries(MAPPINGS).map(([key,title])=>`<label class="field">${title}<r290-entity-picker data-setting="${key}"></r290-entity-picker><small>${STATUS_HINTS[key]||(key.includes("energy")?'Kumulierter Energiezähler, keine momentane Leistung.':'Vorhandene Home-Assistant-Entität auswählen.')}</small></label>`).join("")}</div><div class="settings-actions"><button class="secondary" data-action="discard-settings">Verwerfen</button><button class="primary" data-action="save-settings">Zuordnungen speichern</button></div></section>
      <section class="card"><div class="card-header"><div><h2>Zusatzpumpenregelung</h2><p>Ein eigener Eintrag innerhalb der R290-Integration</p></div></div><p class="small muted">Einrichtung in zwei Schritten: Sensoren und Stellglied zuordnen, danach Betriebsgrenzen und Inbetriebnahme festlegen. Die Reihenfolge der Wärmepumpen muss in allen Sensorlisten übereinstimmen.</p><a class="primary" href="/config/integrations/integration/r290_heatpump">Regler einrichten / Optionen ↗</a></section>
      <section class="card"><div class="card-header"><div><h2>Integration & Daten</h2><p>Gemeinsame Datenbasis für Anzeige und Regelung</p></div></div><div class="status-row"><span>Version</span><strong>${esc(this.data.version)}</strong></div><div class="status-row"><span>Konfigurationseinträge</span><strong>${this.data.entries.length}</strong></div><div class="status-row"><span>Recorder-Verlauf</span>${this.badge(this.data.recorder?'Verfügbar':'Nicht geladen',this.data.recorder?'green':'amber')}</div><p class="small muted">Verläufe verwenden die in Home Assistant vorhandene Aufbewahrungsdauer. InfluxDB wird von dieser Oberfläche nicht direkt abgefragt.</p></section></div>`;
  }
  async onClick(event){
    if(chartClick(this,event))return;
    const series=event.target.closest('[data-curve-series]');if(series){this._curveHidden??=new Set();const key=series.dataset.curveSeries;this._curveHidden.has(key)?this._curveHidden.delete(key):this._curveHidden.add(key);this.render();return;}
    const history=event.target.closest('[data-history]');if(history){this.showHistory(history.dataset.history);return;}
    const rawHistory=event.target.closest('[data-raw-history]');if(rawHistory){showRawHistory(this,rawHistory.dataset.rawHistory,Number(rawHistory.dataset.address));return;}
    const button=event.target.closest("button,a");if(!button||button.disabled)return;
    if(button.dataset.sourceSuggest){suggestSources(this,button.dataset.sourceSuggest);return;}
    if(await serviceClick(this,button))return;
    if(button.dataset.language){
      this.language=button.dataset.language;try{localStorage.setItem('r290.control.language',this.language);}catch{}
      setLocale(this.language);this.setAttribute('lang',this.language);this.render();translateTree(this.shadowRoot,this.language);
      if(this._editingSettings){refreshPlantLanguage(this);refreshSourcesLanguage(this);refreshElectricLanguage(this);}
      for(const b of this.shadowRoot.querySelectorAll('[data-language]'))b.setAttribute('aria-pressed',String(b.dataset.language===this.language));
      for(const picker of this.shadowRoot.querySelectorAll('r290-entity-picker'))picker.setLanguage(this.language);
      return;
    }
    if(button.dataset.diagnosticAction){diagnosticAction(this,button.dataset.diagnosticAction);return;}
    if(button.hasAttribute("data-fault-refresh")){await loadFaults(this);return;}
    if(await parameterClick(this,button))return;
    if(button.dataset.temperature){this._hiddenTemperatures??=new Set();const id=button.dataset.temperature;this._hiddenTemperatures.has(id)?this._hiddenTemperatures.delete(id):this._hiddenTemperatures.add(id);this.render();return;}
    if(button.dataset.view){this.navigate(button.dataset.view);return;}
    if(button.dataset.group){this.group=button.dataset.group;this.render();return;}
    if(button.dataset.curve){this._parameterTab=button.dataset.curve;this.group=button.dataset.curve;this.differences=false;this.query="";this.navigate("parameters");return;}
    if(button.dataset.days){this.days=Number(button.dataset.days);this._chartDayOverrides=Object.fromEntries(["operation-temperature","operation-frequency","analysis-power"].map(k=>[k,this.days]));this._chartSlots={};this.history=null;this._historyError="";this.loadHistory();return;}
    if(button.dataset.edit){this.editParameter(button.dataset.edit);return;}
    if(button.dataset.mode){this.editMode(button.dataset.mode);return;}
    if(button.dataset.export){this.exportCSV(button.dataset.export);return;}
    const action=button.dataset.action;
    if(action==="refresh")await this.load();
    else if(action==="toggle-motion"){this._animationPaused=!this._animationPaused;this.render();}
    else if(action==="overview-history-refresh")await loadOverviewHistory(this);
    else if(action==="ha-menu")this.dispatchEvent(new CustomEvent("hass-toggle-menu",{bubbles:true,composed:true}));
    else if(action==="system-unlock")this.unlockSystem();
    else if(action==="system-lock"){try{await this.ws("system_access",{action:"lock",entry_ids:this.units.map(u=>u.id)});await this.load();}catch(e){this.toast(e.message,true);}}
    else if(action==="unlock"){this.unlocked=!this.unlocked;this.render();}
    else if(action==="history-refresh"){this._historyError="";this._chartSlots={};await this.loadHistory();}
    else if(action==="discard-settings"){this._editingSettings=false;button.blur();this.render();}
    else if(action==="save-settings")await this.saveSettings();
    else if(action==="close-dialog")this.closeModal();
    else if(action==="confirm-dialog")await this.confirmModal();
  }
  onChange(event){const el=event.target;
    if(el.hasAttribute('data-source')||el.hasAttribute('data-electric')){this._editingSettings=true;return;}
    if(serviceChange(this,el))return;
    if(el.hasAttribute('data-plant')||el.hasAttribute('data-plant-unit')||el.hasAttribute('data-valve-unit')){this._editingSettings=true;return;}
    if(el.hasAttribute('data-diagnostic-scope')){stopDiagnostics(this);this._diagnosticScope=el.value;this._diagnosticCursor=0;el.blur();this.render();return;}
    if(el.hasAttribute('data-fault-days')){this._faultDays=Number(el.value);el.blur();loadFaults(this);return;}
if(el.hasAttribute("data-curve-entry")){this._curveEntry=el.value;el.blur();this.render();return;}if(el.dataset.curveField){if(el.tagName==="SELECT")curveInput(this,el);return;}if(el.dataset.setting)this._editingSettings=true;if(el.id==="new-value"){const preview=this.shadowRoot.querySelector("#preview-value");if(preview)preview.textContent=el.value;}if(el.dataset.control==="differences"){this.differences=el.checked;this.renderParameterTable();}if(el.dataset.control==="controller"){this.controllerId=el.value;el.blur();this.render();}}
  onInput(event){
    if(chartSearch(event))return;const el=event.target;
    if(el.dataset.pointField){curveInput(this,el);return;}
    if(el.hasAttribute('data-source')||el.hasAttribute('data-electric')){this._editingSettings=true;return;}
    if(el.hasAttribute('data-plant')||el.hasAttribute('data-valve-unit')){this._editingSettings=true;return;}
    if(el.hasAttribute('data-register-note')){this._registerNotes??={};this._registerNotes[el.dataset.registerNote]=el.value;try{localStorage.setItem('r290.register.notes',JSON.stringify(this._registerNotes));}catch{this.toast(this.language==='en'?'Local storage unavailable. Export notes as JSON.':'Lokaler Speicher nicht verfügbar. Notizen als JSON exportieren.',true);}return;}
    if(el.hasAttribute('data-diagnostic-query')){this._diagnosticQuery=el.value;const position=el.selectionStart;el.blur();this.render();const next=this.shadowRoot.querySelector('[data-diagnostic-query]');next?.focus({preventScroll:true});next?.setSelectionRange(position,position);return;}
if(el.dataset.curveField){curveInput(this,el);return;}if(el.dataset.setting)this._editingSettings=true;if(el.dataset.control==="search"){this.query=el.value;this.renderParameterTable();}if(el.id==="new-value"){const preview=this.shadowRoot.querySelector("#preview-value");if(preview)preview.textContent=el.value;}}
  navigate(view){view=canonical(view);if(!validView(view))return;if(this._schematicDirty&&view!=="schematic"){this.toast(this.language==='en'?'Save or discard the schematic draft first.':'Schaubildentwurf zuerst speichern oder verwerfen.',true);return;}if(view!=="parameters"&&hasCurveDraft(this)){this.toast("Bitte Kurvenentwurf zuerst speichern oder verwerfen.",true);return;}if(this._editingSettings){this.toast("Bitte die geänderten Zuordnungen zuerst speichern oder verwerfen.",true);return;}if(this.view!==view)stopDiagnostics(this);this.view=view;history.replaceState(null,"",`${location.pathname}${location.search}#${view}`);this.shadowRoot.activeElement?.blur();this.render();}
  async saveSettings(){
    const controls=[...this.shadowRoot.querySelectorAll("[data-setting]")];
    if([...controls,...this.shadowRoot.querySelectorAll('r290-entity-picker[data-source],r290-entity-picker[data-electric]')].some(el=>!el.reportValidity()))return;
    const settings=Object.fromEntries(controls.map(el=>[el.dataset.setting,el.type==="number"?Number(el.value):el.value]));
    try{settings.electric=readElectricForm(this);settings.plant=readPlantForm(this);settings.heat_sources=readSourcesForm(this);await this.ws("settings",{settings});this.overviewHistory=null;this._overviewError="";this.history=null;this._historyError="";this._editingSettings=false;this.shadowRoot.activeElement?.blur();await this.load();this.toast("Zuordnungen gespeichert.");}
    catch(err){this.toast(err.message||String(err),true);}
  }
  openModal(title,subtitle,body,submit){
    this._modal=submit;
    const dialog=document.createElement("dialog");dialog.className="dialog";
    dialog.setAttribute("aria-labelledby","dialog-title");
    dialog.innerHTML=`<h2 id="dialog-title">${title}</h2><div class="subtitle">${subtitle}</div>${body}<div class="dialog-error" role="alert"></div><footer><button class="secondary" data-action="close-dialog">Abbrechen</button><button class="primary" data-action="confirm-dialog">Bestätigen</button></footer>`;
    dialog.addEventListener("cancel",e=>{e.preventDefault();this.closeModal();});this.shadowRoot.append(dialog);translateTree(dialog,this.language);dialog.showModal();
  }
  closeModal(){this.shadowRoot.querySelector("dialog")?.remove();this._modal=null;this.render();}
  async confirmModal(){
    const dialog=this.shadowRoot.querySelector("dialog"),button=dialog.querySelector('[data-action="confirm-dialog"]');
    if([...dialog.querySelectorAll("input,select")].some(el=>!el.reportValidity()))return;
    button.disabled=true;
    try{const message=await this._modal(dialog);this.closeModal();await this.load();if(message)this.toast(message);}
    catch(err){dialog.querySelector(".dialog-error").textContent=tr(err.message||String(err),this.language);button.disabled=false;}
  }
  systemUnlocked(entry){return (this.data?.system_access?.[entry]||0)>(Date.now()-(this._loadedAt||Date.now()))/1000;}
  canEditParameter(id){const entity=this.data?.entities.find(e=>e.id===id);return entity&&(recordFor(this,entity)?.section===4?this.systemUnlocked(entity.entry_id):this.unlocked);}
  unlockSystem(){
    const en=this.language==='en';
    this.openModal(en?'Unlock system parameters':'Systemparameter entsperren',en?'Enter the current P183 password. Unlock lasts 10 minutes for this connection.':'Aktuelles Passwort aus P183 eingeben. Die Freigabe gilt 10 Minuten für diese Verbindung.',`<label class="field">${en?'Device':'Gerät'}<select name="system-unit"><option value="all">${en?'All configured heat pumps':'Alle eingerichteten Wärmepumpen'}</option>${this.units.map(u=>`<option value="${esc(u.id)}">${esc(u.title)}</option>`).join('')}</select></label><label class="field">${en?'Password (P183)':'Passwort (P183)'}<input type="password" name="system-password" inputmode="numeric" pattern="[0-9]{1,4}" maxlength="4" required autocomplete="off"></label>`,async dialog=>{
      const field=dialog.querySelector('[name=system-password]'),password=field.value,unit=dialog.querySelector('[name=system-unit]').value;field.value='';
      const result=await this.ws('system_access',{action:'unlock',entry_ids:unit==='all'?this.units.map(u=>u.id):[unit],password});this.data.system_access=result.system_access;this._loadedAt=Date.now();return en?'System parameters unlocked.':'Systemparameter freigegeben.';
    });
  }
  editParameter(id){
    if(!this.canEditParameter(id)||this._hass?.connected===false)return;
    const state=this.states[id];if(!state)return;
    const domain=id.split(".")[0],a=state.attributes,expected=state.state;
    let input=domain==="number"?`<input id="new-value" type="number" required min="${esc(a.min)}" max="${esc(a.max)}" step="${esc(a.step||1)}" value="${esc(expected)}">`:`<select id="new-value">${(domain==="switch"?["off","on"]:a.options||[]).map(v=>`<option ${v===expected?'selected':""} value="${esc(v)}">${esc(v)}</option>`).join("")}</select>`;
    this.openModal("Änderung prüfen",`${esc(this.name(id))}<br>${esc(id)}`,`<div class="change-preview"><div><span class="small muted">Aktuell</span><strong>${esc(expected)}</strong></div><span>→</span><div><span class="small muted">Neuer Wert</span><strong id="preview-value">${esc(expected)}</strong></div></div><label class="field">Neuer Wert ${esc(a.unit_of_measurement||"")}${input}</label><p class="small muted">Der Befehl wird an Home Assistant gesendet. Den bestätigten Gerätewert anschließend nach der nächsten Abfrage prüfen.</p>`,async dialog=>{
      const value=dialog.querySelector("#new-value").value;
      await this.ws("parameter",{entity_id:id,expected,value,confirmed:true});this.pending.set(id,{value,at:Date.now()});return "Befehl gesendet. Geräterückmeldung ausstehend.";
    });
  }
  editMode(mode){
    const c=this.controller;if(!c)return;
    this.openModal("Pumpenbetrieb ändern",`${esc(c.name)} · ${esc(modeNames[c.mode])} → ${esc(modeNames[mode])}`,
      `${mode==="manual"?`<label class="field spacer">Fester Stellwert in %<input id="manual-value" type="number" required min="${c.config.min_speed}" max="${c.config.max_speed}" step="1" value="${c.config.manual_speed}"></label>`:""}<p>${mode==="observe"?'Die Regelung gibt die Steuerung ab. Der letzte Ausgangswert bleibt bestehen. Eine bisherige Automation wird nicht automatisch aktiviert.':'Diese Betriebsart sendet Stellbefehle an die Zusatzpumpe. Die bestätigten Betriebsgrenzen gelten; bekannte konkurrierende Automationen müssen deaktiviert sein.'}</p>`,async dialog=>{
        await this.ws("pump",{entry_id:c.entry_id,mode,confirmed:true,...(mode==="manual"?{manual_speed:Number(dialog.querySelector("#manual-value").value)}:{})});return "Pumpenbetriebsart übernommen.";
      });
  }
  toast(message,error=false){
    this.shadowRoot.querySelector(".toast")?.remove();clearTimeout(this._toastTimer);const el=document.createElement("div");el.className=`toast ${error?'error':""}`;el.setAttribute("role","status");el.textContent=tr(message,this.language);this.shadowRoot.append(el);this._toastTimer=setTimeout(()=>el.remove(),7000);
  }
  exportCSV(kind){
    let rows;
    if(kind==="pump")rows=[['timestamp_utc','kind','mode','reason','speed_pct'],...(this.controller?.records||[]).map(r=>[r.at,r.kind,r.mode,r.reason,r.speed??""])];
    else if(kind==="audit")rows=[['timestamp_utc','entity_id','before','requested','result'],...this.data.audit.map(r=>[r.at,r.entity_id,r.before,r.requested,r.result])];
    else rows=[['entity_id','timestamp_utc','value','unit','note'],...Object.entries(this.history?.series||{}).flatMap(([id,s])=>s.points.map(p=>[id,new Date(p[0]*1000).toISOString(),p[1]??"",s.unit,'chart samples; envelope downsampled']))];
    const cell=value=>'"'+String(value??"").replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"';
    const blob=new Blob(['\uFEFF'+rows.map(r=>r.map(cell).join(';')).join('\r\n')],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`r290-${kind}-${new Date().toISOString().slice(0,10)}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
}
if(!customElements.get("r290-control-panel"))customElements.define("r290-control-panel",R290ControlPanel);

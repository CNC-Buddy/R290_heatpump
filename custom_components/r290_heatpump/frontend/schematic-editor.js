import {esc} from './model.js?v=1.1.0';
import {patchHTML} from './dom.js?v=1.1.0';
import {copy,emptyGraph,createNode,nodePorts,connection,inspect,circuits,colors} from './schematic-model.js?v=1.1.0';
import {preset} from './schematic-presets.js?v=1.1.0';
import {renderGraph,paths,nodeLabel,dimensions} from './schematic-svg.js?v=1.1.0';
import {moveSegment,retainRoutes} from './schematic-routing.js?v=1.1.0';
import {bindingsFor,bindingHelp} from './schematic-bindings.js?v=1.1.0';
import {isTank,zoneHeights,zoneName,attachHeater,moveNode} from './schematic-tanks.js?v=1.1.0';
import {renderChart,chartClick,chartHover,chartLeave,chartStyles,refreshChartHover} from './chart-ui.js?v=1.1.0';
import './entity-picker.js?v=1.1.0';

const texts={same_node:['Zwei verschiedene Bauteile wählen.','Choose two different components.'],occupied:['Anschluss belegt. Für Abzweige ein T-Stück einsetzen.','Port occupied. Insert a T junction for branches.'],incompatible:['Kreis, Vor-/Rücklauf oder Flussrichtung passen nicht zusammen.','Circuit, supply/return or direction do not match.'],port:['Anschluss unbekannt.','Unknown port.'],format:['Ungültiges Dateiformat oder zu große Anlage.','Invalid file format or plant too large.'],component:['Ungültiges Bauteil oder Messquelle.','Invalid component or source.'],pipe:['Ungültige Leitung oder Knickpunkte.','Invalid pipe or waypoints.'],empty:['Bauteile hinzufügen oder eine Vorlage laden.','Add components or load a template.'],open:['Anschlusspaar unvollständig','Incomplete port group'],isolated:['Bauteil nicht verbunden','Component disconnected'],required:['Pflichtanschlüsse fehlen','Required ports missing'],loop:['Geschlossener Rücklauf fehlt','Closed return path missing']};
const styles=`
${chartStyles}
:host{display:block;color:#203640;font:14px system-ui,sans-serif;min-width:0}*{box-sizing:border-box}button,input,select{font:inherit}button{cursor:pointer}button:disabled{opacity:.45;cursor:default}button,select,input{border:1px solid var(--line);border-radius:8px;color:inherit;background:var(--surface-inset);padding:9px 12px}button:hover{background:var(--surface-raised)}button:focus-visible,input:focus-visible,select:focus-visible,[tabindex]:focus-visible{outline:2px solid #a94d30;outline-offset:3px}.primary{background:#b85131;color:white;border-color:#b85131}.primary:hover{background:#9f462a}.danger{color:#a43e33}.toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:12px 0}.toolbar .spacer{flex:1}.hint{font-size:12px;color:#657680;line-height:1.6}.notice{padding:12px 15px;border-radius:9px;background:#edf4ed;margin:8px 0;line-height:1.5}.notice.error{background:#faeae1;color:#94432b}.notice[hidden]{display:none}.layout{display:grid;grid-template-columns:minmax(0,1fr) 270px;gap:18px}.stage-wrap{min-width:0;border:1px solid #ded8cd;border-radius:14px;background:#fffdf9;overflow:hidden}.stage{overflow:auto;max-height:75vh;min-height:390px;overscroll-behavior:contain}.svg-container{min-width:760px}.sg-svg{width:100%;height:auto;display:block;touch-action:pan-x pan-y}.editing .sg-node{touch-action:none;cursor:move}.sg-node-label{font:600 17px system-ui;fill:#233b46}.sg-reading{font:500 16px system-ui;fill:#476d80;cursor:pointer}.sg-reading,.sg-status,.sg-node-label{paint-order:stroke fill;stroke:#fffdf9;stroke-width:5;stroke-linejoin:round}.readonly .sg-value{font-size:23px;font-weight:700;fill:#243f50}.readonly .sg-node-label{font-size:19px;fill:#203e51}.readonly .stage-wrap{border-color:#e5eaf0;background:linear-gradient(145deg,#fff,#fcfdfc)}.readonly .legend{border-color:#e8edf0;color:#4c7185}.live-tools{display:flex;align-items:center;flex-wrap:wrap;gap:7px}.sg-status{font:12px system-ui;fill:#76828a}.sg-pipe,.sg-flow{stroke-linecap:round;stroke-linejoin:round}.sg-hit{cursor:pointer}.sg-segment{touch-action:none}.sg-segment.vertical{cursor:ew-resize}.sg-segment.horizontal{cursor:ns-resize}.sg-tank-zones [data-reading]{cursor:pointer}.zone-field{border-top:1px solid #e5dfd6;padding-top:8px}.sg-heater{cursor:move}.sg-flow{stroke-dasharray:3 18;animation:sg-flow 1.5s linear infinite}.fan-running .sg-fan{transform-origin:60px 60px;animation:sg-spin 4s linear infinite}.sg-svg [data-port]{cursor:crosshair}.legend{display:flex;flex-wrap:wrap;gap:10px;padding:12px;font-size:11px;border-top:1px solid #e5dfd6}.legend i{display:inline-block;width:18px;height:3px;vertical-align:middle;margin-right:4px}.inspector{padding:16px;border:1px solid #e0d9cf;border-radius:12px;background:#fffdfa;min-width:0}.inspector h3{margin:0 0 12px}.field{display:grid;gap:5px;margin:12px 0;font-size:12px;font-weight:600}.field input,.field select{width:100%;min-width:0}.inline{display:flex;gap:8px}.inline>*{min-width:0;flex:1}.port-list{display:grid;gap:4px;margin:10px 0}.port-list button{text-align:left;font-size:12px;padding:8px}.port-list button.active{border-color:#b85131;background:#fbefdc}.checks{margin-top:14px;padding:14px;background:#f6f3ed;border-radius:10px;font-size:12px;line-height:1.7}.checks ul{margin:8px 0;padding-left:19px}.edge-list{max-height:200px;overflow:auto}.edge-list button{display:block;width:100%;font-size:11px;margin:4px 0;text-align:left}.small-button{font-size:12px;padding:6px 9px}.live-actions{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 12px}.live-actions h2{margin:0;font-size:20px}.file{display:none}.coordinate input{max-width:110px}summary{cursor:pointer;font-weight:600}.help{max-width:85ch}.readonly .stage{max-height:none}.readonly .svg-container{min-width:800px}.sg-edge.selected .sg-pipe{filter:drop-shadow(0 0 3px #a68c64)}.port-warning{color:#a45134}
@keyframes sg-flow{to{stroke-dashoffset:-42}}@keyframes sg-spin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.sg-flow,.fan-running .sg-fan{animation:none}}@media(max-width:1050px){.layout{grid-template-columns:1fr}.inspector{order:2}.stage{max-height:65vh}.toolbar{gap:6px}.toolbar button{font-size:12px}.readonly .svg-container{min-width:800px}}`;

class SchematicEditor extends HTMLElement {
 constructor(){
   super();this.attachShadow({mode:'open'});this.shadowRoot.innerHTML=`<style>${styles}</style><link rel="stylesheet" href="/r290_heatpump_static/theme.css?v=1.1.0"><div id="root"></div>`;this.zoom=100;this.message='';this.geometryKey='';
   this.shadowRoot.addEventListener('click',e=>{e.stopPropagation();this.click(e).catch(err=>this.fail(err));});
   this.shadowRoot.addEventListener('change',e=>{e.stopPropagation();this.change(e).catch(err=>this.fail(err));});
   this.shadowRoot.addEventListener('keydown',e=>this.key(e));
   this.shadowRoot.addEventListener('pointermove',e=>chartHover(this.p,e));this.shadowRoot.addEventListener('pointerout',chartLeave);
   this.shadowRoot.addEventListener('pointermove',e=>this.previewMove(e));
   this.shadowRoot.addEventListener('pointerdown',e=>{this.placementTouch=this.pendingNode&&e.pointerType==='touch'?{clientX:e.clientX,clientY:e.clientY}:null;this.dragStart(e);});
   this.addEventListener('pointermove',e=>this.dragMove(e));this.addEventListener('pointerup',e=>this.dragEnd(e));
   this.addEventListener('pointercancel',()=>{this.placementTouch=null;this.cancelDrag();});
 }
 t(de,en){return this.p.language==='en'?en:de;}
 word(code){return texts[code]?.[this.p.language==='en'?1:0]||code;}
 configure(p){
   this.p=p;this.catalog=p._schematicCatalog;this.editor=this.dataset.mode==='editor';
   if(!this.catalog){patchHTML(this.shadowRoot.getElementById('root'),`<p>${esc(p._schematicCatalogError||this.t('Bauteilkatalog wird geladen …','Loading component catalogue …'))}</p>`);return;}
   const stored=p.data.settings.schematic||{},changedLanguage=this.language!==p.language;this.language=p.language;
   if(this.editor){
     let session=p._schematicSession;
     if(!session||!session.dirty&&session.revision!==(stored.revision||0))session=p._schematicSession={graph:copy(stored.draft||stored.published||emptyGraph()),revision:stored.revision||0,dirty:false,undo:[],redo:[],selected:'',port:''};
     const changed=this.session!==session;this.session=session;
     if(changed){this.pendingNode=null;this.canvasBounds=null;this.baseWidth=null;}
     if(changed||changedLanguage||!this.shadowRoot.querySelector('.layout'))this.render();else if(!this.drag)this.updateCanvas();
   }else{this.session={graph:stored.published||emptyGraph(),selected:'',port:''};if(changedLanguage||!this.shadowRoot.querySelector('.readonly'))this.render();else this.updateCanvas();}
 }
 get graph(){return this.session.graph;}
 checkpoint(){this.session.undo.push(copy(this.graph));if(this.session.undo.length>30)this.session.undo.shift();this.session.redo=[];}
 changed(){this.session.dirty=true;this.p._schematicDirty=true;this.geometryKey='';this.render();}
 mutate(fn){this.checkpoint();retainRoutes(this.graph,this.geometry);fn();this.changed();}
 fail(err){this.message=this.word(err.message||String(err));this.bad=true;this.render();}
 coords(event){const svg=this.shadowRoot.querySelector('.sg-svg');const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(this.drag?.matrix||svg.getScreenCTM().inverse());return [Math.max(0,Math.min(3600,Math.round(point.x/10)*10)),Math.max(0,Math.min(3600,Math.round(point.y/10)*10))];}
 placementPosition(event){const pos=this.coords(event),spec=this.catalog[this.pendingNode.type];return pos.map((v,i)=>Math.max(0,Math.min(3600,Math.round((v-(i?spec.height:spec.width)/2)/10)*10)));}
 previewMove(e){
   if(!this.pendingNode||!e.target.closest('.sg-svg'))return;
   [this.pendingNode.x,this.pendingNode.y]=this.placementPosition(e);
   this.shadowRoot.querySelector('.sg-placement')?.setAttribute('transform',`translate(${this.pendingNode.x} ${this.pendingNode.y})`);
 }
 cancelPlacement(){this.pendingNode=null;this.message='';this.bad=false;this.render();}
 placeNode(){
   if(!this.pendingNode)return;
   const node=this.pendingNode;this.pendingNode=null;this.message='';this.bad=false;
   this.mutate(()=>{this.graph.nodes.push(node);this.session.selected=node.id;this.session.port='';});
   this.shadowRoot.querySelector(`[data-node="${node.id}"]`)?.focus({preventScroll:true});
 }
 render(){
   if(!this.session||!this.catalog)return;
   const checks=inspect(this.graph,this.catalog),n=this.graph.nodes.find(n=>n.id===this.session.selected),edge=this.graph.edges.find(e=>e.id===this.session.selected);
   if(checks.errors.length){this.message=checks.errors.map(c=>this.word(c)).join(' ');this.bad=true;}
   const legend=Object.entries(circuits).filter(([c])=>c!=='electric'||this.graph.edges.some(e=>this.graph.nodes.find(n=>n.id===e.from.node)?.circuit==='electric')).map(([c,l])=>`<span>${l[this.p.language==='en'?1:0]} ${Object.entries(colors[c]).map(([leg,color])=>`<i style="background:${color}"></i>${leg==='power'?'':leg==='supply'?this.t('VL','Supply'):this.t('RL','Return')}`).join(' / ')}</span>`).join('');
   const stage=`<div class="stage-wrap"><div class="stage"><div class="svg-container" style="width:${this.zoom}%;min-width:${Math.round((this.editor?760:1100)*this.zoom/100)}px"></div></div><div class="legend">${legend}</div></div>`;
   if(!this.editor){patchHTML(this.shadowRoot.getElementById('root'),`<div class="readonly"><div class="live-actions"><h2>${this.t('Anlagenschaubild','Plant schematic')}</h2><button data-action="edit">${this.t('Schaubild bearbeiten','Edit schematic')}</button></div><div class="live-tools"><label class="hint">Zoom <select id="zoom">${[50,75,100,125,150,200].map(z=>`<option value="${z}" ${this.zoom===z?'selected':''}>${z} %</option>`).join('')}</select></label><button data-action="motion" class="small-button">${this.p._animationPaused?this.t('Animation starten','Resume animation'):this.t('Animation pausieren','Pause animation')}</button></div>${stage}<p class="hint">${this.t('Durchfluss nur bei aktuellen Rückmeldungen animiert. Unbekannte Werte bleiben leer.','Flow is animated only with current feedback. Unknown values remain empty.')}</p><div class="tank-charts" data-preserve-children></div></div>`);this.updateCanvas();return;}
   const available=Object.entries(this.catalog).filter(([key])=>!['pv','battery','house','grid'].includes(key));
   patchHTML(this.shadowRoot.getElementById('root'),`<div class="editing"><p class="hint help">${this.t('Bauteile hinzufügen und verschieben. Zum Verbinden nacheinander zwei Anschlüsse anklicken. Leitung anklicken und die quadratischen Griffe ziehen. Kreuzende Linien sind keine Verbindung; Abzweige brauchen ein T-Stück. Der Baukasten beschreibt nur die Anzeige.','Add and move components. Click two ports to connect them. Select a pipe and drag its square handles. Crossing lines are not a connection; branches need a T junction. The editor configures the display only.')}</p>
   <div class="toolbar"><select id="preset" aria-label="${this.t('Vorlage','Template')}"><option value="full">${this.t('Kaskade + getrennte Wärmequelle','Cascade + isolated heat source')}</option><option value="cascade">${this.t('Kaskade + Puffer + Warmwasser','Cascade + buffer + hot water')}</option><option value="direct">${this.t('Einzel-WP · direkter Heizkreis','Single HP · direct heating')}</option><option value="empty">${this.t('Leere Zeichenfläche','Empty canvas')}</option></select><button data-action="preset">${this.t('Vorlage laden','Load template')}</button><span class="spacer"></span><button data-action="undo" ${!this.session.undo.length?'disabled':''}>↶ ${this.t('Zurück','Undo')}</button><button data-action="redo" ${!this.session.redo.length?'disabled':''}>↷ ${this.t('Wiederholen','Redo')}</button><button data-action="export">${this.t('Exportieren','Export')}</button><button data-action="import">${this.t('Importieren','Import')}</button><input class="file" type="file" accept="application/json,.json" id="import-file"></div>
   <div class="toolbar"><select id="component" aria-label="${this.t('Bauteil','Component')}">${available.map(([key,s])=>`<option value="${key}" ${this.componentType===key?'selected':''}>${s.label[this.p.language==='en'?1:0]}</option>`).join('')}</select><button data-action="add">+ ${this.t('Bauteil hinzufügen','Add component')}</button>${this.pendingNode?`<button data-action="cancel-placement">${this.t('Platzierung abbrechen','Cancel placement')}</button>`:''}<label>${this.t('Zoom','Zoom')} <select id="zoom">${[50,75,100,125,150,200].map(z=>`<option value="${z}" ${this.zoom===z?'selected':''}>${z} %</option>`).join('')}</select></label><span class="hint">${this.graph.nodes.length} ${this.t('Bauteile','components')} · ${this.graph.edges.length} ${this.t('Leitungen','pipes')}</span></div>
   <div role="status" aria-live="polite" class="notice ${this.bad?'error':''}" ${!this.message?'hidden':''}>${esc(this.message)}</div>
   <div class="layout">${stage}<aside class="inspector">${n?this.nodeForm(n):edge?this.edgeForm(edge):`<h3>${this.t('Bauteil auswählen','Select a component')}</h3><p class="hint">${this.t('Anschlüsse können auch in der Liste ausgewählt werden. Pfeiltasten verschieben das gewählte Bauteil, Entf löscht es.','Ports can also be selected from the list. Arrow keys move the selected component; Delete removes it.')}</p>`}</aside></div>
   <div class="checks"><strong>${checks.errors.length?this.t('Verbindungen prüfen','Check connections'):checks.open.length?this.t('Entwurf noch unvollständig','Draft incomplete'):this.t('Verbindungen vollständig','Connections complete')}</strong>${checks.open.length?`<ul>${checks.open.slice(0,12).map(i=>`<li>${esc(i.node)}: ${esc(this.word(i.code))}${i.ports?` (${i.ports.join(', ')})`:''}</li>`).join('')}</ul>`:''}<p>${this.t('Prüfung von Anschlussarten und geschlossenen Wegen; keine Auslegung oder Freigabe der realen Hydraulik.','Checks port types and closed paths; does not size or approve the physical installation.')}</p><details><summary>${this.t('Alle Leitungen','All pipes')}</summary><div class="edge-list">${this.graph.edges.map(e=>`<button data-edge="${e.id}">${esc(e.from.node)} · ${esc(e.from.port)} → ${esc(e.to.node)} · ${esc(e.to.port)}</button>`).join('')}</div></details></div>
   <div class="toolbar"><span class="hint">${this.session.dirty?this.t('Ungespeicherter Entwurf','Unsaved draft'):this.t('Entwurf gespeichert','Draft saved')}</span><span class="spacer"></span><button data-action="reload">${this.t('Entwurf verwerfen','Discard draft')}</button><button data-action="draft" ${this.saving||checks.errors.length?'disabled':''}>${this.t('Entwurf speichern','Save draft')}</button><button class="primary" data-action="publish" ${this.saving||checks.errors.length||checks.open.length?'disabled':''}>${this.t('Speichern & anzeigen','Save & display')}</button><button data-action="disable" ${this.saving||!this.p.data.settings.schematic?.published?'disabled':''}>${this.t('Bisheriges Schema anzeigen','Show previous schematic')}</button></div></div>`);
   this.updateCanvas();this.configurePickers(n);
 }
 nodeForm(n){
   const s=this.catalog[n.type],label=nodeLabel(n,this.catalog,this.p.language),ports=nodePorts(n,this.catalog),index=this.p.language==='en'?1:0;
   return `<h3>${esc(label)}</h3><label class="field">${this.t('Bezeichnung','Label')}<input data-property="label" value="${esc(n.label)}" maxlength="70" placeholder="${esc(s.label[index])}"></label>
   ${this.tankForm(n)}
   <div class="inline coordinate"><label class="field">X<input type="number" min="0" max="3600" step="10" data-property="x" value="${n.x}"></label><label class="field">Y<input type="number" min="0" max="3600" step="10" data-property="y" value="${n.y}"></label></div>
   ${s.circuits.length>1?`<label class="field">${this.t('Kreis','Circuit')}<select data-property="circuit">${s.circuits.map(c=>`<option value="${c}" ${c===n.circuit?'selected':''}>${circuits[c][index]}</option>`).join('')}</select></label>`:''}${n.circuit!=='electric'&&s.legs.length>1?`<label class="field">${this.t('Leitungsart','Pipe type')}<select data-property="leg">${s.legs.filter(l=>l!=='power').map(l=>`<option value="${l}" ${l===n.leg?'selected':''}>${l==='supply'?this.t('Vorlauf','Supply'):this.t('Rücklauf','Return')}</option>`).join('')}</select></label>`:''}
   <div class="inline"><button class="small-button" data-action="flip">⇆ ${this.t('Spiegeln','Flip')}</button><button class="small-button" data-action="flip-y">⇅ ${this.t('Spiegeln','Flip')}</button></div>
   <div class="port-list">${Object.entries(ports).map(([k,v])=>{const used=this.graph.edges.some(e=>[e.from,e.to].some(ep=>ep.node===n.id&&ep.port===k));return `<button data-port="${n.id}:${k}" class="${this.session.port===`${n.id}:${k}`?'active':''}" style="border-left:4px solid ${colors[v.circuit][v.leg]}">${v.label[index]} · ${used?this.t('belegt','connected'):this.t('frei','free')}</button>`;}).join('')}</div>
   ${bindingsFor(n).length?`<details data-key="sources" open><summary>${this.t('Messwerte zuordnen','Assign readings')}</summary><p class="hint">${bindingHelp(n,index===1)}</p>${bindingsFor(n).map(({key,label})=>`<label class="field">${label[index]}<r290-entity-picker data-binding="${key}"></r290-entity-picker></label>`).join('')}</details>`:''}
   <button class="danger" data-action="delete">${this.t('Bauteil mit Verbindungen entfernen','Remove component and its connections')}</button>`;
 }
 tankForm(n){
   if(n.type==='heater')return `<label class="field">${this.t('Einbau im Speicher','Mount in tank')}<select data-tank><option value="">${this.t('Frei platzieren','Free placement')}</option>${this.graph.nodes.filter(isTank).map(t=>`<option value="${t.id}" ${n.tank===t.id?'selected':''}>${esc(nodeLabel(t,this.catalog,this.p.language))}</option>`).join('')}</select></label><p class="hint">${this.t('Heizstab im Speicher nach oben oder unten ziehen. Beim Verschieben des Speichers bewegt er sich mit. Nur Darstellung, keine Schaltfunktion.','Drag the heater up or down inside the tank. It moves with the tank. Display only; no switching.')}</p>`;
   if(!isTank(n))return '';
   const zones=n.temperature_zones||[],en=this.p.language==='en';
   return `<label class="field">${this.t('Temperaturfühler','Temperature sensors')}<select data-zone-count>${[0,1,2,3,4].map(c=>`<option value="${c}" ${zones.length===c?'selected':''}>${c||this.t('Einzelwert (bisherige Anzeige)','Single reading (previous view)')}</option>`).join('')}</select></label>${zones.map((z,i)=>`<div class="zone-field"><label class="field">${zoneName(i,zones.length,en)}<r290-entity-picker data-zone-entity="${i}"></r290-entity-picker></label><label class="field">${this.t('Fühlerhöhe · % von oben','Sensor height · % from top')}<input data-zone-height="${i}" type="number" min="${i?zones[i-1].height+8:5}" max="${i+1<zones.length?zones[i+1].height-8:95}" step="1" value="${z.height}"></label></div>`).join('')}<p class="hint">${this.t('Farben veranschaulichen die Messpunkte, keine berechnete Speicherladung. Fehlende oder veraltete Werte erscheinen grau.','Colours illustrate measurement points, not calculated storage charge. Missing or stale readings are grey.')}</p>`;
 }
 edgeForm(e){return `<h3>${this.t('Leitung','Pipe')}</h3><p class="hint">${esc(e.from.node)} · ${esc(e.from.port)} → ${esc(e.to.node)} · ${esc(e.to.port)}</p><p class="hint">${this.t('Die quadratischen Griffe verschieben den jeweiligen Leitungsabschnitt. Auch mit Pfeiltasten bedienbar. Die Anschlüsse bleiben verbunden.','Drag a square handle to move that pipe section, or use the arrow keys. Endpoints stay connected.')}</p><button data-action="auto-route">${this.t('Automatisch neu führen','Reroute automatically')}</button><p class="hint">${e.points?.length?this.t('Manuell positioniert · bleibt beim Verschieben von Bauteilen erhalten.','Manually positioned · retained when moving components.'):this.t('Automatische Leitungsführung','Automatic routing')}</p><button class="danger" data-action="delete">${this.t('Leitung entfernen','Remove pipe')}</button>`;}
 configurePickers(n){
   if(!n)return;const items=Object.values(this.p.states).filter(s=>/^(sensor|binary_sensor|switch|input_boolean|number|input_number|select|input_select|fan|climate)\./.test(s.entity_id)).map(s=>({id:s.entity_id,name:s.attributes?.friendly_name||s.entity_id,unit:s.attributes?.unit_of_measurement||''}));
   for(const picker of this.shadowRoot.querySelectorAll('[data-zone-entity]')){const i=Number(picker.dataset.zoneEntity);picker.configure(items.filter(s=>s.id.startsWith('sensor.')&&['°C','°F','K'].includes(s.unit)),n.temperature_zones[i].entity,zoneName(i,n.temperature_zones.length,this.p.language==='en'),this.p.language);}
   for(const picker of this.shadowRoot.querySelectorAll('[data-binding]')){const field=bindingsFor(n).find(b=>b.key===picker.dataset.binding),current=n.bindings?.[field.key]||'';picker.configure(items.filter(s=>!field.units||field.units.includes(s.unit)||s.id===current),current,field.label[this.p.language==='en'?1:0],this.p.language);}
 }
 updateCanvas(){
   const canvas=this.shadowRoot.querySelector('.svg-container');if(!canvas)return;
   const checked=inspect(this.graph,this.catalog);if(checked.errors.length)return;
   const key=JSON.stringify(this.graph.nodes.map(({bindings,...n})=>n))+JSON.stringify(this.graph.edges);
   if(key!==this.geometryKey){this.geometry=paths(this.graph,this.catalog);this.geometryKey=key;}
   let bounds=dimensions(this.graph,this.catalog);
   if(this.editor){
     // Grow the editing area without shrinking or rescaling existing objects.
     if(this.drag&&this.canvasBounds)bounds=this.canvasBounds;
     this.baseWidth??=bounds.width;
     this.canvasBounds={width:Math.max(bounds.width,this.canvasBounds?.width||0),height:Math.max(bounds.height,this.canvasBounds?.height||0)};
     bounds=this.canvasBounds;
     canvas.style.width=`${this.zoom*bounds.width/this.baseWidth}%`;
     canvas.style.minWidth=`${760*this.zoom/100*bounds.width/this.baseWidth}px`;
   }
   patchHTML(canvas,renderGraph(this.graph,this.catalog,this.p,{editor:this.editor,selected:this.session.selected,selectedPort:this.session.port,geometry:this.geometry,bounds,preview:this.pendingNode}));
   const svg=canvas.querySelector('.sg-svg');svg.style.cursor=this.pendingNode?'crosshair':'';if(this.editor)svg.setAttribute('tabindex','0');
   const charts=this.shadowRoot.querySelector('.tank-charts');if(charts)patchHTML(charts,this.graph.nodes.filter(n=>isTank(n)&&n.temperature_zones?.some(z=>z.entity)).map(n=>`<section class="tank-history"><h3>${esc(nodeLabel(n,this.catalog,this.p.language))} · ${this.t('Temperaturverlauf','Temperature history')}</h3>${renderChart(this.p,`tank-${n.id}`,{ids:n.temperature_zones.map(z=>z.entity).filter(Boolean),unit:'°C',width:Math.max(310,Math.round(charts.clientWidth-34)),title:nodeLabel(n,this.catalog,this.p.language),labels:Object.fromEntries(n.temperature_zones.map((z,i)=>[z.entity,zoneName(i,n.temperature_zones.length,this.p.language==='en')]))})}</section>`).join(''));
   refreshChartHover(this.p,this.shadowRoot);
   if(this.drag?.viewBox)canvas.querySelector('.sg-svg')?.setAttribute('viewBox',this.drag.viewBox);
 }
 async click(e){
   if(this.saving)return;
   if(this.pendingNode&&e.target.closest('.sg-svg')){[this.pendingNode.x,this.pendingNode.y]=this.placementPosition(this.placementTouch||e);this.placementTouch=null;this.placeNode();return;}
   if(chartClick(this.p,e)){this.updateCanvas();return;}
   if(this.suppressClick){this.suppressClick=false;return;}
   const history=e.target.closest('[data-reading]');if(history){this.p.showHistory(history.dataset.reading);return;}
   const action=e.target.closest('[data-action]')?.dataset.action;
   if(action==='motion'){this.p._animationPaused=!this.p._animationPaused;this.render();return;}
   if(action==='edit'){this.p.navigate('schematic');return;}
   if(!this.editor)return;
   if(this.placing&&e.target.closest('.sg-svg')){
     const line=this.graph.edges.find(x=>x.id===this.session.selected);if(line){if((line.points||[]).length>=16)throw Error('pipe');this.mutate(()=>{line.points??=[];line.points.push(this.coords(e));});}this.placing=false;this.message='';this.render();return;
   }
   const port=e.target.closest('[data-port]')?.dataset.port;
   if(port){this.choosePort(port);return;}
   const node=e.target.closest('[data-node]')?.dataset.node,edge=e.target.closest('[data-edge]')?.dataset.edge;
   if(node||edge){this.session.selected=node||edge;this.session.port='';this.render();return;}
   if(!action)return;
   if(action==='add'){
     if(this.graph.nodes.length>=80)throw Error('component');const type=this.shadowRoot.querySelector('#component').value;
     let id=`${type}_1`,i=1;while(this.graph.nodes.some(n=>n.id===id))id=`${type}_${++i}`;
     this.pendingNode=createNode(type,this.catalog,id);this.placing=false;this.session.port='';
     const stage=this.shadowRoot.querySelector('.stage').getBoundingClientRect();
     [this.pendingNode.x,this.pendingNode.y]=this.placementPosition({clientX:stage.x+stage.width/2,clientY:stage.y+stage.height/2});
     this.message=this.t('Auf die gewünschte Stelle klicken oder tippen, um das Bauteil abzusetzen. Pfeiltasten verschieben die Vorschau, Enter setzt ab, Esc bricht ab.','Click or tap the desired position. Arrow keys move the preview, Enter places it, Esc cancels.');this.bad=false;this.render();
     this.shadowRoot.querySelector('.sg-svg')?.focus({preventScroll:true});
   }else if(action==='cancel-placement'){this.cancelPlacement();}
   else if(this.pendingNode){this.cancelPlacement();return this.click(e);}
   else if(action==='preset'){const choice=this.shadowRoot.querySelector('#preset').value;this.mutate(()=>{this.session.graph=preset(choice,this.catalog,this.p);this.session.selected='';this.session.port='';this.canvasBounds=null;this.baseWidth=null;});}
   else if(action==='undo'||action==='redo'){const stack=this.session[action];if(stack.length){this.session[action==='undo'?'redo':'undo'].push(copy(this.graph));this.session.graph=stack.pop();this.session.selected='';this.session.port='';this.session.dirty=true;this.p._schematicDirty=true;this.render();}}
   else if(action==='delete')this.remove();
   else if(action==='flip'||action==='flip-y'){const n=this.graph.nodes.find(n=>n.id===this.session.selected);if(n)this.mutate(()=>{n[action==='flip'?'flip':'flip_y']=!n[action==='flip'?'flip':'flip_y'];this.reroute(n.id);});}
   else if(action==='auto-route'){const line=this.graph.edges.find(x=>x.id===this.session.selected);if(line)this.mutate(()=>{line.points=[];delete line.route;});}
   else if(action==='waypoint'){this.placing=true;this.message=this.t('Auf die Zeichenfläche klicken, um den nächsten Knickpunkt zu setzen.','Click the canvas to place the next waypoint.');this.bad=false;this.render();}
   else if(action==='export'){const url=URL.createObjectURL(new Blob([JSON.stringify(this.graph,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='r290-anlagenschaubild.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
   else if(action==='import')this.shadowRoot.querySelector('#import-file').click();
   else if(action==='reload'){this.p._schematicDirty=false;this.p._schematicSession=null;this.message='';await this.p.load();this.configure(this.p);}
   else if(['draft','publish','disable'].includes(action))await this.save(action);
 }
 choosePort(key){
   const [node,port]=key.split(':'),ep={node,port};
   if(this.session.port===key){this.session.port='';this.render();return;}
   if(!this.session.port){this.session.port=key;this.session.selected=node;this.message=this.t('Zweiten passenden Anschluss auswählen.','Select a second compatible port.');this.bad=false;this.render();return;}
   const [first,firstPort]=this.session.port.split(':'),pair=connection(this.graph,this.catalog,{node:first,port:firstPort},ep);
   let id='pipe_1',i=1;while(this.graph.edges.some(e=>e.id===id))id=`pipe_${++i}`;
   if(this.graph.edges.length>=160)throw Error('pipe');this.message='';this.mutate(()=>{this.graph.edges.push({id,...pair,points:[]});this.session.port='';this.session.selected=id;});
 }
 async change(e){
   if(this.saving)return;const el=e.target;
   if(el.id==='zoom'){this.zoom=Number(el.value);this.render();return;}
   if(el.id==='component'){this.componentType=el.value;if(this.pendingNode)this.cancelPlacement();return;}
   if(el.id==='preset'){this.presetType=el.value;return;}
   if(!this.editor)return;
   if(el.id==='import-file'){
     const file=el.files?.[0];if(!file)return;if(file.size>250000)throw Error('format');let graph;try{graph=JSON.parse(await file.text());}catch{throw Error('format');}
     const report=inspect(graph,this.catalog);if(report.errors.length)throw Error(report.errors[0]);this.message=graph.nodes.some(n=>['pv','battery','house','grid'].includes(n.type))?this.t('PV, Batterie, Haus und Netz werden beim Speichern in die separate Stromübersicht übernommen.','PV, battery, house and grid will move to the separate electricity overview when saved.'):'';this.mutate(()=>{this.session.graph=graph;this.session.selected='';this.session.port='';this.canvasBounds=null;this.baseWidth=null;this.pendingNode=null;});return;
   }
   const n=this.graph.nodes.find(n=>n.id===this.session.selected);if(!n)return;
   if(el.hasAttribute('data-tank')){this.mutate(()=>attachHeater(this.graph,n,el.value));return;}
   if(el.hasAttribute('data-zone-count')){this.mutate(()=>{n.temperature_zones=(zoneHeights[Number(el.value)]||[]).map((height,i)=>({height,entity:n.temperature_zones?.[i]?.entity||''}));});return;}
   if(el.hasAttribute('data-zone-entity')||el.hasAttribute('data-zone-height')){if(!el.reportValidity())return;const i=Number(el.dataset.zoneEntity??el.dataset.zoneHeight);this.mutate(()=>{if(el.hasAttribute('data-zone-entity'))n.temperature_zones[i].entity=el.value||'';else n.temperature_zones[i].height=Number(el.value);});return;}
   if(el.dataset.binding){if(!el.reportValidity())return;this.mutate(()=>{n.bindings??={};n.bindings[el.dataset.binding]=el.value||'';});return;}
   const prop=el.dataset.property;if(!prop)return;if(!el.reportValidity())return;
   if(n[prop]===(['x','y'].includes(prop)?Number(el.value):el.value))return;
   if(['circuit','leg'].includes(prop)&&this.graph.edges.some(e=>e.from.node===n.id||e.to.node===n.id)){this.message=this.t('Vor einem Kreiswechsel die angeschlossenen Leitungen entfernen.','Remove connected pipes before changing the circuit.');this.bad=true;this.render();return;}
   this.mutate(()=>{if(['x','y'].includes(prop))moveNode(this.graph,n,prop==='x'?Number(el.value):n.x,prop==='y'?Number(el.value):n.y);else n[prop]=el.value;if(prop==='circuit')n.leg=n.circuit==='electric'?'power':n.leg==='power'?'supply':n.leg;if(['x','y'].includes(prop))this.reroute(n.id);});
 }
 remove(){const id=this.session.selected;if(!id)return;this.mutate(()=>{for(const n of this.graph.nodes)if(n.tank===id)delete n.tank;this.session.graph.nodes=this.graph.nodes.filter(n=>n.id!==id);this.session.graph.edges=this.graph.edges.filter(e=>e.id!==id&&e.from.node!==id&&e.to.node!==id);this.session.selected='';this.session.port='';});}
 reroute(){this.geometryKey='';} // Retain explicit pipe routes when a component moves.
 async save(action){
   if(this.saving)return;for(const el of this.shadowRoot.querySelectorAll('r290-entity-picker'))if(!el.reportValidity())return;
   if(action==='disable'&&this.session.dirty){this.message=this.t('Entwurf zuerst speichern oder verwerfen.','Save or discard the draft first.');this.bad=true;this.render();return;}
   const report=inspect(this.graph,this.catalog);if(report.errors.length||action==='publish'&&report.open.length){this.message=this.t('Bitte zuerst die Anschlüsse vervollständigen.','Complete the connections first.');this.bad=true;this.render();return;}
   this.saving=true;this.render();
   try{const graph=copy(this.graph);retainRoutes(graph,this.geometry);const result=await this.p.ws('schematic',{action,expected_revision:this.session.revision,...(action==='disable'?{}:{graph})});if(action!=='disable')this.session.graph=copy(result.schematic.draft);if(result.electric)this.p.data.settings.electric=result.electric;this.p.data.settings.schematic=result.schematic;this.session.revision=result.schematic.revision;this.session.dirty=false;this.p._schematicDirty=false;this.message=action==='publish'?this.t('Gespeichert. Die Anlagenübersicht verwendet jetzt dieses Schaubild.','Saved. The plant overview now uses this schematic.'):this.t('Gespeichert. Keine Geräteeinstellungen geändert.','Saved. No device settings changed.');this.bad=false;}
   catch(err){this.message=err.message;this.bad=true;}
   finally{this.saving=false;this.render();}
 }
 key(e){
   if(this.saving)return;
   if(e.composedPath().some(n=>n?.matches?.('input,select,textarea,r290-entity-picker')))return;
   if(this.pendingNode){
     if(e.key==='Escape'){e.preventDefault();this.cancelPlacement();return;}
     if(e.key==='Enter'){e.preventDefault();this.placeNode();return;}
     const d={ArrowLeft:[-20,0],ArrowRight:[20,0],ArrowUp:[0,-20],ArrowDown:[0,20]}[e.key];
     if(d){e.preventDefault();this.pendingNode.x=Math.max(0,Math.min(3600,this.pendingNode.x+d[0]));this.pendingNode.y=Math.max(0,Math.min(3600,this.pendingNode.y+d[1]));this.updateCanvas();}return;
   }
   const segment=e.target.closest('[data-segment]');
   if(this.editor&&segment&&e.key.startsWith('Arrow')){const route=this.geometry[segment.dataset.edge].route,i=Number(segment.dataset.segment),axis=route[i][0]===route[i+1][0]?0:1,delta={ArrowLeft:[-10,0],ArrowRight:[10,0],ArrowUp:[0,-10],ArrowDown:[0,10]}[e.key];if(delta?.[axis]){e.preventDefault();const points=moveSegment(route,i,route[i][axis]+delta[axis]);this.mutate(()=>this.graph.edges.find(x=>x.id===segment.dataset.edge).points=points);this.shadowRoot.querySelector(`[data-segment="${i}"]`)?.focus({preventScroll:true});}return;}
   const el=e.target.closest('[data-port],[data-reading],[data-node],[data-edge]');
   if(['Enter',' '].includes(e.key)&&el){e.preventDefault();el.dispatchEvent(new MouseEvent('click',{bubbles:true}));return;}
   if(!this.editor)return;
   if(e.key==='Escape'){this.cancelDrag();this.session.port='';this.placing=false;this.message='';this.render();}
   if(e.key==='Delete'){e.preventDefault();this.remove();}
   const n=this.graph.nodes.find(n=>n.id===this.session.selected),d={ArrowLeft:[-20,0],ArrowRight:[20,0],ArrowUp:[0,-20],ArrowDown:[0,20]}[e.key];
   if(n&&d){e.preventDefault();this.mutate(()=>{moveNode(this.graph,n,n.x+d[0],n.y+d[1]);this.reroute(n.id);});this.shadowRoot.querySelector(`[data-node="${n.id}"]`)?.focus({preventScroll:true});}
 }
 dragStart(e){
   if(!this.editor||this.saving||e.button!==0||this.placing||this.pendingNode||e.target.closest('[data-port],[data-reading]'))return;
   const segment=e.target.closest('[data-segment]'),node=e.target.closest('[data-node]');if(!segment&&!node)return;
   const svg=this.shadowRoot.querySelector('.sg-svg'),start=this.coords(e),before=copy(this.graph);
   if(segment){const id=segment.dataset.edge;this.drag={id,segment:Number(segment.dataset.segment),route:copy(this.geometry[id].route),kind:'pipe'};}
   else {const n=this.graph.nodes.find(n=>n.id===node.dataset.node);this.drag={id:n.id,x:n.x,y:n.y,kind:'node'};}
   Object.assign(this.drag,{start,before,moved:false,pointer:e.pointerId,matrix:svg.getScreenCTM().inverse(),viewBox:svg.getAttribute('viewBox')});
   e.preventDefault();this.setPointerCapture(e.pointerId);
 }
 dragMove(e){
   if(!this.drag||e.pointerId!==this.drag.pointer)return;const pos=this.coords(e),d=this.drag;
   if(pos[0]===d.start[0]&&pos[1]===d.start[1]&&!d.moved)return;
   if(!d.retained){retainRoutes(this.graph,this.geometry);d.retained=true;}
   if(d.kind==='pipe'){
     const axis=d.route[d.segment][0]===d.route[d.segment+1][0]?0:1,value=d.route[d.segment][axis]+pos[axis]-d.start[axis];
     if(value<0||value>3600)return;
     try{this.graph.edges.find(x=>x.id===d.id).points=moveSegment(d.route,d.segment,value);}catch{return;}
     d.moved=value!==d.route[d.segment][axis];
   }else{
     const n=this.graph.nodes.find(n=>n.id===d.id);
     moveNode(this.graph,n,d.x+pos[0]-d.start[0],d.y+pos[1]-d.start[1]);d.moved=n.x!==d.x||n.y!==d.y;
   }
   this.updateCanvas();
 }
 dragEnd(e){
   if(!this.drag||e.pointerId!==this.drag.pointer)return;const d=this.drag;this.drag=null;this.releasePointerCapture(e.pointerId);
   if(d.moved){this.session.undo.push(d.before);if(this.session.undo.length>30)this.session.undo.shift();this.session.redo=[];this.session.selected=d.id;this.suppressClick=true;setTimeout(()=>{this.suppressClick=false;},0);this.changed();}
   else {this.session.graph=d.before;this.render();}
 }
 cancelDrag(){if(!this.drag)return;const d=this.drag;this.session.graph=d.before;this.drag=null;if(this.hasPointerCapture(d.pointer))this.releasePointerCapture(d.pointer);this.render();}

}
customElements.define('r290-schematic',SchematicEditor);

export function schematicView(p){return p.heading(p.language==='en'?'Build your plant schematic.':'Die Anlage zusammenstellen.',p.language==='en'?'Connect components once; use the same diagram for live readings.':'Bauteile einmal verbinden und dasselbe Schaubild für Livewerte verwenden.')+'<r290-schematic data-mode="editor" data-preserve-children></r290-schematic>';}
export function configureSchematics(p){for(const el of p.shadowRoot.querySelectorAll('r290-schematic'))el.configure(p);}

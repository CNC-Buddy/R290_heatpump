import {esc,fmt,numeric,chartPaths} from './model.js?v=1.1.1';

const palette=Array.from({length:6},(_,i)=>`var(--plot-${i+1})`);
export const chartStyles=`.interactive-chart{position:relative;min-width:0}.chart-tools{display:flex;justify-content:flex-end;align-items:center;gap:10px;margin-bottom:6px;font-size:12px;color:var(--muted)}.chart-gear{border:1px solid var(--line);border-radius:8px;background:var(--surface-inset);color:var(--ink);cursor:pointer;font-size:19px;padding:4px 10px}.chart-legend{display:flex;flex-wrap:wrap;gap:7px;margin-top:8px}.chart-legend button{border:0;border-radius:6px;background:transparent;color:var(--ink);cursor:pointer;padding:5px 8px;font:inherit;font-size:12px}.chart-legend button[aria-pressed=false]{opacity:.65;text-decoration:line-through}.chart-key{display:inline-block;width:10px;height:4px;vertical-align:middle;margin-right:6px}.chart-tooltip{position:absolute;z-index:3;pointer-events:none;background:var(--surface-raised);border:1px solid var(--card-border);color:#fff;padding:10px 13px;border-radius:9px;font-size:12px;max-width:280px;box-shadow:0 4px 18px #20364022}.chart-tooltip[hidden]{display:none}.chart-tooltip div{display:flex;justify-content:space-between;gap:16px;line-height:1.8}.chart-tooltip strong{display:block;margin-bottom:4px}.interactive-chart .chart{width:100%;display:block;overflow:visible}.interactive-chart .series{fill:none;stroke-width:1.4;vector-effect:non-scaling-stroke}.interactive-chart .grid-line{stroke:var(--line);stroke-width:1}.interactive-chart .chart text{fill:var(--muted);font:11px system-ui}.chart-sensors{max-height:320px;overflow:auto;margin:12px 0}.chart-sensors label{display:flex;gap:9px;padding:8px;border-bottom:1px solid var(--line)}.chart-sensors label[hidden]{display:none}.chart-sensors small{display:block;color:var(--muted);font-size:11px}.chart-sensors input{width:auto}.tank-history{margin-top:16px;padding:16px;border:1px solid var(--line);border-radius:12px}.tank-history h3{margin:0 0 8px}`;
const text=(p,de,en)=>p.language==='en'?en:de;
export const periodLabel=(p,days)=>days<1?`${days*24} ${text(p,'Stunden','hours')}`:days===1?`24 ${text(p,'Stunden','hours')}`:`${days} ${text(p,'Tage','days')}`;
export function compatibleUnit(from,to){return from===to||to==='°C'&&['°F','K'].includes(from)||to==='W'&&from==='kW';}
function convert(v,unit,target){v=numeric(v);return v===null||!compatibleUnit(unit,target)?null:unit==='°F'?(v-32)*5/9:unit==='K'?v-273.15:unit==='kW'&&target==='W'?v*1000:v;}
const hidden=(p,key)=>key==='overview-temperature'?(p._hiddenTemperatures??=new Set()):((p._chartHidden??={})[key]??=new Set());
function load(p,key,spec,ids,days){
  p._chartSlots??={};const signature=JSON.stringify([ids,days]),old=p._chartSlots[key];
  if(old?.signature===signature&&(old.pending||old.error||Date.now()-old.at<300000))return old;
  const slot={signature,pending:true};p._chartSlots[key]=slot;
  if(!ids.length){slot.pending=false;slot.error=text(p,'Keine Messquellen gewählt.','No sources selected.');return slot;}
  p.ws('history',{entity_ids:ids,days}).then(history=>{slot.history=history;slot.at=Date.now();},err=>{slot.error=err.message;}).finally(()=>{slot.pending=false;if(p._chartSlots[key]===slot)p.render();});
  return slot;
}
export function renderChart(p,key,spec){
  const pref=p.data?.settings?.charts?.[key],ids=[...new Set(pref?.entity_ids||spec.ids)].filter(Boolean),days=spec.daysOverride||pref?.days||spec.days||1;
  const slot=spec.managed?{history:spec.history,error:spec.error}:spec.history&&(!pref||spec.synced)?{history:spec.history}:load(p,key,spec,ids,days),h=slot.history,width=spec.width||680,height=spec.height||210;
  const meta={spec,ids,days,series:[],start:0,end:0};(p._chartMeta??={})[key]=meta;
  const rows=ids.map((id,i)=>({id,label:spec.labels?.[id]||p.name(id),color:spec.colors?.[id]||palette[i%palette.length],unit:spec.unit,points:(h?.series?.[id]?.points||[]).map(([t,v])=>[t,convert(v,h.series[id].unit,spec.unit)])}));
  const visible=rows.filter(s=>!hidden(p,key).has(s.id));meta.series=visible;
  const values=visible.flatMap(s=>s.points.map(p=>p[1]).filter(v=>v!==null));
  let content='';
  if(slot.error)content=`<p role="alert">${esc(slot.error)}</p><button data-chart-refresh="${key}">${text(p,'Erneut laden','Retry')}</button>`;
  else if(!h)content=`<p role="status">${text(p,'Verlauf wird geladen …','Loading history …')}</p>`;
  else{
    const min=values.length?Math.floor((Math.min(...values)-1)/5)*5:0,max=values.length?Math.max(min+5,Math.ceil((Math.max(...values)+1)/5)*5):5;
    const start=Date.parse(h.start)/1000,end=Date.parse(h.end)/1000;Object.assign(meta,{start,end,min,max,width,height});
    content=`<svg class="chart ${key==='overview-temperature'?'overview-chart':''}" data-chart-hover="${key}" viewBox="0 0 ${width} ${height}" style="height:${height}px" role="img" aria-label="${esc(spec.title||text(p,'Verlauf','History'))}" tabindex="0"><text x="${width-16}" y="10" text-anchor="end">${esc(spec.unit)}</text>${[0,1,2,3].map(i=>{const y=12+i*(height-38)/3;return `<line class="grid-line" x1="32" x2="${width-16}" y1="${y}" y2="${y}"/><text x="25" y="${y+4}" text-anchor="end">${fmt(max-i*(max-min)/3,0)}</text>`;}).join('')}${visible.map(s=>`<path class="series" data-series="${esc(s.id)}" stroke="${s.color}" d="${chartPaths(s.points,start,end,min,max,width,height)}"><title>${esc(s.label)}</title></path>`).join('')}${[0,.5,1].map(t=>`<text x="${32+t*(width-48)}" y="${height-2}" text-anchor="${t===0?'start':t===1?'end':'middle'}">${p.date((start+(end-start)*t)*1000,days<=1?{hour:'2-digit',minute:'2-digit'}:{day:'2-digit',month:'2-digit'})}</text>`).join('')}<line data-crosshair x1="32" x2="32" y1="12" y2="${height-26}" stroke="#76909c" stroke-dasharray="3 4" visibility="hidden"/></svg>${!values.length?`<p class="hint">${text(p,'Keine sichtbaren Messwerte. Quellen über die Legende einblenden.','No visible readings. Enable sources in the legend.')}</p>`:''}`;
  }
  return `<div class="interactive-chart" data-chart="${key}"><div class="chart-tools"><span>${periodLabel(p,days)}</span><button class="chart-gear" data-chart-config="${key}" aria-label="${text(p,'Diagramm konfigurieren','Configure chart')}" title="${text(p,'Zeitraum und Messquellen','Period and sources')}">⚙</button></div>${content}<div class="chart-tooltip" hidden role="status"></div>${spec.legend===false?'':`<div class="chart-legend">${rows.map(s=>`<button data-chart-toggle="${key}" data-chart-entity="${esc(s.id)}" aria-pressed="${!hidden(p,key).has(s.id)}"><span class="chart-key" style="background:${s.color}"></span>${esc(s.label)}</button>`).join('')}</div>`}</div>`;
}
function target(event,selector){return event.composedPath().find(el=>el instanceof Element&&Element.prototype.matches.call(el,selector));}
export function chartHover(p,event){
  const svg=target(event,'[data-chart-hover]');if(!svg)return;
  const meta=p._chartMeta?.[svg.dataset.chartHover],box=svg.closest('[data-chart]'),tip=box?.querySelector('.chart-tooltip'),cross=svg.querySelector('[data-crosshair]');if(!meta?.end||!tip)return;
  const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(svg.getScreenCTM().inverse());
  if(point.x<32||point.x>meta.width-16||point.y<12||point.y>meta.height-26){delete svg._chartPointer;tip.hidden=true;cross?.setAttribute('visibility','hidden');return;}
  svg._chartPointer={clientX:event.clientX,clientY:event.clientY};
  const time=meta.start+(point.x-32)/(meta.width-48)*(meta.end-meta.start);
  tip.innerHTML=`<strong>${p.date(time*1000,{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}</strong>${meta.series.map(s=>{let left=0,right=s.points.length;while(left<right){const m=(left+right)>>1;if(s.points[m][0]<=time)left=m+1;else right=m;}const value=s.points[left-1]?.[1];return `<div><span><i class="chart-key" style="background:${s.color}"></i>${esc(s.label)}</span><b>${value==null?'—':`${fmt(value,1)} ${esc(s.unit)}`}</b></div>`;}).join('')}`;
  tip.hidden=false;const bounds=box.getBoundingClientRect();tip.style.left=`${Math.max(0,Math.min(event.clientX-bounds.left+12,bounds.width-tip.offsetWidth))}px`;tip.style.top=`${Math.max(32,event.clientY-bounds.top-tip.offsetHeight-10)}px`;
  if(cross){cross.setAttribute('x1',point.x);cross.setAttribute('x2',point.x);cross.setAttribute('visibility','visible');}
}
export function chartLeave(event){const svg=target(event,'[data-chart-hover]');if(svg&&!svg.contains(event.relatedTarget)){delete svg._chartPointer;const box=svg.closest('[data-chart]');box?.querySelector('.chart-tooltip')?.setAttribute('hidden','');svg.querySelector('[data-crosshair]')?.setAttribute('visibility','hidden');}}
export function chartClick(p,event){
  const toggle=target(event,'[data-chart-toggle]');if(toggle){const set=hidden(p,toggle.dataset.chartToggle),id=toggle.dataset.chartEntity;set.has(id)?set.delete(id):set.add(id);p.render();return true;}
  const retry=target(event,'[data-chart-refresh]');if(retry){if(p._chartSlots)delete p._chartSlots[retry.dataset.chartRefresh];if(retry.dataset.chartRefresh==='overview-temperature'){p._overviewError='';p.overviewHistory=null;}p.render();return true;}
  const button=target(event,'[data-chart-config]');if(!button)return false;
  const key=button.dataset.chartConfig,meta=p._chartMeta?.[key];if(!meta)return true;
  const pref=p.data.settings.charts?.[key],revision=pref?.revision||0;
  const selected=new Set(meta.ids);
  const sources=Object.values(p.states).filter(s=>s.entity_id.startsWith('sensor.')&&compatibleUnit(s.attributes.unit_of_measurement,meta.spec.unit)).sort((a,b)=>Number(selected.has(b.entity_id))-Number(selected.has(a.entity_id))||p.name(a.entity_id).localeCompare(p.name(b.entity_id),p.language));
  p.openModal(text(p,'Diagramm konfigurieren','Configure chart'),esc(meta.spec.title||''),`<label class="field">${text(p,'Zeitraum','Period')}<select name="chart-days">${[.25,.5,1,2,7,30].map(d=>`<option value="${d}" ${d===meta.days?'selected':''}>${periodLabel(p,d)}</option>`).join('')}</select></label><label class="field">${text(p,'Messquellen suchen','Search sources')}<input type="search" data-chart-search></label><p>${text(p,'1–24 Messquellen wählen. Die Auswahl wird in Home Assistant gespeichert.','Choose 1–24 sources. Preferences are saved in Home Assistant.')}</p><div class="chart-sensors">${sources.map(s=>`<label data-chart-choice><input type="checkbox" name="chart-source" value="${esc(s.entity_id)}" ${meta.ids.includes(s.entity_id)?'checked':''}><span>${esc(p.name(s.entity_id))}<small>${esc(s.entity_id)}</small></span></label>`).join('')}</div>`,async dialog=>{
    const entity_ids=[...dialog.querySelectorAll('[name=chart-source]:checked')].map(el=>el.value);if(!entity_ids.length||entity_ids.length>24)throw Error(text(p,'Bitte 1–24 Messquellen auswählen.','Select 1–24 sources.'));
    const result=await p.ws('charts',{key,expected_revision:revision,days:Number(dialog.querySelector('[name=chart-days]').value),entity_ids});p.data.settings.charts={...p.data.settings.charts,[key]:result.chart};if(p._chartDayOverrides)delete p._chartDayOverrides[key];if(p._chartSlots)delete p._chartSlots[key];hidden(p,key).clear();if(key==='overview-temperature'){p._overviewError='';p.overviewHistory=null;}return text(p,'Diagramm gespeichert.','Chart saved.');
  });return true;
}
export function chartSearch(event){const field=target(event,'[data-chart-search]');if(!field)return false;for(const row of field.closest('dialog').querySelectorAll('[data-chart-choice]'))row.hidden=!row.textContent.toLowerCase().includes(field.value.trim().toLowerCase());return true;}

export function refreshChartHover(p,root=p.shadowRoot){for(const svg of root.querySelectorAll('[data-chart-hover]'))if(svg._chartPointer)chartHover(p,{...svg._chartPointer,composedPath:()=>[svg]});}

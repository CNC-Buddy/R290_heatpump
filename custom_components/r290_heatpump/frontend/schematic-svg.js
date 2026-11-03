import {esc,fmt} from './model.js?v=1.1.0';
import {nodePorts,colors,activeEdges,freshValue,isOn} from './schematic-model.js?v=1.1.0';
import {presentationArt,presentationDefs} from './schematic-art.js?v=1.1.0';

import {orthogonal,autoRoute,viaPoints,simplify,equal,validRoute} from './schematic-routing.js?v=1.1.0';
import {bindingsFor} from './schematic-bindings.js?v=1.1.0';
import {tankLayers,tankReadings,heaterArt} from './schematic-tanks.js?v=1.1.0';

const direction={left:[-1,0],right:[1,0],top:[0,-1],bottom:[0,1]};
const labelTranslations={'Zapfstelle 1':'Outlet 1','Zapfstelle 2':'Outlet 2','Zusatzpumpe':'Auxiliary pump','Pufferladepumpe':'Buffer charging pump','Heizkreispumpe':'Heating circuit pump','Zirkulationspumpe':'Circulation pump','Warmwasser':'Hot water','Umschaltventil WP':'HP diverter valve','Umschaltventil WE2':'Source 2 diverter valve'};
export function nodeLabel(n,c,lang){return n.label?(lang==='en'?labelTranslations[n.label]||n.label:n.label):c[n.type].label[lang==='en'?1:0];}
export function dimensions(graph,catalog){const points=graph.edges.flatMap(e=>e.points?.length?e.points:e.route||[]);return {width:Math.max(1100,...graph.nodes.map(n=>n.x+catalog[n.type].width+(n.temperature_zones?.length?225:130)),...points.map(p=>p[0]+80)),height:Math.max(500,...graph.nodes.map(n=>n.y+catalog[n.type].height+130),...points.map(p=>p[1]+80))};}
function endpoint(ep,graph,catalog){const n=graph.nodes.find(n=>n.id===ep.node),p=nodePorts(n,catalog)[ep.port];return {point:[n.x+p.x,n.y+p.y],p};}
export function paths(graph,catalog){
  const result={};
  for(const e of graph.edges){
    const a=endpoint(e.from,graph,catalog),b=endpoint(e.to,graph,catalog);
    const stub=({point,p})=>point.map((v,i)=>v+direction[p.side][i]*30);
    const start=stub(a),end=stub(b),axis=p=>['left','right'].includes(p.side)?0:1;
    const owners=[e.from.node,e.to.node].map(id=>graph.nodes.find(n=>n.id===id)?.tank).filter(Boolean);
    const boxes=graph.nodes.filter(n=>!n.tank&&!owners.includes(n.id)).map(n=>[n.x-12,n.y-12,n.x+catalog[n.type].width+12,n.y+catalog[n.type].height+12]);
    const saved=validRoute(e.route)&&equal(e.route[0],start)&&equal(e.route.at(-1),end);
    const route=e.points?.length?viaPoints(start,end,e.points,axis(a.p),axis(b.p)):saved?e.route:autoRoute(start,end,boxes,axis(a.p),axis(b.p));
    const points=simplify([a.point,...route,b.point]);
    let d=`M${points[0].join(' ')}`;
    for(let i=1;i<points.length-1;i++){
      const before=points[i-1],at=points[i],after=points[i+1],lengthA=Math.hypot(at[0]-before[0],at[1]-before[1]),lengthB=Math.hypot(after[0]-at[0],after[1]-at[1]),radius=Math.min(9,lengthA/2,lengthB/2);
      const entry=at.map((v,j)=>v+(before[j]-v)*radius/lengthA),exit=at.map((v,j)=>v+(after[j]-v)*radius/lengthB);
      d+=`L${entry.join(' ')}Q${at.join(' ')} ${exit.join(' ')}`;
    }
    d+=`L${points.at(-1).join(' ')}`;
    result[e.id]={d,color:colors[a.p.circuit][a.p.leg],points,route};
  }
  return result;
}
function componentArt(n,s,ports){
  const w=s.width,h=s.height,line=(a,b,color,width=3)=>`<path d="M${a.join(' ')}L${b.join(' ')}" stroke="${color}" stroke-width="${width}" fill="none"/>`;
  const paint=k=>colors[ports[k].circuit][ports[k].leg];
  if(n.type==='junction')return Object.keys(ports).map(k=>line([w/2,h/2],[ports[k].x,ports[k].y],paint(k))).join('')+`<circle cx="20" cy="20" r="5" fill="${paint('a')}"/>`;
  if(n.type==='circulation_end')return `<path d="M0 20H40V60" fill="none" stroke="${paint('hot')}" stroke-width="4"/><path d="M40 60V100H0" fill="none" stroke="${paint('return')}" stroke-width="4"/>`;
  if(n.type==='valve')return ['common','a','b'].map(k=>line([w/2,h/2],[ports[k].x,ports[k].y],paint(k))).join('')+`<path d="M35 35L65 65V35L35 65Z" fill="#fff7e9" stroke="#67777d" stroke-width="2"/>`;
  if(n.type==='pump')return `${line([0,40],[100,40],paint('in'))}<circle cx="50" cy="40" r="27" fill="#e0ede2" stroke="#51836a" stroke-width="2"/><path d="${n.flip?'M63 23V57L35 40Z':'M37 23V57L65 40Z'}" fill="#51836a"/>`;
  if(n.type==='heat_meter')return `${line([0,40],[100,40],paint('in'))}<rect x="12" y="15" width="76" height="50" rx="8" fill="#e7eeec" stroke="#64777c"/><rect x="26" y="26" width="48" height="25" rx="3" fill="#f4f9e8"/><text x="50" y="44" text-anchor="middle" font-size="13">kWh</text>`;
  if(n.type==='plate')return `<rect x="14" y="8" width="72" height="124" rx="8" fill="#edf0ec" stroke="#79898c"/>${['primary_in','primary_out','secondary_in','secondary_out'].map(k=>line([ports[k].x,ports[k].y],[ports[k].x<50?32:68,ports[k].y],paint(k))).join('')}<path d="M32 30V110" fill="none" stroke="${paint('primary_in')}" stroke-width="5"/><path d="M68 110V30" fill="none" stroke="${paint('secondary_in')}" stroke-width="5"/><path d="M49 20V120M54 20V120" stroke="#a4afaa" stroke-width="2"/>`;
  if(['dhw_tank','buffer'].includes(n.type)){
    let svg=`<rect x="18" y="8" width="124" height="260" rx="32" fill="${n._tankFill||'url(#sg-water)'}" stroke="#758b93" stroke-width="2"/><ellipse cx="80" cy="28" rx="61" ry="20" fill="#f2dccb" stroke="#b39177"/>`;
    const coil=(a,b)=>{const aa=ports[a],bb=ports[b];return `${line([aa.x,aa.y],[50,aa.y],paint(a))}<path d="M50 ${aa.y}H112q12 8 0 16H50q-12 8 0 16H112q12 8 0 16H50V${bb.y}" fill="none" stroke="${paint(a)}" stroke-width="3"/>${line([50,bb.y],[bb.x,bb.y],paint(b))}`;};
    if(n.type==='dhw_tank')svg+=coil('wp_in','wp_out');else for(const k of ['charge_in','charge_out','heating_out','heating_in'])svg+=line([ports[k].x,ports[k].y],[ports[k].x<80?28:132,ports[k].y],paint(k));
    svg+=coil('we2_in','we2_out');
    if(n.type==='dhw_tank')for(const k of ['hot','circulation'])svg+=line([132,ports[k].y],[ports[k].x,ports[k].y],paint(k));
    return svg;
  }
  if(n.type==='heat_pump')return `<rect x="4" y="6" width="172" height="108" rx="12" fill="#f1f4f0" stroke="#6d858f" stroke-width="2"/><circle cx="60" cy="60" r="39" fill="#dce6e7" stroke="#7e9297" stroke-width="3"/><g class="sg-fan">${[0,72,144,216,288].map(a=>`<path d="M60 60q-28-40 2-34q22 5 8 31Z" transform="rotate(${a} 60 60)" fill="#8b9da1"/>`).join('')}</g><circle cx="60" cy="60" r="7" fill="#eff4f1"/><path d="M117 25H156M117 36H156M117 47H156" stroke="#afbdbe" stroke-width="3"/>${['supply','return'].map(k=>line([160,ports[k].y],[ports[k].x,ports[k].y],paint(k))).join('')}`;
  if(n.type==='heat_source')return `<rect x="20" y="4" width="138" height="112" rx="12" fill="#ecebe7" stroke="#7b8e92"/><path d="M90 23q-40 40-15 59q-5-20 13-26q22 30 5 37q45-20-3-70Z" fill="#a68192"/>${['supply','return'].map(k=>line([158,ports[k].y],[ports[k].x,ports[k].y],paint(k))).join('')}`;
  if(n.type==='radiator')return `<rect x="15" y="8" width="139" height="104" rx="6" fill="#f5f5ef" stroke="#7d9199"/>${Array.from({length:9},(_,i)=>line([28+i*13,18],[28+i*13,102],'#a9b7ba',4)).join('')}${['in','out'].map(k=>line([0,ports[k].y],[15,ports[k].y],paint(k))).join('')}`;
  if(n.type==='tap')return `<path d="M60 80V35q0-25 25-25q20 0 20 20H88" fill="none" stroke="#718d98" stroke-width="9"/><path d="M45 43H75" stroke="#647a82" stroke-width="6"/>`;
  if(n.type==='heater')return heaterArt();
  const icons={pv:'☀',battery:'▥',grid:'⚡',house:'⌂',heater:'♨'};
  return `<rect x="12" y="5" width="116" height="80" rx="15" fill="#f3eee1" stroke="#a39264"/><text x="70" y="63" text-anchor="middle" font-size="43" fill="#997935">${icons[n.type]||'◈'}</text>${line([70,85],[70,100],'#b49624')}`;
}
export function renderPlacement(node,catalog,language){
  if(!node)return '';
  const spec=catalog[node.type];
  return `<g class="sg-placement" transform="translate(${node.x} ${node.y})" pointer-events="none" opacity=".7"><rect x="-8" y="-8" width="${spec.width+16}" height="${spec.height+16}" rx="12" fill="var(--accent-soft)" stroke="var(--accent)" stroke-width="2" stroke-dasharray="6 5"/>${componentArt(node,spec,nodePorts(node,catalog))}<text x="${spec.width/2}" y="-18" text-anchor="middle" class="sg-node-label">${esc(nodeLabel(node,catalog,language))}</text></g>`;
}
export function renderGraph(graph,catalog,p,{editor=false,selected='',selectedPort='',geometry={},showPorts=editor,bounds=dimensions(graph,catalog),preview=null}={}){
  const active=activeEdges(graph,catalog,p),lang=p.language,english=lang==='en';
  const top=editor?0:Math.max(0,Math.min(...graph.nodes.map(n=>n.y-45),...Object.values(geometry).flatMap(g=>g.route.map(pt=>pt[1]-12)),0+Math.max(0,bounds.height-200)));
  let svg=`<svg class="sg-svg" ${editor?'tabindex="0"':''} viewBox="0 ${top} ${bounds.width} ${bounds.height-top}" aria-label="${english?'Plant schematic':'Anlagenschaubild'}" role="group"><defs>${presentationDefs}<linearGradient id="sg-water" x2="0" y2="1"><stop stop-color="#f2d3bd"/><stop offset="1" stop-color="#c7dce3"/></linearGradient><pattern id="sg-grid" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="var(--line)"/></pattern></defs>${editor?`<rect width="100%" height="100%" fill="url(#sg-grid)"/>`:''}`;
  for(const e of graph.edges){const path=geometry[e.id];if(!path)continue;svg+=`<g data-key="edge-${e.id}" class="sg-edge ${selected===e.id?'selected':''}" data-edge="${e.id}"><path d="${path.d}" stroke="var(--surface-inset)" stroke-width="9" fill="none"/><path class="sg-pipe" d="${path.d}" stroke="${path.color}" stroke-width="${selected===e.id?5:3}" fill="none"/>${active.has(e.id)?`<path class="sg-flow" d="${path.d}" fill="none" stroke="#fffdf9" stroke-width="2"/>`:''}${editor?`<path class="sg-hit" d="${path.d}" stroke="transparent" stroke-width="15" fill="none" tabindex="0" role="button" aria-label="${english?'Pipe':'Leitung'} ${esc(e.id)}"/>`:''}</g>`;}
  for(const n of [...graph.nodes].sort((a,b)=>Number(!!a.tank)-Number(!!b.tank))){const s=catalog[n.type],ports=nodePorts(n,catalog),label=nodeLabel(n,catalog,lang),status=freshValue(p,n.bindings?.flow||n.bindings?.status);
    const running=active.size&&graph.edges.some(e=>active.has(e.id)&&(e.from.node===n.id||e.to.node===n.id));
    const layers=tankLayers(n,p);
    const original={...n,flip:false,flip_y:false,_tankFill:layers.fill},originalPorts=nodePorts(original,catalog),art=(!editor&&presentationArt(original,s,originalPorts,colors))||componentArt(original,s,originalPorts);
    const transform=`translate(${n.flip?s.width:0} ${n.flip_y?s.height:0}) scale(${n.flip?-1:1} ${n.flip_y?-1:1})`;
    const fanRunning=!p._animationPaused&&isOn(p,n.bindings?.fan)===true;
    svg+=`<g transform="translate(${n.x} ${n.y})" data-key="node-${n.id}" data-node="${n.id}" class="sg-node ${selected===n.id?'selected':''} ${running?'running':''} ${fanRunning?'fan-running':''}" ${editor?`tabindex="0" role="button" aria-label="${esc(label)}"`:''}><title>${esc(label)} · ${esc(n.id)}</title>${editor?`<rect class="sg-node-hit" x="-5" y="-8" width="${s.width+10}" height="${s.height+16}" rx="9" fill="${selected===n.id?'var(--accent-soft)':'transparent'}" stroke="${selected===n.id?'var(--accent)':'transparent'}"/>`:''}<g transform="${transform}">${layers.defs}${art}</g>${tankReadings(n,p)}`;
    if(!n.tank&&!['junction','circulation_end'].includes(n.type))svg+=`<text x="${s.width/2}" y="-18" text-anchor="middle" class="sg-node-label">${esc(label)}</text>`;
    for(const [key,port] of Object.entries(ports))if(showPorts){const name=port.label[english?1:0],color=colors[port.circuit][port.leg];svg+=`<circle cx="${port.x}" cy="${port.y}" r="${editor?7:3.5}" fill="${selectedPort===`${n.id}:${key}`?'var(--accent)':color}" stroke="var(--surface-inset)" stroke-width="2" data-port="${n.id}:${key}" ${editor?`tabindex="0" role="button" aria-label="${esc(label)}: ${esc(name)}"`:''}><title>${esc(name)} · ${port.circuit} · ${port.direction}</title></circle>`;}
    const visible=new Set(bindingsFor(n).map(b=>b.key));
    const fields=['value','supply','return','soc'].filter(k=>visible.has(k)&&n.bindings?.[k]&&!(k==='value'&&n.temperature_zones?.length));
    let y=s.height+24;
    for(const field of fields){const id=n.bindings[field],v=freshValue(p,id),state=p.states[id],numeric=v!==null&&v.trim()!==''&&Number.isFinite(Number(v)),text=v===null?'—':numeric?`${fmt(Number(v),1)} ${state?.attributes?.unit_of_measurement||''}`:v;
      const prefix=field==='supply'?(english?'Supply':'Vorlauf'):field==='return'?(english?'Return':'Rücklauf'):field==='soc'?(english?'Charge':'Ladezustand'):'';
      svg+=`<text x="${n.tank?s.width+24:s.width/2}" y="${n.tank?y-s.height+20:y}" text-anchor="${n.tank?'start':'middle'}" class="sg-reading ${field==='value'?'sg-value':''}" tabindex="0" role="button" data-reading="${esc(id)}" aria-label="${english?'History':'Verlauf'}: ${esc(label)} ${prefix}">${prefix?`${prefix} · `:''}${esc(text)}</text>`;y+=field==='value'&&!editor?27:20;
    }
    if(['pump','heat_source','heat_pump'].includes(n.type))svg+=`<text x="${s.width/2}" y="${y}" text-anchor="middle" class="sg-status">${status===null?(english?'Status unknown':'Status unbekannt'):running?(english?'Flow active':'Durchfluss aktiv'):english?'No confirmed flow':'Kein bestätigter Fluss'}</text>`;
    svg+='</g>';
  }
  if(editor&&geometry[selected]){const route=geometry[selected].route;
    svg+=`<g class="sg-route-handles" data-key="handles-${selected}">${route.slice(0,-1).map((a,i)=>{const b=route[i+1],vertical=a[0]===b[0],x=(a[0]+b[0])/2,y=(a[1]+b[1])/2;return `<g data-segment="${i}" data-edge="${selected}" tabindex="0" role="button" aria-label="${english?'Move pipe section':'Leitungsabschnitt verschieben'} ${i+1}" class="sg-segment ${vertical?'vertical':'horizontal'}"><circle cx="${x}" cy="${y}" r="17" fill="transparent"/><rect x="${x-7}" y="${y-7}" width="14" height="14" rx="4" fill="var(--surface-raised)" stroke="var(--accent)" stroke-width="2"/><path d="${vertical?`M${x-4} ${y}h8`:`M${x} ${y-4}v8`}" stroke="var(--accent)" stroke-width="2"/></g>`;}).join('')}</g>`;
  }
  return svg+renderPlacement(preview,catalog,lang)+'</svg>';
}

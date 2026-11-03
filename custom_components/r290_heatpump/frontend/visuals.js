// Native SVG artwork. All readings are supplied by the panel; no external assets.
import {esc, fmt} from './model.js?v=1.1.0';

export function icon(name, className='') {
  const paths={
    electricity:'<path d="M14 2L4 14h7l-1 8 10-13h-7Z"/>',
    waves:'<path d="M6 3C-1 9 12 13 5 21M13 3C6 9 19 13 12 21M20 3C13 9 26 13 19 21"/>',
    ratio:'<path d="m12 3 10 6-10 6L2 9Z M2 15l10 6 10-6"/>',
    starts:'<path d="M4 20V14M9 20V10M14 20V6M19 20V2"/>',
    menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',
    refresh:'<path d="M20 7v5h-5M4 17v-5h5M5.6 7a7.5 7.5 0 0 1 12.7-1L20 9M4 15l1.7 3A7.5 7.5 0 0 0 18.4 17"/>',
    cloud:'<path d="M6 19a5 5 0 0 1-1-9.9A7 7 0 0 1 18.4 8a5.5 5.5 0 0 1-.9 11Z"/>',
    arrow:'<path d="m9 5 7 7-7 7"/>',
    eye:'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    heat:'<path d="M5 5v14M10 5v14M15 5v14M20 5v14M3 8h19M3 16h19"/>',
    clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    check:'<path d="m5 12 4 4L19 6"/>',
    alert:'<path d="m12 3 10 18H2Z M12 9v5M12 17v.1"/>',
  };
  return `<svg class="ui-icon ${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]||paths.heat}</svg>`;
}

export function pumpIcon(className='') {
  return `<svg class="pump-art ${className}" viewBox="0 0 120 120" aria-hidden="true"><circle class="pump-halo" cx="60" cy="60" r="50" fill="none" stroke="#659d79" stroke-width="3"/><circle cx="60" cy="60" r="46" fill="#f0efeb"/><path d="M8 60h104" stroke="#387357" stroke-width="9"/><circle cx="60" cy="60" r="42" fill="#d0e4d2" stroke="#2a654c" stroke-width="3"/><circle cx="60" cy="60" r="35" fill="#8cbea0"/><path d="M48 35Q45 33 45 38v44q0 5 4 2l34-21q5-3 0-6Z" fill="#256647" stroke="#205a40" stroke-width="2"/><path d="M31 59a29 29 0 0 1 29-29" fill="none" stroke="#fff" stroke-width="2" opacity=".6"/></svg>`;
}

export function outdoorUnit(x,y,running=false) {
  return `<g transform="translate(${x} ${y})"><rect x="7" y="103" width="14" height="8" rx="2" fill="#7f8a8d"/><rect x="102" y="103" width="14" height="8" rx="2" fill="#7f8a8d"/><rect width="125" height="105" rx="8" fill="url(#case)" stroke="#405463" stroke-width="2"/><path d="M91 1v103" stroke="#aeb7bb"/><rect x="100" y="15" width="15" height="4" rx="2" fill="#8f999b"/><circle cx="47" cy="53" r="35" fill="#52616c" stroke="#344956" stroke-width="2"/><g class="fan-blades ${running?'running':''}">${[0,60,120,180,240,300].map(a=>`<path d="M47 53q-27-28-3-31 16 0 8 28Z" fill="#b8bfc0" stroke="#dbe0df" transform="rotate(${a} 47 53)"/>`).join('')}</g><circle cx="47" cy="53" r="31" fill="none" stroke="#d8dddd"/><circle cx="47" cy="53" r="7" fill="#eceded"/><path d="M99 75h17m-17 6h17m-17 6h17" stroke="#b3bbbd"/></g>`;
}

export function tank(x,y,w,h,coil=false) {
  return `<g transform="translate(${x} ${y})"><path d="M0 11Q0-3 ${w/2}-3T${w} 11v${h-23}q0 13-${w/2} 13T0 ${h-12}Z" fill="url(#water)" stroke="#3d5360" stroke-width="2"/><ellipse cx="${w/2}" cy="11" rx="${w/2}" ry="12" fill="#eec4ad" stroke="#bd6a47" stroke-width="2"/><path d="M${w/2} -1v-5" stroke="#405463" stroke-width="3"/>${coil?`<path d="M0 ${h-58}h${w*.65}q11 0 0 8H${w*.28}q-11 0 0 8h${w*.37}q11 0 0 8H${w*.28}q-11 0 0 8H${w/2}v28" fill="none" stroke="#bd6244" stroke-width="4"/>`:''}</g>`;
}

// Each path follows the water direction. Base pipes and animated overlays share
// geometry, including the internal heat-exchanger paths. The two return tees
// require different directions for DHW (upper inlet) and buffer (lower inlet).
const FLOW_PATHS={
  supply1:'M290 137h20q16 0 16 16v62q0 15 15 15',
  supply2:'M290 350h20q16 0 16-16v-89q0-15 15-15',
  common:'M341 230H570',
  dhwSupply:'M570 230v-57q0-16 16-16h108',
  dhwCoil:'M694 157H743q12 0 0 8H716q-12 0 0 8H743q12 0 0 8H716q-12 0 0 8H732V215',
  dhwReturn:'M732 215v37q0 14-14 14H355',
  heatingSupply:'M570 230v99q0 16 16 16h24',
  heatingExchanger:'M610 345h14q6 0 6 6v20q0 6-6 6H610',
  heatingReturn:'M610 377h-15v37H355',
  dhwReturn1:'M355 266V160H290',
  dhwReturn2:'M355 266v148H302q-13 0-13-13v-27',
  heatingReturn1:'M355 414V160H290',
  heatingReturn2:'M355 414H302q-13 0-13-13v-27',
  unknownReturn1:'M355 215V160H290',
  unknownReturn2:'M355 414H302q-13 0-13-13v-27',
  chargeExchanger:'M674 379h-14q-6 0-6-6v-22q0-6 6-6H674',
  chargeSupply:'M674 345H727',
  chargeTank:'M727 345h23q8 0 8 8v18q0 8-8 8H727',
  chargeReturn:'M727 379H674',
  radiatorTank:'M805 379h-20q-8 0-8-8v-18q0-8 8-8H805',
  radiatorSupply:'M805 345h75v15h28',
  radiator:'M908 360h41q6 0 6 6v23q0 6-6 6h-27q-6 0-6-6v-10H908',
  radiatorReturn:'M908 379H805'
};
const pipe=(key,attrs='')=>`<path d="${FLOW_PATHS[key]}" ${attrs}/>`;

export function schematic({historyLabel='Verlauf anzeigen',speedId,powerId,tankId,bufferId,units,speed,power,tankTemp,bufferTemp,tankVolume,bufferVolume,pumpRunning=false,phase,bufferCharging=false,radiatorRunning=false}) {
  const history=id=>id?`data-history="${esc(id)}" role="button" tabindex="0" aria-label="${esc(historyLabel)}: ${esc(id)}"`:'';
  const flowing=units.some(u=>u.flowing), hot=[],cold=[];
  const move=(list,key,branch='')=>list.push(pipe(key,`data-key="${key}" data-flow="${key}"${branch?` data-branch="${branch}"`:''}`));
  units.slice(0,2).forEach((u,i)=>{
    if(!u.flowing)return;
    move(hot,`supply${i+1}`);
    move(cold,`${phase==='dhw'?'dhw':phase==='heating'?'heating':'unknown'}Return${i+1}`);
  });
  if(flowing){
    move(hot,'common');
    if(phase==='dhw'){
      for(const key of ['dhwSupply','dhwCoil'])move(hot,key,'dhw');
      move(cold,'dhwReturn','dhw');
    }else if(phase==='heating'){
      for(const key of ['heatingSupply','heatingExchanger'])move(hot,key,'heating');
      move(cold,'heatingReturn','heating');
    }
  }
  // The plate exchanger separates primary and secondary water. Never infer
  // either secondary pump from compressor operation or primary flow alone.
  if(bufferCharging){
    for(const key of ['chargeExchanger','chargeSupply','chargeTank'])move(hot,key,'buffer-charge');
    move(cold,'chargeReturn','buffer-charge');
  }
  if(radiatorRunning){
    for(const key of ['radiatorTank','radiatorSupply','radiator'])move(hot,key,'radiators');
    move(cold,'radiatorReturn','radiators');
  }
  const unitLabels=units.slice(0,2).map((u,i)=>{
    const y=68+i*213;
    return `<g class="schematic-unit" data-unit="${esc(u.slave)}"><text x="26" y="${y-18}" class="svg-title">Wärmepumpe ${esc(u.slave)}</text>${outdoorUnit(26,y,u.fanRunning)}<rect x="160" y="${y}" width="127" height="107" rx="9" fill="var(--surface-inset)"/><text x="173" y="${y+21}" class="svg-muted">Verdichter</text><text x="173" y="${y+45}" class="svg-value" ${history(u.frequencyId)}>${esc(u.frequency)}</text><text x="173" y="${y+70}" class="svg-muted">Vorlauf</text><text x="275" y="${y+70}" text-anchor="end" class="hot-text" ${history(u.supplyId)}>${esc(u.supply)}</text><text x="173" y="${y+93}" class="svg-muted">Rücklauf</text><text x="275" y="${y+93}" text-anchor="end" class="cold-text" ${history(u.returnId)}>${esc(u.return)}</text></g>`;
  }).join('');
  return `<svg class="plant-svg" viewBox="0 0 1000 470" role="group" aria-label="Hydraulikschema: zwei parallele Wärmepumpen, gemeinsame Zusatzpumpe vor dem Umschaltventil. Warmwasserspeicher und Plattenwärmetauscher am Heizpuffer. Separater Rücklauf.">
    <defs><linearGradient id="case" x2="1" y2="1"><stop stop-color="#fcfcf9"/><stop offset="1" stop-color="#dbdeda"/></linearGradient><linearGradient id="water" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#e9b69a"/><stop offset=".48" stop-color="#e8d5c7"/><stop offset="1" stop-color="#abc8d9"/></linearGradient><linearGradient id="exchanger-primary" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#d17b52"/><stop offset="1" stop-color="#74a5bd"/></linearGradient><mask id="supply-crossings"><rect width="1000" height="470" fill="white"/><path d="M355 218v24M558 266h24" stroke="black" stroke-width="11"/><circle cx="427" cy="230" r="28" fill="black"/><rect x="554" y="213" width="29" height="34" fill="black"/></mask></defs>
    <g class="hot-pipe">${['supply1','supply2','common','dhwSupply','heatingSupply'].map(key=>pipe(key)).join('')}</g>
    <g fill="none" stroke="var(--surface)" stroke-width="11"><path d="M355 218v24M558 266h24"/></g>
    <g class="cold-pipe">${['dhwReturn','dhwReturn1','dhwReturn2','heatingReturn'].map(key=>pipe(key)).join('')}</g>
    <g class="hot-pipe">${['chargeSupply','radiatorSupply'].map(key=>pipe(key)).join('')}</g><g class="cold-pipe">${['chargeReturn','radiatorReturn'].map(key=>pipe(key)).join('')}</g>
    ${unitLabels}
    <circle cx="341" cy="230" r="5" fill="#c75a35"/><circle cx="355" cy="414" r="5" fill="#4d91b4"/>
    <g class="schematic-pump ${pumpRunning?'running':''}" transform="translate(395 198)"><circle class="pump-halo" cx="32" cy="32" r="32" fill="none" stroke="#659d79" stroke-width="2"/><circle cx="32" cy="32" r="28" fill="#b8d5bd" stroke="#2d6e50" stroke-width="2.5"/><path d="M22 14q-2-1-2 2v33q0 3 3 1l26-16q3-2 0-4Z" fill="#286948"/></g>
    <text x="427" y="175" text-anchor="middle" class="svg-title">Zusatzpumpe</text><text x="427" y="197" text-anchor="middle" class="svg-value" ${history(speedId)}>${esc(speed)}</text><text x="427" y="288" text-anchor="middle" class="svg-title" ${history(powerId)}>${esc(power)}</text>
    <g stroke="#62727a" stroke-width="2" fill="#bdc4c7"><path d="m555 218 15 12-15 12Z M581 214l-11 16-8-16Z M581 246l-11-16-8 16Z"/><path d="M570 204v-8"/></g><text x="568" y="183" text-anchor="middle" class="svg-muted">3/2-Wege-Ventil</text>
    ${tank(694,62,76,153)}<g class="hot-pipe">${pipe('dhwCoil')}</g><text x="791" y="76" class="svg-title">Warmwasser</text><text x="791" y="99" class="svg-muted">${esc(tankVolume)}</text><text x="791" y="130" class="svg-temp hot-text" ${history(tankId)}>${esc(tankTemp)}</text><text x="791" y="157" class="svg-muted">Kleiner interner</text><text x="791" y="176" class="svg-muted">Wärmetauscher</text>
    <rect x="610" y="320" width="64" height="81" rx="6" fill="#e7e8e3" stroke="#526671" stroke-width="2"/>${Array.from({length:7},(_,i)=>`<path d="M${618+i*8} 329v62" stroke="${i%2?'#7997a3':'#b97254'}" stroke-width="3"/>`).join('')}
    <g class="exchanger-paths">${pipe('heatingExchanger')}${pipe('chargeExchanger')}</g>
    <text x="642" y="438" text-anchor="middle" class="svg-muted">Plattenwärmetauscher</text>
    ${tank(727,292,78,128)}<text x="766" y="285" text-anchor="middle" class="svg-title">Heizungspuffer</text><text x="820" y="305" class="svg-muted">${esc(bufferVolume)}</text><text x="820" y="332" class="svg-temp hot-text" ${history(bufferId)}>${esc(bufferTemp)}</text>
    <g transform="translate(908 350)" stroke="#607581" stroke-width="2"><rect width="62" height="61" rx="4" fill="#f4f3ef"/>${Array.from({length:7},(_,i)=>`<path d="M${7+i*8} 7v47"/>`).join('')}<path d="M62 10h6v8h-6"/></g><text x="939" y="434" text-anchor="middle" class="svg-muted">Heizkörper</text>
    <g class="flow-motion hot-motion" data-key="supply-motion" mask="url(#supply-crossings)">${hot.join('')}</g>
    <g class="flow-motion cold-motion" data-key="return-motion">${cold.join('')}</g>
  </svg>`;
}

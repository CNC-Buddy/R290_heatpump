/* Electricity overview: isolated local fixture, no Home Assistant access. */
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE?pathToFileURL(path.join(process.env.PLAYWRIGHT_MODULE,'index.mjs')).href:'playwright');
const server=createServer(async(req,res)=>{
 const name=new URL(req.url,'http://localhost').pathname;
 if(name==='/'){res.setHeader('Content-Type','text/html');res.end('<!doctype html><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0}</style><script type="module" src="/fixture.mjs"></script>');return;}
 const file=name==='/fixture.mjs'?path.join(root,'tests/frontend-fixture.mjs'):/^\/r290_heatpump_static\/[a-z0-9-]+\.(js|css|json)$/.test(name)?path.join(root,'custom_components/r290_heatpump/frontend',path.basename(name)):null;
 if(!file){res.writeHead(404);res.end();return;}
 res.setHeader('Content-Type',file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':'text/javascript');res.end(await readFile(file));
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
let browser,checks=0;const pass=text=>{checks++;console.log('PASS '+text);};
try{
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE});
 const page=await browser.newPage({viewport:{width:1800,height:1250}}),base=`http://127.0.0.1:${server.address().port}`,errors=[];
 page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());
 await page.goto(base);await page.getByRole('heading',{name:'Anlagenübersicht'}).waitFor();
 assert.equal(await page.locator('.electric-overview').count(),0);
 await page.evaluate(async()=>{
  for(const [id,state,unit] of [['pv',6800,'W'],['house',3.6,'kW'],['battery',2400,'W'],['soc',72,'%'],['grid',-.8,'kW'],['hp',2400,'W'],['energy',300,'kWh']])fixture.states['sensor.test_'+id]={entity_id:'sensor.test_'+id,state:String(state),attributes:{unit_of_measurement:unit,friendly_name:'Test '+id},last_reported:new Date().toISOString()};
  fixture.data.settings.electric={enabled:true,pv_power:'sensor.test_pv',house_power:'sensor.test_house',battery_power:'sensor.test_battery',battery_soc:'sensor.test_soc',grid_power:'sensor.test_grid',hp_power:'sensor.test_hp',battery_positive:'charge',grid_positive:'import'};
  const {preset}=await import('/r290_heatpump_static/schematic-presets.js');const catalog=await(await fetch('/r290_heatpump_static/schematic-catalog.json')).json();
  const graph=preset('full',catalog,panel);fixture.data.settings.schematic={revision:1,draft:graph,published:structuredClone(graph)};
  await panel.load();
 });
 const area=page.locator('.electric-overview'),item=kind=>area.locator(kind==='heat'?'.electric-heat':`[data-electric-item=${kind}]`);
 const assertConnected=async()=>{
  const issues=await area.evaluate(area=>{
   const grid=area.querySelector('.electric-flow-grid').getBoundingClientRect(),near=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y)<1;
   const ports=[...area.querySelectorAll('.electric-port')].map(el=>{const r=el.getBoundingClientRect();return{x:r.left+r.width/2-grid.left,y:r.top-grid.top};});
   const lines=[...area.querySelectorAll('.electric-wire')].map(el=>({el,points:el.getAttribute('d').match(/[ML][\d.]+ [\d.]+/g).map(s=>{const [x,y]=s.slice(1).split(' ').map(Number);return{x,y};})}));
   const onSegment=(p,a,b)=>Math.abs(Math.hypot(p.x-a.x,p.y-a.y)+Math.hypot(p.x-b.x,p.y-b.y)-Math.hypot(a.x-b.x,a.y-b.y))<.2;
   const issues=[];
   for(const line of lines)for(const end of [line.points[0],line.points.at(-1)])if(!ports.some(p=>near(p,end))&&!lines.some(other=>other!==line&&other.points.slice(1).some((b,i)=>onSegment(end,other.points[i],b))))issues.push('open end '+JSON.stringify(end));
   for(const port of ports)if(!lines.some(line=>[line.points[0],line.points.at(-1)].some(p=>near(p,port))))issues.push('unconnected component');
   for(let i=0;i<lines.length;i++)for(let j=i+1;j<lines.length;j++)for(let a=1;a<lines[i].points.length;a++)for(let b=1;b<lines[j].points.length;b++){
    const p=lines[i].points[a-1],q=lines[i].points[a],r=lines[j].points[b-1],s=lines[j].points[b];
    const overlap=(x1,x2,y1,y2)=>Math.min(Math.max(x1,x2),Math.max(y1,y2))-Math.max(Math.min(x1,x2),Math.min(y1,y2));
    if((p.x===q.x&&r.x===s.x&&p.x===r.x&&overlap(p.y,q.y,r.y,s.y)>1)||(p.y===q.y&&r.y===s.y&&p.y===r.y&&overlap(p.x,q.x,r.x,s.x)>1))issues.push('overlapping line sections');
   }
   return issues;
  });assert.deepEqual(issues,[]);
 };
 await page.locator('r290-schematic .sg-svg').waitFor();
 assert.match(await item('pv').textContent(),/6,8 kW/);assert.match(await item('house').textContent(),/3,6 kW/);assert.match(await item('battery').textContent(),/72 %.*Laden · 2,4 kW/s);assert.match(await item('grid').textContent(),/0,8 kW.*Einspeisung/s);
 assert.match(await item('heat').textContent(),/davon Wärmeerzeuger.*2,4 kW/s);
 assert.equal(await area.locator('.electric-route.has-flow').count(),7);
 assert.equal(await area.locator('[data-electric-route^="bus-"].has-flow').count(),3);
 assert.equal(await area.locator('[data-electric-route=branch-house].reverse').count(),1);
 assert.equal(await area.locator('[data-electric-route=branch-heat].reverse').count(),0);
 await assertConnected();
 assert.ok((await area.boundingBox()).y<(await page.locator('[data-key=plant-card]').boundingBox()).y);
 assert.equal(await page.locator('r290-schematic').evaluate(el=>el.graph.nodes.filter(n=>['pv','house','battery','grid'].includes(n.type)).length),0);
 assert.ok(await page.locator('r290-schematic .sg-svg').evaluate(el=>el.viewBox.baseVal.y>50));
 await page.screenshot({path:path.join(root,'artifacts/r290-electric-overview-b21-de.png'),fullPage:true});
 await area.screenshot({path:path.join(root,'artifacts/r290-electric-strip-b21-de.png')});
 assert.equal(await area.locator('[data-electric-item]').count(),4);assert.ok((await area.boundingBox()).height<250);
 assert.ok(await item('house').locator('.electric-heat').count());
 assert.ok(await area.locator('.electric-item-main').evaluateAll(els=>els.every(el=>getComputedStyle(el).borderTopWidth==='0px')));
 pass('compact four-component strip without tiles, shared heating meter beneath house total, connected animated bus');

 await page.evaluate(()=>{window.opened=[];panel.addEventListener('hass-more-info',e=>window.opened.push(e.detail));});
 await item('pv').locator('[data-history]').click();assert.equal(await page.evaluate(()=>window.opened.at(-1).entityId),'sensor.test_pv');
 await item('heat').locator('[data-history]').click();assert.equal(await page.evaluate(()=>window.opened.at(-1).entityId),'sensor.test_hp');
 const motion=area.locator('[data-electric-route=bus-pv] .electric-motion').first(),offset=()=>motion.evaluate(el=>getComputedStyle(el).offsetDistance);
 const before=await offset();await page.waitForTimeout(170);assert.notEqual(await offset(),before);
 await page.evaluate(async()=>{window.flowNode=panel.shadowRoot.querySelector('[data-electric-route=bus-pv] .electric-motion');await panel.load();});
 assert.ok(await page.evaluate(()=>window.flowNode===panel.shadowRoot.querySelector('[data-electric-route=bus-pv] .electric-motion')));
 await area.locator('[data-action=toggle-motion]').click();assert.equal(await motion.evaluate(el=>getComputedStyle(el).animationPlayState),'paused');
 await page.waitForTimeout(70);const paused=await offset();await page.waitForTimeout(170);assert.equal(await offset(),paused);
 await area.locator('[data-action=toggle-motion]').click();
 await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await motion.evaluate(el=>getComputedStyle(el).animationName),'none');await page.emulateMedia({reducedMotion:'no-preference'});
 pass('shared-meter history, actual moving flow, stable nodes on live updates, pause and reduced-motion preference');

 await page.evaluate(async()=>{fixture.data.settings.electric.battery_positive='discharge';fixture.data.settings.electric.grid_positive='export';await panel.load();});
 assert.match(await item('battery').textContent(),/Entladen/);assert.match(await item('grid').textContent(),/Netzbezug/);
 assert.equal(await area.locator('[data-electric-route=branch-battery].reverse').count(),0);
 assert.equal(await area.locator('[data-electric-route=branch-grid].reverse').count(),0);
 assert.equal(await area.locator('[data-electric-route^="bus-"].has-flow').count(),0);
 await page.evaluate(async()=>{fixture.data.settings.electric.battery_positive='unknown';fixture.data.settings.electric.grid_positive='unknown';fixture.states['sensor.test_pv'].last_reported=new Date(Date.now()-600000).toISOString();fixture.states['sensor.test_house'].state='0';await panel.load();});
 assert.equal(await area.locator('.electric-route.has-flow').count(),0);assert.match(await item('pv').textContent(),/Meldung veraltet/);assert.match(await item('house').textContent(),/0 kW.*Kein Leistungsfluss/s);assert.match(await item('battery').textContent(),/Richtung nicht festgelegt/);
 for(const value of ['unavailable','-10']){await page.evaluate(async value=>{fixture.states['sensor.test_hp'].state=value;await panel.load();},value);assert.equal(await area.locator('.electric-route.has-flow').count(),0);assert.match(await item('heat').textContent(),/Nicht verfügbar/);}
 await page.evaluate(async()=>{fixture.states['sensor.test_hp'].state='2400';fixture.states['sensor.test_hp'].last_reported=new Date(Date.now()-600000).toISOString();await panel.load();});
 assert.equal(await area.locator('.electric-route.has-flow').count(),0);assert.match(await item('heat').textContent(),/Meldung veraltet/);
 await page.evaluate(async()=>{fixture.states['sensor.test_hp'].last_reported=new Date().toISOString();await panel.load();});
 await page.evaluate(async()=>{fixture.states['sensor.test_battery'].state='unavailable';fixture.states['sensor.test_soc'].state='101';fixture.states['sensor.test_house'].attributes.unit_of_measurement='kWh';await panel.load();});
 assert.match(await item('battery').textContent(),/Nicht verfügbar/);assert.doesNotMatch(await item('battery').textContent(),/101/);assert.match(await item('house').textContent(),/Nicht verfügbar/);
 await page.evaluate(async()=>{for(const key of ['pv','house','battery','soc']){fixture.states['sensor.test_'+key].last_reported=new Date().toISOString();}fixture.states['sensor.test_house'].state='3.6';fixture.states['sensor.test_house'].attributes.unit_of_measurement='kW';fixture.states['sensor.test_battery'].state='2400';fixture.states['sensor.test_soc'].state='72';fixture.data.settings.electric.battery_positive='charge';fixture.data.settings.electric.grid_positive='import';await panel.load();});
 pass('opposite signs, unknown directions, stale/missing/invalid readings and real zero are distinguished');

 await page.evaluate(async()=>{fixture.states['sensor.test_pv'].state='0';fixture.states['sensor.test_battery'].state='-2400';fixture.states['sensor.test_grid'].state='1.2';fixture.states['sensor.test_hp'].state='0';await panel.load();});
 assert.match(await item('grid').textContent(),/Netzbezug/);assert.match(await item('battery').textContent(),/Entladen/);
 assert.equal(await area.locator('[data-electric-route^="bus-"].has-flow.reverse').count(),2);
 assert.equal(await area.locator('[data-electric-route=bus-pv].has-flow').count(),0);
 assert.equal(await area.locator('[data-electric-route=branch-heat].has-flow').count(),0);
 assert.match(await item('heat').textContent(),/0 kW/s);
 await page.evaluate(async()=>{fixture.states['sensor.test_pv'].state='6800';fixture.states['sensor.test_battery'].state='2400';fixture.states['sensor.test_grid'].state='-.8';fixture.states['sensor.test_hp'].state='2400';await panel.load();});
 pass('night-time battery and grid supply reverses main flow; inactive heat generators and zero-flow line stay still');

 // Derive house power only when no direct house source is assigned.
 await page.evaluate(()=>{window.electricBefore=structuredClone({config:fixture.data.settings.electric,states:fixture.states});});
 const setCalculation=async(pv,grid,battery,gridPositive='import',batteryPositive='charge')=>page.evaluate(async values=>{
  const [pv,grid,battery,gridPositive,batteryPositive]=values;
  Object.assign(fixture.data.settings.electric,{house_power:'',grid_positive:gridPositive,battery_positive:batteryPositive});
  for(const [key,state] of Object.entries({pv,grid,battery})){const s=fixture.states['sensor.test_'+key];s.state=String(state);s.attributes.unit_of_measurement='kW';s.last_reported=new Date().toISOString();}
  await panel.load();
 },[pv,grid,battery,gridPositive,batteryPositive]);
 const houseValue=item('house').locator('strong');
 await setCalculation(.85,3.18,0);
 await page.evaluate(async()=>{fixture.states['sensor.test_pv'].state='850';fixture.states['sensor.test_pv'].attributes.unit_of_measurement='W';fixture.states['sensor.test_hp'].state='3270';fixture.states['sensor.test_soc'].state='1';await panel.load();});
 assert.match(await houseValue.textContent(),/4,03 kW/);assert.match(await item('house').textContent(),/Berechnet.*3,27 kW/s);
 assert.equal(await area.locator('[data-electric-route=branch-house].has-flow.reverse').count(),1);
 assert.equal(await area.locator('[data-electric-route^="bus-"].has-flow').count(),3);
 await area.screenshot({path:path.join(root,'artifacts/r290-electric-calculated-b21-de.png')});
 await houseValue.locator('[data-history]').click();
 const sources=page.getByRole('dialog',{name:'Verlauf der Ausgangswerte'});await sources.waitFor();
 assert.equal(await sources.locator('[data-history]').count(),3);
 await sources.locator('[data-history="sensor.test_grid"]').click();assert.equal(await page.evaluate(()=>window.opened.at(-1).entityId),'sensor.test_grid');
 for(const [values,expected] of [ [[6.8,-.8,2.4],'3,6 kW'],[[6.8,.8,-2.4,'export','discharge'],'3,6 kW'],[[0,1.2,-2.4],'3,6 kW'],[[0,-1.2,2.4,'export','discharge'],'3,6 kW'],[[0,0,0,'unknown','unknown'],'0 kW'] ]){
  await setCalculation(...values);assert.equal(await houseValue.textContent(),expected);assert.match(await item('house').textContent(),/Berechnet/);
 }
 assert.equal(await area.locator('.electric-route.has-flow').count(),0);
 pass('unassigned house derives 4.03 kW from screenshot inputs, excludes Shelly submeter, supports all signs, real zero, flow and source histories');

 for(const mutate of [
  ()=>{fixture.states['sensor.test_pv'].last_reported=new Date(Date.now()-600000).toISOString();},
  ()=>{fixture.states['sensor.test_grid'].state='unavailable';},
  ()=>{fixture.states['sensor.test_battery'].attributes.unit_of_measurement='kWh';},
  ()=>{fixture.data.settings.electric.battery_power='';},
  ()=>{fixture.data.settings.electric.grid_positive='unknown';},
  ()=>{fixture.data.settings.electric.battery_positive='unknown';},
  ()=>{fixture.states['sensor.test_pv'].attributes.restored=true;},
  ()=>{fixture.data.settings.electric.grid_power='sensor.test_pv';},
 ]){
  await setCalculation(6.8,-.8,2.4);await page.evaluate(async source=>{(new Function(`return (${source})`))()();await panel.load();},mutate.toString());
  assert.equal(await houseValue.textContent(),'—');assert.match(await item('house').textContent(),/Berechnung:/);
  assert.equal(await area.locator('[data-electric-route=branch-house].has-flow').count(),0);assert.equal(await area.locator('[data-electric-route^="bus-"].has-flow').count(),0);
  await page.evaluate(()=>{Object.assign(fixture.data.settings.electric,electricBefore.config);for(const [id,state] of Object.entries(electricBefore.states))fixture.states[id]=structuredClone(state);});
 }
 await setCalculation(1,-3,0);assert.equal(await houseValue.textContent(),'—');assert.match(await item('house').textContent(),/Messwerte widersprüchlich/);
 await setCalculation(6.8,-.8,2.4);await page.evaluate(async()=>{fixture.data.settings.electric.house_power='sensor.test_house';fixture.states['sensor.test_house'].state='5';await panel.load();});
 assert.equal(await houseValue.textContent(),'5 kW');assert.doesNotMatch(await item('house').textContent(),/Berechnet/);
 await page.evaluate(async()=>{fixture.states['sensor.test_house'].state='unavailable';await panel.load();});assert.equal(await houseValue.textContent(),'—');assert.doesNotMatch(await item('house').textContent(),/Berechnet/);
 await page.evaluate(async()=>{Object.assign(fixture.data.settings.electric,electricBefore.config);for(const [id,state] of Object.entries(electricBefore.states))fixture.states[id]=structuredClone(state);await panel.load();});
 pass('missing, stale, invalid, restored, ambiguous-direction, duplicate and contradictory inputs suppress calculation; assigned house sensor always wins');

 await area.locator('[data-view=settings]').click();
 const form=page.locator('.electric-setup'),pv=form.locator('[data-electric=pv_power]');
 await form.screenshot({path:path.join(root,'artifacts/r290-electric-setup-b21-de.png')});
 assert.equal(await form.locator('[data-electric=hp_power]').evaluate(el=>el.value),'sensor.test_hp');assert.match(await form.textContent(),/Wärmepumpen und Heizstäbe/);
 await pv.locator('input').fill('sensor.test');assert.equal(await pv.getByRole('option').count(),5);assert.doesNotMatch(await pv.textContent(),/sensor.test_soc|sensor.test_energy/);
 await pv.getByRole('option').filter({hasText:'sensor.test_pv'}).click();
 const housePicker=form.locator('[data-electric=house_power]');
 await housePicker.locator('input').fill('');await housePicker.locator('input').press('Enter');await housePicker.locator('input').press('Tab');
 assert.equal(await housePicker.evaluate(el=>el.value),'');
 await form.locator('[data-electric=grid_positive]').selectOption('export');
 await page.getByRole('button',{name:'EN',exact:true}).click();assert.equal(await form.locator('[data-electric=grid_positive]').inputValue(),'export');assert.equal(await pv.evaluate(el=>el.value),'sensor.test_pv');
 assert.match(await form.textContent(),/Positive battery value means/);
 await form.locator('[data-electric=enabled]').uncheck();await form.locator('[data-action=save-settings]').click();await page.waitForFunction(()=>!panel._editingSettings);
 await page.locator('.app-header [data-view=overview]').click();assert.equal(await area.count(),0);
 await page.locator('.app-header [data-view=settings]').click();assert.equal(await pv.evaluate(el=>el.value),'sensor.test_pv');assert.equal(await form.locator('[data-electric=grid_positive]').inputValue(),'export');
 await form.locator('[data-electric=enabled]').check();await form.locator('[data-action=save-settings]').click();await page.waitForFunction(()=>!panel._editingSettings);
 assert.equal(await page.evaluate(()=>fixture.data.settings.electric.house_power),'');
 pass('filtered searchable setup mappings, DE/EN draft preservation, persisted disable/re-enable without losing assignments');

 await page.locator('.section-tabs [data-view=schematic]').click();
 const editor=page.locator('r290-schematic[data-mode=editor]');await editor.locator('#component').waitFor();
 assert.equal(await editor.locator('#component option').evaluateAll(els=>els.filter(el=>['pv','battery','house','grid'].includes(el.value)).length),0);
 assert.equal(await editor.locator('#preset option[value=full_pv]').count(),0);assert.equal(await editor.locator('#component option[value=heater]').count(),1);
 await page.evaluate(async()=>{fixture.data.settings.electric.grid_positive='import';await panel.load();});
 await page.locator('.app-header [data-view=overview]').click();
 for(const width of [1800,1280,768,390]){
  await page.setViewportSize({width,height:1000});
  for(const lang of ['DE','EN']){
   await page.getByRole('button',{name:lang,exact:true}).click();
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   assert.ok(await area.evaluate(el=>el.scrollWidth<=el.clientWidth+1));
   for(const kind of ['pv','house','battery','grid'])assert.ok(await item(kind).locator('.electric-readings').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
   await assertConnected();
   assert.equal(await area.locator('.electric-route.has-flow').count(),7);
   assert.match(await item('house').textContent(),lang==='DE'?/Berechnet/:/Calculated/);
  }
 }
 await area.screenshot({path:path.join(root,'artifacts/r290-electric-overview-b21-mobile-en.png'),style:'.toast{visibility:hidden}'});
 await page.evaluate(()=>{panel._hass.connected=false;panel.render();});assert.equal(await area.locator('.electric-route.has-flow').count(),0);assert.match(await item('heat').textContent(),/Disconnected/);
 assert.equal(await houseValue.textContent(),'—');assert.match(await item('house').textContent(),/Calculation: Disconnected/);
 assert.equal(await page.evaluate(()=>fixture.writes.length),0);assert.deepEqual(errors,[]);
 pass('hydraulic editor offers no PV components, heaters remain; four viewport sizes and two languages without overflow or device writes');
 console.log(JSON.stringify({passed:checks}));
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}

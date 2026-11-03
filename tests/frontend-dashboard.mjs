/* Optional heat sources: isolated local fixture, no Home Assistant access. */
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
 const page=await browser.newPage({viewport:{width:1700,height:1100}}),base=`http://127.0.0.1:${server.address().port}`,errors=[];
 page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());
 await page.goto(base);await page.getByRole('heading',{name:'Anlagenübersicht'}).waitFor();
 assert.equal(await page.locator('.app-header .nav').count(),5);
 await page.locator('.app-header [data-view=service]').click();
 assert.equal(await page.locator('.section-tabs button').count(),6);assert.equal(await page.locator('[data-service-test]').count(),0);
 await page.locator('.section-tabs [data-view=factory]').click();assert.equal(await page.locator('[data-service-test]').count(),5);
 await page.locator('.section-tabs [data-view=system]').click();assert.equal(await page.locator('#parameter-table tbody tr').count(),263);
 await page.locator('.app-header [data-view=parameters]').click();assert.equal(await page.locator('[data-parameter-tab=all],[data-parameter-tab=devices]').count(),0);
 await page.locator('.app-header [data-view=settings]').click();assert.equal(await page.locator('.section-tabs button').count(),3);
 await page.locator('.section-tabs [data-view=schematic]').click();const editor=page.locator('r290-schematic[data-mode=editor]');
 await editor.locator('#preset').selectOption('full');await editor.locator('[data-action=preset]').click();
 const edge=await editor.evaluate(el=>el.graph.edges.find(e=>e.from.node==='we2'&&e.from.port==='supply'));
 await editor.locator(`.sg-edge[data-edge="${edge.id}"] .sg-hit`).dispatchEvent('click');
 const handle=editor.locator('[data-segment]').first();await handle.scrollIntoViewIfNeeded();const box=await handle.boundingBox();
 const before=await editor.evaluate(el=>structuredClone(el.graph));
 await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2,box.y+box.height/2+36,{steps:4});await page.mouse.up();
 const routed=await editor.evaluate((el,id)=>el.graph.edges.find(e=>e.id===id).points,edge.id);assert.ok(routed.length>0);assert.notDeepEqual(routed,edge.points);
 await editor.locator('[data-action=undo]').click();assert.deepEqual(await editor.evaluate(el=>el.graph),before);
 await editor.locator('[data-action=redo]').click();
 await editor.locator('.sg-node[data-node=we2]').dispatchEvent('click');await editor.locator('[data-property=x]').fill('80');await editor.locator('[data-property=x]').dispatchEvent('change');
 assert.deepEqual(await editor.evaluate((el,id)=>el.graph.edges.find(e=>e.id===id).points,edge.id),routed);
 pass('menu grouping; separated device info and factory tests; pipe dragging with undo/redo and retained manual route');
 await editor.locator('.sg-node[data-node=buffer]').dispatchEvent('click');await editor.locator('[data-zone-count]').selectOption('4');
 for(const [i,id] of ['sensor.tank','sensor.buffer','sensor.radiator_supply','sensor.radiator_return'].entries()){
   const picker=editor.locator(`[data-zone-entity="${i}"]`);await picker.locator('input').fill(id);await picker.getByRole('option').filter({hasText:id}).first().click();
 }
 await editor.locator('[data-zone-height="1"]').fill('40');await editor.locator('[data-zone-height="1"]').dispatchEvent('change');
 assert.equal(await editor.locator('[data-node=buffer] .sg-tank-zones [data-reading]').count(),4);
 await editor.locator('#component').selectOption('heater');await editor.locator('[data-action=add]').click();
 await page.keyboard.press('Enter');
 await editor.locator('[data-tank]').selectOption('buffer');
 const attached=await editor.evaluate(el=>structuredClone(el.graph.nodes.find(n=>n.type==='heater')));
 await editor.locator('.sg-node[data-node=buffer]').dispatchEvent('click');const oldY=Number(await editor.locator('[data-property=y]').inputValue());
 await editor.locator('[data-property=y]').fill(String(oldY+30));await editor.locator('[data-property=y]').dispatchEvent('change');
 assert.equal(await editor.evaluate(el=>el.graph.nodes.find(n=>n.type==='heater').y),attached.y+30);
 await editor.locator('[data-action=publish]').click();await page.waitForFunction(()=>fixture.data.settings.schematic?.published);
 await page.locator('.app-header [data-view=overview]').click();const live=page.locator('r290-schematic[data-mode=live]');
 await live.locator('[data-chart="tank-buffer"] .series').first().waitFor();assert.equal(await live.locator('[data-chart="tank-buffer"] .series').count(),4);
 await page.evaluate(()=>{window.popup=null;panel.showHistory=id=>window.popup=id;});await live.locator('[data-node=buffer] .sg-tank-zones [data-reading]').first().click();assert.equal(await page.evaluate(()=>popup),'sensor.tank');
 await live.screenshot({path:path.join(root,'artifacts/r290-tank-zones-live-de.png')});
 await page.evaluate(()=>{fixture.states['sensor.tank'].state='unavailable';panel.render();});assert.match(await live.locator('[data-node=buffer] .sg-tank-zones').textContent(),/—/);
 await page.evaluate(()=>{fixture.states['sensor.tank'].state='53.8';panel.render();});
 pass('four temperature zones, sensor heights, heater mounting and following tank, saved topology, missing values and history clicks');
 const tankChart=live.locator('[data-chart="tank-buffer"]');await tankChart.locator('[data-chart-toggle]').first().click();assert.equal(await tankChart.locator('.series').count(),3);await tankChart.locator('[data-chart-toggle]').first().click();
 const svg=tankChart.locator('svg');await svg.scrollIntoViewIfNeeded();const rect=await svg.boundingBox();await page.mouse.move(rect.x+rect.width/2,rect.y+rect.height/2);
 assert.equal(await tankChart.locator('.chart-tooltip').isVisible(),true);assert.match(await tankChart.locator('.chart-tooltip').innerText(),/°C/);await page.evaluate(()=>panel.render());assert.equal(await tankChart.locator('.chart-tooltip').isVisible(),true);
 await tankChart.locator('[data-chart-config]').click();await page.locator('dialog [name=chart-days]').selectOption('7');
 while(await page.locator('dialog [name=chart-source]:checked').count())await page.locator('dialog [name=chart-source]:checked').first().uncheck();await page.locator('dialog [value="sensor.tank"][name=chart-source]').check();await page.locator('dialog [value="sensor.buffer"][name=chart-source]').check();
 await page.getByRole('button',{name:'Bestätigen',exact:true}).click();await page.waitForFunction(()=>fixture.data.settings.charts?.['tank-buffer']?.days===7);
 await page.waitForFunction(()=>fixture.calls.some(m=>m.type.endsWith('/history')&&m.days===7&&m.entity_ids.length===2));
 await page.evaluate(()=>{panel._chartSlots={};panel.render();});await tankChart.locator('.series').first().waitFor();assert.equal(await tankChart.locator('.series').count(),2);
 assert.match(await tankChart.locator('.chart-tools').innerText(),/7 Tage/);
 await page.locator('.app-header [data-view=operating]').click();const chart=page.locator('[data-chart="operation-temperature"]');await chart.locator('.series').first().waitFor();
 const count=await chart.locator('.series').count();await chart.locator('[data-chart-toggle]').first().click();assert.equal(await chart.locator('.series').count(),count-1);
 await page.getByRole('button',{name:'EN',exact:true}).click();await chart.locator('[data-chart-config]').click();await page.getByRole('heading',{name:'Configure chart',exact:true}).waitFor();await page.getByRole('button',{name:'Cancel',exact:true}).click();
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.evaluate(()=>fixture.writes.length),0);assert.deepEqual(errors,[]);
 pass('hover values, legend toggles, durable chart period/source selection, local history requests, EN/mobile and zero device writes');

 await page.setViewportSize({width:1440,height:1000});await page.locator('.app-header [data-view=parameters]').click();
 for(const tab of ['Radiators','Hot water','Underfloor heating','Cooling']){
   await page.getByRole('tab',{name:tab,exact:true}).click();
   const curve=page.locator('.curve-chart');await curve.scrollIntoViewIfNeeded();const box=await curve.boundingBox();
   await page.mouse.move(0,0);await curve.hover();await page.locator('.curve-hover-tooltip').waitFor({state:'visible'});
   assert.match(await page.locator('.curve-hover-tooltip').innerText(),/Outside:.*°C/);await page.evaluate(()=>panel.render());assert.equal(await page.locator('.curve-hover-tooltip').isVisible(),true);
   await page.locator('[data-curve-series=live]').click();assert.equal(await page.locator('.curve-live').isVisible(),false);assert.equal(await page.locator('.curve-control-points').isVisible(),false);
   await page.locator('[data-curve-series=live]').click();assert.equal(await page.locator('.curve-live').isVisible(),true);
 }
 assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>fixture.writes.length),0);
 pass('all four heating/cooling curves show hover values and toggle line plus control-point markers');
 console.log(JSON.stringify({passed:checks}));
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}

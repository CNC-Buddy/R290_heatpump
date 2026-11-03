/* Multi-point editor against a local HA double. Never connects to live devices. */
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
import {curveValue,pointError,insertPoint} from '../custom_components/r290_heatpump/frontend/curve-model.js';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const points=[{outdoor:-15,target:50},{outdoor:0,target:35},{outdoor:20,target:25}];
for(const [outside,target] of [[-40,50],[-15,50],[-5,40],[0,35],[10,30],[40,25]])assert.equal(curveValue({points},outside),target);
assert.equal(curveValue({points},NaN),null);
assert.ok(pointError([points[0],points[0]]));
assert.ok(pointError([{outdoor:0,target:true},points[2]]));
assert.equal(insertPoint(Array.from({length:10},(_,i)=>({outdoor:i,target:35}))),null);
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
 const page=await browser.newPage({viewport:{width:1500,height:1000}}),base=`http://127.0.0.1:${server.address().port}`,errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());
 await page.goto(base);await page.getByRole('heading',{name:'Anlagenübersicht'}).waitFor();
 assert.match(await page.locator('.site-context').innerText(), /v1\.1\.1/);
 await page.evaluate(()=>panel.navigate('parameters'));
 // The master alone supplies the control mode and target spread.
 assert.equal(await page.locator('.curve-estimate').count(),1);
 assert.match(await page.locator('#curve-estimates').innerText(),/Vorlauf · Prognose/);
 assert.equal((await page.locator('#curve-estimates strong').innerText()).replace(/\s+/g,' ').trim(),'34 °C');
 assert.match(await page.locator('#curve-estimates').innerText(),/P099 3 K/);
 assert.doesNotMatch(await page.locator('#curve-estimates').innerText(),/P099 8 K/);
 await page.evaluate(()=>{fixture.states['number.p116_1'].state='1'; panel.render();});
 assert.match(await page.locator('#curve-estimates').innerText(),/Rücklauf · Prognose/);
 assert.equal((await page.locator('#curve-estimates strong').innerText()).replace(/\s+/g,' ').trim(),'28 °C');
 await page.evaluate(()=>{fixture.states['number.p099_1'].state='unavailable'; panel.render();});
 assert.equal(await page.locator('.curve-estimate').count(),0);
 assert.match(await page.locator('#curve-estimates').innerText(),/Prognose nicht verfügbar/);
 await page.evaluate(()=>{fixture.states['number.p116_1'].state='0';fixture.states['number.p099_1'].state='3'; panel.render();});
 pass('master P116 and P099, reverse control and missing data');
 await page.getByRole('tab',{name:'Kühlung',exact:true}).click();
 assert.equal(await page.locator('.curve-estimate').count(),1);
 assert.equal((await page.locator('#curve-estimates strong').innerText()).replace(/\s+/g,' ').trim(),'28 °C');
 await page.evaluate(()=>{fixture.states['number.p116_1'].state='1'; panel.render();});
 assert.equal((await page.locator('#curve-estimates strong').innerText()).replace(/\s+/g,' ').trim(),'34 °C');
 await page.evaluate(()=>{fixture.states['number.p116_1'].state='0'; panel.render();});
 await page.getByRole('tab',{name:'Heizkörper',exact:true}).click();
 pass('cooling forecast reverses the flow and return temperature difference');
 const add=()=>page.locator('[data-parameter-action="add-point"]');
 assert.ok(await add().isDisabled());assert.equal(await page.locator('[data-point-handle]').count(),0);
 await page.getByRole('button',{name:'Bearbeitung freigeben',exact:true}).click();
 await add().click();assert.equal(await page.locator('[data-point-row]').count(),3);
 await page.getByRole('spinbutton',{name:'Außen · Stützpunkt 2',exact:true}).fill('0');
 await page.getByRole('spinbutton',{name:'Soll · Stützpunkt 2',exact:true}).fill('35');
 await page.locator('[data-point-field]').first().blur();
 await page.evaluate(()=>{for(let i=0;i<5;i++)panel.render();});
 assert.equal(await page.getByRole('spinbutton',{name:'Soll · Stützpunkt 2',exact:true}).inputValue(),'35');
 assert.equal(await page.evaluate(()=>fixture.writes.length),0);
 await page.getByRole('button',{name:'Änderung prüfen →'}).click();
 assert.match(await page.locator('.point-review').innerText(),/35/);
 assert.equal(await page.evaluate(()=>fixture.writes.length),0);
 await page.getByRole('button',{name:'Bestätigen',exact:true}).click();
 await page.waitForFunction(()=>fixture.writes.length===1);
 assert.deepEqual(await page.evaluate(()=>fixture.writes[0].points),points);
 assert.equal(await page.evaluate(()=>fixture.writes[0].changes.length),0);
 await page.evaluate(()=>panel.load());assert.equal(await page.locator('[data-point-row]').count(),3);
 assert.equal(await page.locator('.curve-draft').count(),0);
 pass('locked editor, point preview, one confirmed save and retained point list after updates');

 await page.getByRole('spinbutton',{name:'Außen · Stützpunkt 2',exact:true}).fill('-15');
 assert.match(await page.locator('#curve-point-error').innerText(),/eindeutig ansteigen/);
 await page.getByRole('button',{name:'Änderung prüfen →'}).click();
 assert.equal(await page.locator('dialog').count(),0);assert.equal(await page.evaluate(()=>fixture.writes.length),1);
 await page.getByRole('button',{name:'Verwerfen',exact:true}).click();
 await page.getByRole('spinbutton',{name:'Soll · Stützpunkt 2',exact:true}).fill('34');
 await page.getByRole('button',{name:'Änderung prüfen →'}).click();
 await page.evaluate(()=>fixture.data.curves.find(c=>c.entry_id==='heatcurve').revision+='stale');
 await page.getByRole('button',{name:'Bestätigen',exact:true}).click();
 await page.locator('dialog [role="alert"]').filter({hasText:'Konfiguration geändert'}).waitFor();
 assert.equal(await page.evaluate(()=>fixture.writes.length),1);
 await page.getByRole('button',{name:'Abbrechen',exact:true}).click();await page.getByRole('button',{name:'Verwerfen',exact:true}).click();
 pass('duplicate outdoor temperatures are rejected and concurrent changes cannot overwrite saved points');

 for(const name of ['Warmwasser','Fußbodenheizung','Kühlung']){
   await page.getByRole('tab',{name,exact:true}).click();await add().click();
   assert.equal(await page.locator('[data-point-row]').count(),3);
 }
 await page.getByRole('tab',{name:'Heizkörper',exact:true}).click();
 assert.equal(await page.getByRole('spinbutton',{name:'Soll · Stützpunkt 2',exact:true}).inputValue(),'35');
 assert.equal(await page.locator('.curve-draft').count(),0);
 await page.getByRole('tab',{name:'Warmwasser',exact:true}).click();assert.equal(await page.locator('.curve-draft').count(),1);
 await page.getByRole('button',{name:'Verwerfen',exact:true}).click();
 for(const name of ['Fußbodenheizung','Kühlung']){await page.getByRole('tab',{name,exact:true}).click();await page.getByRole('button',{name:'Verwerfen',exact:true}).click();}
 await page.getByRole('tab',{name:'Heizkörper',exact:true}).click();
 for(let i=3;i<10;i++)await add().click();
 assert.equal(await page.locator('[data-point-row]').count(),10);assert.ok(await add().isDisabled());
 for(let i=10;i>2;i--)await page.locator('[data-parameter-action="remove-point"]').last().click();
 assert.equal(await page.locator('[data-point-row]').count(),2);
 assert.ok(await page.locator('[data-parameter-action="remove-point"]').first().isDisabled());
 await page.getByRole('button',{name:'Verwerfen',exact:true}).click();
 pass('all four curve drafts are independent and enforce the two-to-ten point limits');

 const handle=()=>page.locator('[data-point-handle="1"]');
 await handle().focus();await page.keyboard.press('ArrowUp');
 assert.equal(await page.getByRole('spinbutton',{name:'Soll · Stützpunkt 2',exact:true}).inputValue(),'35.1');
 await page.keyboard.press('Shift+ArrowLeft');
 assert.equal(await page.getByRole('spinbutton',{name:'Außen · Stützpunkt 2',exact:true}).inputValue(),'-1');
 const box=await handle().boundingBox();await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2+12,box.y+box.height/2-12,{steps:4});await page.mouse.up();
 assert.ok(Number(await page.getByRole('spinbutton',{name:'Soll · Stützpunkt 2',exact:true}).inputValue())>35.1);
 assert.equal(await page.evaluate(()=>fixture.writes.length),1);
 await page.evaluate(()=>{panel.shadowRoot.querySelector('.toast')?.remove();});
 await page.getByRole('button',{name:'EN',exact:true}).click();
 assert.equal(await page.getByRole('spinbutton',{name:'Target · control point 2',exact:true}).count(),1);
 await page.screenshot({path:path.join(root,'artifacts/r290-multipoint-curves-en.png'),fullPage:true});
 await page.getByRole('button',{name:'DE',exact:true}).click();
 await page.screenshot({path:path.join(root,'artifacts/r290-multipoint-curves-de.png'),fullPage:true});
 pass('keyboard and drag edit only a draft, with translated controls and preserved values');

 await page.getByRole('button',{name:'Verwerfen',exact:true}).click();
 await page.evaluate(()=>{panel.hass={...panel.hass,connected:false};panel.render();});
 assert.ok(await add().isDisabled());assert.equal(await page.locator('[data-point-handle]').count(),0);
 assert.ok(await page.locator('[data-point-field]').first().isDisabled());
 await page.evaluate(()=>{panel.hass={...panel.hass,connected:true};panel.render();});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:path.join(root,'artifacts/r290-multipoint-curves-mobile.png'),fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
 const mobile=await page.getByRole('spinbutton',{name:'Soll · Stützpunkt 2',exact:true});
 await mobile.fill('36');await mobile.blur();
 await page.evaluate(()=>{window.scrollTo(0,250);window.curveY=scrollY;panel.render();});
 assert.equal(await page.evaluate(()=>scrollY),await page.evaluate(()=>curveY));
 assert.equal(await mobile.inputValue(),'36');assert.equal(await page.evaluate(()=>fixture.writes.length),1);
 assert.deepEqual(errors,[]);
 pass('offline controls are blocked, mobile layout fits and live refresh preserves position and draft');
 console.log(`${checks} multi-point browser checks passed`);
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}

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
 await page.evaluate(()=>{fixture.data.sources={dhw_entity:'binary_sensor.dhw'};return panel.load();});
 const phaseCheck=await page.evaluate(async()=>{
   const {phaseSegments}=await import('/r290_heatpump_static/operating-data.js');
   const series={freq:{states:[[0,'40'],[40,'0'],[50,'unavailable']]},def:{states:[[0,'off'],[20,'on'],[30,'off']]},ww:{states:[[0,'off'],[10,'on'],[30,'unavailable']]}};
   return phaseSegments(series,{frequency:'freq',defrost:'def',dhw:'ww'},0,60).map(s=>[s.start,s.end,s.phase]);
 });
 assert.deepEqual(phaseCheck,[[0,10,'heating'],[10,20,'dhw'],[20,30,'defrost'],[30,40,'unknown'],[40,50,'idle'],[50,60,'unknown']]);
 await page.evaluate(()=>{fixture.data.settings.charts={'operation-temperature':{days:7,entity_ids:['sensor.tank','sensor.buffer'],revision:1}};return panel.load();});
 await page.evaluate(()=>panel.navigate('operation'));
 await page.getByRole('heading',{name:'Betriebsdaten.',exact:true}).waitFor();
 await page.locator('.phase-track').first().waitFor();
 assert.equal(await page.locator('.app-header .nav').count(),5);
 assert.equal(await page.locator('.phase-track').count(),2);
 assert.ok(await page.locator('.phase-track [title^=Warmwasser]').count()>0);
 assert.equal(await page.locator('[data-chart="operation-temperature"] .series').count(),2);
 assert.match(await page.locator('[data-chart="operation-temperature"] .chart-tools').innerText(),/7 Tage/);
 assert.match(await page.locator('.operating-quality').innerText(),/Zeitgrenzen.*unsicher/);
 await page.locator('.history-controls [data-days="1"]').click();
 await page.waitForFunction(()=>panel.history&&panel.days===1&&!panel._historyLoading);
 for(const key of ['operation-temperature','operation-frequency','analysis-power'])assert.match(await page.locator(`[data-chart="${key}"] .chart-tools`).innerText(),/24 Stunden/);
 await page.locator('[data-chart="analysis-power"] [data-chart-config]').click();
 await page.locator('dialog [name=chart-days]').selectOption('0.5');
 await page.getByRole('button',{name:'Bestätigen',exact:true}).click();
 await page.waitForFunction(()=>fixture.data.settings.charts['analysis-power']?.days===0.5);
 await page.waitForFunction(()=>panel._chartMeta['analysis-power'].end>0);
 assert.match(await page.locator('[data-chart="analysis-power"] .chart-tools').innerText(),/12 Stunden/);
 assert.equal(await page.evaluate(()=>panel.days),1);
 await page.locator('.history-controls [data-days="7"]').click();
 await page.waitForFunction(()=>panel.history&&panel.days===7&&!panel._historyLoading);
 for(const key of ['operation-temperature','operation-frequency','analysis-power'])assert.match(await page.locator(`[data-chart="${key}"] .chart-tools`).innerText(),/7 Tage/);
 await page.evaluate(()=>panel.shadowRoot.querySelector('.toast')?.remove());
 await page.screenshot({path:path.join(root,'artifacts/r290-operating-data-de.png'),fullPage:true});
 await page.getByRole('button',{name:'EN',exact:true}).click();
 await page.getByRole('heading',{name:'Operating data.',exact:true}).waitFor();
 await page.screenshot({path:path.join(root,'artifacts/r290-operating-data-en.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.waitForFunction(()=>[...panel.shadowRoot.querySelectorAll('.operating-chart svg')].every(svg=>Math.abs(svg.getBoundingClientRect().width-svg.viewBox.baseVal.width)<=1));
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await page.screenshot({path:path.join(root,'artifacts/r290-operating-data-mobile.png'),fullPage:true});
 await page.setViewportSize({width:1700,height:1100});
 assert.equal(await page.evaluate(()=>fixture.writes.length),0);
 pass('merged data view: phases with unknown gaps, saved chart settings, shared period override, per-chart persistence, DE/EN/mobile, no device writes');

 await page.evaluate(()=>{panel.unlocked=true;panel.query='P099';panel.navigate('system');});
 assert.equal(await page.locator('[data-edit]').count(),0);
 await page.locator('[data-action=system-unlock]').click();
 await page.locator('[name=system-unit]').selectOption('hp1');
 await page.locator('[name=system-password]').fill('1111');
 await page.getByRole('button',{name:'Confirm',exact:true}).click();
 assert.match(await page.locator('.dialog-error').innerText(),/does not match/);
 assert.equal(await page.locator('[name=system-password]').inputValue(),'');
 await page.locator('[name=system-password]').fill('2468');
 await page.getByRole('button',{name:'Confirm',exact:true}).click();
 await page.locator('[data-edit="number.p099_1"]').waitFor();
 assert.equal(await page.locator('[data-edit="number.p099_2"]').count(),0);
 assert.equal(await page.evaluate(()=>fixture.writes.length),0);
 await page.locator('[data-edit="number.p099_1"]').click();
 await page.locator('#new-value').fill('5');await page.getByRole('button',{name:'Confirm',exact:true}).click();
 await page.waitForFunction(()=>fixture.writes.length===1);
 await page.locator('[data-action=system-lock]').click();
 await page.waitForFunction(()=>!panel.data.system_access.hp1);
 assert.equal(await page.locator('[data-edit]').count(),0);
 await page.locator('[data-action=system-unlock]').click();
 await page.locator('[name=system-password]').fill('2468');await page.getByRole('button',{name:'Confirm',exact:true}).click();
 await page.locator('[data-edit="number.p099_1"]').waitFor();
 await page.evaluate(()=>{panel._loadedAt=Date.now()-601000;panel.render();});
 assert.equal(await page.locator('[data-edit]').count(),0);
 pass('P183 prompt, rejected password cleared, grant per device, confirmed edit, explicit lock and expiry hide system editors independently of curve editing');

 for(const language of ['de','en']){
   await page.getByRole('button',{name:language.toUpperCase(),exact:true}).click();
   await page.evaluate(()=>{panel.query='';panel.differences=false;panel.navigate('machine');});
   await page.getByRole('heading',{name:language==='en'?'Machine information':'Maschineninfo',exact:true}).first().waitFor();
   assert.equal(await page.locator('#parameter-table tbody tr').count(),36);
   assert.equal(await page.locator('[data-edit]').count(),0);
   for(const [tab,count] of [['main',36],['realtime',192],['user',12],['user2',15]]){
     if(tab!=='main'){
       await page.locator('.app-header [data-view=parameters]').click();
       assert.equal(await page.locator('[data-parameter-tab=main]').count(),0);
       await page.locator(`[data-parameter-tab="${tab}"]`).click();
     }
     assert.equal(await page.locator('#parameter-table tbody tr').count(),count);
     const descriptions=await page.locator('.parameter-description').allTextContents();
     assert.ok(descriptions.every(s=>s.length>20));
     assert.ok(descriptions.every(s=>!s.includes(language==='en'?'Keine dokumentierte Erklärung':'No documented explanation')));
     if(tab==='user'){
       await page.locator('#parameter-table summary').first().click();
       assert.match(await page.locator('.parameter-description').first().innerText(),language==='en'?/temperature/i:/temperatur/i);
     }
   }
 }
 assert.deepEqual(errors,[]);
 pass('all 255 main/realtime/user/user2 rows and their explanations available in both languages; machine information in Service');
 console.log(JSON.stringify({passed:checks}));
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}

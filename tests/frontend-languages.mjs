/* Isolated, loopback-only localization and offline diagnosis checks. */
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE?pathToFileURL(path.join(process.env.PLAYWRIGHT_MODULE,'index.mjs')).href:'playwright');
const server=createServer(async(req,res)=>{
  const pathname=new URL(req.url,'http://localhost').pathname;
  if(pathname==='/'){res.setHeader('Content-Type','text/html');res.end('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0}</style></head><body><script type="module" src="/fixture.mjs"></script></body></html>');return;}
  let file=pathname==='/fixture.mjs'?path.join(root,'tests/frontend-fixture.mjs'):pathname==='/diagnosis'?path.join(root,'artifacts/r290-register-diagnose.html'):null;
  if(/^\/r290_heatpump_static\/[a-z0-9-]+\.(js|css|json)$/.test(pathname))file=path.join(root,'custom_components/r290_heatpump/frontend',path.basename(pathname));
  if(!file){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',file.endsWith('.html')?'text/html':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':'text/javascript');res.end(await readFile(file));
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
let browser;const texts={};
try{
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE});
  const page=await browser.newPage({viewport:{width:1440,height:1050}}),base=`http://127.0.0.1:${server.address().port}`;
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());
  await page.goto(base);await page.getByRole('heading',{name:'Anlagenübersicht'}).waitFor();
  const modelChecks=await page.evaluate(async()=>{
    const {curveValue,defaultValue}=await import('/r290_heatpump_static/parameters.js?v=1.3.0');
    return {below:curveValue({t_out_min:-15,t_out_max:20,t_flow_min:25,t_flow_max:50},-20),above:curveValue({t_out_min:-15,t_out_max:20,t_flow_min:25,t_flow_max:50},25),mid:curveValue({t_out_min:-15,t_out_max:20,t_flow_min:25,t_flow_max:50},2.5),rising:curveValue({t_out_min:-15,t_out_max:20,t_flow_min:40,t_flow_max:25},2.5),missing:curveValue({t_out_min:-15,t_out_max:20,t_flow_min:25},5),zero:defaultValue({default_observed:0,default_manual:8}),manual:defaultValue({default_observed:null,default_manual:8})};
  });
  assert.deepEqual(modelChecks,{below:50,above:25,mid:37.5,rising:32.5,missing:null,zero:0,manual:8});
  await page.getByRole('button',{name:'EN',exact:true}).click();
  await page.getByRole('heading',{name:'Plant overview',exact:true}).waitFor();
  await page.reload();await page.getByRole('heading',{name:'Plant overview',exact:true}).waitFor();
  assert.equal(await page.locator('r290-control-panel').getAttribute('lang'),'en');
  for(const [view,label] of [['overview','Plant'],['pump','Auxiliary pump'],['operation','Operation'],['analysis','Energy'],['parameters','Parameters'],['faults','Fault history'],['diagnostics','Diagnostics'],['service','Service'],['settings','Setup']]){
    await page.evaluate(view=>panel.navigate(view),view);
    texts[view]=await page.locator('.content').innerText();
    if(view==='diagnostics'){
      assert.match(texts[view],/Automatic scheduler/);
      assert.match(texts[view],/Response time P95/);
      assert.ok(!texts[view].includes('Wartende Aufträge'));
      await page.locator('.bus-health summary').click();
      assert.match(await page.locator('.bus-health').innerText(),/Writes confirmed by readback/);
      await page.screenshot({path:path.join(root,'artifacts/r290-nextgen-communication-en.png')});
    }
    if(view==='parameters'){
      for(const name of ['Radiators','Hot water','Underfloor heating','Cooling']){
        if(name==='System parameters'){await page.locator('.app-header [data-view=service]').click();await page.locator('.section-tabs [data-view=system]').click();}else await page.getByRole('tab',{name,exact:true}).click();assert.equal(await page.locator('.curve-live').count(),1);
      }
      await page.getByRole('tab',{name:'Radiators',exact:true}).click();
      await page.screenshot({path:path.join(root,'artifacts/r290-curves-en.png'),fullPage:true});
      await page.getByRole('tab',{name:'PV & offsets',exact:true}).click();texts.pv=await page.locator('.curve-editor').innerText();
      await page.getByRole('tab',{name:'Fine tuning',exact:true}).click();texts.fine=await page.locator('.curve-editor').innerText();
      await page.locator('.app-header [data-view=service]').click();await page.locator('.section-tabs [data-view=system]').click();
      await page.getByRole('searchbox',{name:'Search parameters',exact:true}).fill('P100');
      assert.match(await page.locator('.default-value').innerText(),/^30/);
      await page.locator('#parameter-table summary').first().click();
      assert.ok((await page.locator('#parameter-table').innerText()).includes('separate auxiliary pump'));
      assert.ok(!(await page.locator('#parameter-table').innerText()).includes('.xlsx'));
      texts.devices=await page.locator('#parameter-table').innerText();
      await page.getByRole('searchbox',{name:'Search parameters',exact:true}).blur();
      await page.evaluate(()=>panel.load());
      assert.ok(await page.locator('#parameter-table details').first().evaluate(e=>e.open));
      await page.getByRole('searchbox',{name:'Search parameters',exact:true}).blur();
    }
    if(view==='settings'){
      await page.locator('[data-setting="name"]').fill('Unsaved plant name');
      await page.getByRole('button',{name:'DE',exact:true}).click();
      assert.equal(await page.locator('[data-setting="name"]').inputValue(),'Unsaved plant name');
      await page.getByRole('button',{name:'EN',exact:true}).click();
      const picker=page.locator('r290-entity-picker[data-setting="heat_energy_entity"]');
      await picker.getByRole('combobox').fill('sensor.heat');
      assert.ok(await picker.getByText(/1 results/).isVisible());
      await picker.getByRole('combobox').press('Escape');
      await page.getByRole('button',{name:'Discard',exact:true}).click();
    }
  }
  assert.equal(await page.evaluate(()=>fixture.writes.length),0);
  assert.ok(!texts.overview.includes('Leistungsaufnahme'));
  assert.ok(!texts.overview.includes('Speicherzweig'));
  assert.ok(!texts.overview.includes('Status unbekannt'));
  assert.ok(!texts.settings.includes('Warmwasserladung'));
  assert.ok(!texts.settings.includes('Nur Anzeige'));
  assert.ok(!texts.operation.includes('Vorlauf'));
  assert.ok(!texts.analysis.includes('Letzte Zustandsänderung'));
  await page.getByRole('button',{name:'Parameters',exact:true}).click();
  await page.locator('.app-header [data-view=service]').click();await page.locator('.section-tabs [data-view=system]').click();
  await page.getByRole('searchbox',{name:'Search parameters',exact:true}).fill('P169');
  await page.locator('#parameter-table summary').first().click();
  assert.match(await page.locator('.parameter-description').innerText(),/neither compressor output nor a staging delay/);
  assert.doesNotMatch(await page.locator('.parameter-description').innerText(),/chat.?gpt/i);
  await page.locator('.app-header [data-view=parameters]').click();
  await page.getByRole('tab',{name:'Realtime parameters',exact:true}).click();
  await page.getByRole('searchbox',{name:'Search parameters',exact:true}).fill('0x0057');
  assert.equal(await page.locator('#parameter-table tbody tr').count(),1);
  assert.equal(await page.locator('#parameter-table tr.diff').count(),0);
  await page.getByLabel('Differences only').check();
  await page.getByLabel('Differences only').blur();
  assert.equal(await page.locator('#parameter-table tbody tr').count(),0);
  await page.evaluate(()=>{fixture.states['sensor.pump_percent_2'].state='70';fixture.states['sensor.pump_pwm_2'].state='30';panel.hass={...panel.hass,states:{...fixture.states}};});
  await page.locator('#parameter-table tr.diff').waitFor({state:'visible'});
  assert.equal(await page.locator('#parameter-table tr.diff').count(),1);
  await page.evaluate(()=>{fixture.states['sensor.pump_percent_2'].state='65';fixture.states['sensor.pump_pwm_2'].state='35';panel.hass={...panel.hass,states:{...fixture.states}};});
  await page.locator('#parameter-table tr.diff').waitFor({state:'detached'});
  await page.getByLabel('Differences only').uncheck();
  assert.match(await page.locator('#parameter-table').innerText(),/Pump speed \(%\)/);
  assert.match(await page.locator('#parameter-table').innerText(),/Raw PWM/);
  assert.match(await page.locator('[data-key="sensor.pump_percent_1"]').innerText(),/65\s*%/);
  assert.match(await page.locator('[data-key="sensor.pump_pwm_1"]').innerText(),/35/);
  await page.evaluate(()=>{window.speedHistory=[];panel.addEventListener('hass-more-info',e=>speedHistory.push(e.detail));});
  await page.locator('[data-history="sensor.pump_percent_1"]').click();
  assert.deepEqual(await page.evaluate(()=>speedHistory.at(-1)),{entityId:'sensor.pump_percent_1',view:'info'});
  await page.getByRole('button',{name:'DE',exact:true}).click();
  assert.match(await page.locator('#parameter-table').innerText(),/Pumpendrehzahl \(%\)/);
  assert.match(await page.locator('#parameter-table').innerText(),/PWM-Rohwert/);
  await page.locator('#parameter-table summary').first().click();
  assert.match(await page.locator('.parameter-description').innerText(),/100 minus PWM/);
  await page.screenshot({path:path.join(root,'artifacts/r290-pump-percent-de.png'),fullPage:true});
  await page.getByRole('button',{name:'EN',exact:true}).click();
  await page.screenshot({path:path.join(root,'artifacts/r290-pump-percent-en.png'),fullPage:true});
  assert.equal(await page.evaluate(()=>fixture.writes.length),0);
  console.log('PASS separate percent/PWM values and history identities, bilingual pump explanation and corrected P169 help; no writes');
  await page.getByRole('tab',{name:'Radiators',exact:true}).click();await page.getByRole('tab',{name:'Base curve',exact:true}).click();
  await page.getByRole('button',{name:'Enable editing',exact:true}).click();
  await page.getByLabel('Setpoint · at cold point',{exact:true}).fill('49');
  await page.getByRole('button',{name:'DE',exact:true}).click();
  assert.equal(await page.getByLabel('Soll · am kalten Stützpunkt',{exact:true}).inputValue(),'49');
  await page.getByRole('button',{name:'EN',exact:true}).click();
  await page.getByRole('button',{name:'Review changes →',exact:true}).click();
  await page.getByRole('heading',{name:'Review curve changes',exact:true}).waitFor();
  assert.ok(await page.getByRole('button',{name:'Confirm',exact:true}).isVisible());
  await page.getByRole('button',{name:'Cancel',exact:true}).click();await page.getByRole('button',{name:'Discard',exact:true}).click();
  await page.getByRole('button',{name:'DE',exact:true}).click();await page.screenshot({path:path.join(root,'artifacts/r290-curves-de.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('button',{name:'EN',exact:true}).click();
  for(const name of ['Radiators','Hot water','Underfloor heating','Cooling','System parameters']){
    if(name==='System parameters'){await page.locator('.app-header [data-view=service]').click();await page.locator('.section-tabs [data-view=system]').click();}else await page.getByRole('tab',{name,exact:true}).click();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    if(name!=='System parameters')assert.equal(await page.locator('.parameter-tabs [aria-selected="true"]').evaluate(e=>{const p=e.parentElement.getBoundingClientRect(),b=e.getBoundingClientRect();return b.left>=p.left-1&&b.right<=p.right+1}),true);
  }
  await page.screenshot({path:path.join(root,'artifacts/r290-parameters-en-mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  await writeFile(path.join(root,'artifacts/ui-language-review.json'),JSON.stringify(texts,null,2));
  console.log('PASS DE/EN navigation, persisted preference, localized defaults/explanations, draft preservation, dialog, picker and mobile layout; no writes');
  await page.goto(base+'/diagnosis');await page.setViewportSize({width:1440,height:1050});
  assert.equal(await page.locator('#values tr').count(),11);
  await page.getByLabel('Nur veränderte Werte').check();
  assert.equal(await page.locator('#values tr').count(),1);
  assert.ok((await page.locator('#values').innerText()).includes('0x00ED'));
  await page.getByLabel('Nur veränderte Werte').uncheck();await page.getByLabel('Nur Werte ungleich 0').uncheck();
  assert.equal(await page.locator('#values tr').count(),128);
  await page.getByLabel('Nur Werte ungleich 0').check();
  await page.getByLabel('Zuordnung 0x00ED',{exact:true}).fill('Test annotation <script>');
  const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Zuordnungen exportieren'}).click();
  const downloaded=JSON.parse(await readFile(await (await downloadPromise).path(),'utf8'));
  assert.equal(downloaded.notes['237'],'Test annotation <script>');
  await page.reload();assert.equal(await page.getByLabel('Zuordnung 0x00ED',{exact:true}).inputValue(),'Test annotation <script>');
  await page.getByLabel('Zuordnung 0x00ED',{exact:true}).fill('');
  await page.screenshot({path:path.join(root,'artifacts/r290-register-diagnose.png'),fullPage:true});
  await page.getByRole('button',{name:'Integrationsprüfung'}).click();
  assert.equal(await page.locator('#counts tr').count(),5);
  assert.equal(await page.locator('#all-registers tr').count(),518);
  assert.deepEqual(errors,[]);
  console.log('PASS offline diagnosis: 128 received addresses, nonzero/change filters, safe editable notes, persistent export and all five workbook audits');
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}

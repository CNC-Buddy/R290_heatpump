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
 const page=await browser.newPage({viewport:{width:1500,height:1000}}),base=`http://127.0.0.1:${server.address().port}`,errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());
 await page.goto(base);await page.getByRole('heading',{name:'Anlagenübersicht'}).waitFor();
 assert.equal(await page.locator('[data-heat-source]').count(),0);
 await page.evaluate(async()=>{
  const put=(id,state,unit='',slug=null)=>{fixture.states[id]={entity_id:id,state:String(state),attributes:{friendly_name:id,unit_of_measurement:unit},last_reported:new Date().toISOString()};if(slug)fixture.data.entities.push({id,entry_id:'hp1',unique_id:`r290_heatpump_${slug}_slave_1`,disabled:false});};
  put('sensor.eh1','on','','relay_output_status_1_hot_water_electric_heating_status');
  put('sensor.eh2','off','','relay_output_status_1_air_conditioner_electric_heating_status');
  put('sensor.floor_eh','off','','relay_output_status_1_floor_heating_electric_heating_status');
  put('sensor.gas','on','','relay_output_status_3_gas_output_status');
  put('sensor.source_dhw',62,'°C','auxiliary_heating_source_hot_water_temperature_value');
  put('sensor.source_heating',55,'°C','auxiliary_heating_source_heating_temperature_value');
  put('binary_sensor.heater_feedback','on');put('sensor.heater_power',2.9,'kW');
  put('sensor.heater_energy',15,'kWh');put('sensor.secondary_heat',150,'kWh');
  fixture.states['number.p140_1'].state='0';fixture.states['number.p139_1'].state='0';
  await panel.load();
 });
 await page.locator('[data-view=settings]').first().click();
 const setup=page.locator('.heat-source-setup');
 await setup.locator('summary').first().click();
 await page.locator('[data-source=dhw_heater][data-source-field=enabled]').check();
 await page.locator('[data-source=dhw_heater][data-source-field=managed_by]').selectOption('heat_pump');
 await page.locator('[data-source=dhw_heater][data-source-field=entry_id]').selectOption('hp1');
 await page.locator('[data-source-suggest=dhw_heater]').click();
 assert.equal(await page.locator('[data-source=dhw_heater][data-source-field=request_entity]').evaluate(el=>el.value),'sensor.eh1');
 await page.getByRole('button',{name:'EN',exact:true}).click();
 assert.equal(await page.locator('[data-source=dhw_heater][data-source-field=enabled]').isChecked(),true);
 assert.equal(await page.locator('[data-source=dhw_heater][data-source-field=request_entity]').evaluate(el=>el.value),'sensor.eh1');
 await page.evaluate(()=>panel.load());
 await page.getByRole('button',{name:'Save heat sources',exact:true}).click();
 await page.waitForFunction(()=>fixture.data.settings.heat_sources?.dhw_heater.enabled);
 await page.locator('[data-view=overview]').first().click();
 assert.match(await page.locator('[data-heat-source=dhw_heater]').textContent(),/Requested · operation unconfirmed/);
 assert.equal(await page.locator('.source-glyph.active').count(),0);
 assert.equal(await page.evaluate(()=>fixture.writes.length),0);
 pass('optional setup, native suggestions, draft language switching, save without actuator commands');

 await page.evaluate(async()=>{
  const cfg=fixture.data.settings.heat_sources;
  Object.assign(cfg.dhw_heater,{feedback_entity:'binary_sensor.heater_feedback',power_entity:'sensor.heater_power',energy_entity:'sensor.heater_energy',electricity_scope:'included'});
  Object.assign(cfg.buffer_heater,{enabled:true,managed_by:'heat_pump',request_entity:'sensor.eh2',entry_id:'hp1'});
  Object.assign(cfg.secondary,{enabled:true,kind:'gas',serves:'both',request_entity:'sensor.gas',heat_entity:'sensor.secondary_heat',dhw_temperature_entity:'sensor.source_dhw',heating_temperature_entity:'sensor.source_heating',entry_id:'hp1'});
  await panel.load();
 });
 assert.equal(await page.locator('[data-heat-source]').count(),3);
 assert.equal(await page.locator('.source-glyph.active').count(),1);
 const history=page.locator('[data-heat-source=dhw_heater] [data-history="sensor.heater_power"]');
 await page.evaluate(()=>{panel.addEventListener('hass-more-info',e=>window.lastHistory=e.detail);});
 await history.click();assert.equal(await page.evaluate(()=>lastHistory.entityId),'sensor.heater_power');
 await page.evaluate(()=>{fixture.states['binary_sensor.heater_feedback'].state='unavailable';panel.render();});
 assert.match(await page.locator('[data-heat-source=dhw_heater]').textContent(),/Feedback unknown/);
 assert.equal(await page.locator('.source-glyph.active').count(),0);
 await page.evaluate(()=>{fixture.states['sensor.eh2'].last_reported=new Date(Date.now()-600000).toISOString();panel.render();});
 assert.match(await page.locator('[data-heat-source=buffer_heater]').textContent(),/State unknown/);
 pass('independent feedback, clickable history, unavailable feedback and stale native reports do not imply running');

 await page.evaluate(()=>{fixture.states['number.p140_1'].state='2';panel.render();});
 assert.match(await page.locator('[data-heat-source=dhw_heater]').textContent(),/output configured as gas request/);
 await page.locator('[data-view=settings]').first().click();
 await page.evaluate(()=>{for(const id of ['dhw_heater','buffer_heater'])panel.shadowRoot.querySelector(`[data-source=${id}][data-source-field=request_entity]`).setValue('');});
 for(const id of ['dhw_heater','buffer_heater'])if(!await page.locator(`[data-detail-id="source-setup-${id}"]`).evaluate(el=>el.open))await page.locator(`[data-detail-id="source-setup-${id}"] summary`).click();
 await page.locator('[data-source-suggest=dhw_heater]').click();
 await page.locator('[data-source-suggest=buffer_heater]').click();
 for(const id of ['dhw_heater','buffer_heater'])assert.equal(await page.locator(`[data-source=${id}][data-source-field=request_entity]`).evaluate(el=>el.value),'');
 await page.getByRole('button',{name:'Discard',exact:true}).click();
 await page.locator('[data-view=overview]').first().click();
 pass('gas reuse is flagged, no EH1 guess in gas mode and no guess between heating relays');

 await page.locator('[data-view=operating]').first().click();
 await page.waitForFunction(()=>!!panel.history);
 assert.match(await page.locator('.source-energy').textContent(),/Electricity included in overall meter · do not add twice/);
 assert.equal(await page.locator('.source-energy-row').count(),3);
 const ids=await page.evaluate(()=>panel.historyIds());assert.ok(ids.includes('sensor.heater_energy')&&ids.includes('sensor.secondary_heat'));
 assert.ok(await page.evaluate(()=>fixture.calls.filter(c=>c.type.endsWith('/history')).every(c=>c.entity_ids.length<=24)));
 pass('source energy remains separately labelled and recorder queries remain bounded');

 await page.evaluate(()=>{
  fixture.states['switch.external_heater']={entity_id:'switch.external_heater',state:'off',attributes:{friendly_name:'Independent heater'}};
 });
 await page.locator('[data-view=settings]').first().click();
 for(const id of ['dhw_heater','buffer_heater'])if(!await page.locator(`[data-detail-id="source-setup-${id}"]`).evaluate(el=>el.open))await page.locator(`[data-detail-id="source-setup-${id}"] summary`).click();
 await page.locator('[data-source=dhw_heater][data-source-field=managed_by]').selectOption('external');
 await page.locator('[data-source=buffer_heater][data-source-field=managed_by]').selectOption('external');
 await page.locator('[data-source=buffer_heater][data-source-field=placement]').selectOption('supply');
 await page.evaluate(()=>{
  for(const id of ['dhw_heater','buffer_heater'])panel.shadowRoot.querySelector(`[data-source=${id}][data-source-field=request_entity]`).setValue('');
  fixture.states['number.p140_1'].state='0';
 });
 await page.locator('[data-source-suggest=dhw_heater]').click();
 assert.equal(await page.locator('[data-source=dhw_heater][data-source-field=request_entity]').evaluate(el=>el.value),'');
 await page.evaluate(()=>{
  for(const id of ['dhw_heater','buffer_heater'])panel.shadowRoot.querySelector(`[data-source=${id}][data-source-field=request_entity]`).setValue('switch.external_heater');
  fixture.states['number.p140_1'].state='2';fixture.states['number.p139_1'].state='2';
 });
 await page.getByRole('button',{name:'DE',exact:true}).click();
 assert.equal(await page.locator('[data-source=buffer_heater][data-source-field=placement]').inputValue(),'supply');
 await page.getByRole('button',{name:'EN',exact:true}).click();
 await page.getByRole('button',{name:'Save heat sources',exact:true}).click();
 await page.waitForFunction(()=>fixture.data.settings.heat_sources.buffer_heater.placement==='supply');
 await page.locator('[data-view=overview]').first().click();
 assert.match(await page.locator('[data-heat-source=buffer_heater]').textContent(),/In heating supply/);
 assert.doesNotMatch(await page.locator('[data-heat-source=buffer_heater]').textContent(),/P139 = 2|Related device parameters/);
 assert.doesNotMatch(await page.locator('[data-heat-source=dhw_heater]').textContent(),/P140 = 2|Related device parameters/);
 assert.equal(await page.evaluate(()=>fixture.writes.length),0);
 pass('external heaters keep their own control sources, ignore unrelated gas settings and retain inline placement in DE/EN');

 await page.locator('[data-view=overview]').first().click();
 await page.evaluate(()=>{fixture.states['binary_sensor.heater_feedback'].state='on';fixture.states['number.p140_1'].state='0';panel.render();panel.shadowRoot.querySelector('.toast')?.remove();});
 await page.getByRole('button',{name:'DE',exact:true}).click();
 await page.locator('.heat-sources').screenshot({path:path.join(root,'artifacts/r290-heat-sources-de.png')});
 await page.getByRole('button',{name:'EN',exact:true}).click();
 await page.setViewportSize({width:390,height:844});
 await page.locator('.heat-sources').screenshot({path:path.join(root,'artifacts/r290-heat-sources-en-mobile.png')});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await page.evaluate(()=>{panel.hass={...panel.hass,connected:false};panel.render();});
 assert.equal(await page.locator('.source-glyph.active').count(),0);
 assert.equal(await page.evaluate(()=>fixture.writes.length),0);assert.deepEqual(errors,[]);
 pass('DE/EN, mobile layout and offline state without writes or JavaScript errors');
 console.log(JSON.stringify({passed:checks}));
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}

/* Loopback fixtures only. Never connects to Home Assistant or physical devices. */
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
let browser, checks=0;const pass=label=>{checks++;console.log('PASS '+label);};
try{
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE});
  const page=await browser.newPage({viewport:{width:1500,height:1100}}),base=`http://127.0.0.1:${server.address().port}`,errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());
  await page.goto(base);await page.getByRole('heading',{name:'Anlagenübersicht'}).waitFor();
  // HA's custom-panel wrapper has automatic height; percentage heights alone cannot fill it.
  await page.addStyleTag({content:'html,body{height:auto;background:#ff00ff}'});
  for (const viewport of [{width:1500,height:1300},{width:390,height:1100}]) {
    await page.setViewportSize(viewport);
    for (const view of ['service','parameters']) {
      await page.evaluate(view=>panel.navigate(view),view);
      const layout=await page.evaluate(()=>{
        const host=panel.getBoundingClientRect(), shell=panel.shadowRoot.querySelector('.shell').getBoundingClientRect();
        return {top:host.top,bottom:shell.bottom,viewport:innerHeight,width:document.documentElement.scrollWidth,viewportWidth:innerWidth};
      });
      assert.equal(layout.top,0);
      assert.ok(layout.bottom>=layout.viewport-1,`${view}: background must reach the panel bottom`);
      assert.ok(layout.width<=layout.viewportWidth,`${view}: no horizontal page overflow`);
    }
  }
  await page.setViewportSize({width:1500,height:1300});
  await page.evaluate(()=>panel.navigate('service'));
  await page.screenshot({path:path.join(root,'artifacts/r290-service-full-height.png'),fullPage:true});
  await page.evaluate(()=>panel.navigate('parameters'));
  await page.screenshot({path:path.join(root,'artifacts/r290-parameters-full-height.png'),fullPage:true});
  await page.setViewportSize({width:1500,height:1100});
  pass('short service and parameter pages fill the available HA panel on desktop and mobile');
  await page.locator('[data-view=settings]').first().click();
  await page.locator('[data-plant=mode]').selectOption('single');
  await page.getByRole('button',{name:'Anlagenaufbau speichern',exact:true}).click();
  assert.equal(await page.evaluate(()=>fixture.calls.filter(m=>m.type.endsWith('/settings')).length),0);
  await page.locator('[data-plant-unit=hp2]').uncheck();
  await page.locator('[data-plant=heating]').selectOption('direct');
  await page.locator('[data-plant=separation]').selectOption('none');
  await page.locator('[data-plant=dhw]').selectOption('none');
  await page.locator('[data-plant=aux_position]').selectOption('none');
  await page.locator('[data-plant=controller_id]').selectOption('');
  await page.getByRole('button',{name:'EN',exact:true}).click();
  assert.match(await page.locator('[data-plant=mode]').locator('..').textContent(),/Plant type/);
  assert.equal(await page.locator('[data-plant=mode]').inputValue(),'single');
  assert.equal(await page.locator('[data-plant-unit=hp2]').isChecked(),false);
  await page.getByRole('button',{name:'DE',exact:true}).click();
  assert.match(await page.locator('[data-plant=mode]').locator('..').textContent(),/Anlagenart/);
  await page.evaluate(()=>panel.load());
  assert.equal(await page.locator('[data-plant=mode]').inputValue(),'single');
  await page.getByRole('button',{name:'Anlagenaufbau speichern',exact:true}).click();
  await page.waitForFunction(()=>fixture.data.settings.plant?.mode==='single');
  await page.locator('[data-view=overview]').first().click();
  assert.equal(await page.locator('.schematic-unit').count(),1);
  assert.equal(await page.locator('[data-pipe=dhw-supply],[data-pipe=charge-tank],.pump-summary').count(),0);
  assert.equal(await page.locator('[data-flow=direct-return]').count(),1);
  await page.screenshot({path:path.join(root,'artifacts/r290-plant-single.png'),fullPage:true});
  assert.equal(await page.evaluate(()=>fixture.writes.length),0);
  pass('single-unit setup validates selection, preserves edits, saves without hardware commands and renders direct circuit');
  await page.evaluate(async()=>{
    fixture.data.settings.plant={...fixture.data.settings.plant,mode:'cascade',unit_ids:['hp1','hp2'],heating:'buffer_parallel',separation:'plate',dhw:'coil',aux_position:'common_supply',controller_id:'pump'};
    fixture.data.settings.dhw_entity='binary_sensor.dhw';fixture.data.settings.buffer_charge_entity='switch.buffer_charge';fixture.data.settings.radiator_pump_entity='switch.radiators';
    fixture.data.settings.dhw_charge_entity='switch.buffer_charge';await panel.load();
  });
  assert.equal(await page.locator('.schematic-unit').count(),2);
  assert.equal(await page.locator('[data-flow=dhw-coil]').count(),1);
  assert.equal(await page.locator('[data-flow=heating-supply]').count(),0);
  assert.equal(await page.locator('[data-flow="unit-1-supply"]').count(),0);
  await page.screenshot({path:path.join(root,'artifacts/r290-plant-cascade.png'),fullPage:true});
  await page.setViewportSize({width:1500,height:600});
  const retained=await page.evaluate(()=>{window.scrollTo(0,180);const svg=panel.shadowRoot.querySelector('.adaptive-schematic svg'),fan=svg.querySelector('.fan-blades.running'),animation=fan.getAnimations()[0],y=scrollY;for(let i=0;i<5;i++)panel.render();return {node:svg===panel.shadowRoot.querySelector('.adaptive-schematic svg'),fan:fan.getAnimations()[0]===animation,scroll:y===scrollY};});
  assert.deepEqual(retained,{node:true,fan:true,scroll:true});
  pass('cascade DHW loop, inactive unit and live DOM/animation/scroll retention');
  await page.setViewportSize({width:1500,height:1100});
  for(const heating of ['direct','buffer_parallel','buffer_series'])for(const separation of ['none','plate'])for(const dhw of ['none','coil','plate']){
    await page.evaluate(async({heating,separation,dhw})=>{Object.assign(fixture.data.settings.plant,{heating,separation,dhw});fixture.states['switch.buffer_charge'].state='on';fixture.states['switch.radiators'].state='on';await panel.load();},{heating,separation,dhw});
    assert.equal(await page.locator('[data-pipe=dhw-supply]').count(),dhw==='none'?0:1);
    assert.equal(await page.locator('[data-pipe=heating-primary-exchanger]').count(),separation==='plate'?1:0);
    assert.equal(await page.locator('[data-pipe=series-buffer]').count(),heating==='buffer_series'?1:0);
    assert.equal(await page.locator('[data-pipe=charge-tank]').count(),heating==='buffer_parallel'?1:0);
    assert.ok(await page.locator('.adaptive-schematic').evaluate(el=>[...el.querySelectorAll('[data-flow]')].every(flow=>flow.getAttribute('d')===el.querySelector(`[data-pipe="${flow.dataset.flow}"]`)?.getAttribute('d'))));
  }
  await page.screenshot({path:path.join(root,'artifacts/r290-plant-series-dhw-plate.png'),fullPage:true});
  pass('all 18 heating/separation/DHW variants render connected base/animation geometry');
  await page.evaluate(async()=>{fixture.data.settings.plant.isolation='feedback';fixture.data.settings.plant.valve_entities={hp1:'binary_sensor.dhw',hp2:'switch.buffer_charge'};fixture.states['binary_sensor.dhw'].state='off';await panel.load();});
  assert.equal(await page.locator('[data-flow="unit-0-supply"]').count(),0);
  assert.match(await page.locator('[data-isolation=hp1]').textContent(),/geschlossen/);
  await page.evaluate(async()=>{fixture.states['binary_sensor.dhw'].state='on';await panel.load();});
  assert.equal(await page.locator('[data-flow="unit-0-supply"]').count(),1);
  pass('closed valve feedback blocks that branch even when a flow value remains positive');
  const many=await page.evaluate(async()=>{
    const saved={entries:fixture.data.entries,entities:fixture.data.entities,plant:fixture.data.settings.plant};
    fixture.data.entries=[...saved.entries];fixture.data.entities=[...saved.entities];
    for(let n=3;n<=11;n++){
      fixture.data.entries.push({id:`hp${n}`,type:'heat_pump',slave:n,title:`WP ${n}`});
      for(const fragment of ['compressor_operating_frequency','water_outlet_temperature_t7','return_water_temperature_t6','water_flow']){
        const old=`sensor.${fragment}_1`,id=`sensor.${fragment}_${n}`;
        fixture.states[id]={...fixture.states[old],entity_id:id};
        fixture.data.entities.push({id,entry_id:`hp${n}`,name:id,unique_id:`r290_heatpump_${fragment}_slave_${n}`,disabled:false});
      }
    }
    fixture.data.settings.plant={...saved.plant,unit_ids:Array.from({length:11},(_,i)=>`hp${i+1}`),isolation:'none',valve_entities:{}};
    await panel.load();panel.history=null;
    const begin=fixture.calls.length;await panel.loadHistory();
    const result={units:panel.shadowRoot.querySelectorAll('.schematic-unit').length,batches:fixture.calls.slice(begin).filter(m=>m.type.endsWith('/history')).map(m=>m.entity_ids.length),last:!!panel.history.series['sensor.compressor_operating_frequency_11']};
    fixture.data.entries=saved.entries;fixture.data.entities=saved.entities;fixture.data.settings.plant=saved.plant;
    await panel.load();return result;
  });
  assert.equal(many.units,11);assert.ok(many.batches.length>1&&many.batches.every(n=>n<=24));assert.ok(many.last);
  pass('eleven-unit cascade remains selectable and history includes every unit in bounded requests');
  await page.setViewportSize({width:390,height:844});
  for(const view of ['overview','settings','service']){
    await page.evaluate(view=>panel.navigate(view),view);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  await page.setViewportSize({width:1500,height:1100});
  await page.getByRole('button',{name:'Geräteinfo und Testwerte lesen',exact:true}).click();
  await page.getByText('4.25',{exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>fixture.writes.length),0);
  await page.screenshot({path:path.join(root,'artifacts/r290-service-de.png'),fullPage:true});
  await page.evaluate(()=>panel.navigate('factory'));
  await page.locator('[data-service-test=fan]').click();
  await page.getByRole('button',{name:'Abbrechen',exact:true}).click();
  assert.equal(await page.evaluate(()=>fixture.writes.length),0);
  await page.locator('[data-service-test=fan]').click();
  await page.getByRole('button',{name:'Bestätigen',exact:true}).click();
  assert.equal(await page.evaluate(()=>fixture.writes.length),0);
  await page.locator('[name=qualified]').check();
  await page.locator('[name=target]').fill('25');
  await page.getByRole('button',{name:'Bestätigen',exact:true}).click();
  await page.locator('[data-service-stop=hp1]').waitFor();
  assert.equal(await page.evaluate(()=>fixture.writes.at(-1).component),'fan');
  await page.evaluate(()=>panel.navigate('overview'));
  assert.equal(await page.locator('[data-service-stop=hp1]').count(),1);
  await page.locator('[data-service-stop=hp1]').click();
  await page.waitForFunction(()=>Object.keys(fixture.data.service.tests).length===0);
  pass('service read is passive; start requires confirmation; global stop stays available after navigation');
  await page.evaluate(()=>panel.navigate('service'));
  await page.getByRole('button',{name:'EN',exact:true}).click();
  await page.getByRole('heading',{name:'Device information',exact:true}).waitFor();
  await page.locator('.section-tabs [data-view=factory]').click();
  await page.screenshot({path:path.join(root,'artifacts/r290-service-en.png'),fullPage:true});
  await page.locator('[data-service-unit]').selectOption('hp2');
  assert.equal(await page.locator('[data-service-test=fan]').isDisabled(),true);
  await page.evaluate(()=>fixture.failNext=true);
  await page.getByRole('button',{name:'Read device info and test values',exact:true}).click();
  await page.getByRole('alert').waitFor();
  assert.equal(await page.locator('[data-service-test=fan]').isDisabled(),true);
  assert.deepEqual(errors,[]);
  pass('DE/EN service UI, narrow screens and failed reads keep controls unavailable; no runtime errors');
  console.log(`${checks} plant/service browser checks passed`);
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}

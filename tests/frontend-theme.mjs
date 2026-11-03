/* Background/layout audit against an isolated HA double, never a live system. */
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const version=JSON.parse(await readFile(path.join(root,'custom_components/r290_heatpump/manifest.json'),'utf8')).version;
const output=path.join(root,`artifacts/theme-audit-${version}${process.env.THEME_FOCUS?'-focused':''}`);await mkdir(output,{recursive:true});
const server=createServer(async(req,res)=>{
  const name=new URL(req.url,'http://localhost').pathname;
  if(name==='/'){
    res.setHeader('Content-Type','text/html');
    // Deliberately auto height, just like HA's custom-panel wrapper. Magenta
    // makes any uncovered page area stand out in the visual review.
    res.end('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>html,body{margin:0;background:#ff00ff}</style><script type="module" src="/fixture.mjs"></script>');return;
  }
  const file=name==='/fixture.mjs'?path.join(root,'tests/frontend-fixture.mjs'):/^\/r290_heatpump_static\/[a-z0-9-]+\.(js|css|json)$/.test(name)?path.join(root,'custom_components/r290_heatpump/frontend',path.basename(name)):null;
  if(!file){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':'text/javascript');res.end(await readFile(file));
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base=`http://127.0.0.1:${server.address().port}`;
const cases=['overview','operating','service','machine','factory','diagnostics','faults','system','settings','pump','schematic'].map(view=>({name:view,view}));
for(const tab of ['heating_curve','hot_water_curve','floor_heating_curve','cooling_curve'])for(const section of ['basis','pv','fine'])cases.push({name:`${tab}-${section}`,view:'parameters',tab,section});
for(const tab of ['realtime','user','user2'])cases.push({name:tab,view:'parameters',tab});
cases.push({name:'overview-published',view:'overview',graph:true});
cases.push({name:'schematic-populated',view:'schematic',graph:true});
const viewports={desktop:{width:1920,height:1200},tablet:{width:1024,height:1366},mobile:{width:390,height:844}};
const results=[],errors=[],failures=[];let browser;
try{
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE});
  for(const [screen,viewport] of Object.entries(viewports))for(const language of ['de','en']){
    if(process.env.THEME_FOCUS&&(screen!=='desktop'||language!=='de'))continue;
    const page=await browser.newPage({viewport});
    page.on('pageerror',e=>errors.push({screen,language,error:e.message}));
    await page.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());
    await page.goto(base);await page.getByRole('heading',{name:'Anlagenübersicht'}).waitFor();
    await page.getByRole('button',{name:language.toUpperCase(),exact:true}).click();
    await page.evaluate(()=>{window.themeOriginal=structuredClone(fixture.data);});
    async function select(c){
      await page.evaluate(async c=>{
        panel.closeModal();panel._schematicDirty=false;panel._editingSettings=false;
        panel._curveDrafts?.clear();panel.error='';panel.query='';panel.differences=false;
        Object.assign(fixture.data,structuredClone(themeOriginal));
        if(c.graph){
          const {preset}=await import('/r290_heatpump_static/schematic-presets.js');
          const catalog=await (await fetch('/r290_heatpump_static/schematic-catalog.json')).json();
          const graph=preset('full',catalog,panel);
          fixture.data.settings.schematic={revision:1,published:graph,draft:c.view==='schematic'?structuredClone(graph):null};
        }
        if(c.emptyPump)fixture.data.controllers=[];
        if(c.emptyCurve){fixture.data.entries=fixture.data.entries.filter(e=>!e.type.endsWith('_curve'));fixture.data.curves=[];}
        await panel.load();panel._parameterTab=c.tab||'heating_curve';panel._curveSection=c.section||'basis';
        panel.navigate(c.view);panel.render();
      },c);
      await page.waitForFunction(()=>!panel._historyLoading);
      if(c.view==='schematic')await page.locator('r290-schematic .stage-wrap').waitFor();
    }
    async function inspect(name){
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      const metrics=await page.evaluate(()=>{
        const shell=panel.shadowRoot.querySelector('.shell'),sr=shell.getBoundingClientRect(),host=panel.getBoundingClientRect();
        const nested=[...panel.shadowRoot.querySelectorAll('r290-schematic')].map(el=>({
          host:getComputedStyle(el).backgroundColor,
          toolbars:[...el.shadowRoot.querySelectorAll('.toolbar,.live-actions,.live-tools')].map(t=>getComputedStyle(t).backgroundColor)
        }));
        const dialog=panel.shadowRoot.querySelector('dialog[open]'),dr=dialog?.getBoundingClientRect();
        return {height:sr.height,viewport:innerHeight,width:document.documentElement.scrollWidth,viewportWidth:innerWidth,
          shellWidth:sr.width,hostWidth:host.width,background:getComputedStyle(shell).backgroundColor,nested,
          documentHeight:document.documentElement.scrollHeight,
          dialog:dialog?{background:getComputedStyle(dialog).backgroundColor,left:dr.left,right:dr.right,top:dr.top,bottom:dr.bottom}:null};
      });
      const key=`${screen}-${language}-${name}`,issues=[];
      if(metrics.height<viewport.height-1)issues.push('background shorter than viewport');
      if(metrics.documentHeight>metrics.height+1)issues.push('content overflows beyond page background');
      if(metrics.width>viewport.width+1)issues.push('horizontal page overflow');
      if(Math.abs(metrics.shellWidth-metrics.hostWidth)>1)issues.push('background does not cover panel width');
      if(metrics.background!=='rgb(7, 20, 30)')issues.push('incorrect page background');
      for(const n of metrics.nested)if([n.host,...n.toolbars].some(v=>v!=='rgba(0, 0, 0, 0)'))issues.push('opaque schematic/toolbar wrapper');
      if(metrics.dialog){const d=metrics.dialog;if(d.background!=='rgb(16, 37, 49)')issues.push('incorrect dialog surface');if(d.left<0||d.right>viewport.width+1||d.top<0||d.bottom>viewport.height+1)issues.push('dialog outside viewport');}
      const shots=[];
      // Capture every named page and dialog, both top and bottom for tall pages.
      await page.evaluate(()=>window.scrollTo(0,0));
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      const top=`${key}-top.png`;await page.screenshot({path:path.join(output,top)});shots.push(top);
      if(!metrics.dialog&&metrics.height>viewport.height+2){
        await page.evaluate(()=>window.scrollTo(0,document.documentElement.scrollHeight));
        await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
        metrics.bottom=await page.evaluate(()=>{
          const shell=panel.shadowRoot.querySelector('.shell'),r=shell.getBoundingClientRect();
          return {scrollY,documentHeight:document.documentElement.scrollHeight,shellTop:r.top,shellBottom:r.bottom,
            bodyHeight:document.body.getBoundingClientRect().height,
            atBottom:document.elementFromPoint(innerWidth/2,innerHeight-1)?.tagName};
        });
        if(metrics.bottom.shellBottom<viewport.height-1)issues.push('background ends above scrolled viewport bottom');
        const bottom=`${key}-bottom.png`;await page.screenshot({path:path.join(output,bottom)});shots.push(bottom);
      }
      if(['system','realtime','machine','user','user2'].includes(name)){
        metrics.tableEnd=await page.evaluate(()=>{
          const table=panel.shadowRoot.querySelector('.device-parameters');table.scrollTop=table.scrollHeight;
          const end=table.querySelector('tbody tr:last-child').getBoundingClientRect(),r=table.getBoundingClientRect();
          return {rowBottom:end.bottom,containerBottom:r.bottom,containerTop:r.top,scrollTop:table.scrollTop,
            pageHeight:document.documentElement.scrollHeight};
        });
        if(metrics.tableEnd.rowBottom>metrics.tableEnd.containerBottom+1||metrics.tableEnd.rowBottom<=metrics.tableEnd.containerTop)issues.push('last table row cannot be reached');
        if(metrics.tableEnd.pageHeight>metrics.height+1)issues.push('table scrolling extends page background');
        await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
        const end=`${key}-table-end.png`;await page.screenshot({path:path.join(output,end)});shots.push(end);
      }
      results.push({screen,language,name,...metrics,issues,screenshots:shots});
      if(issues.length)failures.push({key,issues});
    }
    for(const c of cases){if(process.env.THEME_FOCUS&&!process.env.THEME_FOCUS.split(',').includes(c.name))continue;await select(c);await inspect(c.name);}
    if(process.env.THEME_FOCUS){await page.close();continue;}

    // Empty and error pages use the same shell but often have much less content.
    await select({view:'pump',emptyPump:true});await inspect('pump-empty');
    await select({view:'parameters',emptyCurve:true});await inspect('curve-empty');
    await select({view:'service'});await page.evaluate(()=>{panel.data=null;panel.error='Test: connection unavailable';panel.render();});await inspect('loading-error');
    await select({view:'service'});await page.evaluate(()=>{panel._serviceError='Test: device did not respond';panel.render();});await inspect('service-error');

    await select({view:'overview'});await page.locator('[data-chart-config]').first().click();await inspect('dialog-chart');
    await select({view:'system'});await page.locator('[data-action=system-unlock]').click();await inspect('dialog-password');
    await select({view:'pump'});await page.locator('[data-mode=manual]').click();await inspect('dialog-pump-mode');
    await select({view:'overview'});await page.evaluate(()=>panel.showHistory('sensor.tank,sensor.buffer'));await inspect('dialog-source-history');
    await select({view:'factory'});await page.locator('[data-service-action=read]').click();await page.locator('[data-service-test=fan]').waitFor();await page.locator('[data-service-test=fan]').click();await inspect('dialog-factory-test');
    await select({view:'parameters'});await page.evaluate(()=>{panel.unlocked=true;panel.render();});await page.locator('[data-parameter-action=add-point]').click();await page.locator('[data-parameter-action=review]').click();await inspect('dialog-curve-review');
    await select({view:'settings'});await page.locator('r290-entity-picker[data-setting=tank_entity] input').fill('tank');await inspect('entity-search');
    assert.equal(await page.evaluate(()=>fixture.writes.length),0,'visual audit must not issue even simulated device writes');
    console.log(`Checked ${screen}/${language}: ${results.filter(r=>r.screen===screen&&r.language===language).length} views`);
    await page.close();
  }
  await writeFile(path.join(output,'report.json'),JSON.stringify({version,date:new Date().toISOString(),viewports,cases:cases.length,checked:results.length,failures,errors,results},null,2));
  assert.deepEqual(errors,[]);assert.deepEqual(failures,[]);
  console.log(`PASS ${results.length} background/layout checks; zero device writes`);
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}

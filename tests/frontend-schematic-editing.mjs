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
 const page=await browser.newPage({viewport:{width:1700,height:1100},hasTouch:true}),base=`http://127.0.0.1:${server.address().port}`,errors=[];
 page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());
 await page.goto(base);await page.getByRole('heading',{name:'Anlagenübersicht'}).waitFor();
 await page.locator('.app-header [data-view=settings]').click();await page.locator('.section-tabs [data-view=schematic]').click();
 const editor=page.locator('r290-schematic[data-mode=editor]'),svg=editor.locator('.sg-svg');
 const geometry=()=>editor.evaluate(el=>Object.fromEntries(Object.entries(el.geometry).map(([k,v])=>[k,v.d])));
 const point=async(x,y)=>svg.evaluate((el,[x,y])=>{const p=new DOMPoint(x,y).matrixTransform(el.getScreenCTM());return {x:p.x,y:p.y};},[x,y]);
 const select=async id=>editor.locator(`.sg-svg [data-node="${id}"]`).dispatchEvent('click');
 await editor.locator('#preset').selectOption('full');await editor.locator('[data-action=preset]').click();
 await editor.locator('[data-action=draft]').click();await page.waitForFunction(()=>fixture.data.settings.schematic?.revision===1);
 const initial=await editor.evaluate(el=>structuredClone(el.graph)),routes=await geometry(),undoCount=await editor.evaluate(el=>el.session.undo.length);
 await editor.locator('#component').selectOption('heat_meter');await editor.locator('[data-action=add]').click();
 assert.deepEqual(await editor.evaluate(el=>el.graph),initial);assert.equal(await editor.evaluate(el=>el.session.dirty),false);
 assert.equal(await editor.locator('.sg-placement').count(),1);
 await page.keyboard.press('Escape');assert.equal(await editor.locator('.sg-placement').count(),0);
 assert.equal(await editor.evaluate(el=>el.session.undo.length),undoCount);assert.deepEqual(await geometry(),routes);
 await editor.locator('[data-action=add]').click();await editor.locator('[data-action=cancel-placement]').click();
 assert.deepEqual(await editor.evaluate(el=>el.graph),initial);
 pass('placement preview and both cancel actions leave graph, undo and saved state unchanged');

 await editor.locator('[data-action=add]').click();
 await svg.scrollIntoViewIfNeeded();const spot=await point(780,510);await page.mouse.move(spot.x,spot.y);
 const expected=await editor.evaluate(el=>({x:el.pendingNode.x,y:el.pendingNode.y}));
 await page.screenshot({path:path.join(root,'artifacts/r290-placement-preview.png')});
 await page.mouse.click(spot.x,spot.y);
 assert.deepEqual(await editor.evaluate(el=>{const n=el.graph.nodes.find(n=>n.id==='heat_meter_1');return {x:n.x,y:n.y};}),expected);
 assert.deepEqual(await geometry(),routes);assert.equal(await editor.locator('.sg-placement').count(),0);
 const afterPlacement=await editor.evaluate(el=>structuredClone(el.graph));
 await editor.locator('[data-action=undo]').click();assert.deepEqual(await editor.evaluate(el=>el.graph),initial);
 await editor.locator('[data-action=redo]').click();assert.deepEqual(await editor.evaluate(el=>el.graph),afterPlacement);
 pass('mouse placement follows cursor, leaves all pipes untouched and supports exact undo/redo');

 const hit=editor.locator('[data-node=heat_meter_1] .sg-node-hit');await hit.scrollIntoViewIfNeeded();const box=await hit.boundingBox();
 const beforeMove=await editor.evaluate(el=>structuredClone(el.graph));
 await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();
 await page.mouse.move(box.x+box.width/2+115,box.y+box.height/2+55,{steps:5});assert.deepEqual(await geometry(),routes);
 await page.mouse.up();assert.deepEqual(await geometry(),routes);
 assert.notEqual(await editor.evaluate(el=>el.graph.nodes.find(n=>n.id==='heat_meter_1').x),expected.x);
 await editor.locator('[data-action=undo]').click();assert.deepEqual(await editor.evaluate(el=>el.graph),beforeMove);
 await editor.locator('[data-action=redo]').click();await select('heat_meter_1');
 await editor.locator('[data-node=heat_meter_1]').focus();await page.keyboard.press('ArrowRight');assert.deepEqual(await geometry(),routes);
 const scale=await svg.evaluate(el=>el.getScreenCTM().a);
 await editor.locator('[data-property=x]').fill('2500');await editor.locator('[data-property=x]').dispatchEvent('change');
 assert.ok(Math.abs(await svg.evaluate(el=>el.getScreenCTM().a)-scale)<.002);assert.deepEqual(await geometry(),routes);
 await editor.locator('[data-property=x]').fill('700');await editor.locator('[data-property=x]').dispatchEvent('change');
 await editor.locator('[data-action=flip]').click();assert.deepEqual(await geometry(),routes);
 await editor.locator('[data-action=draft]').click();await page.waitForFunction(()=>fixture.data.settings.schematic?.revision===2);
 await editor.locator('[data-action=reload]').click();await page.waitForFunction(()=>!panel._schematicDirty);assert.deepEqual(await geometry(),routes);
 pass('unconnected drag, keyboard move, coordinate edit and flip preserve pipes; canvas grows without rescaling; routes survive save/reload');

 await select('wp1');const oldX=Number(await editor.locator('[data-property=x]').inputValue());
 await editor.locator('[data-property=x]').fill(String(oldX+40));await editor.locator('[data-property=x]').dispatchEvent('change');
 const changed=await geometry(),edges=await editor.evaluate(el=>el.graph.edges);
 for(const e of edges)assert.equal(changed[e.id]===routes[e.id],e.from.node!=='wp1'&&e.to.node!=='wp1',e.id);
 await editor.locator('[data-action=undo]').click();assert.deepEqual(await geometry(),routes);
 pass('moving a connected heat pump adapts only its own connections');

 await editor.locator('#component').selectOption('heater');await editor.locator('[data-action=add]').click();
 const preview=await editor.evaluate(el=>el.pendingNode.x);await page.keyboard.press('ArrowRight');await page.keyboard.press('Enter');
 assert.equal(await editor.evaluate(el=>el.graph.nodes.find(n=>n.id==='heater_1').x),preview+20);
 assert.deepEqual(await editor.locator('[data-binding]').evaluateAll(els=>els.map(el=>el.dataset.binding)),['value','status']);
 await editor.locator('[data-tank]').selectOption('buffer');assert.deepEqual(await geometry(),routes);
 await editor.locator('[data-action=draft]').click();await page.waitForFunction(()=>fixture.data.settings.schematic?.revision===3);
 await editor.locator('[data-action=reload]').click();await page.waitForFunction(()=>!panel._schematicDirty);
 pass('keyboard placement, electrical heater fields and tank mounting survive save/reload');

 await page.setViewportSize({width:390,height:844});await editor.locator('#zoom').selectOption('200');
 await editor.locator('#component').selectOption('pump');await editor.locator('[data-action=add]').click();
 await editor.locator('.stage').scrollIntoViewIfNeeded();
 await editor.locator('.stage').evaluate(el=>{el.scrollLeft=400;el.scrollTop=200;});
 const stage=await editor.locator('.stage').boundingBox(),tap={x:Math.round(stage.x+100),y:Math.round(stage.y+100)};
 const touchExpected=await editor.evaluate((el,p)=>el.placementPosition({clientX:p.x,clientY:p.y}),tap);
 await page.touchscreen.tap(tap.x,tap.y);
 assert.deepEqual(await editor.evaluate(el=>{const n=el.graph.nodes.find(n=>n.id==='pump_1');return [n.x,n.y];}),touchExpected);
 assert.deepEqual(await geometry(),routes);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.evaluate(()=>fixture.writes.length),0);assert.deepEqual(errors,[]);
 pass('touch placement at 200% zoom in a scrolled mobile canvas; no page overflow, console errors or device writes');
 console.log(JSON.stringify({passed:checks}));
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}

// Export the shared vector artwork as local HA brand PNGs; no release/archive.
import {mkdir, writeFile, copyFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {brandIcon, brandLogo} from '../custom_components/r290_heatpump/frontend/branding.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = path.join(root, 'brands/r290_heatpump');
const destination = path.join(root, 'custom_components/r290_heatpump/brand');
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(path.join(process.env.PLAYWRIGHT_MODULE, 'index.mjs')).href : 'playwright');
await mkdir(source, {recursive: true});
await mkdir(destination, {recursive: true});
await mkdir(path.join(root, 'artifacts'), {recursive: true});
const browser = await chromium.launch({headless: true, executablePath: process.env.CHROMIUM_EXECUTABLE});
try {
  const page = await browser.newPage({deviceScaleFactor: 1});
  await page.route('**/*', route => route.abort());
  for (const [name, svg] of [['icon', brandIcon()], ['dark_icon', brandIcon()], ['logo', brandLogo(false)], ['dark_logo', brandLogo(true)]]) {
    await page.setContent(`<style>body{margin:0}svg{display:block}</style>${svg}`);
    await page.evaluate(() => document.fonts.ready);
    const box = await page.locator('svg').evaluate(el => {const b = el.getBBox();return {x:b.x,y:b.y,width:b.width,height:b.height};});
    const vector = svg.replace(/viewBox="[^"]+"/, `viewBox="${box.x} ${box.y} ${box.width} ${box.height}"`);
    await writeFile(path.join(source, `${name}.svg`), vector + '\n');
    for (const scale of [1, 2]) {
      const height = 256 * scale, width = Math.round(height * box.width / box.height);
      await page.setViewportSize({width, height});
      await page.setContent(`<style>body{margin:0;background:transparent}svg{display:block;width:${width}px;height:${height}px}</style>${vector}`);
      const filename = `${name}${scale === 2 ? '@2x' : ''}.png`;
      await page.screenshot({path: path.join(destination, filename), omitBackground: true});
      await copyFile(path.join(destination, filename), path.join(source, filename));
      console.log(`${filename}: ${width} × ${height}`);
    }
  }
  await page.setViewportSize({width: 1280, height: 640});
  await page.setContent(`<style>
    *{box-sizing:border-box}body{margin:0;background:#07141e;color:#edf5fa;font:16px 'Segoe UI',sans-serif;padding:36px}
    h1{margin:0 0 30px;font-size:28px}section{display:flex;align-items:center;gap:40px;margin-bottom:24px;padding:28px;border:1px solid #326176;border-radius:16px;background:#102531}
    .light{background:#f5f8fa;color:#163746}span{width:120px;flex-shrink:0}svg{display:block}.icon{width:96px;height:96px}.logo{width:630px}.sizes{display:flex;gap:24px;align-items:center;padding-left:188px}.sizes svg{width:var(--size);height:var(--size)}p{color:#a7bdcb}
    </style><h1>R290 NextGen · Icon & Logo</h1><section><span>Dunkle Ansicht</span><div class="icon">${brandIcon()}</div><div class="logo">${brandLogo()}</div></section><section class="light"><span>Helle Ansicht</span><div class="icon">${brandIcon()}</div><div class="logo">${brandLogo(false)}</div></section><p>Icon in kleinen Größen</p><div class="sizes"><div style="--size:64px">${brandIcon()}</div><div style="--size:32px">${brandIcon()}</div><div style="--size:24px">${brandIcon()}</div></div>`);
  await page.screenshot({path: path.join(root, 'artifacts/r290-nextgen-brand.png')});
} finally {
  await browser.close();
}

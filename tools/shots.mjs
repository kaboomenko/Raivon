// Drives the built prototype in headless Chromium at iPhone size and saves screenshots.
// Usage: node tools/shots.mjs [outDir]
import { chromium } from '@playwright/test';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { mkdirSync } from 'node:fs';

const out = resolve(process.argv[2] ?? 'shots');
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
await page.goto(pathToFileURL(resolve('apps/client/dist/index.html')).href);
await page.waitForTimeout(1500);
const shot = async (name) => page.screenshot({ path: `${out}/${name}.png` });
await shot('01_intro');
await page.click('#go');
await page.waitForTimeout(500);
await shot('02_map');
await page.evaluate(() => window.__raivon.startPickGoal(2));
await page.waitForTimeout(500);
await shot('03_pick_goal');
await page.evaluate(() => { const r = window.__raivon; r.confirmWar(r.G.goalChoices[0]); });
await page.waitForTimeout(400);
await shot('04_war');
await page.evaluate(() => window.__raivon.startOffensive());
await page.waitForTimeout(800);
// scripted player: card «Атака» on the best target each 2 s
await page.evaluate(() => {
  const r = window.__raivon;
  window.__bot = setInterval(() => {
    const b = r.G.battle; if (!b) return;
    let best = null;
    for (const c of r.G.world.cells) {
      if (!b.canTarget(1, c.id)) continue;
      const ids = b.adjacentIdleArmies(1, c.id).map((a) => a.id);
      if (!ids.length) continue;
      const f = b.forecast(1, ids, c.id).f + (c.id === r.G.war.goal ? 0.3 : 0);
      if (f >= 1.2 && (!best || f > best.f)) best = { id: c.id, f };
    }
    if (best) b.issue(1, { t: 'card', card: 'attack', target: best.id });
  }, 2000);
});
await page.waitForTimeout(6000);
await shot('05_battle');
await page.waitForTimeout(12000);
await shot('06_battle_later');
// fast-forward the rest of the offensive
await page.evaluate(() => { const b = window.__raivon.G.battle; while (b && !b.over) b.step(); });
await page.waitForTimeout(800);
await shot('07_result');
await page.evaluate(() => { document.querySelector('#panel').className = 'hidden'; window.__raivon.openPeace(); });
await page.waitForTimeout(600);
await shot('08_peace');
await page.evaluate(() => window.__raivon.signPeace());
await page.waitForTimeout(2300);
await shot('09_ceremony_mid');
await page.waitForTimeout(4500);
await shot('10_ceremony_end');
console.log(JSON.stringify({ errors }, null, 1));
await browser.close();

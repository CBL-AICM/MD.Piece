// Visual-language change: before/after screenshots of key screens.
// Usage: SHOT_TAG=before node visual_language_shots.mjs
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const TAG = process.env.SHOT_TAG || 'after';
const SHOT_DIR = resolve(__dirname, 'visual_language_shots');
mkdirSync(SHOT_DIR, { recursive: true });

const URL_BASE = process.env.PREVIEW_URL || 'http://127.0.0.1:3000/';
const VIEWPORT = { width: 390, height: 844 };
const PAGES = ['home', 'rewards', 'vitals', 'medications', 'settings'];

(async () => {
  const browser = await chromium.launch();
  const issues = [];
  const ctx = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 2,
    ignoreHTTPSErrors: true,
  });
  const page = await ctx.newPage();
  page.on('pageerror', e => issues.push(`pageerror: ${e.message}`));
  page.on('console', m => { if (m.type() === 'error') issues.push(`console.error: ${m.text()}`); });

  await page.addInitScript(() => {
    const user = { id: 'demo-user', username: 'demo', nickname: '示範', role: 'patient', avatar_color: '#5B9FE8' };
    localStorage.setItem('mdpiece_user', JSON.stringify(user));
    localStorage.setItem('mdpiece_onboarded', '1');
    localStorage.setItem('mdpiece_landing_theme', 'light');
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get() { return undefined; } });
  });

  await page.goto(URL_BASE, { waitUntil: 'load' });
  await page.waitForSelector('#landing-enter', { timeout: 5000 }).catch(() => {});
  await page.evaluate(() => {
    const landing = document.getElementById('landing');
    if (landing) { landing.style.display = 'none'; landing.classList.add('fade-out'); }
    const app = document.getElementById('app-wrapper');
    if (app) app.classList.add('show');
  });
  await page.waitForTimeout(800);

  for (const name of PAGES) {
    await page.evaluate((p) => {
      if (typeof setTopbarPageTitle === 'function') try { setTopbarPageTitle(p); } catch (e) {}
      if (typeof showPage === 'function') showPage(p);
    }, name);
    await page.waitForTimeout(1400);
    await page.evaluate(() => { try { window.lucide && window.lucide.createIcons(); } catch (e) {} });
    await page.waitForTimeout(300);

    const overflow = await page.evaluate(() => {
      const winW = window.innerWidth;
      const off = [];
      document.querySelectorAll('body *').forEach(el => {
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden') return;
        const r = el.getBoundingClientRect();
        if (r.right > winW + 2 && r.width > 0) {
          off.push({ tag: el.tagName.toLowerCase(), cls: (typeof el.className === 'string' ? el.className : '').slice(0, 40), excess: Math.round(r.right - winW) });
        }
      });
      off.sort((a, b) => b.excess - a.excess);
      return off.slice(0, 4);
    });
    if (overflow.length > 0) issues.push(`[${name}] overflow: ${JSON.stringify(overflow)}`);

    const shot = resolve(SHOT_DIR, `${name}-${TAG}.png`);
    await page.screenshot({ path: shot, fullPage: true });
    console.log(`[${name}] (${TAG}) overflow=${overflow.length} -> ${shot}`);
  }

  await ctx.close();
  await browser.close();

  if (issues.length) {
    console.log('\nIssues:');
    for (const i of issues) console.log('  ' + i);
  } else {
    console.log('\nNo overflow / page errors detected.');
  }
})();

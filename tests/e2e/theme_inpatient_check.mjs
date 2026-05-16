// 白天 / 暗色 模式視覺對比 — 把每個住院畫面在兩種主題各跑一張
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHOT_DIR = resolve(__dirname, 'home_shots');
mkdirSync(SHOT_DIR, { recursive: true });

const URL_BASE = process.env.PREVIEW_URL || 'http://127.0.0.1:3000/';

async function snap(theme) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 1600 }, deviceScaleFactor: 2, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.addInitScript((th) => {
    localStorage.setItem('mdpiece_user', JSON.stringify({ id:'demo', username:'demo', nickname:'示範' }));
    localStorage.setItem('mdpiece_onboarded', '1');
    localStorage.setItem('mdpiece_landing_theme', th);
    localStorage.setItem('mdpiece_care_mode', 'inpatient');
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get(){ return undefined; } });
  }, theme);
  await page.route('**/admissions/?**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ admissions:[{ id:'a1', status:'active', type:'acute', admit_date:new Date(Date.now()-2*86400000).toISOString(), diagnosis:'類風濕關節炎', ward:'8B-12' }] }) }));
  await page.route('**/admissions/a1', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ id:'a1', status:'active', medications:[] }) }));
  await page.route('**/emotions/daily**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ daily:[] }) }));

  await page.goto(URL_BASE, { waitUntil:'load' });
  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display='none';
    const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
    if (typeof showPage === 'function') showPage('home');
  });
  await page.waitForSelector('.home-inpatient', { timeout: 8000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: resolve(SHOT_DIR, `theme-${theme}-home.png`), fullPage: true });

  // 衛教獨立頁
  await page.evaluate(() => { if (typeof navigateTo === 'function') navigateTo('inpatientEdu', null); });
  await page.waitForSelector('.ip-edu-page', { timeout: 4000 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: resolve(SHOT_DIR, `theme-${theme}-edu.png`), fullPage: true });

  await browser.close();
}
await snap('light');
await snap('dark');
console.log('done');

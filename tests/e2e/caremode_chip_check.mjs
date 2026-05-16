// Care-mode chip 對比修：截 light + dark 兩主題下、active 兩種狀態 (門診 / 住院)
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHOT_DIR = resolve(__dirname, 'home_shots');
mkdirSync(SHOT_DIR, { recursive: true });
const URL_BASE = process.env.PREVIEW_URL || 'http://127.0.0.1:3000/';

async function snap(theme, mode, label) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 500 }, deviceScaleFactor: 2, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.addInitScript((args) => {
    localStorage.setItem('mdpiece_user', JSON.stringify({ id:'demo', username:'demo', nickname:'示範' }));
    localStorage.setItem('mdpiece_onboarded', '1');
    localStorage.setItem('mdpiece_landing_theme', args.theme);
    localStorage.setItem('mdpiece_care_mode', args.mode);
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get(){ return undefined; } });
  }, { theme, mode });
  await page.route('**/admissions/?**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ admissions:[] }) }));
  await page.route('**/medications/?**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ medications:[] }) }));
  await page.route('**/emotions/daily**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ daily:[] }) }));

  await page.goto(URL_BASE, { waitUntil:'load' });
  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display='none';
    const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
    if (typeof showPage === 'function') showPage('home');
  });
  await page.waitForSelector('.care-mode-card', { timeout: 6000 });
  await page.waitForTimeout(800);
  const el = await page.$('.care-mode-card');
  await el.screenshot({ path: resolve(SHOT_DIR, `caremode-${label}.png`) });
  await browser.close();
}

await snap('light', 'outpatient', 'light-outpatient');
await snap('light', 'inpatient',  'light-inpatient');
await snap('dark',  'outpatient', 'dark-outpatient');
await snap('dark',  'inpatient',  'dark-inpatient');
console.log('done');

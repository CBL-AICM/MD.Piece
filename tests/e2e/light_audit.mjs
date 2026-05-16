// 全面截圖白日模式下的住院 UI，找對比問題
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHOT_DIR = resolve(__dirname, 'home_shots/light-audit');
mkdirSync(SHOT_DIR, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 1600 }, deviceScaleFactor: 2, ignoreHTTPSErrors: true });
const page = await ctx.newPage();
await page.addInitScript(() => {
  localStorage.setItem('mdpiece_user', JSON.stringify({ id:'demo', username:'demo', nickname:'示範' }));
  localStorage.setItem('mdpiece_onboarded', '1');
  localStorage.setItem('mdpiece_landing_theme', 'light');
  localStorage.setItem('mdpiece_care_mode', 'inpatient');
  // Mock some data so things render
  localStorage.setItem('mdpiece_inpatient_rounds', JSON.stringify([
    { id:'r1', time: new Date().toISOString(), doctor:'張醫師', text:'類風濕用藥計畫照原訂，下午抽血追蹤 CRP，可下床走動。' },
  ]));
  Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get(){ return undefined; } });
});
const today = new Date().toISOString().slice(0,10);
await page.route('**/admissions/?**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ admissions:[
  { id:'a1', status:'active', type:'acute', admit_date:new Date(Date.now()-2*86400000).toISOString(), diagnosis:'類風濕關節炎', ward:'8B-12', discharge_date: new Date(Date.now()+3*86400000).toISOString().slice(0,10)+'T10:00' }
] }) }));
await page.route('**/admissions/a1', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ id:'a1', status:'active', type:'acute', medications:[
  { id:'m1', name:'Methotrexate', dose:'15mg', next_due_date: `${today}T14:00` },
] }) }));
await page.route('**/emotions/daily**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ daily:[
  { date: today, average_score: 0.6, count: 1 },
] }) }));

await page.goto('http://127.0.0.1:3000/', { waitUntil:'load' });
await page.evaluate(() => {
  const l = document.getElementById('landing'); if (l) l.style.display='none';
  const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
  if (typeof showPage === 'function') showPage('home');
});
await page.waitForSelector('.home-inpatient', { timeout: 8000 });
await page.waitForTimeout(1800);

// 1. 主頁 (整頁長截圖)
await page.screenshot({ path: resolve(SHOT_DIR, '1-home-full.png'), fullPage: true });
// 2. 個別區塊
const sections = [
  ['ip-now', '2-now'],
  ['ip-next', '3-next'],
  ['ip-sos', '4-sos'],
  ['ip-timeline', '5-timeline'],
  ['ip-progress', '6-progress'],
  ['ip-rounds', '7-rounds'],
  ['ip-trends', '8-trends'],
  ['ip-discharge', '9-discharge'],
  ['ip-edu', '10-edu'],
];
for (const [sel, name] of sections) {
  const el = await page.$('.' + sel);
  if (el) await el.screenshot({ path: resolve(SHOT_DIR, name + '.png') });
}

// 3. Sheets — open one of each
await page.click('#ip-rounds-add-btn');
await page.waitForTimeout(300);
await page.screenshot({ path: resolve(SHOT_DIR, '11-rounds-composer.png'), clip: { x:0, y:0, width:390, height:1200 } });
await page.evaluate(() => onInpatientRoundsCancel());
await page.waitForTimeout(200);

// Exam composer
await page.click('#ip-exam-add-btn');
await page.waitForTimeout(400);
await page.screenshot({ path: resolve(SHOT_DIR, '12-exam-composer.png'), clip: { x:0, y:0, width:390, height:1200 } });
await page.evaluate(() => closeInpatientExamComposer());
await page.waitForTimeout(300);

// Timeline tap → sheet
await page.click('.ip-tl-kind-med, .ip-tl-kind-meal');
await page.waitForSelector('#ip-tl-sheet.open', { timeout: 2000 }).catch(()=>{});
await page.waitForTimeout(300);
await page.screenshot({ path: resolve(SHOT_DIR, '13-timeline-sheet.png'), clip: { x:0, y:0, width:390, height:1200 } });
await page.evaluate(() => _closeInpatientTimelineSheet && _closeInpatientTimelineSheet());
await page.waitForTimeout(300);

// 衛教獨立頁
await page.evaluate(() => navigateTo('inpatientEdu', null));
await page.waitForSelector('.ip-edu-page', { timeout: 4000 });
await page.waitForTimeout(400);
await page.screenshot({ path: resolve(SHOT_DIR, '14-edu-page.png'), fullPage: true });

console.log('done, screenshots in', SHOT_DIR);
await browser.close();

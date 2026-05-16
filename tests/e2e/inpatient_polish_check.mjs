// 一次驗 4 件事：
//   A) 白日模式 contrast — --ip-muted 是否提高
//   B) 出院進度 stepper 4 步 (入院 / 感覺好 / 排定出院 / 出院) — 「感覺好一點」可推進
//   C) 趨勢 chip — 點下開 quicklog sheet，submit 後 sparkline 有資料
//   D) 衛教獨立頁 — 新增的 4 個經濟主題都在 (insurance/studentIns/illness14/social)
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHOT_DIR = resolve(__dirname, 'home_shots');
mkdirSync(SHOT_DIR, { recursive: true });

const URL_BASE = process.env.PREVIEW_URL || 'http://127.0.0.1:3000/';

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 1200 }, deviceScaleFactor: 2, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  const issues = [];
  page.on('pageerror', e => {
    if (/serviceWorker|addEventListener|querySelectorAll|register/.test(e.message)) return;
    issues.push(`pageerror: ${e.message}`);
  });
  await page.addInitScript(() => {
    localStorage.setItem('mdpiece_user', JSON.stringify({ id:'demo', username:'demo', nickname:'示範' }));
    localStorage.setItem('mdpiece_onboarded', '1');
    localStorage.setItem('mdpiece_landing_theme', 'light');
    localStorage.setItem('mdpiece_care_mode', 'inpatient');
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get(){ return undefined; } });
  });
  // Active admission with discharge_date scheduled
  const futureDischarge = new Date(Date.now() + 4*86400000).toISOString().slice(0,10) + 'T10:00';
  await page.route('**/admissions/?**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ admissions:[
    { id:'a1', status:'active', type:'acute', admit_date:new Date(Date.now()-2*86400000).toISOString(), diagnosis:'類風濕關節炎', ward:'8B-12', discharge_date: futureDischarge },
  ] }) }));
  await page.route('**/admissions/a1', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ id:'a1', status:'active', medications:[] }) }));
  await page.route('**/emotions/daily**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ daily: [] }) }));

  await page.goto(URL_BASE, { waitUntil:'load' });
  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display='none';
    const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
    if (typeof showPage === 'function') showPage('home');
  });
  await page.waitForSelector('.home-inpatient', { timeout: 8000 });
  await page.waitForTimeout(1800);

  // ── A) Contrast: --ip-muted 不應該是 rgba(31,61,88,0.55) 太淺 ─────
  const mutedColor = await page.$eval('.ip-rounds-empty', el => getComputedStyle(el).color);
  // 解析 rgba/rgb 看 alpha
  const m = mutedColor.match(/rgba?\(([^)]+)\)/);
  if (m) {
    const parts = m[1].split(',').map(s => parseFloat(s.trim()));
    const alpha = parts.length === 4 ? parts[3] : 1;
    if (alpha < 0.65) issues.push(`A: muted alpha too low (${alpha}) — text barely visible on light bg`);
  }

  // ── B) 出院進度 — 4 個 step, 「感覺好一點」推進 ─────────────
  const stepCount = await page.$$eval('.ip-step', els => els.length);
  if (stepCount !== 4) issues.push(`B: expected 4 steps, got ${stepCount}`);
  const stepIds = await page.$$eval('.ip-step', els => els.map(li => li.dataset.stepId));
  const expectedIds = ['admit','feeling','planned','done'];
  if (JSON.stringify(stepIds) !== JSON.stringify(expectedIds)) {
    issues.push(`B: step ids expected ${expectedIds}, got ${stepIds}`);
  }
  // 點「感覺好一點」 → 應該標 done
  await page.click('.ip-step[data-step-id="feeling"] .ip-step-dot');
  await page.waitForTimeout(800);
  const feelingDone = await page.$eval('.ip-step[data-step-id="feeling"]', el => el.classList.contains('done'));
  if (!feelingDone) issues.push('B: feeling step should be done after click');

  // ── C) 趨勢 quicklog ────────────────────────────────────
  // 預設 pain/fatigue/mood 都應該是「點一下記今天」(empty)
  const arrowBefore = await page.$eval('#ip-trend-arrow-fatigue', el => el.textContent);
  if (arrowBefore !== '＋') issues.push(`C: fatigue arrow expected "+", got "${arrowBefore}"`);
  // 點疲勞 chip → quicklog 開
  await page.click('.ip-trend-chip[data-key="fatigue"]');
  await page.waitForSelector('#ip-quicklog-sheet.open', { timeout: 2000 });
  await page.waitForTimeout(300);
  const qlBtns = await page.$$eval('.ip-ql-num', els => els.length);
  if (qlBtns !== 5) issues.push(`C: quicklog expected 5 buttons, got ${qlBtns}`);
  await page.locator('.ip-ql-panel').screenshot({ path: resolve(SHOT_DIR, 'quicklog-fatigue.png') });
  // 點 3 分
  await page.click('.ip-ql-num[data-v="3"]');
  await page.waitForTimeout(600);
  // sheet 關閉，趨勢線應該有資料
  const fatigueFootAfter = await page.$eval('#ip-trend-foot-fatigue', el => el.textContent);
  if (fatigueFootAfter.includes('點一下')) issues.push(`C: fatigue should have data after log, got "${fatigueFootAfter}"`);

  // ── D) 衛教獨立頁有經濟主題 ─────────────────────────────
  await page.evaluate(() => navigateTo('inpatientEdu', null));
  await page.waitForSelector('.ip-edu-page', { timeout: 4000 });
  await page.waitForTimeout(400);
  const totalSections = await page.$$eval('.ip-edu-section', els => els.length);
  if (totalSections !== 14) issues.push(`D: expected 14 edu sections (10 + 4 new finance), got ${totalSections}`);
  const newTopics = ['insurance', 'studentIns', 'illness14', 'social'];
  for (const t of newTopics) {
    const exists = await page.$('#ip-edu-sec-' + t);
    if (!exists) issues.push(`D: missing edu topic ${t}`);
  }
  // 截圖經濟區
  await page.evaluate(() => _ipEduScrollTo('insurance'));
  await page.waitForTimeout(800);
  await page.screenshot({ path: resolve(SHOT_DIR, 'edu-finance-topics.png'), clip: { x:0, y:0, width:390, height:1200 } });

  // 全頁長截
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);
  await page.screenshot({ path: resolve(SHOT_DIR, 'polish-edu-full.png'), fullPage: true });

  // 回首頁長截 (light)
  await page.evaluate(() => navigateTo('home', null));
  await page.waitForSelector('.home-inpatient', { timeout: 4000 });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: resolve(SHOT_DIR, 'polish-home-light-full.png'), fullPage: true });

  await browser.close();

  if (issues.length) {
    console.log('❌ Issues:');
    issues.forEach(i => console.log('  ' + i));
    process.exit(1);
  }
  console.log('✓ Inpatient polish — 4 fixes all green:');
  console.log('  A) Light mode contrast 提高');
  console.log('  B) 出院進度 4 步 + 感覺好一點可推進');
  console.log('  C) 疼痛/疲勞/心情 chip → quicklog sheet 1-5 分 + emoji → 寫進趨勢');
  console.log('  D) 衛教新增 4 個經濟主題 (insurance/studentIns/illness14/social)');
})();

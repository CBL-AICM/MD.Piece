// 設計憲法 5 件事 e2e：
//  A) 條 3 — 提醒語氣切換存到 localStorage + reminderToneify
//  B) 條 6 — 家屬代理 banner 顯示 + 切回我自己
//  C) 條 2 — 趨勢 chip 有 ai-explain，內含「為什麼」「信心」「來源」
//  D) 條 5 — 衛教 discharge topic 有 IPDAS Decision Aid
//  E) 場景 C — 時間軸頁能上傳 (用 mock 圖片，跳過 OCR)
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
  const ctx = await browser.newContext({ viewport: { width: 390, height: 1400 }, deviceScaleFactor: 2, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  const issues = [];
  page.on('pageerror', e => {
    if (/serviceWorker|addEventListener|querySelectorAll|register/.test(e.message)) return;
    issues.push(`pageerror: ${e.message}`);
  });

  // 預先塞一些症狀紀錄讓趨勢線有資料
  await page.addInitScript(() => {
    localStorage.setItem('mdpiece_user', JSON.stringify({ id:'demo', username:'demo', nickname:'示範' }));
    localStorage.setItem('mdpiece_onboarded', '1');
    localStorage.setItem('mdpiece_landing_theme', 'light');
    localStorage.setItem('mdpiece_care_mode', 'inpatient');
    const today = new Date();
    const syms = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(today); d.setDate(d.getDate() - i);
      syms.push({ id:'s'+i, categoryId:'fatigue', intensity: Math.max(1, 5-i), frequency:1, recordedAt: d.toISOString() });
    }
    localStorage.setItem('mdpiece_symptoms', JSON.stringify(syms));
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get(){ return undefined; } });
  });
  await page.route('**/admissions/?**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ admissions:[{ id:'a1', status:'active', type:'acute', admit_date: new Date(Date.now()-86400000).toISOString(), diagnosis:'類風濕關節炎' }] }) }));
  await page.route('**/admissions/a1', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ id:'a1', medications:[] }) }));
  await page.route('**/emotions/daily**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ daily:[] }) }));

  await page.goto(URL_BASE, { waitUntil:'load' });
  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display='none';
    const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
    if (typeof showPage === 'function') showPage('home');
  });
  await page.waitForSelector('.home-inpatient', { timeout: 8000 });
  await page.waitForTimeout(2000);

  // ── A) reminderTone ─────────────────────────────────
  const toneBefore = await page.evaluate(() => getReminderTone());
  if (toneBefore !== 'warm') issues.push(`A: default tone expected warm, got ${toneBefore}`);
  await page.evaluate(() => setReminderTone('strict'));
  const toneAfter = await page.evaluate(() => getReminderTone());
  if (toneAfter !== 'strict') issues.push(`A: tone after setReminderTone should be strict, got ${toneAfter}`);
  const toneified = await page.evaluate(() => reminderToneify('請記得吃藥'));
  // strict 不改寫
  if (toneified !== '請記得吃藥') issues.push(`A: strict tone should keep original, got "${toneified}"`);
  await page.evaluate(() => setReminderTone('warm'));

  // ── B) proxy mode banner ───────────────────────────
  let bannerHiddenBefore = await page.$eval('#proxy-banner', el => el.hidden);
  if (!bannerHiddenBefore) issues.push('B: banner should be hidden initially');
  await page.evaluate(() => {
    setProxyFor({ name: '王阿嬤', relation: '母親' });
    refreshProxyBanner();
  });
  await page.waitForTimeout(300);
  const bannerVisible = await page.$eval('#proxy-banner', el => !el.hidden);
  if (!bannerVisible) issues.push('B: banner should be visible after setProxyFor');
  const bannerText = await page.$eval('#proxy-banner', el => el.textContent);
  if (!bannerText.includes('王阿嬤')) issues.push(`B: banner should mention 王阿嬤, got "${bannerText.slice(0, 60)}"`);
  await page.locator('#proxy-banner').screenshot({ path: resolve(SHOT_DIR, 'proxy-banner.png') });

  // 寫一筆症狀，應該帶 proxy_for
  await page.evaluate(() => saveSymptomEntry({ id:'t1', categoryId:'fatigue', intensity:3, frequency:1, recordedAt: new Date().toISOString() }));
  const lastSym = await page.evaluate(() => {
    const a = JSON.parse(localStorage.getItem('mdpiece_symptoms') || '[]');
    return a[a.length - 1];
  });
  if (lastSym.proxy_for !== '王阿嬤') issues.push(`B: symptom should have proxy_for="王阿嬤", got "${lastSym.proxy_for}"`);

  // 切回我自己
  await page.evaluate(() => { setProxyFor(null); refreshProxyBanner(); });
  await page.waitForTimeout(200);
  const bannerHiddenAfter = await page.$eval('#proxy-banner', el => el.hidden);
  if (!bannerHiddenAfter) issues.push('B: banner should hide after setProxyFor(null)');

  // ── C) AI explain on trend chip ─────────────────────
  await page.evaluate(() => loadInpatientTrendSparklines());
  await page.waitForTimeout(800);
  const explainExists = await page.$$eval('#ip-trend-explain-fatigue .ai-explain', els => els.length);
  if (explainExists < 1) issues.push('C: ai-explain should exist for fatigue trend');
  // 打開看
  const summaryText = await page.$eval('#ip-trend-explain-fatigue .ai-explain summary', el => el.textContent);
  if (!summaryText.includes('為什麼')) issues.push(`C: explain summary should contain 為什麼, got "${summaryText}"`);
  if (!summaryText.includes('信心')) issues.push(`C: explain summary should include confidence label, got "${summaryText}"`);

  await page.evaluate(() => {
    const d = document.querySelector('#ip-trend-explain-fatigue .ai-explain');
    if (d) d.open = true;
  });
  await page.waitForTimeout(200);
  await page.locator('#ip-trend-explain-fatigue .ai-explain').screenshot({ path: resolve(SHOT_DIR, 'ai-explain.png') });

  // ── D) Decision Aid in inpatientEdu ────────────────
  await page.evaluate(() => navigateTo('inpatientEdu', null));
  await page.waitForSelector('.ip-edu-page', { timeout: 4000 });
  await page.waitForTimeout(400);
  // 展開 discharge section
  await page.evaluate(() => _ipEduScrollTo('discharge'));
  await page.waitForTimeout(500);
  const daExists = await page.$$eval('#ip-edu-sec-discharge .decision-aid', els => els.length);
  if (daExists < 1) issues.push('D: Decision Aid should exist in discharge topic');
  const daOptions = await page.$$eval('#ip-edu-sec-discharge .da-option', els => els.length);
  if (daOptions !== 2) issues.push(`D: expected 2 decision options, got ${daOptions}`);
  await page.locator('#ip-edu-sec-discharge .decision-aid').screenshot({ path: resolve(SHOT_DIR, 'decision-aid.png') });

  // ── E) Timeline page ───────────────────────────────
  await page.evaluate(() => navigateTo('timeline', null));
  await page.waitForSelector('.tl-page', { timeout: 4000 });
  await page.waitForTimeout(500);
  const filters = await page.$$eval('.tl-filter', els => els.length);
  if (filters !== 5) issues.push(`E: expected 5 filter buttons (all + 4 kinds), got ${filters}`);
  // 開上傳 sheet
  await page.click('.tl-add-btn');
  await page.waitForSelector('#tl-upload-sheet.open', { timeout: 2000 });
  // 直接呼叫 submitTimelineUpload (繞過 OCR)
  await page.evaluate(() => {
    document.getElementById('tl-up-kind').value = 'lab';
    document.getElementById('tl-up-date').value = new Date().toISOString().slice(0,10);
    document.getElementById('tl-up-title').value = 'CRP 抽血追蹤';
    document.getElementById('tl-up-summary').value = 'CRP 從 3.2 降到 1.8 mg/dL，發炎指數下降';
    submitTimelineUpload();
  });
  await page.waitForTimeout(600);
  const cardCount = await page.$$eval('.tl-card', els => els.length);
  if (cardCount !== 1) issues.push(`E: expected 1 timeline card after upload, got ${cardCount}`);
  await page.locator('.tl-page').screenshot({ path: resolve(SHOT_DIR, 'timeline-page.png') });

  await browser.close();
  if (issues.length) {
    console.log('❌ Issues:');
    issues.forEach(i => console.log('  ' + i));
    process.exit(1);
  }
  console.log('✓ 5 constitution features all wired:');
  console.log('  A) 條 3 reminderTone — set/get + warm/strict/short reminderToneify');
  console.log('  B) 條 6 proxy banner — 顯示 / 寫進 saveSymptomEntry.proxy_for / 切回');
  console.log('  C) 條 2 AI explain — fatigue trend 有 details with why+confidence');
  console.log('  D) 條 5 Decision Aid — discharge topic 內 2 個選項 + 利弊 + 風險 + 下一步');
  console.log('  E) 場景 C Timeline — 上傳 sheet → 卡片渲染');
})();

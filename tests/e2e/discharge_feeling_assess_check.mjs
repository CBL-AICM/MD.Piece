// 驗 (08) 出院進度 的「好一點」可由 (07) 這幾天的變化趨勢自動評估：
//   1) 沒有 7 日紀錄時 — feeling step 不會被標 suggested，sub-text 維持「我感覺好一點時點這」
//   2) 注入 7 天 pain↘ / fatigue↘ / mood↗ 的紀錄 → reload 後 feeling step 應自動帶 suggested
//      + sub-text 改成「AI 評估：好一點了 · 點此確認」+ 出現 aiExplain (為什麼…) 卡
//   3) 點 feeling step 仍然推進到 done（既有 manual click 行為不被破壞，相容 inpatient_polish_check）
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHOT_DIR = resolve(__dirname, 'home_shots');
mkdirSync(SHOT_DIR, { recursive: true });

const URL_BASE = process.env.PREVIEW_URL || 'http://127.0.0.1:3000/';

function seedSymptomsAndMood() {
  // 7 天 pain↘ (5→1)、fatigue↘ (5→1)、mood↗ (1→5)；用同樣的 categoryId / 1-5 scale
  const today = new Date();
  const syms = [];
  const moods = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(today); d.setDate(d.getDate() - i);
    const iso = d.toISOString();
    const recoveredness = 6 - i; // 1..7 高 → 好轉中
    const painVal    = Math.max(1, 6 - recoveredness);          // 5,4,3,2,1
    const fatigueVal = Math.max(1, 6 - recoveredness);          // 5,4,3,2,1
    const moodVal    = Math.min(5, recoveredness);              // 1,2,3,4,5
    syms.push({ id: 'p_' + i, categoryId: 'headache', intensity: painVal, frequency: 1, recordedAt: iso });
    syms.push({ id: 'f_' + i, categoryId: 'fatigue',  intensity: fatigueVal, frequency: 1, recordedAt: iso });
    moods.push({ value: moodVal, at: iso });
  }
  localStorage.setItem('mdpiece_symptoms', JSON.stringify(syms));
  localStorage.setItem('mdpiece_inpatient_mood_local', JSON.stringify(moods));
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 1400 }, deviceScaleFactor: 2, ignoreHTTPSErrors: true });
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
  const futureDischarge = new Date(Date.now() + 4*86400000).toISOString().slice(0,10) + 'T10:00';
  await page.route('**/admissions/?**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ admissions:[
    { id:'a1', status:'active', type:'acute', admit_date:new Date(Date.now()-6*86400000).toISOString(), diagnosis:'類風濕關節炎', ward:'8B-12', discharge_date: futureDischarge },
  ] }) }));
  await page.route('**/admissions/a1', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ id:'a1', status:'active', medications:[] }) }));
  // 後端 mood 回空，強迫使用 local mood series 來評估
  await page.route('**/emotions/daily**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ daily: [] }) }));
  await page.route('**/emotions/log', r => r.fulfill({ status:200, contentType:'application/json', body: '{}' }));

  // ── 1) 沒紀錄：feeling step 不應該被 suggested ──────────────
  await page.goto(URL_BASE, { waitUntil:'load' });
  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display='none';
    const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
    if (typeof showPage === 'function') showPage('home');
  });
  await page.waitForSelector('.home-inpatient', { timeout: 8000 });
  await page.waitForTimeout(1800);

  const stepCount = await page.$$eval('.ip-step', els => els.length);
  if (stepCount !== 4) issues.push(`expected 4 steps, got ${stepCount}`);

  const suggestedBefore = await page.$eval('.ip-step[data-step-id="feeling"]', el => el.classList.contains('suggested'));
  if (suggestedBefore) issues.push('no-data state: feeling step should NOT have .suggested');
  const subBefore = await page.$eval('.ip-step[data-step-id="feeling"] .ip-step-sub', el => el.textContent.trim());
  if (subBefore !== '我感覺好一點時點這') issues.push(`no-data sub-text expected "我感覺好一點時點這", got "${subBefore}"`);
  const explainEmpty = await page.$eval('#ip-discharge-feeling-explain', el => el.innerHTML.trim());
  if (explainEmpty !== '') issues.push(`no-data explainer should be empty, got "${explainEmpty.slice(0,60)}"`);

  // ── 2) 注入 7 天好轉趨勢 → 重新觸發 trend + stepper 應自動 suggest ──
  await page.evaluate(seedSymptomsAndMood);
  await page.evaluate(() => {
    // 清掉舊的 feeling localStorage 標記，確保我們測「未手動標記」的情況
    Object.keys(localStorage).filter(k => k.indexOf('mdpiece_inpatient_feeling_') === 0).forEach(k => localStorage.removeItem(k));
    // 重新跑 trend (會帶起 _ipRefreshFeelingHint) + 重灌 stepper
    if (typeof loadInpatientActiveAdmission === 'function') loadInpatientActiveAdmission();
    if (typeof loadInpatientTrendSparklines === 'function') loadInpatientTrendSparklines();
  });
  await page.waitForTimeout(1500);

  const verdict = await page.evaluate(() => {
    const a = window._ipLatestFeelingAssessment;
    return a ? { verdict: a.verdict, have: a.have, confidence: a.confidence || null } : null;
  });
  if (!verdict || verdict.verdict !== 'better') {
    issues.push(`assessment expected verdict=better, got ${JSON.stringify(verdict)}`);
  }
  const suggestedAfter = await page.$eval('.ip-step[data-step-id="feeling"]', el => el.classList.contains('suggested'));
  if (!suggestedAfter) issues.push('improving trend: feeling step should have .suggested class');
  const subAfter = await page.$eval('.ip-step[data-step-id="feeling"] .ip-step-sub', el => el.textContent.trim());
  if (!/好一點/.test(subAfter)) issues.push(`improving sub-text expected to mention 好一點, got "${subAfter}"`);
  const explainerHtml = await page.$eval('#ip-discharge-feeling-explain', el => el.innerHTML);
  if (!/ai-explain/.test(explainerHtml)) issues.push('improving state: aiExplain block should be mounted under stepper');
  if (!/為什麼依\s*07\s*趨勢建議「好一點」/.test(explainerHtml)) issues.push('aiExplain summary should reference 07 趨勢');

  await page.locator('.ip-discharge').screenshot({ path: resolve(SHOT_DIR, 'discharge-feeling-suggested.png') });

  // ── 3) 點 feeling step 仍然推進到 done（與 inpatient_polish_check 相容） ──
  await page.click('.ip-step[data-step-id="feeling"] .ip-step-dot');
  await page.waitForTimeout(800);
  const feelingDone = await page.$eval('.ip-step[data-step-id="feeling"]', el => el.classList.contains('done'));
  if (!feelingDone) issues.push('manual click: feeling step should still be done after click');
  const feelingSuggestedAfterClick = await page.$eval('.ip-step[data-step-id="feeling"]', el => el.classList.contains('suggested'));
  if (feelingSuggestedAfterClick) issues.push('after click → done, .suggested should be cleared');
  const explainerAfterClick = await page.$eval('#ip-discharge-feeling-explain', el => el.innerHTML.trim());
  if (explainerAfterClick !== '') issues.push('after click → done, explainer should be cleared');

  await browser.close();

  if (issues.length) {
    console.log('❌ Issues:');
    issues.forEach(i => console.log('  ' + i));
    process.exit(1);
  }
  console.log('✓ Discharge feeling step driven by 07 trend assessment:');
  console.log('  1) no data → no suggestion');
  console.log('  2) pain↘ / fatigue↘ / mood↗ 7d → .suggested + aiExplain rendered');
  console.log('  3) manual click still toggles to done (backwards compatible)');
})();

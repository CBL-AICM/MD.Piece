// E2E：床邊症狀 → 自動建議「想問醫師」 — 住院模式 v2 Phase 2（critique P0-2/P0-3）
//  1. 有床邊症狀 → #ip-qpl-personal 渲染個人化建議題，每顆帶 source 標籤（來自：痛 8/10）
//  2. 點建議題 → addInpatientQuestion → POST /inpatient/questions 帶該題文字
//  3. 無建議（suggested:[]）→ #ip-qpl-personal 清空，不臆造（規則 12）
//  4. submitBedside 後 → 重新打 /inpatient/suggested-questions（症狀更新即時刷新，P0-2 迴圈）
//
// 後端 /inpatient/* 以 page.route mock（與 inpatient_*_check 同慣例），不需真後端。
// 純規則計分邏輯由 backend 單元測試（_suggest_from_bedside 6 斷言）覆蓋；本檔專測前端串接行為。
import { chromium } from 'playwright';

const URL_BASE = process.env.PREVIEW_URL || 'http://127.0.0.1:3000/';
const PID = 'ipsq-e2e';

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  const issues = [];
  page.on('pageerror', e => {
    if (/serviceWorker|addEventListener|querySelectorAll|register/.test(e.message)) return;
    issues.push('pageerror: ' + e.message);
  });

  await page.addInitScript(() => {
    localStorage.setItem('mdpiece_user', JSON.stringify({ id: 'ipsq-e2e', username: 'demo', nickname: '示範', role: 'patient' }));
    localStorage.setItem('mdpiece_onboarded', '1');
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get() { return undefined; } });
  });

  // ── route mocks + 計數 ──
  let suggestedCalls = 0;
  let postedQuestion = null;
  let suggestedBody = { suggested: [], based_on: { has_log: false } };

  await page.route('**/inpatient/suggested-questions**', route => {
    suggestedCalls++;
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(suggestedBody) });
  });
  await page.route('**/inpatient/questions?**', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ questions: [] }),
  }));
  await page.route('**/inpatient/questions', route => {
    if (route.request().method() === 'POST') {
      postedQuestion = JSON.parse(route.request().postData() || '{}');
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'q1', text: postedQuestion.text, status: 'open' }) });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ questions: [] }) });
  });
  await page.route('**/inpatient/qpl-bank', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ questions: [] }),
  }));
  await page.route('**/inpatient/bedside**', route => {
    if (route.request().method() === 'POST') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'b1' }) });
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ logs: [] }) });
  });

  await page.goto(URL_BASE, { waitUntil: 'load' });
  await page.waitForFunction(
    () => typeof bedside === 'function' && typeof loadInpatientSuggestedQuestions === 'function' && typeof _ipPid === 'function',
    undefined, { timeout: 8000 },
  );

  // 隱藏 landing 全螢幕 overlay（否則攔截點擊）+ 把 bedside 頁注入 DOM（含 #ip-qpl-personal / #ip-bs-form）
  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display = 'none';
    const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
    const host = document.createElement('div');
    host.id = 'e2e-bedside-host';
    host.innerHTML = bedside();
    document.body.appendChild(host);
  });

  // ── S1：有症狀 → 渲染個人化建議 + source 標籤 ──
  suggestedBody = {
    suggested: [
      { text: '我的疼痛到 8 分了，止痛藥可以再調整嗎？', source: '痛 8/10' },
      { text: '我這幾天晚上睡不好，有沒有辦法改善？', source: '睡眠不好' },
    ],
    based_on: { has_log: true },
  };
  await page.evaluate(() => loadInpatientSuggestedQuestions());
  await page.waitForFunction(() => document.querySelectorAll('#ip-qpl-personal .ip-qpl-suggest').length > 0, undefined, { timeout: 4000 });

  const n = await page.$$eval('#ip-qpl-personal .ip-qpl-suggest', els => els.length);
  if (n !== 2) issues.push(`render: expected 2 personal suggestions, got ${n}`);
  const headTxt = await page.$eval('#ip-qpl-personal .ip-qpl-personal-head', el => el.textContent).catch(() => '');
  if (!/依你今天記的/.test(headTxt)) issues.push('render: missing personalized head label');
  const catTxt = await page.$$eval('#ip-qpl-personal .ip-qpl-cat', els => els.map(e => e.textContent).join('|'));
  if (!/痛 8\/10/.test(catTxt)) issues.push(`render: source tag should show "痛 8/10", got "${catTxt}"`);

  // ── S2：點建議 → POST /inpatient/questions 帶該題文字 ──
  await page.click('#ip-qpl-personal .ip-qpl-suggest');
  await page.waitForTimeout(300);
  if (!postedQuestion) issues.push('click: suggestion click should POST /inpatient/questions');
  else if (postedQuestion.text !== '我的疼痛到 8 分了，止痛藥可以再調整嗎？') {
    issues.push(`click: posted wrong text: "${postedQuestion.text}"`);
  } else if (postedQuestion.patient_id !== 'ipsq-e2e') {
    issues.push(`click: posted wrong patient_id: "${postedQuestion.patient_id}"`);
  }

  // ── S3：無建議 → #ip-qpl-personal 清空（不臆造，規則 12）──
  suggestedBody = { suggested: [], based_on: { has_log: true } };
  await page.evaluate(() => loadInpatientSuggestedQuestions());
  await page.waitForFunction(() => document.querySelectorAll('#ip-qpl-personal .ip-qpl-suggest').length === 0, undefined, { timeout: 4000 });
  const emptyHtml = await page.$eval('#ip-qpl-personal', el => el.innerHTML.trim());
  if (emptyHtml !== '') issues.push('empty: #ip-qpl-personal should be empty when no suggestions');

  // ── S4：submitBedside 後 → 重新打 suggested-questions（P0-2 迴圈刷新）──
  const before = suggestedCalls;
  await page.evaluate(() => { window._ipBedsideDraft = { pain: 8 }; if (typeof _ipBedsideDraft !== 'undefined') { _ipBedsideDraft.pain = 8; } });
  await page.evaluate(() => submitBedside());
  await page.waitForTimeout(400);
  if (suggestedCalls <= before) issues.push('refresh: submitBedside should re-fetch /inpatient/suggested-questions');

  await browser.close();

  if (issues.length) {
    console.log('❌ Issues:');
    issues.forEach(i => console.log('  ' + i));
    process.exit(1);
  }
  console.log('✓ All inpatient suggested-questions (Phase 2) checks passed.');
  console.log('  - render: personalized suggestions with source tags (來自：痛 8/10)');
  console.log('  - click: suggestion → POST /inpatient/questions with that text + patient_id');
  console.log('  - empty: #ip-qpl-personal cleared when suggested=[] (no fabrication)');
  console.log('  - refresh: submitBedside re-fetches suggested-questions (P0-2 loop)');
})();

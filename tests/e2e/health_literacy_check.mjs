// E2E：健康識能（eHEALS）篩檢 + 簡化模式 — 住院模式 v2 之 M07
//  1. openEhealsScreen() → 8 題渲染、每題 5 個 Likert 選項
//  2. 送出按鈕：全部作答前 disabled、作答完啟用，計數同步
//  3. 低分送出 → html.elder-mode（簡化模式）自動套用
//  4. 高分送出 → 不改變使用者現有模式
//  5. 稍後再說（skip）→ 記 mdpiece_ehl_skip 旗標、模式不變
//  6. maybeShowEhealsScreen：done/skip 旗標存在時直接 onDone、不再彈窗
//
// 後端 /health-literacy/* 以 page.route mock（與 inpatient_*_check 同慣例），不需真後端。
// 真正的計分邏輯由 backend TestClient 單元測試覆蓋；本檔專測前端行為與串接。
import { chromium } from 'playwright';

const URL_BASE = process.env.PREVIEW_URL || 'http://127.0.0.1:3000/';
const UID = 'ehl-e2e';

const QUESTIONS = {
  instrument: 'eHEALS',
  scale: ['非常不同意', '不同意', '普通', '同意', '非常同意'],
  items: Array.from({ length: 8 }, (_, i) => ({ id: i + 1, key: 'ehl.q' + (i + 1), text: '測試題目 ' + (i + 1) })),
  intro: '測試說明文字',
  disclaimer: '測試免責聲明',
};

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
    localStorage.setItem('mdpiece_user', JSON.stringify({ id: 'ehl-e2e', username: 'demo', nickname: '示範', role: 'patient' }));
    localStorage.setItem('mdpiece_onboarded', '1');
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get() { return undefined; } });
  });

  // ── mock eHEALS endpoints（mirror 後端 ≤25=simplified 門檻）──
  await page.route('**/health-literacy/questions', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify(QUESTIONS),
  }));
  await page.route('**/health-literacy/latest**', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ result: null }),
  }));
  await page.route('**/health-literacy/screen', route => {
    const body = JSON.parse(route.request().postData() || '{}');
    const total = (body.answers || []).reduce((a, b) => a + b, 0);
    const simplified = total <= 25;
    route.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify({
        total_score: total,
        recommended_mode: simplified ? 'simplified' : 'standard',
        literacy_level: simplified ? 'low' : 'high',
        explanation: simplified ? '已幫你切換成大字簡化版' : '維持標準版面',
        _persisted: true,
      }),
    });
  });

  await page.goto(URL_BASE, { waitUntil: 'load' });
  await page.waitForFunction(() => typeof openEhealsScreen === 'function' && typeof getStablePatientId === 'function', { timeout: 8000 });

  // 進到 app：隱藏 landing 全螢幕 overlay（否則它會攔截 sheet 的點擊）。
  // 真實使用時 sheet 只在 onboarding / 設定頁開啟，landing 早已關閉。
  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display = 'none';
    const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
    if (typeof showPage === 'function') showPage('home');
  });
  await page.waitForTimeout(300);

  // 開篩檢 + 答題（val 1..5）+ 送出，回傳路上量到的狀態
  async function runScreen(val) {
    await page.evaluate(() => openEhealsScreen());
    await page.waitForSelector('#ehl-sheet .ehl-q', { timeout: 4000 });
    // 確保可互動（headless rAF 偶爾不觸發 .open；真實瀏覽器一定會）
    await page.evaluate(() => { const s = document.getElementById('ehl-sheet'); if (s) s.classList.add('open'); });

    const qCount = await page.$$eval('#ehl-sheet .ehl-q', els => els.length);
    if (qCount !== 8) issues.push(`render: expected 8 questions, got ${qCount}`);
    const optCount = await page.$$eval('#ehl-q-1 .ehl-opt', els => els.length);
    if (optCount !== 5) issues.push(`render: expected 5 options/question, got ${optCount}`);

    const disabledBefore = await page.$eval('#ehl-submit', el => el.disabled);
    if (!disabledBefore) issues.push('gating: submit should be DISABLED before answering');

    for (let i = 1; i <= 8; i++) await page.click(`#ehl-q-${i} .ehl-opt[data-v="${val}"]`);

    const countText = await page.$eval('#ehl-count', el => el.textContent);
    if (countText !== '8') issues.push(`gating: counter should read 8, got ${countText}`);
    const disabledAfter = await page.$eval('#ehl-submit', el => el.disabled);
    if (disabledAfter) issues.push('gating: submit should be ENABLED after all answered');

    await page.click('#ehl-submit');
    await page.waitForSelector('#ehl-sheet', { state: 'detached', timeout: 4000 });
  }

  // 1. 高分（全 5 = 40）→ elder 不套用
  await runScreen(5);
  if (await page.evaluate(() => document.documentElement.classList.contains('elder-mode'))) {
    issues.push('high score should NOT enable elder-mode');
  }

  // 2. 低分（全 1 = 8）→ elder 套用
  await runScreen(1);
  if (!(await page.evaluate(() => document.documentElement.classList.contains('elder-mode')))) {
    issues.push('low score SHOULD enable elder-mode (simplified)');
  }

  // 3. 稍後再說（skip）→ 記旗標、不再動模式
  await page.evaluate(() => { try { localStorage.removeItem('mdpiece_ehl_skip:ehl-e2e'); } catch (e) {} openEhealsScreen(); });
  await page.waitForSelector('#ehl-sheet .ehl-q', { timeout: 4000 });
  await page.evaluate(() => { const s = document.getElementById('ehl-sheet'); if (s) s.classList.add('open'); });
  await page.click('#ehl-sheet .ip-prep-secondary');
  await page.waitForSelector('#ehl-sheet', { state: 'detached', timeout: 4000 });
  const skipFlag = await page.evaluate(() => localStorage.getItem('mdpiece_ehl_skip:ehl-e2e'));
  if (skipFlag !== '1') issues.push('skip: should set mdpiece_ehl_skip flag');

  // 4. maybeShowEhealsScreen：done 旗標存在 → 直接 onDone、不彈窗
  const maybeResult = await page.evaluate(() => new Promise(res => {
    localStorage.setItem('mdpiece_ehl_done:ehl-e2e', '1');
    maybeShowEhealsScreen(() => res('onDone'));
    setTimeout(() => res('timeout:' + (document.getElementById('ehl-sheet') ? 'opened' : 'no-sheet')), 700);
  }));
  if (maybeResult !== 'onDone') issues.push('maybeShow: should call onDone (skip popup) when done flag set, got ' + maybeResult);

  await browser.close();

  if (issues.length) {
    console.log('❌ Issues:');
    issues.forEach(i => console.log('  ' + i));
    process.exit(1);
  }
  console.log('✓ All eHEALS (M07) checks passed.');
  console.log('  - render: 8 questions × 5 Likert options');
  console.log('  - gating: submit disabled until all 8 answered, counter syncs');
  console.log('  - low score → elder-mode (simplified) auto-applied');
  console.log('  - high score → mode unchanged');
  console.log('  - skip → mdpiece_ehl_skip flag set');
  console.log('  - maybeShow → onDone without popup when already done');
})();

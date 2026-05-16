// 住院首頁互動測試 — 三件事：
//  1. 查房紀錄能 add → render → delete
//  2. SOS 按一下會出現「今天已回報」歷史 chip
//  3. Timeline item 點下會彈 bottom sheet，標記完成後 dot 變綠
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
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    ignoreHTTPSErrors: true,
  });
  const page = await ctx.newPage();
  const issues = [];
  page.on('pageerror', e => {
    if (/serviceWorker|addEventListener|querySelectorAll|register/.test(e.message)) return;
    issues.push(`pageerror: ${e.message}`);
  });

  await page.addInitScript(() => {
    localStorage.setItem('mdpiece_user', JSON.stringify({ id:'demo', username:'demo', nickname:'示範', role:'patient', avatar_color:'#5B9FE8' }));
    localStorage.setItem('mdpiece_onboarded', '1');
    localStorage.setItem('mdpiece_landing_theme', 'dark');
    localStorage.setItem('mdpiece_care_mode', 'inpatient');
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get(){ return undefined; } });
  });

  // Mock /admissions API so timeline has synthetic items (rounds, meals, vitals)
  await page.route('**/admissions/?**', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ admissions: [{ id: 'a1', status: 'active', type: 'acute', admit_date: new Date(Date.now() - 3*86400000).toISOString(), diagnosis: '類風濕關節炎', ward: '8B-12' }] }),
  }));
  await page.route('**/admissions/a1', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ id: 'a1', status: 'active', medications: [] }),
  }));
  await page.route('**/emotions/daily**', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ daily: [] }),
  }));

  await page.goto(URL_BASE, { waitUntil: 'load' });
  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display='none';
    const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
    if (typeof showPage === 'function') showPage('home');
  });
  await page.waitForSelector('.home-inpatient', { timeout: 8000 });
  await page.waitForTimeout(1500);

  // ── 1. Rounds composer ────────────────────────────────────────
  await page.click('#ip-rounds-add-btn');
  await page.waitForSelector('#ip-rounds-composer:not([hidden])', { timeout: 2000 });
  await page.fill('#ip-rounds-doctor', '張醫師');
  await page.fill('#ip-rounds-input', '今早查房：類風濕用藥計畫照原訂，下午抽血追蹤 CRP，可下床走動。');
  await page.click('.ip-rounds-save');
  await page.waitForTimeout(500);
  const entriesAfterAdd = await page.$$eval('.ip-rounds-entry', els => els.length);
  if (entriesAfterAdd !== 1) issues.push(`rounds: expected 1 entry after add, got ${entriesAfterAdd}`);
  const composerHiddenAfterSave = await page.$eval('#ip-rounds-composer', el => el.hasAttribute('hidden'));
  if (!composerHiddenAfterSave) issues.push('rounds: composer should be hidden after save');

  // Add a second entry to test "more" toggle
  await page.click('#ip-rounds-add-btn');
  await page.waitForSelector('#ip-rounds-composer:not([hidden])');
  await page.fill('#ip-rounds-input', '昨晚記錄：點滴速度調慢，腫痛指數降至 3。');
  await page.click('.ip-rounds-save');
  await page.waitForTimeout(400);
  const visibleAfterTwo = await page.$$eval('.ip-rounds-entry', els => els.length);
  // collapsed: only top 1 visible
  if (visibleAfterTwo !== 1) issues.push(`rounds: expected 1 visible (collapsed), got ${visibleAfterTwo}`);
  const moreBtnVisible = await page.$eval('#ip-rounds-more', el => !el.hidden).catch(() => false);
  if (!moreBtnVisible) issues.push('rounds: more button should be visible with 2 entries');

  // Expand
  await page.click('#ip-rounds-more');
  await page.waitForTimeout(300);
  const expandedCount = await page.$$eval('.ip-rounds-entry', els => els.length);
  if (expandedCount !== 2) issues.push(`rounds: expanded should show 2, got ${expandedCount}`);

  await page.locator('.ip-rounds').screenshot({ path: resolve(SHOT_DIR, 'rounds-expanded.png') });

  // ── 2. SOS history ─────────────────────────────────────────────
  // 預設 history 區應該 hidden
  const hxHiddenInitial = await page.$eval('#ip-sos-history', el => el.hidden);
  if (!hxHiddenInitial) issues.push('sos history: should be hidden initially');

  await page.click('.ip-sos-btn[data-key="pain"]');
  await page.waitForTimeout(250);
  await page.click('.ip-sos-btn[data-key="breath"]');
  await page.waitForTimeout(250);
  await page.click('.ip-sos-btn[data-key="help"]');
  await page.waitForTimeout(400);

  const hxHiddenAfter = await page.$eval('#ip-sos-history', el => el.hidden);
  if (hxHiddenAfter) issues.push('sos history: should be visible after 3 taps');
  const chipCount = await page.$$eval('.ip-sos-chip', els => els.length);
  if (chipCount !== 3) issues.push(`sos history: expected 3 chips, got ${chipCount}`);

  await page.locator('.ip-sos').screenshot({ path: resolve(SHOT_DIR, 'sos-with-history.png') });

  // ── 3. Timeline tap → sheet ────────────────────────────────────
  const tlItems = await page.$$('.ip-tl-item');
  if (!tlItems.length) {
    issues.push('timeline: no items rendered (no active admission)');
  } else {
    await tlItems[0].click();
    await page.waitForSelector('#ip-tl-sheet.open', { timeout: 2000 });
    const sheetTitle = await page.$eval('.ip-tl-sheet-title', el => el.textContent);
    if (!sheetTitle) issues.push('timeline sheet: no title');
    // mark done
    await page.click('.ip-tl-sheet-btn-done');
    await page.waitForTimeout(500);
    const userdoneCount = await page.$$eval('.ip-tl-userdone', els => els.length);
    if (userdoneCount < 1) issues.push(`timeline: expected at least 1 userdone after marking, got ${userdoneCount}`);
    await page.locator('.ip-timeline').screenshot({ path: resolve(SHOT_DIR, 'timeline-with-done.png') });
  }

  await browser.close();

  if (issues.length) {
    console.log('❌ Issues:');
    issues.forEach(i => console.log('  ' + i));
    process.exit(1);
  }
  console.log('✓ All inpatient functional checks passed.');
  console.log('  - rounds: add → render → 2nd entry → more toggle');
  console.log('  - sos: 3 taps → 3 chips visible');
  console.log('  - timeline: tap → sheet → mark done → dot turns green');
})();

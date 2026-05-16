// 長期療程「下次打藥」提醒 — 兩個位置：
//   1. Hero「下次打藥」chip（在「下次回診」chip 旁邊）
//   2. Layer 03「住院 / 療程」卡的倒數 badge
//
// 三個情境：
//   A) 5 天後 → 兩處顯示「5 天後」，urgency=soon
//   B) 今天   → 兩處顯示「今天」+ pulse 動畫
//   C) 已過期 3 天 → 兩處顯示「逾 3 天」/「已過期 3 天」，urgency=overdue
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHOT_DIR = resolve(__dirname, 'home_shots');
mkdirSync(SHOT_DIR, { recursive: true });

const URL_BASE = process.env.PREVIEW_URL || 'http://127.0.0.1:3000/';

async function bootPage(browser, daysAhead) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  page.on('pageerror', e => {
    if (/serviceWorker|addEventListener|querySelectorAll|register/.test(e.message)) return;
    console.error('pageerror:', e.message);
  });
  await page.addInitScript(() => {
    localStorage.setItem('mdpiece_user', JSON.stringify({ id:'demo', username:'demo', nickname:'示範', role:'patient', avatar_color:'#5B9FE8' }));
    localStorage.setItem('mdpiece_onboarded', '1');
    localStorage.setItem('mdpiece_landing_theme', 'light');
    localStorage.setItem('mdpiece_care_mode', 'outpatient');
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get(){ return undefined; } });
  });

  // Mock /admissions/ list with one active chronic_infusion
  await page.route('**/admissions/?**', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ admissions: [{ id: 'a1', status: 'active', type: 'chronic_infusion', admit_date: new Date(Date.now() - 30*86400000).toISOString(), diagnosis: '類風濕關節炎' }] }),
  }));
  // Mock the detail with one med whose next_due_date is N days from now
  const dueDate = new Date(Date.now() + daysAhead * 86400000);
  const dueIso = dueDate.toISOString().slice(0, 10) + 'T10:00';
  await page.route('**/admissions/a1', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ id: 'a1', status: 'active', medications: [{ id: 'm1', name: 'Humira', dose: '40mg', next_due_date: dueIso }] }),
  }));
  // Silence other endpoints
  await page.route('**/medications/?**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ medications: [] }) }));
  await page.route('**/emotions/daily**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ daily: [] }) }));
  await page.route('**/medications/logs**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ logs: [] }) }));

  await page.goto(URL_BASE, { waitUntil: 'load' });
  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display='none';
    const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
    if (typeof showPage === 'function') showPage('home');
  });
  await page.waitForSelector('.home-layered', { timeout: 8000 });
  await page.waitForTimeout(1800);
  return { ctx, page };
}

(async () => {
  const browser = await chromium.launch();
  const issues = [];

  // ── 場景 A: 5 days ahead ────────────────────────────
  {
    const { ctx, page } = await bootPage(browser, 5);
    const chipVisible = await page.$eval('#home-infusion-chip', el => !el.hidden);
    if (!chipVisible) issues.push('A: chip should be visible at 5 days ahead');
    const chipCount = await page.$eval('#home-infusion-chip-count', el => el.textContent);
    if (chipCount !== '5 天後') issues.push(`A: chip count expected "5 天後", got "${chipCount}"`);
    const urgency = await page.$eval('#home-infusion-chip', el => el.dataset.urgency);
    if (urgency !== 'soon') issues.push(`A: urgency expected "soon", got "${urgency}"`);

    const badgeVisible = await page.$eval('.hsec-card[data-page="admissions"] .hsec-badge', el => !el.hidden);
    if (!badgeVisible) issues.push('A: admissions card badge should be visible');
    const badgeText = await page.$eval('.hsec-card[data-page="admissions"] .hsec-badge', el => el.textContent);
    if (badgeText !== '5 天後') issues.push(`A: badge text expected "5 天後", got "${badgeText}"`);

    await page.locator('.home-visit-row').screenshot({ path: resolve(SHOT_DIR, 'infusion-chip-5d.png') });
    await page.locator('.hsec-card[data-page="admissions"]').screenshot({ path: resolve(SHOT_DIR, 'infusion-badge-5d.png') });
    await ctx.close();
  }

  // ── 場景 B: today ────────────────────────────────────
  {
    const { ctx, page } = await bootPage(browser, 0);
    const chipCount = await page.$eval('#home-infusion-chip-count', el => el.textContent);
    if (chipCount !== '就是今天') issues.push(`B: chip count expected "就是今天", got "${chipCount}"`);
    const chipUrgency = await page.$eval('#home-infusion-chip', el => el.dataset.urgency);
    if (chipUrgency !== 'today') issues.push(`B: urgency expected "today", got "${chipUrgency}"`);
    const badgeText = await page.$eval('.hsec-card[data-page="admissions"] .hsec-badge', el => el.textContent);
    if (badgeText !== '今天') issues.push(`B: badge text expected "今天", got "${badgeText}"`);

    await page.locator('.home-visit-row').screenshot({ path: resolve(SHOT_DIR, 'infusion-chip-today.png') });
    await ctx.close();
  }

  // ── 場景 C: overdue 3 days ──────────────────────────
  {
    const { ctx, page } = await bootPage(browser, -3);
    const chipCount = await page.$eval('#home-infusion-chip-count', el => el.textContent);
    if (chipCount !== '已過期 3 天') issues.push(`C: chip count expected "已過期 3 天", got "${chipCount}"`);
    const chipUrgency = await page.$eval('#home-infusion-chip', el => el.dataset.urgency);
    if (chipUrgency !== 'overdue') issues.push(`C: urgency expected "overdue", got "${chipUrgency}"`);
    const badgeText = await page.$eval('.hsec-card[data-page="admissions"] .hsec-badge', el => el.textContent);
    if (badgeText !== '逾 3 天') issues.push(`C: badge text expected "逾 3 天", got "${badgeText}"`);

    await page.locator('.home-visit-row').screenshot({ path: resolve(SHOT_DIR, 'infusion-chip-overdue.png') });
    await ctx.close();
  }

  await browser.close();

  if (issues.length) {
    console.log('❌ Issues:');
    issues.forEach(i => console.log('  ' + i));
    process.exit(1);
  }
  console.log('✓ Infusion reminder works in 3 scenarios:');
  console.log('  - 5 days ahead: chip + badge show "5 天後"');
  console.log('  - today: pulse style, shows "就是今天" / "今天"');
  console.log('  - overdue 3 days: coral/danger style, "逾 3 天"');
})();

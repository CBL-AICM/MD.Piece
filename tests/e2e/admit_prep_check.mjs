// 即將住院 / 即將打藥 prep sheet — 三個情境：
//   A) 3 天後有 acute admission → 「下次住院」chip 顯示，點開 sheet 有 5 區清單 + 「提前開始入院」CTA
//   B) 勾選 checklist 後 progress 條更新、state 持久（reload 後保留）
//   C) chronic_infusion next_due_date 在 5 天後 → 「下次打藥」chip 點開 sheet 有 3 區清單 + 「今日提前施打」CTA
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHOT_DIR = resolve(__dirname, 'home_shots');
mkdirSync(SHOT_DIR, { recursive: true });

const URL_BASE = process.env.PREVIEW_URL || 'http://127.0.0.1:3000/';

async function mockApis(page, opts) {
  await page.route('**/admissions/?**', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ admissions: opts.admissions || [] }),
  }));
  await page.route('**/admissions/a-acute', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ id: 'a-acute', status: 'active', type: 'acute', medications: [] }),
  }));
  await page.route('**/admissions/a-inf', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ id: 'a-inf', status: 'active', type: 'chronic_infusion', medications: opts.infusionMeds || [] }),
  }));
  await page.route('**/medications/?**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ medications: [] }) }));
  await page.route('**/emotions/daily**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ daily: [] }) }));
  await page.route('**/medications/logs**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ logs: [] }) }));
}

async function boot(browser, opts) {
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
  await mockApis(page, opts);
  await page.goto(URL_BASE, { waitUntil: 'load' });
  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display='none';
    const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
    if (typeof showPage === 'function') showPage('home');
  });
  await page.waitForSelector('.home-layered', { timeout: 8000 });
  await page.waitForTimeout(1600);
  return { ctx, page };
}

(async () => {
  const browser = await chromium.launch();
  const issues = [];
  const inThreeDays = new Date(Date.now() + 3*86400000).toISOString().slice(0,10) + 'T10:00';
  const inFiveDays = new Date(Date.now() + 5*86400000).toISOString().slice(0,10) + 'T14:00';

  // ── A) 3 天後 acute admission ───────────────────────
  {
    const { ctx, page } = await boot(browser, {
      admissions: [{ id: 'a-acute', status: 'active', type: 'acute', admit_date: inThreeDays, diagnosis: '預定膝蓋手術' }],
    });
    const chipVisible = await page.$eval('#home-admit-chip', el => !el.hidden);
    if (!chipVisible) issues.push('A: admit chip should be visible');
    const chipText = await page.$eval('#home-admit-chip-count', el => el.textContent);
    if (chipText !== '3 天後') issues.push(`A: chip expected "3 天後", got "${chipText}"`);
    const urgency = await page.$eval('#home-admit-chip', el => el.dataset.urgency);
    if (urgency !== 'soon') issues.push(`A: urgency expected "soon" got "${urgency}"`);

    // 點開 sheet
    await page.click('#home-admit-chip');
    await page.waitForSelector('#ip-prep-sheet.open', { timeout: 2000 });
    const sections = await page.$$eval('.ip-prep-section', els => els.length);
    if (sections !== 5) issues.push(`A: admit sheet should have 5 sections, got ${sections}`);
    const ctaText = await page.$eval('.ip-prep-cta', el => el.textContent);
    if (!ctaText.includes('提前開始入院')) issues.push(`A: cta expected "提前開始入院", got "${ctaText}"`);

    // 勾兩項 → progress 跳到 (2/total) — input 是 visually hidden，要點 label
    const labels = await page.$$('.ip-prep-check');
    await labels[0].click();
    await page.waitForTimeout(150);
    await labels[1].click();
    await page.waitForTimeout(200);
    const progressText = await page.$eval('#ip-prep-progress-text', el => el.textContent);
    if (!progressText.startsWith('2 / ')) issues.push(`A: progress expected "2 / ...", got "${progressText}"`);
    await page.locator('.ip-prep-panel').screenshot({ path: resolve(SHOT_DIR, 'admit-prep-sheet.png') });

    // B) reload + 重開 sheet → 勾選保留
    await page.evaluate(() => closeAdmissionPrepSheet());
    await page.waitForTimeout(300);
    await page.reload({ waitUntil: 'load' });
    await mockApis(page, { admissions: [{ id: 'a-acute', status: 'active', type: 'acute', admit_date: inThreeDays, diagnosis: '預定膝蓋手術' }] });
    await page.evaluate(() => {
      const l = document.getElementById('landing'); if (l) l.style.display='none';
      const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
      if (typeof showPage === 'function') showPage('home');
    });
    await page.waitForSelector('.home-layered', { timeout: 8000 });
    await page.waitForTimeout(1600);
    await page.click('#home-admit-chip');
    await page.waitForSelector('#ip-prep-sheet.open', { timeout: 2000 });
    const progressAfterReload = await page.$eval('#ip-prep-progress-text', el => el.textContent);
    if (!progressAfterReload.startsWith('2 / ')) issues.push(`B: reload — progress expected to persist "2 / ...", got "${progressAfterReload}"`);

    await ctx.close();
  }

  // ── C) chronic_infusion 5 天後 ──────────────────────
  {
    const { ctx, page } = await boot(browser, {
      admissions: [{ id: 'a-inf', status: 'active', type: 'chronic_infusion', admit_date: new Date(Date.now() - 60*86400000).toISOString(), diagnosis: '類風濕關節炎' }],
      infusionMeds: [{ id: 'm1', name: 'Humira', dose: '40mg', next_due_date: inFiveDays }],
    });
    const chipVisible = await page.$eval('#home-infusion-chip', el => !el.hidden);
    if (!chipVisible) issues.push('C: infusion chip should be visible');
    await page.click('#home-infusion-chip');
    await page.waitForSelector('#ip-prep-sheet.open', { timeout: 2000 });
    const sections = await page.$$eval('.ip-prep-section', els => els.length);
    if (sections !== 3) issues.push(`C: infusion sheet should have 3 sections, got ${sections}`);
    const ctaText = await page.$eval('.ip-prep-cta', el => el.textContent);
    if (!ctaText.includes('施打')) issues.push(`C: cta expected to mention 施打, got "${ctaText}"`);
    await page.locator('.ip-prep-panel').screenshot({ path: resolve(SHOT_DIR, 'infusion-prep-sheet.png') });
    await ctx.close();
  }

  await browser.close();

  if (issues.length) {
    console.log('❌ Issues:');
    issues.forEach(i => console.log('  ' + i));
    process.exit(1);
  }
  console.log('✓ Admit/Infusion prep sheet works:');
  console.log('  - acute future: chip + 5-section checklist + 提前開始入院 CTA');
  console.log('  - checklist state persists across reload');
  console.log('  - chronic_infusion future: chip + 3-section checklist + 施打 CTA');
})();

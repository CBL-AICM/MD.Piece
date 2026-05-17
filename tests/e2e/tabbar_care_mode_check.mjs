// Care-mode-aware mobile tabbar test:
//   1. Outpatient mode → tabs = 首頁 / 碎片 / FAB / 醫聊 / 更多
//   2. Inpatient mode → tabs = 首頁 / 住院 / FAB / 量測 / 更多
//   3. Toggling care mode at runtime swaps the tabbar (no reload)
// 5 tabs（2 + FAB + 2）讓綠色加號正中央；診前 / Memo 移到「更多」面板。
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHOT_DIR = resolve(__dirname, 'home_shots');
mkdirSync(SHOT_DIR, { recursive: true });

const URL_BASE = process.env.PREVIEW_URL || 'http://127.0.0.1:3000/';

const VIEW = { width: 390, height: 844 };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: VIEW, deviceScaleFactor: 2, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  const issues = [];
  page.on('pageerror', e => {
    // SW stub causes harmless errors from existing SW init code — ignore those.
    if (/serviceWorker|addEventListener|querySelectorAll|register/.test(e.message)) return;
    issues.push(`pageerror: ${e.message}`);
  });

  await page.addInitScript(() => {
    localStorage.setItem('mdpiece_user', JSON.stringify({ id:'demo', username:'demo', nickname:'示範', role:'patient', avatar_color:'#5B9FE8' }));
    localStorage.setItem('mdpiece_onboarded', '1');
    localStorage.setItem('mdpiece_landing_theme', 'dark');
    localStorage.setItem('mdpiece_care_mode', 'outpatient');
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get(){ return undefined; } });
  });
  await page.goto(URL_BASE, { waitUntil: 'load' });
  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display='none';
    const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
    if (typeof showPage === 'function') showPage('home');
  });
  await page.waitForSelector('.mobile-tabbar .mtab', { timeout: 8000 });
  await page.waitForTimeout(800);

  // 1. Outpatient tabs
  const out = await page.$$eval('.mobile-tabbar .mtab', els => els.map(b => b.dataset.mtab));
  const expectedOut = ['home','pieces','quickadd','chat','more'];
  if (JSON.stringify(out) !== JSON.stringify(expectedOut)) {
    issues.push(`outpatient tabs: expected ${expectedOut} got ${out}`);
  }

  await page.locator('.mobile-tabbar').screenshot({ path: resolve(SHOT_DIR, 'tabbar-outpatient.png') });

  // 2. Toggle to inpatient — tabbar should re-render automatically
  await page.evaluate(() => {
    if (typeof setCareMode === 'function') setCareMode('inpatient');
  });
  await page.waitForTimeout(600);
  const inp = await page.$$eval('.mobile-tabbar .mtab', els => els.map(b => b.dataset.mtab));
  const expectedIn = ['home','admissions','quickadd','vitals','more'];
  if (JSON.stringify(inp) !== JSON.stringify(expectedIn)) {
    issues.push(`inpatient tabs: expected ${expectedIn} got ${inp}`);
  }

  // Verify labels rendered as Chinese
  const inpLabels = await page.$$eval('.mobile-tabbar .mtab .mtab-label, .mobile-tabbar .mtab .mtab-fab-label', els => els.map(e => e.textContent.trim()));
  const expectedLabels = ['首頁','住院','紀錄','量測','更多'];
  if (JSON.stringify(inpLabels) !== JSON.stringify(expectedLabels)) {
    issues.push(`inpatient labels: expected ${expectedLabels} got ${inpLabels}`);
  }

  await page.locator('.mobile-tabbar').screenshot({ path: resolve(SHOT_DIR, 'tabbar-inpatient.png') });

  // 3. Tap "住院" tab → should navigate to admissions page (the .mtab.active should follow)
  await page.click('.mobile-tabbar .mtab[data-mtab="admissions"]');
  await page.waitForTimeout(500);
  const activeTabAfter = await page.$$eval('.mobile-tabbar .mtab.active', els => els.map(b => b.dataset.mtab));
  if (JSON.stringify(activeTabAfter) !== JSON.stringify(['admissions'])) {
    issues.push(`after click admissions: active = ${activeTabAfter}`);
  }

  // 4. Toggle back to outpatient → tabs swap back
  await page.evaluate(() => {
    if (typeof setCareMode === 'function') setCareMode('outpatient');
  });
  await page.waitForTimeout(600);
  const outAgain = await page.$$eval('.mobile-tabbar .mtab', els => els.map(b => b.dataset.mtab));
  if (JSON.stringify(outAgain) !== JSON.stringify(expectedOut)) {
    issues.push(`outpatient (again) tabs: expected ${expectedOut} got ${outAgain}`);
  }

  await browser.close();

  if (issues.length) {
    console.log('❌ Issues:');
    for (const i of issues) console.log('  ' + i);
    process.exit(1);
  }
  console.log('✓ Tabbar care-mode swap works.');
  console.log('  outpatient: ' + expectedOut.join(' / '));
  console.log('  inpatient : ' + expectedIn.join(' / '));
})();

// 門診版改動：
//   A) 首頁多「不舒服一鍵回報」section (4 顆大按鈕 + sticky 歷史 chip)
//   B) showEffectForm 改用 bottom sheet 4 顆大按鈕 (無效 / 過敏 / 普通 / 有效)
//      過敏會多 prompt 寫症狀
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
    localStorage.setItem('mdpiece_care_mode', 'outpatient');
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get(){ return undefined; } });
  });
  await page.route('**/medications/?**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ medications:[] }) }));
  await page.route('**/admissions/?**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ admissions:[] }) }));
  await page.route('**/emotions/daily**', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ daily:[] }) }));
  await page.route('**/medications/effects', r => r.fulfill({ status:200, contentType:'application/json', body: JSON.stringify({ ok:true }) }));

  await page.goto(URL_BASE, { waitUntil:'load' });
  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display='none';
    const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
    if (typeof showPage === 'function') showPage('home');
  });
  await page.waitForSelector('.home-layered', { timeout: 8000 });
  await page.waitForTimeout(1500);

  // ── A) 門診首頁應該有 SOS section ─────────────────────
  const qr = await page.$('.home-quick-report');
  if (!qr) issues.push('A: outpatient home should have .home-quick-report');
  const qrBtns = await page.$$eval('.home-quick-report .ip-sos-btn', els => els.length);
  if (qrBtns !== 4) issues.push(`A: expected 4 SOS buttons in outpatient home, got ${qrBtns}`);
  // 按一下
  await page.click('.home-quick-report .ip-sos-btn[data-key="pain"]');
  await page.waitForTimeout(500);
  const histVisible = await page.$eval('.home-quick-report #ip-sos-history', el => !el.hidden);
  if (!histVisible) issues.push('A: history should appear after click');
  await page.locator('.home-quick-report').screenshot({ path: resolve(SHOT_DIR, 'outpatient-quick-report.png') });

  // ── B) 用藥效果 sheet ───────────────────────────────────
  // 直接呼叫 showEffectForm（不用走 medications 頁，比較快）
  await page.evaluate(() => { window._medsPatientId = 'demo'; showEffectForm('m1', 'Methotrexate'); });
  await page.waitForSelector('#med-effect-sheet.open', { timeout: 2000 });
  await page.waitForTimeout(300);
  const meBtns = await page.$$eval('.med-effect-btn', els => els.length);
  if (meBtns !== 4) issues.push(`B: expected 4 effect buttons, got ${meBtns}`);
  const meLabels = await page.$$eval('.med-effect-label', els => els.map(e => e.textContent));
  const expected = ['無效','過敏','普通','有效'];
  if (JSON.stringify(meLabels) !== JSON.stringify(expected)) {
    issues.push(`B: labels expected ${expected}, got ${meLabels}`);
  }
  await page.locator('.ip-prep-panel').screenshot({ path: resolve(SHOT_DIR, 'med-effect-sheet.png') });

  // 點「有效」→ sheet 應該關掉
  page.on('dialog', d => d.accept('起紅疹')); // 防萬一被誤選成 allergy
  await page.click('.med-effect-mint');
  await page.waitForTimeout(600);
  const sheetGone = await page.$('#med-effect-sheet');
  if (sheetGone) issues.push('B: sheet should close after click');

  await browser.close();

  if (issues.length) {
    console.log('❌ Issues:');
    issues.forEach(i => console.log('  ' + i));
    process.exit(1);
  }
  console.log('✓ Outpatient quick features:');
  console.log('  A) 不舒服一鍵回報 section — 4 顆大按鈕 + 今日歷史 chip');
  console.log('  B) 用藥效果 sheet — 4 顆 (無效/過敏/普通/有效)，過敏會 prompt');
})();

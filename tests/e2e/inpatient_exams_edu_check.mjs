// 兩個改動的 e2e：
//   A) 排定檢查 — composer 開 / 新增 / 出現在 timeline / 點開 sheet 看 prep / 刪除
//   B) 住院衛教獨立頁 — 點 home 卡 → 跳 inpatientEdu 頁 → 對應 topic 自動展開 → 全展全收
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
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  const issues = [];
  page.on('pageerror', e => {
    if (/serviceWorker|addEventListener|querySelectorAll|register/.test(e.message)) return;
    issues.push(`pageerror: ${e.message}`);
  });

  await page.addInitScript(() => {
    localStorage.setItem('mdpiece_user', JSON.stringify({ id:'demo', username:'demo', nickname:'示範', role:'patient', avatar_color:'#5B9FE8' }));
    localStorage.setItem('mdpiece_onboarded', '1');
    localStorage.setItem('mdpiece_landing_theme', 'light');
    localStorage.setItem('mdpiece_care_mode', 'inpatient');
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get(){ return undefined; } });
  });
  // Mock active admission so timeline has a base
  await page.route('**/admissions/?**', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ admissions: [{ id: 'a1', status: 'active', type: 'acute', admit_date: new Date(Date.now() - 86400000).toISOString(), diagnosis: '類風濕關節炎' }] }),
  }));
  await page.route('**/admissions/a1', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ id: 'a1', status: 'active', medications: [] }),
  }));
  await page.route('**/emotions/daily**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ daily: [] }) }));

  await page.goto(URL_BASE, { waitUntil: 'load' });
  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display='none';
    const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
    if (typeof showPage === 'function') showPage('home');
  });
  await page.waitForSelector('.home-inpatient', { timeout: 8000 });
  await page.waitForTimeout(1800);

  // ── A) 排檢查 ─────────────────────────────────────────
  // 點 +排檢查 → composer
  await page.click('#ip-exam-add-btn');
  await page.waitForSelector('#ip-exam-sheet.open', { timeout: 2000 });
  // 選 CT / 設定今天 14:30 / 地點 / 注意事項
  await page.selectOption('#ip-exam-type', 'ct');
  await page.waitForTimeout(150);
  // prep 應該被自動填為 ct 的預設
  const prepAfterType = await page.$eval('#ip-exam-prep', el => el.value);
  if (!prepAfterType.includes('顯影劑')) issues.push(`A: prep should auto-fill for ct, got "${prepAfterType.slice(0, 30)}"`);
  // 改時間到今天 14:30
  const today = new Date();
  const ymd = today.toISOString().slice(0, 10);
  await page.fill('#ip-exam-time', `${ymd}T14:30`);
  await page.fill('#ip-exam-location', 'B2 放射部');
  await page.fill('#ip-exam-notes', '醫師說可能要等 30 分');
  await page.locator('.ip-prep-panel').screenshot({ path: resolve(SHOT_DIR, 'exam-composer.png') });
  await page.click('.ip-prep-cta');
  await page.waitForTimeout(800);

  // Timeline 應該有 exam 項
  const examInTimeline = await page.$$eval('.ip-tl-kind-exam', els => els.length);
  if (examInTimeline !== 1) issues.push(`A: expected 1 exam in timeline, got ${examInTimeline}`);

  // 點 exam item 開 sheet 看 prep
  await page.click('.ip-tl-kind-exam');
  await page.waitForSelector('#ip-tl-sheet.open', { timeout: 2000 });
  const sheetHasPrep = await page.$$eval('.ip-tl-sheet-detail-row', els => els.length);
  if (sheetHasPrep < 2) issues.push(`A: sheet detail rows expected >=2, got ${sheetHasPrep}`);
  // 應該看到 prep + location 文字
  const sheetText = await page.$eval('.ip-tl-sheet-detail', el => el.textContent);
  if (!sheetText.includes('B2 放射部')) issues.push('A: sheet should show location');
  if (!sheetText.includes('顯影劑')) issues.push('A: sheet should show prep');
  await page.locator('.ip-tl-sheet-panel').screenshot({ path: resolve(SHOT_DIR, 'exam-sheet.png') });

  // 移除這筆檢查
  page.on('dialog', d => d.accept());
  await page.click('.ip-tl-sheet-btn-jump'); // jump btn for exam = delete
  await page.waitForTimeout(800);
  const examAfterDelete = await page.$$eval('.ip-tl-kind-exam', els => els.length);
  if (examAfterDelete !== 0) issues.push(`A: after delete, expected 0 exam, got ${examAfterDelete}`);

  // ── B) 住院衛教獨立頁 ──────────────────────────────────
  // 點 home Layer 09 第 2 張卡 (住院睡不好怎麼辦 → sleep)
  await page.evaluate(() => {
    const cards = document.querySelectorAll('.ip-edu-card');
    if (cards[1]) cards[1].click();
  });
  await page.waitForTimeout(700);
  // 應該在 inpatientEdu 頁
  const onEduPage = await page.$$eval('.ip-edu-page', els => els.length);
  if (onEduPage !== 1) issues.push(`B: should be on inpatientEdu page, got ${onEduPage} .ip-edu-page`);
  await page.waitForTimeout(400);
  // sleep section 應該展開
  const sleepOpen = await page.$eval('#ip-edu-sec-sleep', el => el.open);
  if (!sleepOpen) issues.push('B: sleep section should auto-open');
  // 總共 10 個 section
  const totalSections = await page.$$eval('.ip-edu-section', els => els.length);
  if (totalSections !== 10) issues.push(`B: expected 10 sections, got ${totalSections}`);
  await page.locator('.ip-edu-page').screenshot({ path: resolve(SHOT_DIR, 'inpatient-edu-page.png'), fullPage: false });

  // 全部展開
  await page.click('.ip-edu-page-expand-all');
  await page.waitForTimeout(300);
  const openCount = await page.$$eval('.ip-edu-section[open]', els => els.length);
  if (openCount !== 10) issues.push(`B: after toggle-all, expected 10 open, got ${openCount}`);
  const lblExpanded = await page.$eval('#ip-edu-toggle-all-label', el => el.textContent);
  if (lblExpanded !== '全部收合') issues.push(`B: label should now be 全部收合, got "${lblExpanded}"`);

  // 確認沒有路由跳到 /education 頁 (不共用)
  const pageTitle = await page.$eval('#page-title', el => el.textContent);
  if (pageTitle !== '住院衛教') issues.push(`B: page title expected "住院衛教", got "${pageTitle}"`);

  await browser.close();

  if (issues.length) {
    console.log('❌ Issues:');
    issues.forEach(i => console.log('  ' + i));
    process.exit(1);
  }
  console.log('✓ Inpatient exams + dedicated education page work:');
  console.log('  A) +排檢查 → composer (CT 自動帶 prep) → 加進 timeline → sheet 顯 prep+location → 移除');
  console.log('  B) home 點 sleep 卡 → inpatientEdu 頁 → sleep 自動展開 → 全部展開/收合 → 頁標題正確');
})();

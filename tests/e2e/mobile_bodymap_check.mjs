// 驗證手機版症狀紀錄頁的人體圖點選互動（PR #378 fix）
//
// 為什麼這個測試重要：
//   - 桌機版人體圖可以點 → 寫進 _symBodyPart → 開記錄表單時帶入 notes
//   - 手機版之前是純靜態圖、點 wrapper 只會 scroll 到桌機區塊（CSS 隱藏）
//   - 這個測試確保手機版的小人「點下去真的能選到部位」、且「選到的部位真的會被
//     後面的紀錄流程拿到」(寫入 _symBodyPart) — 不只是視覺有變化
//
// 用法：
//   PREVIEW_URL=http://127.0.0.1:3030/ node tests/e2e/mobile_bodymap_check.mjs
import { chromium } from 'playwright';

const URL = process.env.PREVIEW_URL || 'http://127.0.0.1:3030/';

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 390, height: 844 }, // iPhone 13
  userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  deviceScaleFactor: 2,
  hasTouch: true,
  isMobile: true,
});
const page = await ctx.newPage();

let exitCode = 0;
function fail(msg) { console.error('FAIL:', msg); exitCode = 1; }
function pass(msg) { console.log('OK  :', msg); }

try {
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(400);

  // 模擬已 onboard 的使用者 + 跳過 howto
  await page.evaluate(() => {
    localStorage.setItem('mdpiece_user', JSON.stringify({
      username: 'audit', nickname: '測試', id_number: 'A123456789',
    }));
    localStorage.setItem('mdpiece_onboarded', '1');
    localStorage.setItem('mdpiece_howto_seen_symptoms', '1');
  });

  // 切到 symptoms 頁
  await page.evaluate(() => {
    const landing = document.getElementById('landing');
    if (landing) landing.style.display = 'none';
    const wrap = document.getElementById('app-wrapper');
    if (wrap && !wrap.classList.contains('show')) wrap.classList.add('show');
    if (typeof window.showPage === 'function') window.showPage('symptoms');
  });
  await page.waitForTimeout(800);

  // 1. SVG body-figure 應存在（手機版）
  const figureExists = await page.locator('.mobile-only .bodymap-wrap svg.body-figure').count();
  if (figureExists === 0) fail('mobile body-figure svg not rendered'); else pass('mobile body-figure svg exists');

  // 2. 8 個 hotspot 應存在
  const hotspotCount = await page.locator('.mobile-only .bodymap-wrap .m-bodymap-hotspot').count();
  if (hotspotCount !== 8) fail(`expected 8 hotspots, got ${hotspotCount}`);
  else pass('8 hotspots rendered');

  // 3. caption 初始顯示提示文字
  const initCap = await page.locator('#m-bodymap-caption').innerText();
  if (!initCap.includes('提示') && !initCap.includes('點選')) fail(`initial caption unexpected: ${initCap}`);
  else pass(`initial caption: "${initCap}"`);

  // 4. _symBodyPart 初始為 ''
  const initPart = await page.evaluate(() => window._symBodyPart);
  if (initPart !== '' && initPart != null) fail(`_symBodyPart should start empty, got: ${JSON.stringify(initPart)}`);
  else pass('_symBodyPart initial state empty');

  // 5. 點頭部 hotspot → _symBodyPart 應為 "頭部"
  await page.locator('.mobile-only .m-bodymap-hotspot[data-part="head"]').click();
  await page.waitForTimeout(150);
  const afterHead = await page.evaluate(() => window._symBodyPart);
  if (afterHead !== '頭部') fail(`after clicking head, _symBodyPart should be '頭部', got: ${JSON.stringify(afterHead)}`);
  else pass('clicking head sets _symBodyPart=頭部');

  // 6. caption 變成「已選：頭部」
  const capAfterHead = await page.locator('#m-bodymap-caption').innerText();
  if (!capAfterHead.includes('頭部')) fail(`caption should mention 頭部, got: "${capAfterHead}"`);
  else pass(`caption updated: "${capAfterHead}"`);

  // 7. marker 應顯示
  const markerVisible = await page.locator('#m-bodymap-marker').evaluate(el => el.style.display !== 'none');
  if (!markerVisible) fail('marker should be visible after click');
  else pass('marker visible after click');

  // 8. hotspot 應 has is-active class
  const isActive = await page.locator('.m-bodymap-hotspot[data-part="head"]').evaluate(el => el.classList.contains('is-active'));
  if (!isActive) fail('clicked hotspot should have is-active class');
  else pass('clicked hotspot has is-active class');

  // 9. 點另一部位（胸口）→ _symBodyPart 切換
  await page.locator('.m-bodymap-hotspot[data-part="chest"]').click();
  await page.waitForTimeout(150);
  const afterChest = await page.evaluate(() => window._symBodyPart);
  if (afterChest !== '胸口') fail(`after clicking chest, _symBodyPart should be '胸口', got: ${JSON.stringify(afterChest)}`);
  else pass('clicking chest updates _symBodyPart=胸口');

  // 10. 點 SVG 非 hotspot 區域 → 仍能找到最近部位
  const svgBox = await page.locator('.mobile-only svg.body-figure').boundingBox();
  if (svgBox) {
    // 點右下（接近右腿區域）
    await page.mouse.click(svgBox.x + svgBox.width * 0.6, svgBox.y + svgBox.height * 0.78);
    await page.waitForTimeout(150);
    const afterArea = await page.evaluate(() => window._symBodyPart);
    if (!afterArea || afterArea === '胸口') fail(`clicking outside hotspot should change body part, got: ${JSON.stringify(afterArea)}`);
    else pass(`clicking outside hotspot finds nearest: ${afterArea}`);
  }

  // 11. clear 後 _symBodyPart 清空、marker 隱藏
  await page.evaluate(() => window.mobileSymBodyClear && window.mobileSymBodyClear());
  await page.waitForTimeout(150);
  const afterClear = await page.evaluate(() => window._symBodyPart);
  if (afterClear !== '') fail(`after clear, _symBodyPart should be '', got: ${JSON.stringify(afterClear)}`);
  else pass('clear resets _symBodyPart');
  const markerHidden = await page.locator('#m-bodymap-marker').evaluate(el => el.style.display === 'none');
  if (!markerHidden) fail('marker should be hidden after clear');
  else pass('marker hidden after clear');

  // 12. 桌機版 IDs 沒被破壞（無 duplicate）
  const dupCount = await page.evaluate(() => {
    const ids = ['sym-body-current', 'sym-body-marker', 'sym-body-ai', 'm-bodymap-marker', 'm-bodymap-caption'];
    return ids.map(id => ({ id, count: document.querySelectorAll(`#${id}`).length }));
  });
  for (const d of dupCount) {
    if (d.count > 1) fail(`duplicate id #${d.id}: ${d.count} occurrences`);
    else pass(`id #${d.id}: ${d.count} (OK)`);
  }

} catch (e) {
  fail('exception: ' + e.message);
  console.error(e.stack);
} finally {
  await browser.close();
}

console.log(exitCode === 0 ? '\nALL CHECKS PASSED' : '\nSOME CHECKS FAILED');
process.exit(exitCode);

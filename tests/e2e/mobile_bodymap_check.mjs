// 驗證症狀紀錄頁人體圖與類型 chip 互動（PR #378 / #379 fix）
//
// 為什麼這個測試重要：
//   - 之前小人是純靜態圖、點 chip 後表單在 >760px 寬螢幕被 .desktop-only 鎖死
//   - 現在小人是 interactive、19 個細部位、chip 在所有寬度都能開表單
//   - 跑三種寬度（mobile / tablet / desktop）確保都正常
//
// 用法：
//   PREVIEW_URL=http://127.0.0.1:3030/ node tests/e2e/mobile_bodymap_check.mjs
import { chromium } from 'playwright';

const URL = process.env.PREVIEW_URL || 'http://127.0.0.1:3030/';

const VIEWPORTS = [
  { name: 'mobile-iphone13', width: 390, height: 844, isMobile: true },
  { name: 'tablet-ipad-air', width: 820, height: 1180, isMobile: false },
  { name: 'desktop-laptop',  width: 1280, height: 800, isMobile: false },
];

const browser = await chromium.launch();

let exitCode = 0;
function fail(scope, msg) { console.error(`FAIL [${scope}]: ${msg}`); exitCode = 1; }
function pass(scope, msg) { console.log(`OK   [${scope}]: ${msg}`); }

for (const vp of VIEWPORTS) {
  const scope = vp.name;
  console.log(`\n── ${scope} (${vp.width}x${vp.height}) ──`);
  const ctx = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
    isMobile: vp.isMobile,
    hasTouch: vp.isMobile,
  });
  const page = await ctx.newPage();

  try {
    await page.goto(URL, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(400);
    await page.evaluate(() => {
      localStorage.setItem('mdpiece_user', JSON.stringify({
        username: 'audit', nickname: '測試', id_number: 'A123456789',
      }));
      localStorage.setItem('mdpiece_onboarded', '1');
      localStorage.setItem('mdpiece_howto_seen_symptoms', '1');
    });
    await page.evaluate(() => {
      const landing = document.getElementById('landing');
      if (landing) landing.style.display = 'none';
      const wrap = document.getElementById('app-wrapper');
      if (wrap && !wrap.classList.contains('show')) wrap.classList.add('show');
      if (typeof window.showPage === 'function') window.showPage('symptoms');
    });
    await page.waitForTimeout(800);

    // ── 人體圖部分 ──
    const figureExists = await page.locator('.mobile-only .bodymap-wrap svg.body-figure').count();
    if (figureExists === 0) fail(scope, 'body-figure svg not rendered');
    else pass(scope, 'body-figure svg exists');

    const hotspotCount = await page.locator('.mobile-only .bodymap-wrap .m-bodymap-hotspot').count();
    if (hotspotCount !== 19) fail(scope, `expected 19 hotspots, got ${hotspotCount}`);
    else pass(scope, '19 細部位 hotspots rendered');

    // 點前額（新增的細部位）
    await page.locator('.m-bodymap-hotspot[data-part="forehead"]').click();
    await page.waitForTimeout(150);
    const afterForehead = await page.evaluate(() => window._symBodyPart);
    if (afterForehead !== '前額') fail(scope, `forehead click: _symBodyPart should be '前額', got: ${JSON.stringify(afterForehead)}`);
    else pass(scope, 'clicking 前額 hotspot sets _symBodyPart=前額');

    // 點手肘（新增的細部位）
    await page.locator('.m-bodymap-hotspot[data-part="l-elbow"]').click();
    await page.waitForTimeout(150);
    const afterElbow = await page.evaluate(() => window._symBodyPart);
    if (afterElbow !== '左手肘') fail(scope, `l-elbow click: _symBodyPart should be '左手肘', got: ${JSON.stringify(afterElbow)}`);
    else pass(scope, 'clicking 左手肘 hotspot sets _symBodyPart=左手肘');

    // 點膝蓋
    await page.locator('.m-bodymap-hotspot[data-part="r-knee"]').click();
    await page.waitForTimeout(150);
    const afterKnee = await page.evaluate(() => window._symBodyPart);
    if (afterKnee !== '右膝') fail(scope, `r-knee click: _symBodyPart should be '右膝', got: ${JSON.stringify(afterKnee)}`);
    else pass(scope, 'clicking 右膝 hotspot sets _symBodyPart=右膝');

    // SVG-wide click 找最近部位
    const svgBox = await page.locator('.mobile-only svg.body-figure').boundingBox();
    if (svgBox) {
      // 點圖中心區域（應該找到軀幹相關部位）
      await page.mouse.click(svgBox.x + svgBox.width * 0.5, svgBox.y + svgBox.height * 0.5);
      await page.waitForTimeout(150);
      const nearest = await page.evaluate(() => window._symBodyPart);
      if (!nearest) fail(scope, 'clicking center should pick nearest part');
      else pass(scope, `nearest-part fallback works: ${nearest}`);
    }

    // ── chip 開表單部分（之前在 >760px 被鎖死）──
    // 先選定一個部位（_symBodyPart='右膝'），然後點 chip 開表單，
    // 預期 notes 自動帶入「[部位：右膝]」（_prefillBodyPartNote）
    await page.locator('.m-bodymap-hotspot[data-part="r-knee"]').click();
    await page.waitForTimeout(150);

    const chipCount = await page.locator('#mobile-sym-chips .chip').count();
    if (chipCount === 0) fail(scope, 'no chips rendered');
    else pass(scope, `${chipCount} chips rendered`);

    await page.locator('#mobile-sym-chips .chip').first().click();
    await page.waitForTimeout(500);
    const formState = await page.evaluate(() => {
      const f = document.getElementById('sym-logform');
      const p = document.querySelector('.sym-page');
      return {
        formDisplay: f ? getComputedStyle(f).display : 'N/A',
        symPageDisplay: p ? getComputedStyle(p).display : 'N/A',
        bodyHasLogging: document.body.classList.contains('is-sym-logging'),
      };
    });
    if (formState.symPageDisplay === 'none') fail(scope, `chip click: .sym-page hidden (display:none) — modal failed to open`);
    else pass(scope, `chip click opens form: .sym-page display=${formState.symPageDisplay}`);
    if (formState.formDisplay !== 'block') fail(scope, `chip click: #sym-logform display=${formState.formDisplay}, expected 'block'`);
    else pass(scope, `#sym-logform display=block`);

    // 部位有被 _prefillBodyPartNote 帶進 notes
    const notes = await page.locator('#lf-notes').inputValue().catch(() => null);
    if (notes == null) fail(scope, 'lf-notes textarea missing');
    else if (!notes.includes('右膝')) fail(scope, `notes should prefill 右膝 from latest pick, got: "${notes}"`);
    else pass(scope, `notes prefilled with body part: "${notes.trim()}"`);

    // ID 不重複
    const dupCount = await page.evaluate(() => {
      const ids = ['sym-body-current', 'sym-body-marker', 'sym-body-ai', 'm-bodymap-marker', 'm-bodymap-caption', 'sym-logform'];
      return ids.map(id => ({ id, count: document.querySelectorAll(`#${id}`).length }));
    });
    for (const d of dupCount) {
      if (d.count > 1) fail(scope, `duplicate id #${d.id}: ${d.count} occurrences`);
    }
    pass(scope, 'no duplicate IDs');

  } catch (e) {
    fail(scope, 'exception: ' + e.message);
    console.error(e.stack);
  } finally {
    await ctx.close();
  }
}

await browser.close();
console.log(exitCode === 0 ? '\nALL CHECKS PASSED' : '\nSOME CHECKS FAILED');
process.exit(exitCode);

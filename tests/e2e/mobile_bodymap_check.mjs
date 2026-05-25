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

    // ── 人體圖部分（正面 + 背面雙圖）──
    const sideCount = await page.locator('.mobile-only .bodymap-wrap .bodymap-side').count();
    if (sideCount !== 2) fail(scope, `expected 2 sides, got ${sideCount}`);
    else pass(scope, '2 sides (正面 + 背面) rendered');

    const labels = await page.locator('.bodymap-side-label').allInnerTexts();
    if (labels[0] !== '正面' || labels[1] !== '背面') fail(scope, `expected labels ['正面','背面'], got ${JSON.stringify(labels)}`);
    else pass(scope, 'side labels OK');

    const frontHotspots = await page.locator('svg.body-figure[data-side="front"] .m-bodymap-hotspot').count();
    const backHotspots  = await page.locator('svg.body-figure[data-side="back"] .m-bodymap-hotspot').count();
    if (frontHotspots !== 19) fail(scope, `expected 19 front hotspots, got ${frontHotspots}`);
    else pass(scope, '19 front 細部位');
    if (backHotspots !== 19) fail(scope, `expected 19 back hotspots, got ${backHotspots}`);
    else pass(scope, '19 back 細部位');

    // 點正面前額
    await page.locator('svg.body-figure[data-side="front"] .m-bodymap-hotspot[data-part="forehead"]').click();
    await page.waitForTimeout(150);
    const r1 = await page.evaluate(() => ({
      part: window._symBodyPart,
      front: document.getElementById('m-bodymap-marker-front').style.display !== 'none',
      back: document.getElementById('m-bodymap-marker-back').style.display !== 'none',
    }));
    if (r1.part !== '前額' || !r1.front || r1.back) fail(scope, `clicking 正面前額: ${JSON.stringify(r1)}`);
    else pass(scope, 'click 正面前額 → marker on front only');

    // 點背面後腦 → front marker 應自動消失
    await page.locator('svg.body-figure[data-side="back"] .m-bodymap-hotspot[data-part="back-head"]').click();
    await page.waitForTimeout(150);
    const r2 = await page.evaluate(() => ({
      part: window._symBodyPart,
      front: document.getElementById('m-bodymap-marker-front').style.display !== 'none',
      back: document.getElementById('m-bodymap-marker-back').style.display !== 'none',
    }));
    if (r2.part !== '後腦' || r2.front || !r2.back) fail(scope, `clicking 後腦: ${JSON.stringify(r2)}`);
    else pass(scope, 'click 背面後腦 → front marker cleared, back marker shown');

    // 背面新部位驗證
    await page.locator('svg.body-figure[data-side="back"] .m-bodymap-hotspot[data-part="waist"]').click();
    await page.waitForTimeout(150);
    const waist = await page.evaluate(() => window._symBodyPart);
    if (waist !== '腰部') fail(scope, `waist click: ${waist}`);
    else pass(scope, 'click 腰部 sets _symBodyPart=腰部');

    await page.locator('svg.body-figure[data-side="back"] .m-bodymap-hotspot[data-part="l-popliteal"]').click();
    await page.waitForTimeout(150);
    const popliteal = await page.evaluate(() => window._symBodyPart);
    if (popliteal !== '左膕窩') fail(scope, `popliteal click: ${popliteal}`);
    else pass(scope, 'click 左膕窩 sets _symBodyPart=左膕窩');

    // SVG-wide click 在背面找最近背面部位（非正面部位）
    const backSvgBox = await page.locator('svg.body-figure[data-side="back"]').boundingBox();
    if (backSvgBox) {
      await page.mouse.click(backSvgBox.x + backSvgBox.width * 0.5, backSvgBox.y + backSvgBox.height * 0.55);
      await page.waitForTimeout(150);
      const nearest = await page.evaluate(() => window._symBodyPart);
      // 應該命中背面部位（含「背」、「腰」、「臀」或「後」字）
      if (!nearest || !(/背|腰|臀|後|膕窩/.test(nearest))) fail(scope, `背面 SVG click nearest should be back part, got: ${nearest}`);
      else pass(scope, `背面 nearest-part fallback: ${nearest}`);
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

// 跨機型 + 跨頁面手機版稽核
//
// 流程：對每個機型在以下頁面做 horizontal-overflow 檢查 + 截圖：
//   landing → home → symptoms → medications → emotions → previsit → memo → vitals
//
// 用法：
//   PREVIEW_URL=http://127.0.0.1:3030/ node tests/e2e/mobile_audit.mjs
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHOT_DIR = resolve(__dirname, 'mobile_shots');
mkdirSync(SHOT_DIR, { recursive: true });

const URL = process.env.PREVIEW_URL ||
  'http://127.0.0.1:3030/';

// 涵蓋 Apple / Samsung / Google 主流手機 + 平板（直向 / 橫向）
const PROFILES = [
  // ── 手機（直向）──
  { name: '320-small-android',    width: 320,  height: 568,  ua: 'Android' },
  { name: '360-galaxy-s8',        width: 360,  height: 740,  ua: 'Samsung' },
  { name: '375-iphone-se',        width: 375,  height: 667,  ua: 'iPhone' },
  { name: '390-iphone-13',        width: 390,  height: 844,  ua: 'iPhone' },
  { name: '393-pixel-7',          width: 393,  height: 851,  ua: 'Pixel' },
  { name: '412-pixel-5',          width: 412,  height: 915,  ua: 'Pixel' },
  { name: '414-iphone-xr',        width: 414,  height: 896,  ua: 'iPhone' },
  { name: '428-iphone-13-pro-max',width: 428,  height: 926,  ua: 'iPhone' },
  { name: '430-iphone-15-pro-max',width: 430,  height: 932,  ua: 'iPhone' },

  // ── 平板（直向）──
  { name: '768-ipad-mini-port',   width: 768,  height: 1024, ua: 'iPad' },
  { name: '810-ipad-port',        width: 810,  height: 1080, ua: 'iPad' },     // iPad 10th
  { name: '820-ipad-air-port',    width: 820,  height: 1180, ua: 'iPad' },     // iPad Air 11"
  { name: '834-ipad-pro11-port',  width: 834,  height: 1194, ua: 'iPad' },     // iPad Pro 11"
  { name: '800-galaxy-tab-port',  width: 800,  height: 1280, ua: 'Samsung' },  // Galaxy Tab 直向
  { name: '1024-ipad-pro13-port', width: 1024, height: 1366, ua: 'iPad' },     // iPad Pro 12.9/13"

  // ── 平板（橫向）── 寬版測試
  { name: '1024-ipad-mini-land',  width: 1024, height: 768,  ua: 'iPad' },
  { name: '1180-ipad-air-land',   width: 1180, height: 820,  ua: 'iPad' },
  { name: '1280-galaxy-tab-land', width: 1280, height: 800,  ua: 'Samsung' },
  { name: '1366-ipad-pro13-land', width: 1366, height: 1024, ua: 'iPad' },
];

const PAGES_TO_TEST = ['home', 'symptoms', 'medications', 'emotions', 'previsit', 'memo', 'vitals', 'labs'];

const USER_AGENTS = {
  iPhone:  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  Samsung: 'Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36',
  Pixel:   'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36',
  Android: 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36',
  iPad:    'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
};

async function measureOverflow(page) {
  return await page.evaluate(() => {
    const winW = window.innerWidth;
    const docW = document.documentElement.scrollWidth;
    const offenders = [];
    document.querySelectorAll('body *').forEach(el => {
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') return;
      const r = el.getBoundingClientRect();
      if (r.right > winW + 1 && r.width > 0 && r.height > 0) {
        offenders.push({
          tag: el.tagName.toLowerCase(),
          cls: (el.className && typeof el.className === 'string' ? el.className : '').slice(0, 60),
          right: Math.round(r.right),
          width: Math.round(r.width),
          excess: Math.round(r.right - winW),
        });
      }
    });
    offenders.sort((a, b) => b.excess - a.excess);
    return {
      windowW: winW,
      docScrollW: docW,
      overflowPx: docW - winW,
      horizontalScroll: docW > winW,
      offendersTop: offenders.slice(0, 4),
    };
  });
}

const results = [];

const browser = await chromium.launch();

for (const p of PROFILES) {
  const ctx = await browser.newContext({
    viewport: { width: p.width, height: p.height },
    userAgent: USER_AGENTS[p.ua],
    deviceScaleFactor: 2,
    hasTouch: true,
    isMobile: true,
  });
  const page = await ctx.newPage();
  try {
    await page.goto(URL, { waitUntil: 'networkidle', timeout: 30000 });
  } catch (e) {
    results.push({ profile: p.name, page: 'landing', error: 'load timeout: ' + e.message });
    await ctx.close();
    continue;
  }
  await page.waitForTimeout(500);

  // 1) Landing page measurement
  const landingData = await measureOverflow(page);
  await page.screenshot({ path: resolve(SHOT_DIR, `${p.name}_landing.png`), fullPage: false });
  results.push({ profile: p.name, page: 'landing', ...landingData });

  // 2) Seed a user so we can bypass landing + auth
  await page.evaluate(() => {
    localStorage.setItem('mdpiece_user', JSON.stringify({
      username: 'audit',
      nickname: '測試',
      id_number: 'A123456789',
    }));
    localStorage.setItem('mdpiece_onboarded', '1');
    localStorage.setItem('mdpiece_howto_seen_meds', '1');
    localStorage.setItem('mdpiece_howto_seen_symptoms', '1');
    localStorage.setItem('mdpiece_howto_seen_emotions', '1');
    localStorage.setItem('mdpiece_howto_seen_previsit', '1');
  });

  // 3) Navigate into the app and walk pages
  for (const pageName of PAGES_TO_TEST) {
    try {
      await page.evaluate((p) => {
        // 模擬 enterApp + 切頁
        const landing = document.getElementById('landing');
        if (landing) landing.style.display = 'none';
        const wrap = document.getElementById('app-wrapper');
        if (wrap && !wrap.classList.contains('show')) wrap.classList.add('show');
        if (typeof window.showPage === 'function') window.showPage(p);
      }, pageName);
      await page.waitForTimeout(600); // 等網路 / 渲染

      const data = await measureOverflow(page);
      await page.screenshot({ path: resolve(SHOT_DIR, `${p.name}_${pageName}.png`), fullPage: false });
      results.push({ profile: p.name, page: pageName, ...data });
    } catch (e) {
      results.push({ profile: p.name, page: pageName, error: e.message });
    }
  }

  await ctx.close();
}

await browser.close();

// 報告
console.log('\n┌──────────────────────────────────────────────────────────────────────┐');
console.log('│ 跨機型 × 跨頁面 audit 結果                                            │');
console.log('└──────────────────────────────────────────────────────────────────────┘\n');

let totalFail = 0;
const byProfile = {};
for (const r of results) {
  if (!byProfile[r.profile]) byProfile[r.profile] = [];
  byProfile[r.profile].push(r);
}

for (const [profile, items] of Object.entries(byProfile)) {
  console.log(`── ${profile} ────────────────────────────────────────────`);
  for (const r of items) {
    if (r.error) {
      console.log(`  ✗ ${r.page.padEnd(12)} ERROR: ${r.error.slice(0, 60)}`);
      totalFail++;
      continue;
    }
    const pass = !r.horizontalScroll;
    if (!pass) totalFail++;
    const mark = pass ? '✓' : '✗';
    console.log(`  ${mark} ${r.page.padEnd(12)} | doc ${r.docScrollW.toString().padStart(4)} / win ${r.windowW.toString().padStart(4)} | overflow ${(r.overflowPx >= 0 ? '+' : '')}${r.overflowPx}px${r.offendersTop.length ? '  ← ' + r.offendersTop[0].tag + '.' + r.offendersTop[0].cls.slice(0, 30) + ' +' + r.offendersTop[0].excess + 'px' : ''}`);
    for (let i = 1; i < r.offendersTop.length; i++) {
      const o = r.offendersTop[i];
      console.log(`                                                    ← ${o.tag}.${o.cls.slice(0,30)} +${o.excess}px`);
    }
  }
  console.log('');
}

console.log(`截圖存到：${SHOT_DIR}`);
console.log(totalFail === 0 ? '\n🟢 全部通過' : `\n🔴 ${totalFail} 個項目失敗`);
process.exit(totalFail === 0 ? 0 : 1);

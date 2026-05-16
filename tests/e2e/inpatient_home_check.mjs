// 住院模式首頁 — 視覺檢查 + 結構斷言
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHOT_DIR = resolve(__dirname, 'home_shots');
mkdirSync(SHOT_DIR, { recursive: true });

const URL_BASE = process.env.PREVIEW_URL || 'http://127.0.0.1:3000/';

const PROFILES = [
  { name: '360-android',   width: 360, height: 740 },
  { name: '390-iphone-13', width: 390, height: 844 },
  { name: '768-tablet',    width: 768, height: 1024 },
  { name: '1280-desktop',  width: 1280, height: 800 },
];

(async () => {
  const browser = await chromium.launch();
  const issues = [];

  for (const p of PROFILES) {
    const ctx = await browser.newContext({
      viewport: { width: p.width, height: p.height },
      deviceScaleFactor: 2,
      ignoreHTTPSErrors: true,
    });
    const page = await ctx.newPage();
    page.on('pageerror', e => {
      // 過濾 PWA / serviceWorker 在無 SW 環境下的常見噪音（與 inpatient_polish_check 一致）
      if (/serviceWorker|addEventListener|querySelectorAll|register/.test(e.message)) return;
      issues.push(`[${p.name}] pageerror: ${e.message}`);
    });

    await page.addInitScript(() => {
      localStorage.setItem('mdpiece_user', JSON.stringify({ id:'demo', username:'demo', nickname:'示範', role:'patient', avatar_color:'#5B9FE8' }));
      localStorage.setItem('mdpiece_onboarded', '1');
      localStorage.setItem('mdpiece_landing_theme', 'dark');
      localStorage.setItem('mdpiece_care_mode', 'inpatient');
      // mock 一筆查房記錄
      localStorage.setItem('mdpiece_inpatient_rounds_latest', JSON.stringify({
        when: '今早 09:15', doctor: '張醫師',
        text: '生命徵象穩定，類風濕關節炎用藥計畫照原訂，今天可下床走動。下午抽血追蹤 CRP。'
      }));
      // mock 一些症狀紀錄（給趨勢線）
      const syms = [];
      const today = new Date();
      for (let i = 0; i < 7; i++) {
        const d = new Date(today); d.setDate(d.getDate() - i);
        syms.push({ id:'s'+i, categoryId:'joint', intensity: Math.max(1, 5 - i), frequency:1, recordedAt: d.toISOString() });
        syms.push({ id:'f'+i, categoryId:'fatigue', intensity: Math.max(1, 6 - i*0.5), frequency:1, recordedAt: d.toISOString() });
      }
      localStorage.setItem('mdpiece_symptoms', JSON.stringify(syms));
      Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get(){ return undefined; } });
    });

    await page.goto(URL_BASE, { waitUntil: 'load' });
    await page.evaluate(() => {
      const l = document.getElementById('landing'); if (l) l.style.display='none';
      const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
      if (typeof showPage === 'function') showPage('home');
    });
    await page.waitForSelector('.home-inpatient', { timeout: 8000 }).catch(() => {});
    await page.waitForTimeout(2000); // wait for fetch to settle + render

    // Structural assertions
    const present = await page.evaluate(() => ({
      hasNow:      !!document.querySelector('.ip-now'),
      hasNext:     !!document.querySelector('.ip-next-card'),
      sosCount:    document.querySelectorAll('.ip-sos-btn').length,
      hasTimeline: !!document.querySelector('.ip-timeline-rail'),
      hasProgress: !!document.querySelector('.ip-ring'),
      hasRounds:   !!document.querySelector('.ip-rounds'),
      trendCount:  document.querySelectorAll('.ip-trend-chip').length,
      stepCount:   document.querySelectorAll('.ip-step').length,
      eduCount:    document.querySelectorAll('.ip-edu-card').length,
    }));
    const expected = { hasNow: true, hasNext: true, sosCount: 4, hasTimeline: true, hasProgress: true, hasRounds: true, trendCount: 3, stepCount: 4, eduCount: 4 };
    for (const k of Object.keys(expected)) {
      if (present[k] !== expected[k]) issues.push(`[${p.name}] ${k}: expected ${expected[k]}, got ${present[k]}`);
    }

    // Horizontal overflow check
    const overflow = await page.evaluate(() => {
      const winW = window.innerWidth;
      const off = [];
      document.querySelectorAll('body *').forEach(el => {
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden') return;
        const r = el.getBoundingClientRect();
        if (r.right > winW + 1 && r.width > 0) {
          off.push({ tag: el.tagName.toLowerCase(), cls: (typeof el.className === 'string' ? el.className : '').slice(0, 50), excess: Math.round(r.right - winW) });
        }
      });
      off.sort((a, b) => b.excess - a.excess);
      return off.slice(0, 3);
    });
    // Allow tiny overflow on horizontally scrolling timeline (it's intentional)
    const realOverflow = overflow.filter(o => !o.cls.includes('ip-tl-') && !o.cls.includes('ip-timeline-rail'));
    if (realOverflow.length > 0) issues.push(`[${p.name}] overflow: ${JSON.stringify(realOverflow)}`);

    const shotPath = resolve(SHOT_DIR, `inpatient-${p.name}.png`);
    await page.screenshot({ path: shotPath, fullPage: true });
    console.log(`[${p.name}] ✓ ${JSON.stringify(present)} → ${shotPath}`);

    await ctx.close();
  }

  await browser.close();

  if (issues.length) {
    console.log('\n❌ Issues:');
    for (const i of issues) console.log('  ' + i);
    process.exit(1);
  }
  console.log('\n✓ All inpatient checks passed.');
})();

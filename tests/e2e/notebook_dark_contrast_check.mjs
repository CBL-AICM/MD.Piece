// Focused regression: 衛教筆記本在 dark theme 下文字色不能是白色
// （fix: --text/--text-dim/--klein lock to navy inside .notebook-wrap）
import { chromium } from 'playwright';

const URL = process.env.PREVIEW_URL || 'https://md-piece-git-claude-fix-text-visibili-d53df2-human530s-projects.vercel.app/';

function parseRgb(s) {
  const m = s.match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  return m[1].split(',').map(x => parseFloat(x.trim()));
}
function luminance([r,g,b]) {
  return 0.2126*r + 0.7152*g + 0.0722*b;
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();

  await page.addInitScript(() => {
    localStorage.setItem('mdpiece_user', JSON.stringify({ id:'demo', username:'demo', nickname:'測試' }));
    localStorage.setItem('mdpiece_onboarded', '1');
    localStorage.setItem('mdpiece_app_theme', 'dark');
    // 防止 service worker 自動 reload 造成 execution context destroy
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get() { return undefined; } });
  });

  const issues = [];
  page.on('pageerror', e => issues.push('pageerror: ' + e.message));

  await page.goto(URL, { waitUntil:'load', timeout: 60000 });
  await page.waitForTimeout(1500);

  // Force dark theme + bypass login
  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display='none';
    const a = document.getElementById('app-wrapper');
    if (a) { a.classList.add('show'); a.setAttribute('data-theme','dark'); }
  });

  await page.waitForTimeout(500);

  // Inject a minimal notebook DOM matching the real structure, so we don't have
  // to navigate the SPA. The CSS scope is what we're verifying.
  await page.evaluate(() => {
    const host = document.createElement('div');
    host.innerHTML = `
      <div class="notebook-wrap">
        <div class="notebook">
          <div class="nb-page left">
            <div class="nb-heading" id="t-heading">纖維肌痛症</div>
            <div class="nb-subtle" id="t-subtle">全身廣泛性疼痛、卻找不到發炎。</div>
            <div class="nb-list">
              <button class="nb-item"><strong id="t-item">中樞性敏感化</strong><small id="t-small">為什麼疼痛訊號被放大</small></button>
            </div>
          </div>
          <div class="nb-page right">
            <div class="nb-content-title" id="t-content-title">章節內容標題</div>
            <div id="edu-content-body"><h2 id="t-h2">章節 H2</h2><p><strong id="t-strong">粗體文字</strong></p></div>
          </div>
        </div>
      </div>`;
    document.body.appendChild(host);
  });

  const targets = ['t-heading','t-subtle','t-item','t-small','t-content-title','t-h2','t-strong'];
  const results = await page.evaluate((ids) => {
    return ids.map(id => {
      const el = document.getElementById(id);
      const c = getComputedStyle(el).color;
      return { id, color: c };
    });
  }, targets);

  let failed = 0;
  for (const r of results) {
    const rgb = parseRgb(r.color);
    if (!rgb) { console.log(`[?] ${r.id}: ${r.color}`); continue; }
    const L = luminance(rgb);
    // Dark navy text on cream should have luminance ≤ 120; white-ish text would be ~255
    const ok = L <= 130;
    console.log(`${ok?'[OK]':'[FAIL]'} ${r.id}: ${r.color}  L=${L.toFixed(0)}`);
    if (!ok) failed++;
  }

  await browser.close();
  if (issues.length) { console.log('--- runtime issues:'); issues.forEach(i => console.log(' ', i)); }

  if (failed > 0) {
    console.error(`\n${failed} element(s) still have light text in dark theme.`);
    process.exit(1);
  }
  console.log('\nAll notebook text colors are dark (contrast restored).');
})();

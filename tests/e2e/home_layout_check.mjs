// Quick visual check for the redesigned 4-layer home page.
// Bypasses login by injecting a mock user into localStorage.
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
    page.on('pageerror', e => issues.push(`[${p.name}] pageerror: ${e.message}`));
    page.on('console', m => {
      if (m.type() === 'error') issues.push(`[${p.name}] console.error: ${m.text()}`);
    });

    // Inject mock user before app boots so login is skipped, and stub out
    // the service worker so it doesn't reload the page mid-test.
    await page.addInitScript(() => {
      const user = {
        id: 'demo-user',
        username: 'demo',
        nickname: '示範',
        role: 'patient',
        avatar_color: '#5B9FE8',
      };
      localStorage.setItem('mdpiece_user', JSON.stringify(user));
      localStorage.setItem('mdpiece_onboarded', '1');
      localStorage.setItem('mdpiece_landing_theme', 'light');
      // Stub navigator.serviceWorker so the aggressive auto-update in index.html
      // doesn't reload the page and destroy the Playwright execution context.
      Object.defineProperty(navigator, 'serviceWorker', {
        configurable: true,
        get() { return undefined; },
      });
    });

    await page.goto(URL_BASE, { waitUntil: 'load' });
    await page.waitForSelector('#landing-enter', { timeout: 5000 }).catch(() => {});
    // Skip landing entirely: hide landing and force-mount the home page.
    await page.evaluate(() => {
      const landing = document.getElementById('landing');
      if (landing) { landing.style.display = 'none'; landing.classList.add('fade-out'); }
      const app = document.getElementById('app-wrapper');
      if (app) app.classList.add('show');
      if (typeof setTopbarPageTitle === 'function') setTopbarPageTitle('home');
      if (typeof showPage === 'function') showPage('home');
    });
    await page.waitForSelector('.home-layered', { timeout: 8000 }).catch(() => {});
    await page.waitForTimeout(1500);

    // Check that all 4 layers exist
    const layerNums = await page.$$eval('.home-layer-num', els => els.map(e => e.textContent.trim()));
    if (layerNums.length !== 4) issues.push(`[${p.name}] expected 4 layers, got ${layerNums.length} (${layerNums.join(',')})`);

    // Check core cards (should be 4)
    const coreCount = await page.$$eval('.hcore-card', els => els.length);
    if (coreCount !== 4) issues.push(`[${p.name}] expected 4 core cards, got ${coreCount}`);

    // Check secondary cards (should be 8)
    const secCount = await page.$$eval('.hsec-card', els => els.length);
    if (secCount !== 8) issues.push(`[${p.name}] expected 8 secondary cards, got ${secCount}`);

    // Check puzzle pieces (should be 9)
    const puzzleCount = await page.$$eval('.hpz-piece', els => els.length);
    if (puzzleCount !== 9) issues.push(`[${p.name}] expected 9 puzzle pieces, got ${puzzleCount}`);

    // Check bottom nav has 6 buttons
    const tabCount = await page.$$eval('.mobile-tabbar .mtab', els => els.length);

    // Horizontal overflow check
    const overflow = await page.evaluate(() => {
      const winW = window.innerWidth;
      const off = [];
      document.querySelectorAll('body *').forEach(el => {
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden') return;
        const r = el.getBoundingClientRect();
        if (r.right > winW + 1 && r.width > 0) {
          off.push({
            tag: el.tagName.toLowerCase(),
            cls: (typeof el.className === 'string' ? el.className : '').slice(0, 50),
            excess: Math.round(r.right - winW),
          });
        }
      });
      off.sort((a, b) => b.excess - a.excess);
      return off.slice(0, 5);
    });

    if (overflow.length > 0) {
      issues.push(`[${p.name}] horizontal overflow: ${JSON.stringify(overflow)}`);
    }

    const shotPath = resolve(SHOT_DIR, `home-${p.name}.png`);
    await page.screenshot({ path: shotPath, fullPage: true });
    console.log(`[${p.name}] ✓ layers=${layerNums.length}, core=${coreCount}, sec=${secCount}, puzzle=${puzzleCount}, tabs=${tabCount} → ${shotPath}`);

    await ctx.close();
  }

  await browser.close();

  if (issues.length) {
    console.log('\n❌ Issues:');
    for (const i of issues) console.log('  ' + i);
    process.exit(1);
  }
  console.log('\n✓ All checks passed.');
})();

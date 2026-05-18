// Audit: 在 dark theme 下走過所有衛教頁，找對比 < WCAG AA 的文字
import { chromium } from 'playwright';

const URL = process.env.PREVIEW_URL || 'http://127.0.0.1:3000/';

function srgbToLin(c) { c/=255; return c<=0.03928 ? c/12.92 : Math.pow((c+0.055)/1.055, 2.4); }
function luminance([r,g,b]) {
  return 0.2126*srgbToLin(r) + 0.7152*srgbToLin(g) + 0.0722*srgbToLin(b);
}
function contrast(rgb1, rgb2) {
  const l1 = luminance(rgb1), l2 = luminance(rgb2);
  const [bright, dark] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (bright + 0.05) / (dark + 0.05);
}
function parseRgb(s) {
  const m = s.match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  const parts = m[1].split(',').map(x => parseFloat(x.trim()));
  return parts.slice(0, 3);
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();

  await page.addInitScript(() => {
    localStorage.setItem('mdpiece_user', JSON.stringify({ id:'demo', username:'demo', nickname:'測試' }));
    localStorage.setItem('mdpiece_onboarded', '1');
    Object.defineProperty(navigator, 'serviceWorker', { configurable:true, get(){ return undefined; }});
  });

  const log = (s) => console.log(s);

  await page.goto(URL, { waitUntil:'load' });
  await page.waitForTimeout(1500);

  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display='none';
    const a = document.getElementById('app-wrapper');
    if (a) { a.classList.add('show'); a.setAttribute('data-theme','dark'); }
    if (typeof showPage === 'function') showPage('education');
  });
  await page.waitForTimeout(2000);

  async function audit(name) {
    const issues = await page.evaluate(() => {
      // Get effective bg by walking up the tree until we find non-transparent
      function effectiveBg(el) {
        let cur = el;
        while (cur && cur.nodeType === 1) {
          const cs = getComputedStyle(cur);
          const m = cs.backgroundColor.match(/rgba?\(([^)]+)\)/);
          if (m) {
            const parts = m[1].split(',').map(x => parseFloat(x.trim()));
            const a = parts.length === 4 ? parts[3] : 1;
            if (a > 0.5) return parts.slice(0, 3);
          }
          cur = cur.parentElement;
        }
        return [5, 6, 6]; // app-wrapper dark bg
      }
      function visible(el) {
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden') return false;
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && r.top < 5000 && r.bottom > 0;
      }
      const out = [];
      const all = document.querySelectorAll('#app-wrapper *');
      all.forEach(el => {
        if (!visible(el)) return;
        // Only check elements with direct text node
        let hasText = false;
        for (const child of el.childNodes) {
          if (child.nodeType === 3 && child.textContent.trim().length > 1) { hasText = true; break; }
        }
        if (!hasText) return;
        const cs = getComputedStyle(el);
        const color = cs.color;
        const m = color.match(/rgba?\(([^)]+)\)/);
        if (!m) return;
        const c = m[1].split(',').map(x => parseFloat(x.trim())).slice(0, 3);
        const bg = effectiveBg(el);
        out.push({
          tag: el.tagName.toLowerCase(),
          cls: typeof el.className === 'string' ? el.className.slice(0,80) : '',
          text: (el.textContent || '').trim().slice(0, 30),
          color: c, bg: bg,
        });
      });
      return out;
    });

    let bad = 0;
    for (const i of issues) {
      const ratio = contrast(i.color, i.bg);
      if (ratio < 4.5) {
        log(`[${name}] FAIL ratio=${ratio.toFixed(2)} color=rgb(${i.color.join(',')}) bg=rgb(${i.bg.join(',')}) <${i.tag}.${i.cls}> "${i.text}"`);
        bad++;
      }
    }
    log(`[${name}] checked ${issues.length} text elements, ${bad} below WCAG AA (4.5)`);
    return bad;
  }

  let total = 0;
  total += await audit('edu-shelf');

  // Try opening a book (notebook view)
  const openedBook = await page.evaluate(() => {
    const book = document.querySelector('.book');
    if (book) { book.click(); return true; }
    return false;
  });
  if (openedBook) {
    await page.waitForTimeout(1200);
    total += await audit('edu-notebook');
    // Try opening a chapter
    const openedChapter = await page.evaluate(() => {
      const item = document.querySelector('.nb-item');
      if (item) { item.click(); return true; }
      return false;
    });
    if (openedChapter) {
      await page.waitForTimeout(2000);
      total += await audit('edu-article');
    }
  }

  await browser.close();
  console.log(`\nTOTAL low-contrast text elements across edu pages (dark mode): ${total}`);
  if (total > 0) process.exit(1);
})();

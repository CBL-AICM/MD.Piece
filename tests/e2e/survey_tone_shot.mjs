// One-off visual capture of the patient survey hub + runner after the
// "research tone → user feedback tone" rewrite. The live hub needs a backend,
// so we boot the real frontend (real i18n.js + app.js + CSS) and call the
// render functions directly with mock data — the strings shown are the real
// shipped i18n values.
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHOT_DIR = resolve(__dirname, 'survey_tone_shots');
mkdirSync(SHOT_DIR, { recursive: true });
const URL_BASE = process.env.PREVIEW_URL || 'http://127.0.0.1:3000/';

// Mirrors backend /surveys/study/.../summary shape (parts come from seed).
const HUB = {
  parts: [
    { key: 'A',  part: 'A',  title: 'A. 背景資料',                 timepoints: ['D0'],          by_timepoint: { D0: { completed: true } } },
    { key: 'B1', part: 'B1', title: 'B1. 慢性病自我效能（SECD-6）',  timepoints: ['D0','D14','D28'], by_timepoint: { D0: { completed: false } } },
    { key: 'B2', part: 'B2', title: 'B2. 數位健康識能（eHEALS 改編）', timepoints: ['D0'],        by_timepoint: { D0: { completed: false } } },
    { key: 'B3', part: 'B3', title: 'B3. 就診前準備度（自編）',       timepoints: ['D0','D14','D28'], by_timepoint: { D0: { completed: false } } },
    { key: 'C1', part: 'C1', title: 'C1. 每日記錄功能',             timepoints: ['D14','D28'],   by_timepoint: {} },
    { key: 'D1', part: 'D1', title: 'D1. 醫師同理（CARE）',          timepoints: ['FU48'],        by_timepoint: {} },
  ],
  adherence: { active_days: 7, by_source: { symptoms: { days: 6 }, vitals: { days: 2 }, sleep: { days: 0 } } },
  eheals_m07: { total_score: 31 },
};

const SURVEY = {
  key: 'B1', title: 'B1. 慢性病自我效能（SECD-6）',
  description: '對做到下列事情有多少把握：1=完全沒把握，10=完全有把握。',
  scoring: { scale: { min: 1, max: 10, min_label: '完全沒把握', max_label: '完全有把握' } },
  items: [
    { id: 'q1', type: 'likert', text: '我有把握自己能控制疲倦不影響想做的事。' },
    { id: 'q2', type: 'likert', text: '我有把握自己能控制不適或疼痛不影響想做的事。' },
    { id: 'q3', type: 'likert', text: '我有把握自己能做不同的事，減少看醫師的次數。' },
  ],
};

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, ignoreHTTPSErrors: true,
  });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push('pageerror: ' + e.message));

  await page.addInitScript(() => {
    localStorage.setItem('mdpiece_user', JSON.stringify({
      id: 'demo-user', username: 'demo', nickname: '示範', role: 'patient', avatar_color: '#5B9FE8',
    }));
    localStorage.setItem('mdpiece_onboarded', '1');
    localStorage.setItem('mdpiece_landing_theme', 'light');
    localStorage.setItem('mdpiece_study_code', 'P01');
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, get() { return undefined; } });
  });

  await page.goto(URL_BASE, { waitUntil: 'load' });
  await page.evaluate(() => {
    const l = document.getElementById('landing'); if (l) l.style.display = 'none';
    const a = document.getElementById('app-wrapper'); if (a) a.classList.add('show');
  });
  await page.waitForTimeout(800);

  // 1) Survey hub
  await page.evaluate((data) => { _studyRenderHub(data); }, HUB);
  await page.waitForTimeout(500);
  const panel = await page.$('#study-sheet .ip-prep-panel');
  await panel.screenshot({ path: resolve(SHOT_DIR, 'hub.png') });
  console.log('✓ hub.png');

  // 2) Single survey runner
  await page.evaluate((s) => { _studyRenderSurvey(s, 'D0'); }, SURVEY);
  await page.waitForTimeout(500);
  const run = await page.$('#study-run .ip-prep-panel');
  await run.screenshot({ path: resolve(SHOT_DIR, 'runner.png') });
  console.log('✓ runner.png');

  await browser.close();
  if (errs.length) { console.log('page errors:\n  ' + errs.join('\n  ')); }
})();

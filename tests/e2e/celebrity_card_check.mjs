// 名人健康時刻卡片的視覺 smoke test
//
// 流程：
//   1) 起 http.server 在 frontend/ 上
//   2) 攔 /education/articles/daily，注入 mock 名人故事 + 一般每日故事
//   3) 導去 #/story，截圖 + 斷言 card 有出現
//
// 用法：node tests/e2e/celebrity_card_check.mjs

import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHOT_DIR = resolve(__dirname, 'celebrity_shots');
mkdirSync(SHOT_DIR, { recursive: true });

const FRONTEND_ROOT = resolve(__dirname, '..', '..', 'frontend');
const PORT = 3987;

const MOCK_DAILY = {
  today: {
    disease:  { slug: 'mock-d', title: '今日疾病故事', summary: '...', body: '## 內文\n還在', tags: [], sources: [], category: 'disease', pushed_on: '2026-05-22' },
    quick_tip:{ slug: 'mock-q', title: '今日健康快訊', summary: '...', body: '小貼士', tags: [], sources: [], category: 'quick_tip', pushed_on: '2026-05-22' },
    news:     { slug: 'mock-n', title: '最新醫療資訊', summary: '...', body: 'news', tags: [], sources: [], category: 'news', pushed_on: '2026-05-22' }
  },
  archive: [],
  news_feed: [
    { title: '衛福部公告 1', summary: '範例公告', link: 'https://www.mohw.gov.tw/x', published: '2026-05-22' }
  ],
  celebrity_stories: [
    {
      person: '余苑綺',
      disease_keyword: '大腸癌',
      icd10_prefix: 'C18',
      disease_name: '大腸癌',
      event_type: '治療中',
      soft_framing: '余苑綺分享治療歷程，提醒我們 50 歲後定期篩檢的重要性。早期發現、早期治療，存活率可以大幅提升。',
      source_title: '余苑綺證實大腸癌復發，分享治療歷程',
      source_link: 'https://example.com/news/1',
      related_articles: [
        { slug: 'colorectal-screening', title: '50 歲後的大腸癌篩檢時間表', summary: '...' },
        { slug: 'colorectal-diet', title: '大腸癌患者的飲食指南', summary: '...' }
      ]
    },
    {
      person: '某資深藝人',
      disease_keyword: '肺腺癌',
      icd10_prefix: 'C34',
      disease_name: '肺癌',
      event_type: '倡議推廣',
      soft_framing: '他用親身經驗呼籲戒菸與定期低劑量電腦斷層篩檢，讓更多人重視早期肺癌的早期偵測。',
      source_title: '某藝人罹肺腺癌，呼籲戒菸',
      source_link: 'https://example.com/news/2',
      related_articles: [
        { slug: 'lung-ldct', title: '低劑量電腦斷層篩檢誰該做？', summary: '...' }
      ]
    },
    {
      person: '某球員',
      disease_keyword: '心臟病',
      icd10_prefix: 'I25',
      disease_name: '慢性缺血性心臟病',
      event_type: '康復',
      soft_framing: '他的康復故事鼓勵了許多病友——術後規律運動和藥物，可以讓生活品質回到正常。',
      source_title: '某球員手術康復回歸',
      source_link: 'https://example.com/news/3',
      related_articles: []
    },
    {
      person: '某政要',
      disease_keyword: '糖尿病',
      icd10_prefix: 'E11',
      disease_name: '第二型糖尿病',
      event_type: '確診',
      soft_framing: '他的確診提醒我們：糖尿病早期常常沒症狀，定期健檢能讓我們及早因應。',
      source_title: '政要證實糖尿病分享心路歷程',
      source_link: 'https://example.com/news/4',
      related_articles: [
        { slug: 'diabetes-monitoring', title: '在家量血糖的訣竅', summary: '...' }
      ]
    }
  ]
};

async function main() {
  // 起 http.server
  console.log(`Starting http.server on port ${PORT}...`);
  const server = spawn('python3', ['-m', 'http.server', String(PORT), '--directory', FRONTEND_ROOT], {
    stdio: ['ignore', 'pipe', 'pipe']
  });

  // 等 server 起來
  await new Promise(r => setTimeout(r, 1500));

  let browser;
  try {
    browser = await chromium.launch();
    const ctx = await browser.newContext({ viewport: { width: 414, height: 896 } });  // iPhone XR sized

    // 攔截 context 層的所有請求；只 mock daily endpoint，其他放行
    await ctx.route('**/*', async route => {
      const url = route.request().url();
      if (url.includes('/education/articles/daily')) {
        console.log('Route intercept (daily):', url);
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_DAILY)
        });
      }
      return route.continue();
    });

    const page = await ctx.newPage();

    // 只記跟本次功能相關的錯誤；忽略 playwright 沙箱本來就抓不到的 CDN / 404 / lucide
    const IGNORED_ERROR_PATTERNS = [
      /Failed to load resource/i,
      /ERR_CERT_AUTHORITY_INVALID/i,
      /ERR_FAILED/i,
      /scope\.querySelectorAll is not a function/i,  // lucide.createIcons 在 mock 環境的副作用
    ];
    const errors = [];
    function recordIfRelevant(label, text) {
      if (IGNORED_ERROR_PATTERNS.some(rx => rx.test(text))) return;
      errors.push(`${label}: ${text}`);
    }
    page.on('pageerror', e => recordIfRelevant('pageerror', e.message));
    page.on('console', msg => {
      if (msg.type() === 'error') recordIfRelevant('console.error', msg.text());
    });
    const url = `http://127.0.0.1:${PORT}/`;
    // 先預埋一筆 user，讓 enterApp() 能進到 app 而不是註冊頁
    await ctx.addInitScript(() => {
      try {
        localStorage.setItem('mdpiece_user', JSON.stringify({
          id: 'smoke-test-user',
          name: '測試使用者',
          createdAt: new Date().toISOString()
        }));
        localStorage.setItem('mdpiece_onboarded', '1');
      } catch (e) {}
    });
    await page.goto(url, { waitUntil: 'networkidle' });

    // 等 app 初始化
    await page.waitForFunction(() => typeof navigateTo === 'function', { timeout: 10000 });

    // 跳過 landing：直接隱藏 landing + 顯示 app-wrapper
    await page.evaluate(() => {
      const landing = document.getElementById('landing');
      if (landing) { landing.classList.add('fade-out'); landing.style.display = 'none'; }
      const wrap = document.getElementById('app-wrapper');
      if (wrap) wrap.classList.add('show');
    });

    // 觸發故事頁
    await page.evaluate(() => navigateTo('story', null));

    // 等渲染（page transition 用 setTimeout 切換 innerHTML，需要 wait）
    await page.waitForSelector('#story-celebrity-card', { state: 'attached', timeout: 10000 });

    await page.waitForFunction(() => {
      const card = document.getElementById('story-celebrity-card');
      const list = document.getElementById('story-celebrity-list');
      return card && card.style.display !== 'none' && list && list.children.length > 0;
    }, { timeout: 5000 });

    const stats = await page.evaluate(() => {
      const card = document.getElementById('story-celebrity-card');
      const items = document.querySelectorAll('.story-celeb-item');
      const events = Array.from(document.querySelectorAll('.story-celeb-event')).map(e => e.textContent.trim());
      const persons = Array.from(document.querySelectorAll('.story-celeb-person')).map(e => e.textContent.trim());
      const relatedBtns = document.querySelectorAll('.story-celeb-related-item');
      return {
        cardVisible: card && card.style.display !== 'none',
        itemCount: items.length,
        events, persons,
        relatedBtnCount: relatedBtns.length
      };
    });

    console.log('Stats:', JSON.stringify(stats, null, 2));

    // 整頁截圖（含名人卡）
    await page.screenshot({
      path: resolve(SHOT_DIR, 'full_story_page.png'),
      fullPage: true
    });

    // 用 JS 滾到名人卡再截圖（scrollIntoViewIfNeeded 對 page transition 過的 element 不穩）
    await page.evaluate(() => {
      const el = document.getElementById('story-celebrity-card');
      if (el) el.scrollIntoView({ block: 'start' });
    });
    await page.waitForTimeout(400);
    await page.screenshot({
      path: resolve(SHOT_DIR, 'celebrity_card.png'),
      fullPage: false
    });

    // 斷言
    const failures = [];
    if (!stats.cardVisible) failures.push('celebrity card not visible');
    if (stats.itemCount !== MOCK_DAILY.celebrity_stories.length) {
      failures.push(`expected ${MOCK_DAILY.celebrity_stories.length} items, got ${stats.itemCount}`);
    }
    if (stats.persons.join(',') !== MOCK_DAILY.celebrity_stories.map(s => s.person).join(',')) {
      failures.push(`persons mismatch: ${stats.persons.join(',')}`);
    }
    const expectedRelated = MOCK_DAILY.celebrity_stories.reduce((sum, s) => sum + (s.related_articles?.length || 0), 0);
    if (stats.relatedBtnCount !== expectedRelated) {
      failures.push(`related btns expected ${expectedRelated}, got ${stats.relatedBtnCount}`);
    }
    if (errors.length) failures.push(`page errors: ${errors.join('; ')}`);

    if (failures.length) {
      console.error('❌ FAIL:');
      failures.forEach(f => console.error('  ' + f));
      process.exitCode = 1;
    } else {
      console.log('✅ ALL PASS — celebrity card rendered correctly');
      console.log(`Screenshots: ${SHOT_DIR}`);
    }
  } finally {
    if (browser) await browser.close();
    server.kill('SIGTERM');
  }
}

main().catch(e => { console.error(e); process.exit(1); });

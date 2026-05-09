/**
 * E2E 回歸測試：藥物百科查詢 (`/drug-search`) — 本 PR 的核心功能
 *
 * 測什麼：
 *   1. 一組常見台灣藥（中文名 / 英文學名 / 商品名）丟進 GET /drug-search/?q=…
 *   2. 驗收每一筆都符合「台灣繁中藥物衛教卡」的最低品質基準：
 *      ─ matched=true、name_zh / name_en 至少一個有值
 *      ─ indication / usage / education 不為空
 *      ─ 不出現大陸用語 / 簡體字（zh_tw 後處理該擋住的字眼）
 *      ─ TFDA 命中率（tfda_matched=true）— 軟性指標，至少要有 1 顆命中
 *   3. 印 summary（HTTP、毫秒、是否 cached / TFDA、字數）
 *
 * 執行：
 *     # 對 production
 *     npm run test:drug
 *
 *     # 對 PR Vercel preview / 本機 backend
 *     API_BASE=https://<preview-url>            npm run test:drug
 *     API_BASE=http://localhost:8000            npm run test:drug
 *
 *     # 自訂查詢清單
 *     QUERIES="阿斯匹靈,Lipitor,Panadol"        npm run test:drug
 *
 * 不依賴 Tesseract / fixture 圖檔（純 API 測試），跑得很快、無外部 OCR 變數。
 */

const API_BASE = process.env.API_BASE || 'https://www.mdpiece.life';
// 每筆查詢之間 sleep — Haiku 沒有 cache 時要呼叫 API、TFDA 第一次要下載 dataset
const DELAY_MS = parseInt(process.env.DELAY_MS || '1500', 10);
const sleep = ms => new Promise(r => setTimeout(r, ms));

// 預設查 4 顆藥，覆蓋：中英商品名、學名、中文俗名、台灣常見 OTC
const DEFAULT_QUERIES = [
  'Lipitor',          // 立普妥（statin 商品名，TFDA 應命中）
  'acetaminophen',    // 乙醯胺酚 / 普拿疼學名
  '阿斯匹靈',          // 中文俗名
  'Metformin',        // 二甲二脈 / 庫魯化錠（糖尿病藥，TFDA 應命中）
];
const queries = (process.env.QUERIES || '').trim()
  ? process.env.QUERIES.split(',').map(s => s.trim()).filter(Boolean)
  : DEFAULT_QUERIES;

// 大陸用語 / 簡體字偵測黑名單 — 任一出現就算後處理失守
// 這份清單只列「在台灣繁中醫療文本裡絕對不該出現」的詞，避免誤判
const FORBIDDEN_PATTERNS = [
  '信息', '软件', '视频', '网络',
  '用药', '服药', '吃药', '处方', '医生', '医师', '医院', '医保',
  '药剂师', '药品', '药物', '药盒', '药袋',
  '过敏', '复诊', '打针', '内服',
  '副反应', '副反應',
  '该药物', '使用本品',
  '血糖水平', '血壓水平', '血压水平', '膽固醇水平',
  // 大陸藥名（學名 / 商品名）— TW 不該用
  '阿司匹林', '乙酰', '撲熱息痛', '扑热息痛', '泰諾林', '泰诺林',
  '青霉素',
  // 單字簡體（保守選一些絕對不會跟繁中衝突的）
  '药', '医', '过', '剂', '时', '处', '产', '会', '们',
  '这', '从', '点', '简', '项', '减', '杨', '酰',
];

console.log(`API: ${API_BASE}`);
console.log(`Queries (${queries.length}): ${queries.join(', ')}\n`);

const results = [];
let exitCode = 0;

for (const q of queries) {
  console.log(`━━━ ${q} ━━━`);
  const r = { q, http: 0, ms: 0, matched: null, cached: null, tfda: null,
              nameZh: null, nameEn: null, eduChars: 0, forbidden: [], errors: [] };

  try {
    const t0 = Date.now();
    const resp = await fetch(`${API_BASE}/drug-search/?q=${encodeURIComponent(q)}`);
    r.ms = Date.now() - t0;
    r.http = resp.status;

    const ctype = resp.headers.get('content-type') || '';
    if (!ctype.includes('application/json')) {
      const body = await resp.text();
      r.errors.push(`Non-JSON response (${ctype}): ${body.slice(0, 120)}`);
      console.log(`  ❌ HTTP ${r.http}, non-JSON (${ctype})`);
      exitCode = 1;
      results.push(r);
      await sleep(DELAY_MS);
      continue;
    }

    const data = await resp.json();
    r.matched = data.matched === true;
    r.cached = data.cached === true;
    r.tfda = data.tfda_matched === true;
    r.nameZh = data.name_zh || null;
    r.nameEn = data.name_en || null;
    r.eduChars = (data.education || '').length;

    if (!r.matched) {
      r.errors.push('matched=false');
    } else {
      if (!r.nameZh && !r.nameEn) r.errors.push('name_zh and name_en both empty');
      if (!data.indication) r.errors.push('indication empty');
      if (!data.usage) r.errors.push('usage empty');
      if (!data.education) r.errors.push('education empty');
    }

    // 大陸用語 / 簡體字檢查（遞迴掃所有 string 欄位）
    const allText = collectStrings(data).join(' ');
    for (const pat of FORBIDDEN_PATTERNS) {
      if (allText.includes(pat)) r.forbidden.push(pat);
    }

    if (r.errors.length || r.forbidden.length) {
      exitCode = 1;
      console.log(`  ❌ HTTP ${r.http}, ${r.ms}ms${r.cached ? ' [cached]' : ''}${r.tfda ? ' [TFDA]' : ''}`);
      if (r.errors.length) console.log(`     content errors: ${r.errors.join('; ')}`);
      if (r.forbidden.length) console.log(`     forbidden TW terms: ${r.forbidden.join(', ')}`);
    } else {
      console.log(`  ✅ HTTP ${r.http}, ${r.ms}ms${r.cached ? ' [cached]' : ''}${r.tfda ? ' [TFDA]' : ''} — ${r.nameZh || r.nameEn} (${r.eduChars} chars)`);
    }
  } catch (e) {
    exitCode = 1;
    r.errors.push(e.message);
    console.log(`  ❌ EXCEPTION: ${e.message}`);
  }

  results.push(r);
  await sleep(DELAY_MS);
}

console.log('\n━━━ SUMMARY ━━━');
console.table(results.map(r => ({
  query: r.q, http: r.http, ms: r.ms,
  matched: r.matched, cached: r.cached, tfda: r.tfda,
  name: r.nameZh || r.nameEn || '-',
  edu: r.eduChars,
  issues: r.errors.length + r.forbidden.length || '',
})));

const tfdaHits = results.filter(r => r.tfda).length;
const passed = results.filter(r => r.matched && !r.errors.length && !r.forbidden.length).length;
console.log(`\nResults: ${passed}/${results.length} clean, TFDA hits: ${tfdaHits}/${results.length}`);

// 軟性警告：TFDA 全 miss 多半是 production 環境變數沒設或網路打不到 data.fda.gov.tw
if (tfdaHits === 0) {
  console.log('⚠️  TFDA 0 命中 — 檢查 TFDA_DRUG_API_URL 是否可達（會 fallback 走純 LLM，不會擋 PR）');
}

console.log(exitCode === 0 ? '\n✅ ALL PASSED' : '\n❌ SOME FAILED');
process.exit(exitCode);


function collectStrings(value, out = []) {
  if (typeof value === 'string') out.push(value);
  else if (Array.isArray(value)) value.forEach(v => collectStrings(v, out));
  else if (value && typeof value === 'object') Object.values(value).forEach(v => collectStrings(v, out));
  return out;
}

/**
 * E2E 回歸測試：藥單／藥袋拍照辨識 pipeline
 *
 *   1. 用 Tesseract.js 對 fixture 影像跑 OCR（chi_tra+eng）
 *   2. POST 到 /medications/recognize（帶 ocr_text 走 client_ocr 路徑）
 *   3. 檢查每張圖能抽出 ≥ 1 筆 medication，summary 印出細節
 *
 * 執行：
 *     # 對 production
 *     node tests/e2e/run_rx_recognition.mjs
 *
 *     # 對自架 backend（uvicorn 本機跑時）
 *     API_BASE=http://localhost:8000 node tests/e2e/run_rx_recognition.mjs
 *
 *     # 指定圖檔（不寫的話跑 fixtures/ 全部）
 *     node tests/e2e/run_rx_recognition.mjs path/to/foo.jpg path/to/bar.jpg
 *
 * 需要：
 *     npm install --no-save tesseract.js@5
 *     fixtures/ 內的圖片（執行 fixtures/generate_rx_images.py 產生）
 */
import { createWorker } from 'tesseract.js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const API_BASE = process.env.API_BASE || 'https://www.mdpiece.life';
const FIXTURES_DIR = path.join(__dirname, 'fixtures');
// 每張圖之間 sleep — 避免打爆 backend 的 Haiku API rate limit
const DELAY_MS = parseInt(process.env.DELAY_MS || '2000', 10);
const sleep = ms => new Promise(r => setTimeout(r, ms));

const args = process.argv.slice(2);
let images;
if (args.length) {
  images = args;
} else {
  if (!fs.existsSync(FIXTURES_DIR)) {
    console.error(`Fixtures dir not found: ${FIXTURES_DIR}`);
    console.error(`Run: python3 ${path.join(FIXTURES_DIR, 'generate_rx_images.py')}`);
    process.exit(1);
  }
  images = fs.readdirSync(FIXTURES_DIR)
    .filter(f => /\.(jpe?g|png)$/i.test(f))
    .sort()
    .map(f => path.join(FIXTURES_DIR, f));
  if (!images.length) {
    console.error(`No fixture images in ${FIXTURES_DIR}. Run the generator first.`);
    process.exit(1);
  }
}

console.log(`API: ${API_BASE}`);
console.log(`Images: ${images.length}\n`);

console.log('Initializing Tesseract worker (chi_tra+eng)...');
const t0 = Date.now();
const worker = await createWorker(['chi_tra', 'eng'], 1);
console.log(`Worker ready in ${(Date.now() - t0) / 1000}s\n`);

const results = [];
let exitCode = 0;

for (const img of images) {
  const name = path.basename(img);
  console.log(`━━━ ${name} ━━━`);
  let ocrMs = 0, apiMs = 0, http = 0, medCount = 0, provider = null, errors = [];

  try {
    const tA = Date.now();
    const { data } = await worker.recognize(img);
    ocrMs = Date.now() - tA;
    console.log(`  OCR: ${ocrMs}ms, ${data.text.trim().length} chars`);

    const tB = Date.now();
    const imgB64 = fs.readFileSync(img).toString('base64');
    const resp = await fetch(`${API_BASE}/medications/recognize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        patient_id: 'test-e2e',
        image_base64: imgB64,
        media_type: 'image/jpeg',
        ocr_text: data.text,
      }),
    });
    apiMs = Date.now() - tB;
    http = resp.status;

    const r = await resp.json();
    const meds = r.parsed || [];
    medCount = meds.length;
    provider = r.provider;
    errors = r.errors || [];

    console.log(`  API: HTTP ${http}, ${apiMs}ms, ${medCount} meds, provider=${provider}`);
    for (const m of meds) {
      const parts = [
        m.name,
        m.dosage && `劑量=${m.dosage}`,
        m.frequency && `頻率=${m.frequency}`,
        m.usage && `用法=${m.usage}`,
        m.duration && `療程=${m.duration}`,
      ].filter(Boolean);
      console.log('    •', parts.join(' | '));
    }
    if (errors.length) console.log('    errors:', JSON.stringify(errors));

    // 劣化測試（檔名含 _dN_）只記錄結果，不會把 exit code 設為失敗 — 用來
    // 觀察 pipeline 在差圖上的耐受度，不適合當 hard pass/fail
    const isDegraded = /_d\d_/.test(name);
    if (http !== 200 || medCount < 1) {
      if (isDegraded) {
        console.log(`  ⚠️  degraded (${name.match(/_d\d_\w+/)?.[0]}) — 0 meds，pipeline 在這個劣化等級已壞`);
      } else {
        console.log('  ❌ FAIL — expected HTTP 200 + ≥ 1 med');
        exitCode = 1;
      }
    } else if (isDegraded) {
      console.log(`  ✓ degraded (${name.match(/_d\d_\w+/)?.[0]}) — pipeline 仍解出 ${medCount} 筆`);
    }
  } catch (e) {
    console.log('  ❌ EXCEPTION:', e.message);
    if (!/_d\d_/.test(name)) exitCode = 1;
  }

  results.push({ name, ocrMs, apiMs, http, medCount, provider });
  console.log();
  if (DELAY_MS > 0) await sleep(DELAY_MS);
}

await worker.terminate();

console.log('━━━ SUMMARY ━━━');
console.table(results);
const totalMeds = results.reduce((a, r) => a + r.medCount, 0);
const totalTime = results.reduce((a, r) => a + r.ocrMs + r.apiMs, 0);
console.log(`Total: ${results.length} images, ${totalMeds} meds extracted, ${(totalTime / 1000).toFixed(1)}s`);
console.log(exitCode === 0 ? '\n✅ ALL PASS' : '\n❌ SOME FAILED');
process.exit(exitCode);

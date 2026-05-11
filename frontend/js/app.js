const API = window.location.hostname === "localhost" ? "http://localhost:8000" : "";
const GITHUB_REPO = "CBL-AICM/MD.Piece";

// ─── 顯示模式（年長版 / 普通版）─────────────────────────────
// 'senior' = 大字體、寬按鈕、高對比；'standard' = 原本的精緻 UI

function getMode() {
  return localStorage.getItem('mdpiece_mode') || 'standard';
}

function setMode(mode) {
  const m = mode === 'senior' ? 'senior' : 'standard';
  localStorage.setItem('mdpiece_mode', m);
  document.documentElement.setAttribute('data-mode', m);
  // 同步切換按鈕顯示（i18n 化：透過字典決定中/英文標籤）
  const t = (window.MDPiece_i18n && window.MDPiece_i18n.t) || ((k) => k);
  const labelKey = m === 'senior' ? 'mode.toNormal' : 'mode.toSenior';
  const fallback = m === 'senior' ? '切換為普通版' : '切換為年長版';
  document.querySelectorAll('[data-mode-toggle]').forEach(function (el) {
    el.textContent = window.MDPiece_i18n ? t(labelKey) : fallback;
    el.setAttribute('aria-pressed', m === 'senior' ? 'true' : 'false');
  });
}

function toggleMode() {
  setMode(getMode() === 'senior' ? 'standard' : 'senior');
}

// 在 DOMContentLoaded 之前先把屬性掛上，避免閃爍
document.documentElement.setAttribute('data-mode', getMode());

// ─── 使用者狀態 ─────────────────────────────────────────────

function getCurrentUser() {
  try {
    return JSON.parse(localStorage.getItem('mdpiece_user'));
  } catch { return null; }
}

function setCurrentUser(user) {
  localStorage.setItem('mdpiece_user', JSON.stringify(user));
}

// 登出 — 清除使用者資料並回到 landing
function logout() {
  if (!confirm('確定要登出嗎？\n\n$ exit\n\n下次回來會回到歡迎頁。')) return;
  try {
    localStorage.removeItem('mdpiece_user');
    localStorage.removeItem('mdpiece_demo_pid');
  } catch (e) {}
  window.location.reload();
}

// 取得或建立一個穩定 UUID（避免 demo 模式下 patient_id 不是 UUID 導致後端寫入失敗）
function getStablePatientId() {
  var user = getCurrentUser();
  if (user && user.id) return user.id;
  var demoId = localStorage.getItem('mdpiece_demo_pid');
  if (!demoId) {
    demoId = generateSecureId();
    localStorage.setItem('mdpiece_demo_pid', demoId);
  }
  return demoId;
}

// 產生 demo patient_id — 一律用 Web Crypto，避免 Math.random 流入 user_id（CodeQL）
function generateSecureId() {
  if (typeof crypto !== 'undefined') {
    if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
    if (typeof crypto.getRandomValues === 'function') {
      var b = new Uint8Array(16);
      crypto.getRandomValues(b);
      // RFC 4122 v4
      b[6] = (b[6] & 0x0f) | 0x40;
      b[8] = (b[8] & 0x3f) | 0x80;
      var hex = Array.prototype.map.call(b, function(x) {
        return ('00' + x.toString(16)).slice(-2);
      }).join('');
      return hex.slice(0, 8) + '-' + hex.slice(8, 12) + '-' + hex.slice(12, 16) + '-' + hex.slice(16, 20) + '-' + hex.slice(20);
    }
  }
  // 最後保險：所有現代瀏覽器都已支援 Web Crypto，這條基本上跑不到
  throw new Error('Web Crypto API unavailable');
}

// ─── 路由 ──────────────────────────────────────────────────

// 占位頁（功能尚未實作）— 終端機輸出風格
function placeholderPage(label, hint, iconName, slug, pct) {
  pct = pct || 67;
  const filled = Math.round(pct / 5);
  const bar = '█'.repeat(filled) + '░'.repeat(20 - filled);
  return `
    <section class="term-card">
      <header class="term-card-head">
        <span class="tc-l">┌──[</span>
        <span class="tc-name">${slug || 'page'}.exe</span>
        <span class="tc-r">]──┐</span>
      </header>
      <div class="term-card-body">
        <p class="tc-prompt"><span class="tc-user">root@mdpiece</span><span class="tc-colon">:</span><span class="tc-path">~/${slug || 'page'}</span><span class="tc-dollar">$</span> open --feature ${slug || 'page'}</p>
        <div class="tc-output">
          <div class="tc-icon-wrap">
            <span class="tc-icon"><i data-lucide="${iconName}"></i></span>
            <span class="tc-icon-frame"></span>
          </div>
          <h2 class="tc-title"><span class="tc-arrow">▸</span> ${label}</h2>
          <p class="tc-desc">${hint}</p>
        </div>
        <div class="tc-progress" aria-label="building progress">
          <span class="tc-progress-label">building</span>
          <span class="tc-progress-bar">[${bar}]</span>
          <span class="tc-progress-pct">${pct}%</span>
        </div>
        <pre class="tc-status">
[ STATUS  ] <span class="tc-status-ok">SCHEDULED</span>
[ STAGE   ] design → wireframe → <span class="tc-blink">building_</span>
[ ETA     ] coming soon · piece by piece</pre>
      </div>
      <footer class="term-card-foot">
        <span class="tc-l">└──[</span>
        <span class="tc-name">press · any · key · to · continue</span>
        <span class="tc-r">]──┘</span>
      </footer>
    </section>
  `;
}
// 生理紀錄使用獨立 vitals() 函式（見下方）
function memo() {
  var _memoList = (typeof memoLoad === 'function') ? memoLoad() : [];
  var _todayKey = new Date().toISOString().slice(0, 10);
  var _todayCount = _memoList.filter(function(m) {
    var t = m.createdAt || m.created_at;
    return t && String(new Date(t).toISOString()).slice(0, 10) === _todayKey;
  }).length;
  var _doctorCount = _memoList.filter(function(m) { return m.forDoctor; }).length;
  return `
    <div class="page-app-hero page-app-hero-rose">
      <div class="page-app-hero-head">
        <span class="page-app-hero-eyebrow">TODAY · 今日 Memo</span>
        <span class="page-app-hero-warn"><i data-lucide="info" style="width:11px;height:11px"></i> 僅存本裝置 · 醫療決策請以醫師為主</span>
      </div>
      <div class="page-app-hero-title">${_todayCount > 0 ? `今天記了 ${_todayCount} 筆 · 標記給醫師 ${_doctorCount} 筆` : '今天還沒記東西 — 想到就丟一筆吧'}</div>
      <div class="page-app-hero-meta">隨手拍症狀／藥袋／傷口，或寫下下次門診要跟醫師說的事</div>
    </div>

    <div class="card memo-quick">
      <button class="memo-quick-btn memo-quick-photo" onclick="memoStartPhoto()">
        <i data-lucide="camera" style="width:24px;height:24px"></i>
        <div>
          <strong>拍張照片</strong>
          <small>症狀、藥袋、傷口、皮疹…</small>
        </div>
      </button>
      <button class="memo-quick-btn memo-quick-upload" onclick="memoStartUpload()">
        <i data-lucide="image-up" style="width:24px;height:24px"></i>
        <div>
          <strong>從相簿上傳</strong>
          <small>挑一張已經拍好的照片</small>
        </div>
      </button>
      <button class="memo-quick-btn memo-quick-text" onclick="memoStartText()">
        <i data-lucide="message-square-text" style="width:24px;height:24px"></i>
        <div>
          <strong>寫下要說的話</strong>
          <small>下次門診想跟醫師講的事</small>
        </div>
      </button>
    </div>

    <input type="file" id="memo-photo-input" accept="image/*" capture="environment" style="display:none" onchange="memoOnPhotoPicked(event)" />
    <input type="file" id="memo-upload-input" accept="image/*" style="display:none" onchange="memoOnPhotoPicked(event)" />

    <div class="card memo-composer" id="memo-composer" style="display:none">
      <div class="memo-composer-head">
        <strong id="memo-composer-title">新 memo</strong>
        <button class="ghost" onclick="memoCancelCompose()" aria-label="取消">
          <i data-lucide="x" style="width:18px;height:18px"></i>
        </button>
      </div>
      <div id="memo-photo-preview" style="display:none"></div>
      <textarea id="memo-text" rows="4" placeholder="想跟醫師說 / 想自己留存的事..."></textarea>
      <div class="memo-composer-row">
        <label class="memo-check">
          <input type="checkbox" id="memo-for-doctor" />
          <span>給醫師看（下次門診帶這條）</span>
        </label>
        <button class="primary" onclick="memoSave()">
          <i data-lucide="save" style="width:14px;height:14px;vertical-align:middle"></i> 儲存
        </button>
      </div>
    </div>

    <div class="card">
      <div class="memo-list-head">
        <h3 style="font-size:1rem;display:flex;align-items:center;gap:6px">
          <i data-lucide="archive" style="width:18px;height:18px"></i>
          <span id="memo-list-title">所有 memo</span>
          <span class="memo-count" id="memo-count">0</span>
        </h3>
        <div class="memo-filter">
          <button class="memo-filter-btn active" data-filter="all" onclick="memoSetFilter('all')">全部</button>
          <button class="memo-filter-btn" data-filter="doctor" onclick="memoSetFilter('doctor')">給醫師</button>
          <button class="memo-filter-btn" data-filter="self" onclick="memoSetFilter('self')">自己</button>
        </div>
      </div>
      <div id="memo-list" class="memo-list"></div>
    </div>
  `;
}
// ─── Memo（拍照 + 給醫師留言 + 給自己備忘） ──────────────────
var MEMO_STORE_KEY = "mdpiece_memos_v1";
var _memoFilter = "all";          // all / doctor / self
var _memoComposeMode = null;       // "photo" | "text" | null
var _memoStagedPhoto = null;       // dataURL，等待儲存
var _memoEditingId = null;         // 編輯中的 memo id（null 表示新增）

function memoLoad() {
  try {
    var raw = localStorage.getItem(MEMO_STORE_KEY);
    if (!raw) return [];
    var parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (e) { return []; }
}
function memoSaveAll(arr) {
  try { localStorage.setItem(MEMO_STORE_KEY, JSON.stringify(arr)); }
  catch (e) { showToast("儲存失敗，可能空間不足", "error"); }
}

function loadMemoPage() {
  _memoFilter = "all";
  _memoComposeMode = null;
  _memoStagedPhoto = null;
  memoRenderList();
  if (typeof lucide !== 'undefined') setTimeout(function() { lucide.createIcons(); }, 30);
}

// ── 觸發新增 ──────────────────────────────────────────────
function memoStartPhoto() {
  _memoComposeMode = "photo";
  // 開啟系統相機（capture="environment"）
  var input = document.getElementById("memo-photo-input");
  if (input) { input.value = ""; input.click(); }
}

function memoStartUpload() {
  _memoComposeMode = "photo";
  // 開啟相簿/檔案選擇器（無 capture，使用者可挑現有照片）
  var input = document.getElementById("memo-upload-input");
  if (input) { input.value = ""; input.click(); }
}

function memoStartText() {
  _memoComposeMode = "text";
  _memoStagedPhoto = null;
  memoOpenComposer("寫下要說的話", { forDoctor: true });
}

function memoOnPhotoPicked(ev) {
  var file = ev.target.files && ev.target.files[0];
  if (!file) return;
  if (!file.type || file.type.indexOf("image/") !== 0) {
    showToast("請選擇圖片檔", "warning");
    return;
  }
  // 大圖縮到 max 1280px、JPEG 0.85，避免 localStorage 爆掉
  memoCompressImage(file, 1280, 0.85).then(function(dataUrl) {
    _memoStagedPhoto = dataUrl;
    memoOpenComposer("為這張照片加備註（可選）", { forDoctor: false });
  }).catch(function() {
    showToast("照片讀取失敗", "error");
  });
}

function memoCompressImage(file, maxDim, quality) {
  return new Promise(function(resolve, reject) {
    var reader = new FileReader();
    reader.onerror = function() { reject(new Error("read failed")); };
    reader.onload = function() {
      var img = new Image();
      img.onerror = function() { reject(new Error("decode failed")); };
      img.onload = function() {
        var w = img.naturalWidth, h = img.naturalHeight;
        var scale = Math.min(1, maxDim / Math.max(w, h));
        var tw = Math.round(w * scale), th = Math.round(h * scale);
        var canvas = document.createElement("canvas");
        canvas.width = tw; canvas.height = th;
        var ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, tw, th);
        try { resolve(canvas.toDataURL("image/jpeg", quality)); }
        catch (e) { reject(e); }
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

function memoOpenComposer(title, opts) {
  opts = opts || {};
  var box = document.getElementById("memo-composer");
  if (!box) return;
  document.getElementById("memo-composer-title").textContent = title;
  document.getElementById("memo-text").value = "";
  document.getElementById("memo-for-doctor").checked = !!opts.forDoctor;

  var preview = document.getElementById("memo-photo-preview");
  if (_memoStagedPhoto) {
    preview.style.display = "block";
    preview.innerHTML = '<img src="' + _memoStagedPhoto + '" alt="預覽" />';
  } else {
    preview.style.display = "none";
    preview.innerHTML = "";
  }
  box.style.display = "block";
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  setTimeout(function() {
    var ta = document.getElementById("memo-text");
    if (ta) ta.focus();
  }, 50);
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function memoCancelCompose() {
  _memoComposeMode = null;
  _memoStagedPhoto = null;
  _memoEditingId = null;
  var box = document.getElementById("memo-composer");
  if (box) box.style.display = "none";
}

function memoSave() {
  var text = (document.getElementById("memo-text").value || "").trim();
  var forDoctor = document.getElementById("memo-for-doctor").checked;
  if (!_memoStagedPhoto && !text) {
    showToast("寫點什麼或加張照片再儲存", "warning");
    return;
  }
  var memos = memoLoad();
  var editingId = _memoEditingId;
  if (editingId) {
    var idx = memos.findIndex(function(x) { return x.id === editingId; });
    if (idx >= 0) {
      memos[idx] = Object.assign({}, memos[idx], {
        type: _memoStagedPhoto ? "photo" : "text",
        photo: _memoStagedPhoto || null,
        text: text,
        forDoctor: !!forDoctor,
        updatedAt: new Date().toISOString()
      });
    }
  } else {
    memos.unshift({
      id: "m_" + Date.now() + "_" + Math.random().toString(36).slice(2, 6),
      type: _memoStagedPhoto ? "photo" : "text",
      photo: _memoStagedPhoto || null,
      text: text,
      forDoctor: !!forDoctor,
      createdAt: new Date().toISOString()
    });
  }
  memoSaveAll(memos);
  memoCancelCompose();
  memoRenderList();
  showToast(editingId ? "已更新" : "已儲存", "success");
}

function memoEdit(id) {
  var memos = memoLoad();
  var m = memos.find(function(x) { return x.id === id; });
  if (!m) return;
  _memoEditingId = id;
  _memoComposeMode = m.photo ? "photo" : "text";
  _memoStagedPhoto = m.photo || null;

  var box = document.getElementById("memo-composer");
  if (!box) return;
  document.getElementById("memo-composer-title").textContent = "編輯 memo";
  document.getElementById("memo-text").value = m.text || "";
  document.getElementById("memo-for-doctor").checked = !!m.forDoctor;

  var preview = document.getElementById("memo-photo-preview");
  if (_memoStagedPhoto) {
    preview.style.display = "block";
    preview.innerHTML = '<img src="' + _memoStagedPhoto + '" alt="預覽" />';
  } else {
    preview.style.display = "none";
    preview.innerHTML = "";
  }
  box.style.display = "block";
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  setTimeout(function() {
    var ta = document.getElementById("memo-text");
    if (ta) ta.focus();
  }, 50);
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function memoDelete(id) {
  if (!confirm("確定要刪除這則 memo？")) return;
  var memos = memoLoad().filter(function(m) { return m.id !== id; });
  memoSaveAll(memos);
  memoRenderList();
}

function memoOpenLightbox(id) {
  var memos = memoLoad();
  var m = memos.find(function(x) { return x.id === id; });
  if (!m) return;
  // 已存在的 overlay 先關掉避免疊起來
  var existing = document.getElementById("memo-lightbox");
  if (existing) existing.remove();

  var bodyHtml = "";
  if (m.photo) {
    bodyHtml += '<img class="memo-lb-photo" src="' + m.photo + '" alt="memo 照片" />';
  }
  if (m.text) {
    bodyHtml += '<div class="memo-lb-text">' + escapeHtml(m.text).replace(/\n/g, "<br>") + '</div>';
  }
  var pill = m.forDoctor
    ? '<span class="memo-pill memo-pill-doctor"><i data-lucide="stethoscope" style="width:12px;height:12px"></i> 給醫師</span>'
    : '<span class="memo-pill memo-pill-self"><i data-lucide="user" style="width:12px;height:12px"></i> 自己</span>';

  var overlay = document.createElement("div");
  overlay.id = "memo-lightbox";
  overlay.className = "memo-lightbox-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.innerHTML =
    '<div class="memo-lightbox-card" onclick="event.stopPropagation()">' +
      '<div class="memo-lightbox-meta">' +
        pill +
        '<span class="memo-time">' + escapeHtml(memoFormatTime(m.createdAt)) + '</span>' +
        '<button class="memo-lightbox-close" onclick="memoCloseLightbox()" aria-label="關閉">' +
          '<i data-lucide="x" style="width:18px;height:18px"></i>' +
        '</button>' +
      '</div>' +
      '<div class="memo-lightbox-body">' + bodyHtml + '</div>' +
    '</div>';
  overlay.addEventListener("click", memoCloseLightbox);
  document.body.appendChild(overlay);
  if (typeof lucide !== 'undefined') lucide.createIcons();
  document.addEventListener("keydown", _memoLightboxEsc);
}

function memoCloseLightbox() {
  var el = document.getElementById("memo-lightbox");
  if (el) el.remove();
  document.removeEventListener("keydown", _memoLightboxEsc);
}

function _memoLightboxEsc(e) {
  if (e.key === "Escape") memoCloseLightbox();
}

function memoToggleDoctor(id) {
  var memos = memoLoad();
  var m = memos.find(function(x) { return x.id === id; });
  if (!m) return;
  m.forDoctor = !m.forDoctor;
  memoSaveAll(memos);
  memoRenderList();
}

function memoSetFilter(f) {
  _memoFilter = f;
  document.querySelectorAll(".memo-filter-btn").forEach(function(b) {
    b.classList.toggle("active", b.getAttribute("data-filter") === f);
  });
  memoRenderList();
}

function memoFormatTime(iso) {
  var d = new Date(iso);
  var now = new Date();
  var diff = (now - d) / 1000;
  if (diff < 60) return "剛剛";
  if (diff < 3600) return Math.floor(diff / 60) + " 分鐘前";
  if (diff < 86400) return Math.floor(diff / 3600) + " 小時前";
  if (diff < 604800) return Math.floor(diff / 86400) + " 天前";
  return d.toISOString().slice(0, 10);
}

function memoRenderList() {
  var listEl = document.getElementById("memo-list");
  var countEl = document.getElementById("memo-count");
  var titleEl = document.getElementById("memo-list-title");
  if (!listEl) return;

  var all = memoLoad();
  var filtered = all.filter(function(m) {
    if (_memoFilter === "doctor") return !!m.forDoctor;
    if (_memoFilter === "self")   return !m.forDoctor;
    return true;
  });

  if (countEl) countEl.textContent = filtered.length;
  if (titleEl) {
    titleEl.textContent = _memoFilter === "doctor" ? "給醫師的話" :
                          _memoFilter === "self"   ? "自己的備忘" : "所有 memo";
  }

  if (!filtered.length) {
    listEl.innerHTML =
      '<div class="memo-empty">' +
        (all.length ? '這個分類下還沒有 memo，換個篩選看看。' :
                      '還沒有 memo —— 從上方「拍照片」或「寫下要說的話」開始吧。') +
      '</div>';
    return;
  }

  var html = filtered.map(function(m) {
    var bodyHtml = "";
    if (m.photo) {
      bodyHtml += '<img class="memo-photo" src="' + m.photo + '" alt="memo 照片" />';
    }
    if (m.text) {
      bodyHtml += '<div class="memo-text">' + escapeHtml(m.text).replace(/\n/g, "<br>") + '</div>';
    }
    var pill = m.forDoctor
      ? '<span class="memo-pill memo-pill-doctor"><i data-lucide="stethoscope" style="width:12px;height:12px"></i> 給醫師</span>'
      : '<span class="memo-pill memo-pill-self"><i data-lucide="user" style="width:12px;height:12px"></i> 自己</span>';
    return '' +
      '<article class="memo-item">' +
        '<div class="memo-item-meta">' +
          pill +
          '<span class="memo-time">' + escapeHtml(memoFormatTime(m.createdAt)) + '</span>' +
          '<button class="memo-toggle" onclick="memoToggleDoctor(\'' + m.id + '\')" title="切換給醫師／自己">' +
            '<i data-lucide="repeat" style="width:14px;height:14px"></i>' +
          '</button>' +
          '<button class="memo-edit" onclick="memoEdit(\'' + m.id + '\')" title="編輯">' +
            '<i data-lucide="pencil" style="width:14px;height:14px"></i>' +
          '</button>' +
          '<button class="memo-del" onclick="memoDelete(\'' + m.id + '\')" title="刪除">' +
            '<i data-lucide="trash-2" style="width:14px;height:14px"></i>' +
          '</button>' +
        '</div>' +
        '<div class="memo-item-body" onclick="memoOpenLightbox(\'' + m.id + '\')" role="button" tabindex="0" aria-label="點擊放大">' + bodyHtml + '</div>' +
      '</article>';
  }).join("");

  listEl.innerHTML = html;
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

// ── 每日故事：分類推送（疾病 / 健康快訊 / 最新資訊）─────────
var STORY_CATEGORIES = [
  { key: "disease",    label: "疾病故事", icon: "stethoscope", desc: "用故事的方式，把一個疾病講給你聽" },
  { key: "quick_tip",  label: "健康快訊", icon: "zap",         desc: "今天就能用的小知識" },
  { key: "news",       label: "最新資訊", icon: "newspaper",   desc: "醫療新聞、衛教快報" }
];

function story() {
  var sectionsHtml = STORY_CATEGORIES.map(function(c) {
    return '' +
      '<div class="card story-section" id="story-section-' + c.key + '">' +
        '<div class="story-section-head">' +
          '<span class="story-section-cat story-cat-' + c.key + '">' +
            '<i data-lucide="' + c.icon + '" style="width:14px;height:14px;vertical-align:middle"></i> ' + c.label +
          '</span>' +
          '<span class="story-section-date" id="story-date-' + c.key + '">—</span>' +
        '</div>' +
        '<p class="story-section-desc">' + c.desc + '</p>' +
        '<div class="story-section-body" id="story-body-' + c.key + '">' +
          '<div style="color:var(--text-dim);font-size:.9rem;padding:12px 0">載入中…</div>' +
        '</div>' +
      '</div>';
  }).join("");

  return `
    <div class="card story-hero">
      <h2 style="display:flex;align-items:center;gap:8px">
        <i data-lucide="book-open" style="width:22px;height:22px"></i> 每日故事
      </h2>
      <p style="margin-top:6px;color:var(--text-dim)">
        每天三則：一篇疾病故事、一則健康快訊、一份最新資訊——用故事的方式，陪你慢慢讀懂自己的身體。
      </p>
    </div>

    ${sectionsHtml}

    <div class="card" id="story-newsfeed-card">
      <h3 style="display:flex;align-items:center;gap:8px;font-size:1rem;margin:0">
        <i data-lucide="rss" style="width:16px;height:16px"></i> 衛福部最新公告
      </h3>
      <p class="story-section-desc" style="margin-top:6px">
        來自衛福部 RSS，每小時更新一次，點標題會在新分頁開啟原文。
      </p>
      <div id="story-newsfeed-list" class="story-newsfeed-list">
        <div style="color:var(--text-dim);font-size:.85rem">載入中…</div>
      </div>
    </div>

    <div class="card" id="story-archive-card">
      <h3 style="display:flex;align-items:center;gap:8px;font-size:1rem;margin:0">
        <i data-lucide="history" style="width:16px;height:16px"></i> 過去幾天
      </h3>
      <p class="story-section-desc" style="margin-top:6px">
        最近錯過的也補得回來。點任一張卡片可以打開那天的文章。
      </p>
      <div id="story-archive-list" class="story-archive-list">
        <div style="color:var(--text-dim);font-size:.85rem">載入中…</div>
      </div>
    </div>
  `;
}

function loadStoryPage() {
  fetch(API + "/education/articles/daily?days=7")
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var today = (data && data.today) || {};
      STORY_CATEGORIES.forEach(function(c) {
        renderStorySection(c.key, today[c.key]);
      });
      renderStoryNewsFeed((data && data.news_feed) || []);
      renderStoryArchive((data && data.archive) || []);
      if (typeof lucide !== 'undefined') lucide.createIcons();
    })
    .catch(function() {
      STORY_CATEGORIES.forEach(function(c) {
        var body = document.getElementById("story-body-" + c.key);
        if (body) body.innerHTML = '<div style="color:var(--text-dim);font-size:.9rem;padding:12px 0">載入失敗，請稍後再試。</div>';
      });
      var nf = document.getElementById("story-newsfeed-list");
      if (nf) nf.innerHTML = '<div style="color:var(--text-dim);font-size:.85rem">無法取得最新公告。</div>';
      var arc = document.getElementById("story-archive-list");
      if (arc) arc.innerHTML = '';
    });
}

function renderStorySection(catKey, article) {
  var dateEl = document.getElementById("story-date-" + catKey);
  var body = document.getElementById("story-body-" + catKey);
  if (!body) return;
  if (!article) {
    if (dateEl) dateEl.textContent = "";
    body.innerHTML = '<div style="color:var(--text-dim);font-size:.9rem;padding:12px 0">這個分類今天還沒有故事。</div>';
    return;
  }
  if (!window._eduArticles) window._eduArticles = {};
  window._eduArticles[article.slug] = article;

  if (dateEl) dateEl.textContent = article.pushed_on || "";

  var tags = (article.tags || []).map(function(t) {
    return '<span class="story-tag">' + escapeHtml(t) + '</span>';
  }).join("");
  var sources = (article.sources || []).map(function(s) {
    return '<li>' + escapeHtml(s) + '</li>';
  }).join("");
  var bodyHtml = article.body
    ? '<div class="story-body">' + markdownToHtml(article.body) + '</div>'
    : '<div style="color:var(--text-dim);font-size:.9rem">內容尚未提供。</div>';

  body.innerHTML =
    '<h3 class="story-title">' + escapeHtml(article.title) + '</h3>' +
    (article.summary ? '<p class="story-summary">' + escapeHtml(article.summary) + '</p>' : '') +
    (tags ? '<div class="story-tags">' + tags + '</div>' : '') +
    bodyHtml +
    (sources
      ? '<div class="story-sources"><div class="story-sources-head">參考來源</div><ol>' + sources + '</ol></div>'
      : '') +
    (article.reviewed_at ? '<div class="story-reviewed">最後審稿：' + escapeHtml(article.reviewed_at) + '</div>' : '');
}

function renderStoryNewsFeed(items) {
  var list = document.getElementById("story-newsfeed-list");
  if (!list) return;
  if (!items.length) {
    list.innerHTML = '<div style="color:var(--text-dim);font-size:.85rem">目前沒有可顯示的公告。</div>';
    return;
  }
  list.innerHTML = items.map(function(n) {
    var link = n.link ? escapeHtml(n.link) : "";
    var title = escapeHtml(n.title || "（無標題）");
    var summary = n.summary ? '<p class="story-news-summary">' + escapeHtml(n.summary) + '</p>' : "";
    var pub = n.published ? '<span class="story-news-date">' + escapeHtml(n.published) + '</span>' : "";
    var titleHtml = link
      ? '<a class="story-news-title" href="' + link + '" target="_blank" rel="noopener noreferrer">' + title + '</a>'
      : '<span class="story-news-title">' + title + '</span>';
    return '<article class="story-news-item">' + titleHtml + pub + summary + '</article>';
  }).join("");
}

function renderStoryArchive(days) {
  var list = document.getElementById("story-archive-list");
  if (!list) return;
  if (!days.length) {
    list.innerHTML = '<div style="color:var(--text-dim);font-size:.85rem">還沒有歷史紀錄。</div>';
    return;
  }
  if (!window._eduArticles) window._eduArticles = {};
  list.innerHTML = days.map(function(day) {
    var rows = STORY_CATEGORIES.map(function(c) {
      var a = day.items && day.items[c.key];
      if (!a) return '';
      window._eduArticles[a.slug] = Object.assign({}, window._eduArticles[a.slug] || {}, a);
      return '<button class="story-archive-item" onclick="storyOpenArchive(\'' + escapeHtml(a.slug) + '\',\'' + c.key + '\')">' +
               '<span class="story-archive-cat story-cat-' + c.key + '">' + escapeHtml(c.label) + '</span>' +
               '<span class="story-archive-title">' + escapeHtml(a.title) + '</span>' +
               (a.summary ? '<span class="story-archive-summary">' + escapeHtml(a.summary) + '</span>' : '') +
             '</button>';
    }).join("");
    return '<div class="story-archive-day">' +
             '<div class="story-archive-day-head">' + escapeHtml(day.date) + '</div>' +
             '<div class="story-archive-day-grid">' + rows + '</div>' +
           '</div>';
  }).join("");
}

function storyOpenArchive(slug, catKey) {
  var cached = (window._eduArticles && window._eduArticles[slug]) || null;

  // RSS fallback 卡（slug 以 news-feed- 開頭）不是真的 markdown article，
  // 後端 /education/articles/{slug} 會 404；直接用 archive 已經帶過來的 payload 渲染。
  var isExternal = (slug && slug.indexOf("news-feed-") === 0)
    || (cached && (cached.external_link || cached.body));
  if (isExternal && cached) {
    var key1 = catKey || cached.category || "news";
    renderStorySection(key1, cached);
    var section1 = document.getElementById("story-section-" + key1);
    if (section1) section1.scrollIntoView({ behavior: "smooth", block: "start" });
    if (typeof lucide !== 'undefined') lucide.createIcons();
    return;
  }

  fetch(API + "/education/articles/" + encodeURIComponent(slug))
    .then(function(r) {
      if (!r.ok) throw new Error("not found");
      return r.json();
    })
    .then(function(article) {
      var prev = (window._eduArticles && window._eduArticles[slug]) || {};
      article.pushed_on = prev.pushed_on || article.pushed_on;
      var key = catKey || article.category || "disease";
      renderStorySection(key, article);
      var section = document.getElementById("story-section-" + key);
      if (section) section.scrollIntoView({ behavior: "smooth", block: "start" });
      if (typeof lucide !== 'undefined') lucide.createIcons();
    })
    .catch(function() {
      var key = catKey || "disease";
      var body = document.getElementById("story-body-" + key);
      if (body) body.innerHTML = '<div style="color:var(--text-dim);font-size:.9rem;padding:12px 0">找不到這篇文章。</div>';
    });
}

function renderPvVisitHero() {
  // 若使用者沒設下次回診日，回空字串（不顯示）
  var iso = (typeof loadNextVisit === 'function') ? loadNextVisit() : '';
  if (!iso) {
    return ''
      + '<div class="pv-visit-hero pv-visit-hero-empty">'
      +   '<div class="pv-visit-hero-icon"><i data-lucide="calendar-plus"></i></div>'
      +   '<div class="pv-visit-hero-body">'
      +     '<div class="pv-visit-hero-eyebrow">下次回診</div>'
      +     '<div class="pv-visit-hero-title">尚未設定回診日</div>'
      +     '<div class="pv-visit-hero-sub">回首頁設好回診日期，這裡就會顯示倒數和本期紀錄範圍。</div>'
      +   '</div>'
      +   '<button class="pv-btn pv-btn-ghost" onclick="navigateTo(\'home\',null)">'
      +     '<i data-lucide="home"></i> 前往設定'
      +   '</button>'
      + '</div>';
  }
  var d = _daysBetween(iso);
  var pretty = iso.replace(/-/g, '/');
  var label, tone, eyebrow;
  if (d > 0)       { label = '倒數 ' + d + ' 天';        tone = 'upcoming'; eyebrow = '下次回診'; }
  else if (d === 0){ label = '今天回診';                 tone = 'today';    eyebrow = '今天就是回診日'; }
  else             { label = '已超過 ' + (-d) + ' 天';   tone = 'past';     eyebrow = '上次回診'; }
  return ''
    + '<div class="pv-visit-hero pv-visit-hero-' + tone + '">'
    +   '<div class="pv-visit-hero-icon"><i data-lucide="calendar-check-2"></i></div>'
    +   '<div class="pv-visit-hero-body">'
    +     '<div class="pv-visit-hero-eyebrow">' + eyebrow + '</div>'
    +     '<div class="pv-visit-hero-title">' + label + '</div>'
    +     '<div class="pv-visit-hero-sub">日期：' + pretty + '　·　出門前可以先看一下這頁的提醒</div>'
    +   '</div>'
    +   '<div class="pv-visit-hero-warn"><i data-lucide="info" style="width:12px;height:12px"></i> 以醫師預約單為準</div>'
    + '</div>';
}

function previsit() {
  var _pvDays = (typeof getReportDays === 'function') ? getReportDays() : 30;
  return ''
    + '<section class="pv-page">'
    + renderPvVisitHero()
    + renderHowto('previsit')
    + '  <header class="pv-header">'
    + '    <div>'
    + '      <p class="pv-eyebrow">回診前用的健康摘要</p>'
    + '      <h2 class="pv-title"><i data-lucide="clipboard-check"></i> 診前報告</h2>'
    + '      <p class="pv-sub">看診前 30 秒讀完：MD.Piece 幫你整理近 ' + _pvDays + ' 天的症狀、情緒、用藥與就診紀錄，並列出這次門診最該問的三件事。</p>'
    + '    </div>'
    + '    <div class="pv-actions-top">'
    + '      <button class="pv-btn pv-btn-ghost" onclick="previsitReload()" title="重新生成">'
    + '        <i data-lucide="refresh-cw"></i> 重新生成'
    + '      </button>'
    + '      <button class="pv-btn pv-btn-ghost" onclick="previsitDownload(\'patient\')" title="患者版：白話摘要 + 想問醫師的三件事，給自己帶進診間念給醫師聽">'
    + '        <i data-lucide="file-down"></i> 患者版 PDF'
    + '      </button>'
    + '      <button class="pv-btn pv-btn-ghost" onclick="previsitDownload(\'doctor\')" title="醫師版：專業臨床摘要 + 追蹤建議 + 風險提醒，可寄給醫師提前閱讀">'
    + '        <i data-lucide="stethoscope"></i> 醫師版 PDF'
    + '      </button>'
    + '      <button class="pv-btn pv-btn-primary" onclick="previsitCopy()" title="複製為純文字帶去診間">'
    + '        <i data-lucide="clipboard-copy"></i> 複製給醫師'
    + '      </button>'
    + '    </div>'
    + '  </header>'
    + ''
    + '  <section class="pv-section pv-timeline-section">'
    + '    <h3 class="pv-section-title"><i data-lucide="route"></i> 本週重點碎片</h3>'
    + '    <div id="pv-timeline" class="pv-timeline">'
    + '      <p class="pv-loading"><i data-lucide="loader" class="pv-spin"></i> MD.Piece 整理中…</p>'
    + '    </div>'
    + '    <p class="pv-disclaimer"><i data-lucide="info"></i> 以下為你自填紀錄，僅供與醫師討論用，並非診斷依據。</p>'
    + '  </section>'
    + ''
    + '  <section class="pv-section pv-checklist">'
    + '    <h3 class="pv-section-title"><i data-lucide="list-checks"></i> 這次最該問醫師的三件事</h3>'
    + '    <ol id="pv-checklist-list" class="pv-checklist-list">'
    + '      <li class="pv-loading"><i data-lucide="loader" class="pv-spin"></i> MD.Piece 整理中…</li>'
    + '    </ol>'
    + '    <p class="pv-source" id="pv-checklist-source"></p>'
    + '  </section>'
    + ''
    + '  <section class="pv-section pv-report">'
    + '    <h3 class="pv-section-title"><i data-lucide="file-text"></i> ' + _pvDays + ' 天健康摘要</h3>'
    + '    <div class="pv-stats" id="pv-stats"></div>'
    + '    <div id="pv-report-body" class="pv-report-body">'
    + '      <p class="pv-loading"><i data-lucide="loader" class="pv-spin"></i> MD.Piece 撰寫中…</p>'
    + '    </div>'
    + '    <p class="pv-source" id="pv-report-source"></p>'
    + '  </section>'
    + ''
    + '  <p class="pv-disclaimer"><i data-lucide="info"></i> 本報告由 MD.Piece 整理你輸入的紀錄，僅供與醫師溝通參考，不取代醫師診斷。</p>'
    + '</section>';
}

// ─── 診前報告 (Pre-consultation Report) ──────────────────────

var _previsitData = { checklist: null, report: null };

function loadPrevisitPage() {
  if (typeof lucide !== 'undefined') lucide.createIcons();
  var pid = (typeof getStablePatientId === 'function') ? getStablePatientId() : null;
  if (!pid) return;

  _previsitData = { checklist: null, report: null };

  // 載入 Timeline（本地症狀 + 雲端情緒，合併時序）
  refreshPvTimeline(pid);

  fetch(API + '/reports/' + encodeURIComponent(pid) + '/checklist')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      _previsitData.checklist = data;
      previsitRenderChecklist(data);
    })
    .catch(function() {
      previsitRenderChecklistError();
    });

  var days = (typeof getReportDays === 'function') ? getReportDays() : 30;
  fetch(API + '/reports/' + encodeURIComponent(pid) + '/monthly?days=' + days)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      _previsitData.report = data;
      previsitRenderReport(data);
    })
    .catch(function() {
      previsitRenderReportError();
    });
}

// 合併本地症狀 + 雲端情緒 → 編年事件列。
// 取最近 14 天、排序時間倒序、最多 6 筆，避免讓 previsit 頁面太長。
async function refreshPvTimeline(pid) {
  var el = document.getElementById('pv-timeline');
  if (!el) return;
  var events = [];
  var now = Date.now();
  var cutoff = now - 14 * 86400000;

  // 1. 本地症狀
  try {
    var syms = (typeof getSymptomEntries === 'function') ? getSymptomEntries() : [];
    syms.forEach(function(e) {
      var t = new Date(e.recordedAt).getTime();
      if (!t || t < cutoff) return;
      var cat = (typeof findSymptomCat === 'function') ? findSymptomCat(e.categoryId) : null;
      var catName = cat ? (cat.zh || cat.name || cat.id) : (e.categoryId || '症狀');
      var intensity = e.intensity ? (' · ' + e.intensity + '/10') : '';
      events.push({
        when: t,
        type: 'symptom',
        title: catName + intensity,
        desc: (e.notes || e.note || e.description || '').slice(0, 80) || '— 無附註',
        icon: 'scan-search',
      });
    });
  } catch (e) {}

  // 2. 雲端情緒（每日聚合）
  try {
    var em = await fetch(API + '/emotions/daily?patient_id=' + pid + '&days=14').then(function(r){return r.json();});
    (em.daily || []).forEach(function(d) {
      if (!d || !d.date) return;
      var t = new Date(d.date + 'T12:00:00').getTime();
      if (t < cutoff) return;
      var pct = (typeof _moodPercent === 'function') ? _moodPercent(d.average_score) : Math.round(d.average_score * 20);
      events.push({
        when: t,
        type: 'mood',
        title: '情緒電力 · ' + pct + '%',
        desc: '當日紀錄 ' + (d.count || 1) + ' 次' + (d.note ? '：' + String(d.note).slice(0, 50) : ''),
        icon: 'battery-charging',
      });
    });
  } catch (e) {}

  // 3. 服藥（取最近一筆當代表，不要把每次打卡都列出來 — 太雜）
  //    只統計「實際吃了」的（taken !== false），跳過 / 沒吃不算在 N 次內，
  //    否則回診報告會把「只是漏掉」的日子當成「完成 N 次」呈現
  try {
    var ml = await fetch(API + '/medications/logs?patient_id=' + pid + '&days=14').then(function(r){return r.json();});
    var byDay = {};
    (ml.logs || []).forEach(function(l) {
      if (!l || !l.taken_at) return;
      if (l.taken === false) return;
      var dayKey = String(l.taken_at).slice(0, 10);
      byDay[dayKey] = (byDay[dayKey] || 0) + 1;
    });
    Object.keys(byDay).forEach(function(day) {
      var t = new Date(day + 'T08:00:00').getTime();
      if (t < cutoff) return;
      events.push({
        when: t,
        type: 'med',
        title: '服藥紀錄 · ' + byDay[day] + ' 次',
        desc: '當日依時段完成的打卡',
        icon: 'pill',
      });
    });
  } catch (e) {}

  events.sort(function(a, b) { return b.when - a.when; });
  events = events.slice(0, 8);

  if (!events.length) {
    el.innerHTML = '<p class="pv-empty">最近 14 天還沒有紀錄；先去症狀／藥物／情緒頁打個卡，這裡就會自動編年呈現。</p>';
    return;
  }

  el.innerHTML = events.map(function(e) {
    var d = new Date(e.when);
    var pretty = (d.getMonth() + 1) + '/' + d.getDate();
    var hh = String(d.getHours()).padStart(2, '0');
    var mm = String(d.getMinutes()).padStart(2, '0');
    var wd = ['日','一','二','三','四','五','六'][d.getDay()];
    return ''
      + '<article class="pv-tl-card" data-type="' + e.type + '">'
      +   '<div class="pv-tl-dot"></div>'
      +   '<div class="pv-tl-body">'
      +     '<div class="pv-tl-time">' + pretty + '（' + wd + '）' + hh + ':' + mm + '</div>'
      +     '<div class="pv-tl-title"><i data-lucide="' + e.icon + '" style="width:14px;height:14px"></i> ' + escapeHtml(e.title) + '</div>'
      +     '<div class="pv-tl-desc">' + escapeHtml(e.desc) + '</div>'
      +   '</div>'
      + '</article>';
  }).join('');
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function previsitRenderChecklist(data) {
  var listEl = document.getElementById('pv-checklist-list');
  var srcEl = document.getElementById('pv-checklist-source');
  if (!listEl) return;
  var items = (data && Array.isArray(data.checklist)) ? data.checklist : [];
  if (!items.length) {
    listEl.innerHTML = '<li class="pv-empty">目前沒有足夠的紀錄產生提問清單，先到症狀／情緒／用藥頁面留下紀錄吧。</li>';
  } else {
    listEl.innerHTML = items.map(function(text, i) {
      return '<li class="pv-check-item">'
        + '<span class="pv-check-num">' + (i + 1) + '</span>'
        + '<span class="pv-check-text">' + escapeHtml(text) + '</span>'
        + '</li>';
    }).join('');
  }
  if (srcEl) srcEl.textContent = previsitSourceLabel(data);
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function previsitRenderChecklistError() {
  var listEl = document.getElementById('pv-checklist-list');
  if (!listEl) return;
  listEl.innerHTML = '<li class="pv-error"><i data-lucide="alert-triangle"></i> 無法連線後端，請稍後再試。</li>';
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function previsitRenderReport(data) {
  var bodyEl = document.getElementById('pv-report-body');
  var statsEl = document.getElementById('pv-stats');
  var srcEl = document.getElementById('pv-report-source');
  if (!bodyEl) return;

  var raw = (data && data.raw_data) || {};
  if (statsEl) {
    statsEl.innerHTML = ''
      + previsitStatCard('scan-search', '症狀', raw.symptom_count, '筆')
      + previsitStatCard('smile', '情緒', raw.emotion_count, '次')
      + previsitStatCard('pill', '用藥', raw.medication_count, '種')
      + previsitStatCard('stethoscope', '就診', raw.visit_count, '次');
  }

  var report = (data && data.report) || '';
  if (!report) {
    bodyEl.innerHTML = '<p class="pv-empty">尚無報告內容。</p>';
  } else {
    bodyEl.innerHTML = markdownToHtml(report);
  }

  if (srcEl) srcEl.textContent = previsitSourceLabel(data);
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function previsitRenderReportError() {
  var bodyEl = document.getElementById('pv-report-body');
  if (!bodyEl) return;
  bodyEl.innerHTML = '<p class="pv-error"><i data-lucide="alert-triangle"></i> 無法連線後端，請稍後再試。</p>';
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function previsitStatCard(icon, label, value, unit) {
  var n = (value === undefined || value === null) ? 0 : value;
  return '<div class="pv-stat">'
    + '<span class="pv-stat-icon"><i data-lucide="' + icon + '"></i></span>'
    + '<div class="pv-stat-body">'
    +   '<div class="pv-stat-num">' + n + ' <small>' + unit + '</small></div>'
    +   '<div class="pv-stat-label">' + label + '</div>'
    + '</div>'
    + '</div>';
}

function previsitSourceLabel(data) {
  if (!data) return '';
  var src = data.source || '';
  var when = data.generated_at ? new Date(data.generated_at).toLocaleString() : '';
  var srcLabel = src === 'ai' ? 'MD.Piece 生成'
    : src === 'default' ? '預設提示（紀錄不足）'
    : src === 'no_data' ? '紀錄不足'
    : src;
  return when ? (srcLabel + ' · ' + when) : srcLabel;
}

function previsitReload() {
  var listEl = document.getElementById('pv-checklist-list');
  var bodyEl = document.getElementById('pv-report-body');
  if (listEl) listEl.innerHTML = '<li class="pv-loading"><i data-lucide="loader" class="pv-spin"></i> MD.Piece 整理中…</li>';
  if (bodyEl) bodyEl.innerHTML = '<p class="pv-loading"><i data-lucide="loader" class="pv-spin"></i> MD.Piece 撰寫中…</p>';
  if (typeof lucide !== 'undefined') lucide.createIcons();
  loadPrevisitPage();
}

function previsitCopy() {
  var d = _previsitData || {};
  var days = (d.report && d.report.days) || ((typeof getReportDays === 'function') ? getReportDays() : 30);
  var lines = [];
  lines.push('【MD.Piece 診前報告】');
  lines.push('產出時間：' + new Date().toLocaleString());
  lines.push('');
  lines.push('▍這次想問醫師的三件事');
  var items = d.checklist && Array.isArray(d.checklist.checklist) ? d.checklist.checklist : [];
  if (items.length) {
    items.forEach(function(t, i) { lines.push((i + 1) + '. ' + t); });
  } else {
    lines.push('（尚無資料）');
  }
  lines.push('');
  lines.push('▍' + days + ' 天健康摘要');
  if (d.report && d.report.raw_data) {
    var r = d.report.raw_data;
    lines.push('症狀 ' + (r.symptom_count || 0) + ' 筆 · 情緒 ' + (r.emotion_count || 0) + ' 次 · 用藥 ' + (r.medication_count || 0) + ' 種 · 就診 ' + (r.visit_count || 0) + ' 次');
    lines.push('');
  }
  lines.push((d.report && d.report.report) || '（尚無資料）');

  var text = lines.join('\n');
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function() {
      if (typeof showToast === 'function') showToast('已複製，貼到任何地方都可以', 'success');
    }, function() {
      previsitFallbackCopy(text);
    });
  } else {
    previsitFallbackCopy(text);
  }
}

function previsitFallbackCopy(text) {
  var ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); } catch (e) {}
  document.body.removeChild(ta);
  if (typeof showToast === 'function') showToast('已複製', 'success');
}

// 固定免責聲明（兩版 PDF 結尾都印這段，不交給 LLM 生成）
var PREVISIT_DISCLAIMER_HTML = ''
  + '<p><strong>⚠ 本報告內容為患者自行記錄之主觀紀錄整理</strong>，由 MD.Piece AI 彙整患者於應用程式中自填的症狀、情緒、用藥、飲食、就診等紀錄產生，<strong>未經臨床檢查或醫療專業驗證</strong>。</p>'
  + '<p>本報告僅供問診溝通參考，<strong>不構成醫療診斷、治療建議或處方依據</strong>。資料可能存在主觀偏差、記憶誤差或記錄遺漏，最終臨床判斷請以主治醫師親自評估為準。</p>';

// 下載診前報告 PDF：
//   audience='patient' → 患者版（白話摘要 + 三件事，自己念給醫師聽）
//   audience='doctor'  → 醫師版（專業臨床摘要 + 追蹤建議 + 風險提醒）
// 期間（days / period_label）由 backend 依「上次回診」自動推算。
function previsitDownload(audience) {
  var pid = (typeof getStablePatientId === 'function') ? getStablePatientId() : null;
  if (!pid) {
    if (typeof showToast === 'function') showToast('找不到使用者，請先登入', 'warning');
    return;
  }
  if (typeof showToast === 'function') showToast('MD.Piece 撰寫中，請稍候…', 'info');

  if (audience === 'doctor') {
    fetch(API + '/reports/' + encodeURIComponent(pid) + '/monthly')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var report = (data && data.report) || '（暫無報告）';
        var counts = (data && data.raw_data) || {};
        var periodLabel = (data && data.period_label) || '近 30 天';
        var html = previsitBuildDoctorHTML(report, counts, periodLabel);
        previsitOpenPrint(html);
      })
      .catch(function() {
        if (typeof showToast === 'function') showToast('產生醫師版報告失敗，請稍後再試', 'error');
      });
    return;
  }

  // patient 版（預設）
  fetch(API + '/reports/' + encodeURIComponent(pid) + '/patient-summary')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var summary = (data && data.summary) || '（暫無摘要）';
      var counts = (data && data.raw_data) || {};
      var periodLabel = (data && data.period_label) || '近 30 天';
      var checklist = (_previsitData && _previsitData.checklist && _previsitData.checklist.checklist) || [];
      var html = previsitBuildPatientHTML(summary, counts, checklist, periodLabel);
      previsitOpenPrint(html);
    })
    .catch(function() {
      if (typeof showToast === 'function') showToast('產生患者版報告失敗，請稍後再試', 'error');
    });
}

// 共用列印樣式（兩版共用）
var _PV_PDF_STYLE = ''
  + '  @page { size: A4; margin: 18mm 16mm; }'
  + '  body { font-family: "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif; color: #222; line-height: 1.75; font-size: 14px; }'
  + '  h1 { font-size: 22px; margin: 0 0 4px; }'
  + '  .meta { color: #666; font-size: 12px; margin-bottom: 18px; }'
  + '  h2 { font-size: 15px; margin: 22px 0 8px; padding-bottom: 4px; border-bottom: 1px solid #ddd; color: #2a5d8f; }'
  + '  h3 { font-size: 14px; margin: 16px 0 6px; color: #2a5d8f; }'
  + '  p { margin: 0 0 10px; }'
  + '  ul, ol { padding-left: 22px; margin: 0 0 10px; }'
  + '  ul li, ol li { margin-bottom: 6px; }'
  + '  table.stats { width: 100%; border-collapse: collapse; margin: 6px 0 4px; }'
  + '  table.stats td { width: 25%; text-align: center; padding: 8px 4px; border: 1px solid #e2e2e2; background: #f7f9fc; }'
  + '  table.stats td strong { display: block; font-size: 18px; color: #2a5d8f; }'
  + '  table.stats td span { font-size: 11px; color: #666; }'
  + '  .disclaimer { margin-top: 28px; padding: 12px 14px; border-top: 2px solid #d9d9d9; background: #fafafa; font-size: 11.5px; color: #555; line-height: 1.6; }'
  + '  .disclaimer p { margin: 0 0 6px; }'
  + '  .disclaimer p:last-child { margin: 0; }';

function previsitBuildPatientHTML(summary, counts, checklist, periodLabel) {
  var dateStr = new Date().toLocaleDateString('zh-TW', { year: 'numeric', month: 'long', day: 'numeric' });
  var paragraphs = String(summary).split(/\n\s*\n/).map(function(p) {
    return '<p>' + escapeHtml(p.trim()).replace(/\n/g, '<br>') + '</p>';
  }).join('');
  var checklistHtml = checklist.length
    ? '<ol>' + checklist.map(function(t) { return '<li>' + escapeHtml(t) + '</li>'; }).join('') + '</ol>'
    : '<p style="color:#888">（暫無）</p>';
  var statsHtml = ''
    + '<table class="stats"><tr>'
    +   '<td><strong>' + (counts.symptom_count || 0) + '</strong><span>症狀紀錄</span></td>'
    +   '<td><strong>' + (counts.emotion_count || 0) + '</strong><span>情緒紀錄</span></td>'
    +   '<td><strong>' + (counts.medication_count || 0) + '</strong><span>用藥</span></td>'
    +   '<td><strong>' + (counts.visit_count || 0) + '</strong><span>就診</span></td>'
    + '</tr></table>';

  return ''
    + '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
    + '<title>MD.Piece 診前報告（患者版）' + dateStr + '</title>'
    + '<style>' + _PV_PDF_STYLE + '</style></head><body>'
    + '<h1>診前報告（患者版）</h1>'
    + '<div class="meta">產出日期：' + dateStr + ' · 報告期間：' + escapeHtml(periodLabel) + '</div>'
    + '<h2>本期間紀錄概覽</h2>'
    + statsHtml
    + '<h2>給醫師的話（我整理的）</h2>'
    + paragraphs
    + '<h2>這次想請醫師確認的事</h2>'
    + checklistHtml
    + '<div class="disclaimer">' + PREVISIT_DISCLAIMER_HTML + '</div>'
    + '</body></html>';
}

function previsitBuildDoctorHTML(reportMarkdown, counts, periodLabel) {
  var dateStr = new Date().toLocaleDateString('zh-TW', { year: 'numeric', month: 'long', day: 'numeric' });
  var bodyHtml = (typeof markdownToHtml === 'function')
    ? markdownToHtml(String(reportMarkdown))
    : '<pre>' + escapeHtml(String(reportMarkdown)) + '</pre>';
  var statsHtml = ''
    + '<table class="stats"><tr>'
    +   '<td><strong>' + (counts.symptom_count || 0) + '</strong><span>症狀紀錄</span></td>'
    +   '<td><strong>' + (counts.emotion_count || 0) + '</strong><span>情緒紀錄</span></td>'
    +   '<td><strong>' + (counts.medication_count || 0) + '</strong><span>用藥</span></td>'
    +   '<td><strong>' + (counts.visit_count || 0) + '</strong><span>就診</span></td>'
    + '</tr></table>';

  return ''
    + '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
    + '<title>MD.Piece 診前報告（醫師版）' + dateStr + '</title>'
    + '<style>' + _PV_PDF_STYLE + '</style></head><body>'
    + '<h1>診前報告（醫師版）</h1>'
    + '<div class="meta">產出日期：' + dateStr + ' · 報告期間：' + escapeHtml(periodLabel) + '</div>'
    + '<h2>本期間紀錄概覽</h2>'
    + statsHtml
    + '<h2>整合摘要</h2>'
    + bodyHtml
    + '<div class="disclaimer">' + PREVISIT_DISCLAIMER_HTML + '</div>'
    + '</body></html>';
}

function previsitOpenPrint(html) {
  var w = window.open('', '_blank');
  if (!w) {
    if (typeof showToast === 'function') showToast('瀏覽器擋掉了新視窗，請允許彈出視窗', 'warning');
    return;
  }
  w.document.open();
  w.document.write(html);
  w.document.close();
  // 等資源載入再開列印對話框
  w.onload = function() {
    setTimeout(function() {
      try { w.focus(); w.print(); } catch (e) {}
    }, 250);
  };
}

function labs() {
  return `
    <div class="card labs-hero">
      <h2 style="display:flex;align-items:center;gap:8px">
        <i data-lucide="trending-up" style="width:22px;height:22px"></i> 報告數值
      </h2>
      <p style="margin-top:6px;color:var(--text-dim)">
        輸入任何檢驗項目（血液、肝腎、免疫、罕見值都可以），MD.Piece 會告訴你正常範圍、是否異常、生活建議。<strong>結果僅供參考，不取代醫師判讀。</strong>
      </p>
    </div>

    <div class="card labs-scan">
      <h3 style="display:flex;align-items:center;gap:8px;font-size:1rem;margin:0">
        <i data-lucide="camera" style="width:18px;height:18px"></i> 拍攝報告自動讀取數值
      </h3>
      <p style="margin-top:6px;color:var(--text-dim);font-size:.85rem">
        拍張檢驗報告（或從相簿選），MD.Piece 會一次抽出所有項目，列出哪些正常、哪些異常。
      </p>
      <div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:8px;align-items:center">
        <label class="primary" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:8px;cursor:pointer">
          <i data-lucide="camera" style="width:14px;height:14px"></i>
          <span>拍攝報告</span>
          <input type="file" accept="image/*" capture="environment" onchange="handleLabPhoto(this)" style="display:none" />
        </label>
        <label class="ghost" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:8px;border:1px solid var(--border);cursor:pointer">
          <i data-lucide="image" style="width:14px;height:14px"></i>
          <span>從相簿選</span>
          <input type="file" accept="image/*" onchange="handleLabPhoto(this)" style="display:none" />
        </label>
        <span id="lab-scan-hint" style="font-size:.78rem;color:var(--text-dim)"></span>
      </div>
      <div id="lab-scan-preview" style="margin-top:10px"></div>
      <div id="lab-scan-result" style="margin-top:10px"></div>
    </div>

    <div class="card labs-form">
      <div class="labs-form-row">
        <label class="labs-field labs-field-wide">
          <span>檢驗項目</span>
          <input type="text" id="lab-name" placeholder="例：血紅素、ANA、IgE、CRP、總膽固醇" />
        </label>
      </div>
      <div class="labs-form-row">
        <label class="labs-field">
          <span>數值</span>
          <input type="text" id="lab-value" placeholder="例：12.3 / 陽性 / >200" />
        </label>
        <label class="labs-field">
          <span>單位（選填）</span>
          <input type="text" id="lab-unit" list="lab-unit-options" placeholder="點選或輸入" />
          <datalist id="lab-unit-options">
            <option value="g/dL"></option>
            <option value="mg/dL"></option>
            <option value="mmol/L"></option>
            <option value="μmol/L"></option>
            <option value="ng/mL"></option>
            <option value="pg/mL"></option>
            <option value="μg/dL"></option>
            <option value="IU/mL"></option>
            <option value="U/L"></option>
            <option value="mIU/L"></option>
            <option value="mEq/L"></option>
            <option value="%"></option>
            <option value="/μL"></option>
            <option value="10^3/μL"></option>
            <option value="10^4/μL"></option>
            <option value="10^6/μL"></option>
            <option value="mm/hr"></option>
            <option value="mmHg"></option>
            <option value="bpm"></option>
            <option value="陰性"></option>
            <option value="陽性"></option>
            <option value="titer (例：1:80)"></option>
          </datalist>
        </label>
      </div>
      <div class="labs-form-row">
        <label class="labs-field labs-field-small">
          <span>年齡</span>
          <input type="number" id="lab-age" min="0" max="120" placeholder="28" />
        </label>
        <label class="labs-field labs-field-small">
          <span>性別</span>
          <select id="lab-sex">
            <option value="">不指定</option>
            <option value="female">女</option>
            <option value="male">男</option>
            <option value="other">其他</option>
          </select>
        </label>
        <button class="primary labs-submit" onclick="labsCheck()">
          <i data-lucide="search" style="width:14px;height:14px;vertical-align:middle"></i> 查詢
        </button>
      </div>
    </div>

    <div id="lab-result" class="card labs-result" style="display:none"></div>

    <div class="card labs-history">
      <div class="labs-history-head">
        <h3 style="font-size:1rem;display:flex;align-items:center;gap:6px">
          <i data-lucide="history" style="width:16px;height:16px"></i> 查詢紀錄
        </h3>
        <button class="ghost" onclick="labsClearHistory()" title="清除紀錄（僅存於此裝置）">
          <i data-lucide="trash-2" style="width:14px;height:14px"></i> 清除
        </button>
      </div>
      <div id="labs-history-list" class="labs-history-list"></div>
    </div>
  `;
}
const account  = () => accountPage();
// pieces() 為實作頁面（位於下方）— 將上次回診後的紀錄做統整保留。

// 頁面在 terminal pane 中顯示的檔名（用於 #app 的 data-page）
const pageSlugForTerminal = {
  home: 'home', symptoms: 'symptoms', medications: 'medications',
  vitals: 'vitals', memo: 'memo', previsit: 'previsit',
  education: 'education', story: 'daily-story', labs: 'lab-values',
  pieces: 'your-pieces', chat: 'med-chat', account: 'account',
  settings: 'settings', diet: 'diet',
  records: 'records', doctors: 'doctors'
};

// Track the current page so we can re-render on language switch
var _currentPageKey = null;

function showPage(page) {
  _currentPageKey = page;
  const app = document.getElementById("app");
  app.setAttribute('data-page', pageSlugForTerminal[page] || page);
  const pages = {
    home, symptoms, symptomsAnalyze, doctors, records, medications, education,
    vitals, emotions, memo, previsit, story, labs, pieces, chat, account, settings, diet,
    drugSearch, diseaseSearch, reminders: reminders
  };
  // Page transition
  app.style.opacity = '0';
  app.style.transform = 'translateY(12px)';
  setTimeout(() => {
    app.innerHTML = pages[page]?.() || "";
    // 頁面載入後的初始化
    if (page === "home") loadHomePage();
    if (page === "doctors") loadDoctors();
    if (page === "records") loadRecordsPage();
    if (page === "education") loadEducationPage();
    if (page === "story") loadStoryPage();
    if (page === "medications") loadMedicationsPage();
    if (page === "memo") loadMemoPage();
    if (page === "labs") loadLabsPage();
    if (page === "pieces") loadPiecesPage();
    if (page === "chat") loadChatPage();
    if (page === "previsit") loadPrevisitPage();
    if (page === "emotions") loadEmotionsPage();
    if (page === "diet") loadDietPage();
    if (page === "symptomsAnalyze") loadSymptomAnalysisHistory();
    if (page === "account") loadAccountPage();
    if (page === "settings") loadSettingsPage();
    if (page === "drugSearch") loadDrugSearchPage();
    if (page === "diseaseSearch") loadDiseaseSearchPage();
    if (page === "reminders") loadRemindersPage();
    // Render Lucide icons
    if (typeof lucide !== 'undefined') lucide.createIcons();
    // Fade in
    requestAnimationFrame(() => {
      app.style.transition = 'opacity .3s ease, transform .3s ease';
      app.style.opacity = '1';
      app.style.transform = 'translateY(0)';
    });
  }, 150);
}

// 語言切換時，重新渲染當前頁面（讓字典中文/英文切換立即生效）
window.addEventListener('mdpiece-lang-change', function () {
  if (_currentPageKey) showPage(_currentPageKey);
});

// ─── 登入 / 註冊 ───────────────────────────────────────────

let _authRole = 'patient';
let _loginRole = 'patient';
let _regAvatarDataUrl = '';

function showIdCardRegister() {
  const overlay = document.getElementById('register-overlay');
  overlay.style.display = 'flex';
  switchAuthTab('login');
  // 預填上次登入過的帳號（若有）
  const lastUsername = localStorage.getItem('mdpiece_last_username') || '';
  const loginInput = document.getElementById('login-username');
  if (loginInput && lastUsername) loginInput.value = lastUsername;
  // 綁定頭像上傳一次
  const fileInput = document.getElementById('reg-avatar-file');
  if (fileInput && !fileInput.dataset.bound) {
    fileInput.dataset.bound = '1';
    fileInput.addEventListener('change', onRegAvatarPicked);
  }
  requestAnimationFrame(() => overlay.classList.add('show'));
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function switchAuthTab(tab) {
  const isLogin = tab === 'login';
  document.getElementById('auth-tab-login').classList.toggle('active', isLogin);
  document.getElementById('auth-tab-register').classList.toggle('active', !isLogin);
  document.getElementById('auth-panel-login').classList.toggle('active', isLogin);
  document.getElementById('auth-panel-register').classList.toggle('active', !isLogin);
  document.getElementById('login-error').hidden = true;
  document.getElementById('register-error').hidden = true;
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function onRegAvatarPicked(e) {
  const file = e.target.files && e.target.files[0];
  if (!file) return;
  shrinkImageToDataUrl(file, 320, 0.85).then(dataUrl => {
    _regAvatarDataUrl = dataUrl;
    const img = document.getElementById('reg-avatar-img');
    const ph = document.getElementById('reg-avatar-placeholder');
    const clr = document.getElementById('reg-avatar-clear');
    img.src = dataUrl;
    img.hidden = false;
    if (ph) ph.hidden = true;
    if (clr) clr.hidden = false;
  }).catch(() => showAuthError('register', '圖片讀取失敗'));
}

function clearRegAvatar() {
  _regAvatarDataUrl = '';
  const img = document.getElementById('reg-avatar-img');
  const ph = document.getElementById('reg-avatar-placeholder');
  const clr = document.getElementById('reg-avatar-clear');
  const file = document.getElementById('reg-avatar-file');
  if (img) { img.hidden = true; img.src = ''; }
  if (ph) ph.hidden = false;
  if (clr) clr.hidden = true;
  if (file) file.value = '';
}

function shrinkImageToDataUrl(file, maxSize, quality) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const scale = Math.min(1, maxSize / Math.max(img.width, img.height));
        const w = Math.round(img.width * scale);
        const h = Math.round(img.height * scale);
        const canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
        resolve(canvas.toDataURL('image/jpeg', quality || 0.85));
      };
      img.onerror = reject;
      img.src = reader.result;
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function showAuthError(panel, msg) {
  const el = document.getElementById(`${panel}-error`);
  if (!el) return;
  el.textContent = msg;
  el.hidden = false;
}

async function submitLogin() {
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  if (!username || !password) return;
  const btn = document.getElementById('login-submit');
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader"></i> 登入中…';
  if (typeof lucide !== 'undefined') lucide.createIcons();
  document.getElementById('login-error').hidden = true;
  try {
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '登入失敗');
    }
    const user = await res.json();
    finishAuth(user);
  } catch (e) {
    showAuthError('login', e.message || '登入失敗，請稍後再試');
    btn.disabled = false;
    btn.innerHTML = original;
    if (typeof lucide !== 'undefined') lucide.createIcons();
  }
}

async function submitRegister() {
  const nickname = document.getElementById('reg-nickname').value.trim();
  const username = document.getElementById('reg-username').value.trim();
  const password = document.getElementById('reg-password').value;
  const password2 = document.getElementById('reg-password2').value;

  if (password !== password2) {
    showAuthError('register', '兩次輸入的密碼不一致');
    return;
  }
  if (password.length < 6) {
    showAuthError('register', '密碼至少 6 個字元');
    return;
  }

  const btn = document.getElementById('register-submit');
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader"></i> 建立中…';
  if (typeof lucide !== 'undefined') lucide.createIcons();
  document.getElementById('register-error').hidden = true;

  const payload = {
    username, password, nickname,
    role: 'patient',
    avatar_url: _regAvatarDataUrl || null,
  };

  try {
    const res = await fetch(`${API}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '註冊失敗');
    }
    const user = await res.json();
    finishAuth(user);
  } catch (e) {
    showAuthError('register', e.message || '註冊失敗，請稍後再試');
    btn.disabled = false;
    btn.innerHTML = original;
    if (typeof lucide !== 'undefined') lucide.createIcons();
  }
}

function finishAuth(user) {
  if (user.username) {
    try { localStorage.setItem('mdpiece_last_username', user.username); } catch {}
  }
  setCurrentUser(user);
  const overlay = document.getElementById('register-overlay');
  overlay.classList.remove('show');
  setTimeout(() => {
    overlay.style.display = 'none';
    document.getElementById('app-wrapper').classList.add('show');
    showPage('home');
    if (typeof lucide !== 'undefined') lucide.createIcons();
    if (typeof maybeShowOnboarding === 'function') maybeShowOnboarding();
  }, 250);
}

// 切換帳號 — 不二次確認，直接回到登入頁
function switchAccount() {
  try { localStorage.removeItem('mdpiece_user'); } catch {}
  try { localStorage.removeItem('mdpiece_demo_pid'); } catch {}
  window.location.reload();
}

// ─── 帳號設定頁面 ──────────────────────────────────────────

function accountPage() {
  const u = getCurrentUser() || {};
  const roleLabel = u.role === 'doctor' ? '醫師' : '患者';
  const roleIcon = u.role === 'doctor' ? 'stethoscope' : 'heart-pulse';
  const avatarHtml = u.avatar_url
    ? `<img src="${u.avatar_url}" alt="" class="acct-avatar-img" />`
    : `<img src="icons/xiaohe.jpg" alt="預設頭像（小禾）" class="acct-avatar-img acct-avatar-default" />`;
  return `
    <section class="acct-wrap">
      <header class="acct-head">
        <h2><i data-lucide="user-cog"></i> 帳號設定</h2>
        <p>管理你的個人資料、頭像與密碼。</p>
      </header>

      <div class="acct-card">
        <div class="acct-profile">
          <label class="acct-avatar" id="acct-avatar" title="點擊更換頭像">
            <input type="file" id="acct-avatar-file" accept="image/*" hidden />
            ${avatarHtml}
            <span class="acct-avatar-edit"><i data-lucide="camera"></i></span>
          </label>
          <div class="acct-meta">
            <div class="acct-row"><span class="acct-key">帳號</span><span class="acct-val">${u.username || '—'}</span></div>
            <div class="acct-row"><span class="acct-key">身份</span><span class="acct-val"><i data-lucide="${roleIcon}" style="width:14px;height:14px"></i> ${roleLabel}</span></div>
            <div class="acct-row"><span class="acct-key">建立時間</span><span class="acct-val">${u.created_at ? new Date(u.created_at).toLocaleString() : '—'}</span></div>
          </div>
        </div>

        <form class="acct-form" onsubmit="event.preventDefault(); saveProfile();">
          <h3>個人資料</h3>
          <label class="acct-field">
            <span>暱稱</span>
            <input id="acct-nickname" type="text" maxlength="20" value="${(u.nickname || '').replace(/"/g, '&quot;')}" required />
          </label>
          <label class="acct-field">
            <span>頭像主色</span>
            <input id="acct-color" type="color" value="${u.avatar_color || '#5B9FE8'}" />
          </label>
          <p class="acct-msg" id="acct-profile-msg" hidden></p>
          <button class="acct-submit" type="submit"><i data-lucide="save"></i> 儲存資料</button>
        </form>

        <form class="acct-form" onsubmit="event.preventDefault(); savePassword();">
          <h3>變更密碼</h3>
          <label class="acct-field">
            <span>目前密碼</span>
            <input id="acct-pw-current" type="password" autocomplete="current-password" required />
          </label>
          <label class="acct-field">
            <span>新密碼</span>
            <input id="acct-pw-new" type="password" autocomplete="new-password" minlength="6" required />
          </label>
          <label class="acct-field">
            <span>確認新密碼</span>
            <input id="acct-pw-new2" type="password" autocomplete="new-password" minlength="6" required />
          </label>
          <p class="acct-msg" id="acct-pw-msg" hidden></p>
          <button class="acct-submit" type="submit"><i data-lucide="key-round"></i> 更新密碼</button>
        </form>

        <div class="acct-actions">
          <button class="acct-action acct-action-secondary" onclick="switchAccount()">
            <i data-lucide="users"></i> 切換帳號
          </button>
          <button class="acct-action acct-action-danger" onclick="logout()">
            <i data-lucide="log-out"></i> 登出
          </button>
        </div>
      </div>
    </section>
  `;
}

function loadAccountPage() {
  const fileInput = document.getElementById('acct-avatar-file');
  if (fileInput) fileInput.addEventListener('change', onAccountAvatarPicked);
  const colorInput = document.getElementById('acct-color');
  if (colorInput) {
    colorInput.addEventListener('input', () => {
      const fb = document.querySelector('#acct-avatar .acct-avatar-fallback');
      if (fb) {
        fb.style.background = colorInput.value + '22';
        fb.style.color = colorInput.value;
        fb.style.borderColor = colorInput.value;
      }
    });
  }
}

async function onAccountAvatarPicked(e) {
  const file = e.target.files && e.target.files[0];
  if (!file) return;
  const u = getCurrentUser();
  if (!u) return;
  try {
    const dataUrl = await shrinkImageToDataUrl(file, 320, 0.85);
    const res = await fetch(`${API}/auth/user/${u.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ avatar_url: dataUrl })
    });
    if (!res.ok) throw new Error('更新頭像失敗');
    const updated = await res.json();
    setCurrentUser({ ...u, ...updated });
    showPage('account');
  } catch (err) {
    showAccountMsg('acct-profile-msg', err.message || '更新頭像失敗', true);
  }
}

async function saveProfile() {
  const u = getCurrentUser();
  if (!u) return;
  const nickname = document.getElementById('acct-nickname').value.trim();
  const avatar_color = document.getElementById('acct-color').value;
  if (!nickname) return;
  try {
    const res = await fetch(`${API}/auth/user/${u.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nickname, avatar_color })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '更新失敗');
    }
    const updated = await res.json();
    setCurrentUser({ ...u, ...updated });
    showAccountMsg('acct-profile-msg', '已儲存', false);
  } catch (e) {
    showAccountMsg('acct-profile-msg', e.message, true);
  }
}

async function savePassword() {
  const u = getCurrentUser();
  if (!u) return;
  const cur = document.getElementById('acct-pw-current').value;
  const next = document.getElementById('acct-pw-new').value;
  const next2 = document.getElementById('acct-pw-new2').value;
  if (next !== next2) {
    showAccountMsg('acct-pw-msg', '兩次輸入的新密碼不一致', true);
    return;
  }
  if (next.length < 6) {
    showAccountMsg('acct-pw-msg', '新密碼至少 6 個字元', true);
    return;
  }
  try {
    const res = await fetch(`${API}/auth/user/${u.id}/password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: cur, new_password: next })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '更新密碼失敗');
    }
    document.getElementById('acct-pw-current').value = '';
    document.getElementById('acct-pw-new').value = '';
    document.getElementById('acct-pw-new2').value = '';
    showAccountMsg('acct-pw-msg', '密碼已更新', false);
  } catch (e) {
    showAccountMsg('acct-pw-msg', e.message, true);
  }
}

function showAccountMsg(id, msg, isError) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.hidden = false;
  el.classList.toggle('acct-msg-error', !!isError);
  el.classList.toggle('acct-msg-ok', !isError);
}

// ─── 首頁 ──────────────────────────────────────────────────

// i18n helpers (fallback to identity if i18n module hasn't loaded)
function _T(k) { return (window.MDPiece_i18n && window.MDPiece_i18n.t) ? window.MDPiece_i18n.t(k) : k; }
function _Tf(k, vars) { return (window.MDPiece_i18n && window.MDPiece_i18n.tf) ? window.MDPiece_i18n.tf(k, vars) : k; }

function getGreetingMessage() {
  var i = Math.floor(Math.random() * 6);
  return _T('home.calm.' + i);
}

function getHealthTip() {
  var i = Math.floor(Math.random() * 8);
  return _T('home.tip.' + i);
}

// === 下次回診（patient-set；存 localStorage，per-user）=========================
function _nextVisitKey() {
  var u = (typeof getCurrentUser === 'function') ? (getCurrentUser() || {}) : {};
  var pid = u.id_number || u.username || 'guest';
  return 'mdpiece_next_visit_' + pid;
}
function loadNextVisit() {
  try { return localStorage.getItem(_nextVisitKey()) || ''; } catch (e) { return ''; }
}
function saveNextVisit(iso) {
  try {
    if (iso) localStorage.setItem(_nextVisitKey(), iso);
    else     localStorage.removeItem(_nextVisitKey());
  } catch (e) {}
}
function _daysBetween(isoDate) {
  // 以「日」為單位差距，今日 0
  var t = new Date(isoDate + 'T00:00:00');
  var n = new Date();
  n.setHours(0,0,0,0);
  return Math.round((t - n) / 86400000);
}
function renderNextVisitChip() {
  var iso = loadNextVisit();
  if (!iso) {
    return ''
      + '<button type="button" class="home-visit-chip home-visit-chip-empty" '
      +   'onclick="openNextVisitEditor()">'
      +   '<i data-lucide="calendar-plus" style="width:14px;height:14px"></i>'
      +   '<span>' + _T('home.visit.set') + '</span>'
      + '</button>'
      + '<input type="date" id="home-visit-input" class="home-visit-input" '
      +   'onchange="onNextVisitChange(this.value)" hidden />';
  }
  var d = _daysBetween(iso);
  var label;
  var cls = 'home-visit-chip';
  if (d > 0)       { label = _Tf('home.visit.daysLeft', { n: d }); }
  else if (d === 0){ label = _T('home.visit.today'); cls += ' home-visit-chip-today'; }
  else             { label = _Tf('home.visit.daysAgo', { n: (-d) }); cls += ' home-visit-chip-past'; }
  var pretty = iso.replace(/-/g, '/').slice(5); // MM/DD
  var doneBtn = (d === 0 || d < 0)
    ? '<button type="button" class="home-visit-done" onclick="markVisitCompleted()" title="' + _T('home.visit.doneTitle') + '">'
      +   '<i data-lucide="check-circle-2" style="width:14px;height:14px"></i>'
      +   '<span>' + _T('home.visit.done') + '</span>'
      + '</button>'
    : '<button type="button" class="home-visit-early" onclick="markVisitEarly()" title="' + _T('home.visit.earlyTitle') + '">'
      +   '<i data-lucide="calendar-x-2" style="width:14px;height:14px"></i>'
      +   '<span>' + _T('home.visit.early') + '</span>'
      + '</button>';
  return ''
    + '<button type="button" class="' + cls + '" onclick="openNextVisitEditor()" title="' + _T('home.visit.editTitle') + '">'
    +   '<i data-lucide="calendar-check-2" style="width:14px;height:14px"></i>'
    +   '<span>' + _T('home.visit.label') + ' ' + pretty + '</span>'
    +   '<span class="home-visit-countdown">' + label + '</span>'
    + '</button>'
    + doneBtn
    + '<button type="button" class="home-visit-clear" onclick="clearNextVisit()" title="' + _T('home.visit.clearTitle') + '">'
    +   '<i data-lucide="x" style="width:12px;height:12px"></i>'
    + '</button>'
    + '<input type="date" id="home-visit-input" class="home-visit-input" '
    +   'value="' + iso + '" onchange="onNextVisitChange(this.value)" hidden />';
}
function openNextVisitEditor() {
  var inp = document.getElementById('home-visit-input');
  if (!inp) return;
  inp.hidden = false;
  // 開啟原生日期 picker（Chrome 支援；其他瀏覽器至少會 focus）
  try { inp.showPicker && inp.showPicker(); } catch (e) {}
  inp.focus();
}
function onNextVisitChange(val) {
  if (!val) return;
  saveNextVisit(val);
  refreshNextVisitChip();
}
function clearNextVisit() {
  saveNextVisit('');
  refreshNextVisitChip();
}
function refreshNextVisitChip() {
  var row = document.getElementById('home-visit-row');
  if (!row) return;
  row.innerHTML = renderNextVisitChip();
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

// === 共用「如何使用這頁？」摺疊面板 =====================================
// 用法：在頁面 renderer 開頭呼叫 renderHowto('meds')
//      → 自動讀 i18n 'howto.meds.title' + 'howto.meds.s1..sN' + 'howto.meds.warn'
// 顯示為 <details> 預設摺疊；第一次造訪該頁時自動展開（localStorage 記住）
function renderHowto(key) {
  var seenKey = 'mdpiece_howto_seen_' + key;
  var seen = false;
  try { seen = localStorage.getItem(seenKey) === '1'; } catch (e) {}
  // 動態收集 s1, s2, ... 到沒下一條為止
  var steps = [];
  for (var i = 1; i <= 10; i++) {
    var t = _T('howto.' + key + '.s' + i);
    if (!t || t === ('howto.' + key + '.s' + i)) break; // i18n 拿不到就停
    steps.push(t);
  }
  if (!steps.length) return '';
  var title = _T('howto.' + key + '.title') || '如何使用這頁？';
  var warn  = _T('howto.' + key + '.warn');
  var stepsHtml = steps.map(function(s, idx) {
    return '<li class="page-howto-step">'
      + '<span class="page-howto-step-n">' + (idx + 1) + '</span>'
      + '<span class="page-howto-step-text">' + escapeHtml(s) + '</span>'
      + '</li>';
  }).join('');
  return ''
    + '<details class="page-howto" data-key="' + key + '"' + (seen ? '' : ' open') + ' ontoggle="_howtoOnToggle(this)">'
    +   '<summary class="page-howto-summary">'
    +     '<span class="page-howto-summary-icon"><i data-lucide="help-circle"></i></span>'
    +     '<span class="page-howto-summary-text">' + escapeHtml(title) + '</span>'
    +     '<span class="page-howto-summary-chev"><i data-lucide="chevron-down"></i></span>'
    +   '</summary>'
    +   '<div class="page-howto-body">'
    +     '<ol class="page-howto-steps">' + stepsHtml + '</ol>'
    +     (warn && warn !== ('howto.' + key + '.warn')
        ? '<p class="page-howto-warn"><i data-lucide="info" style="width:13px;height:13px"></i> ' + escapeHtml(warn) + '</p>'
        : '')
    +   '</div>'
    + '</details>';
}
function _howtoOnToggle(el) {
  if (el && el.open) {
    var k = el.getAttribute('data-key');
    try { localStorage.setItem('mdpiece_howto_seen_' + k, '1'); } catch (e) {}
  }
}

// === Nav 狀態 Badge ======================================================
// 在 sidebar 各 nav-item 末端顯示「今日打卡狀態」小膠囊：
//   - 已打卡：綠色 "+N"
//   - 未打卡：橘色脈動 "!"
//   - 回診倒數：橘色脈動 "DN" (N 天)
// 來源都用既有 API / localStorage，不打額外端點。
async function refreshNavBadges() {
  var pid = (typeof getStablePatientId === 'function') ? getStablePatientId() : null;
  if (!pid) return;
  var todayISO = new Date().toISOString().slice(0, 10);

  function setBadge(key, text, tone) {
    var el = document.querySelector('[data-nav-badge="' + key + '"]');
    if (!el) return;
    if (!text) { el.textContent = ''; el.removeAttribute('data-tone'); return; }
    el.textContent = text;
    el.setAttribute('data-tone', tone || 'todo');
  }

  // 症狀：今日筆數（本地）
  try {
    var syms = (typeof getSymptomEntries === 'function') ? getSymptomEntries() : [];
    var n = syms.filter(function(e) { return String(e.recordedAt || '').slice(0, 10) === todayISO; }).length;
    setBadge('symptoms', n > 0 ? ('+' + n) : '!', n > 0 ? 'done' : 'todo');
  } catch (e) {}

  // 藥物：今日 log 數
  try {
    var ml = await fetch(API + '/medications/logs?patient_id=' + pid + '&days=1').then(function(r){return r.json();}).catch(function(){return{logs:[]};});
    var nm = (ml.logs || []).filter(function(l) { return l && l.taken_at && String(l.taken_at).slice(0,10) === todayISO && l.taken !== false; }).length;
    setBadge('medications', nm > 0 ? ('+' + nm) : '!', nm > 0 ? 'done' : 'todo');
  } catch (e) {}

  // 情緒
  try {
    var em = await fetch(API + '/emotions/daily?patient_id=' + pid + '&days=1').then(function(r){return r.json();}).catch(function(){return{daily:[]};});
    var d = (em.daily || []).find(function(x) { return x.date === todayISO; });
    var nc = d ? (d.count || 0) : 0;
    setBadge('emotions', nc > 0 ? ('+' + nc) : '!', nc > 0 ? 'done' : 'todo');
  } catch (e) {}

  // 生理（本地 localStorage，由 getVitalEntries() 統一讀取）
  try {
    var vList = (typeof getVitalEntries === 'function') ? getVitalEntries() : [];
    var nv = vList.filter(function(v) {
      return v && String(v.recordedAt || v.date || '').slice(0, 10) === todayISO;
    }).length;
    setBadge('vitals', nv > 0 ? ('+' + nv) : '', nv > 0 ? 'done' : 'todo');
  } catch (e) {}

  // 回診倒數
  try {
    var iso = (typeof loadNextVisit === 'function') ? loadNextVisit() : '';
    if (iso) {
      var d2 = _daysBetween(iso);
      if (d2 >= 0 && d2 <= 7) {
        setBadge('previsit', d2 === 0 ? 'TODAY' : ('D' + d2), 'todo');
      } else {
        setBadge('previsit', '');
      }
    }
  } catch (e) {}
}

// === 今日拼圖 Digest =====================================================
// 顯示「今天打了多少卡」— 症狀 / 用藥 / 情緒 / 飲食。
// 目標 = 6 個碎片（症狀＋藥＋情緒 三大類各算 1，再加 3 個彈性 slot 反映多筆紀錄）。
function renderTodayDigestCard() {
  return ''
    + '<section class="home-digest" aria-label="今日拼圖">'
    +   '<div class="home-digest-head">'
    +     '<span class="home-digest-eyebrow">TODAY · 今日拼圖</span>'
    +     '<span class="home-digest-progress" id="home-digest-progress">— / 6 個碎片</span>'
    +   '</div>'
    +   '<div class="home-digest-bar"><div class="home-digest-bar-fill" id="home-digest-bar-fill" style="width:0%"></div></div>'
    +   '<div class="home-digest-stats">'
    +     '<div class="home-digest-stat" data-cat="symptom">'
    +       '<span class="home-digest-icon"><i data-lucide="scan-search"></i></span>'
    +       '<span class="home-digest-num" id="hd-symptom">—</span>'
    +       '<span class="home-digest-label">症狀</span>'
    +     '</div>'
    +     '<div class="home-digest-stat" data-cat="med">'
    +       '<span class="home-digest-icon"><i data-lucide="pill"></i></span>'
    +       '<span class="home-digest-num" id="hd-med">—</span>'
    +       '<span class="home-digest-label">用藥</span>'
    +     '</div>'
    +     '<div class="home-digest-stat" data-cat="mood">'
    +       '<span class="home-digest-icon"><i data-lucide="battery-charging"></i></span>'
    +       '<span class="home-digest-num" id="hd-mood">—</span>'
    +       '<span class="home-digest-label">情緒</span>'
    +     '</div>'
    +   '</div>'
    + '</section>';
}
async function refreshTodayDigest() {
  var pid = (typeof getStablePatientId === 'function') ? getStablePatientId() : null;
  if (!pid) return;
  var todayISO = new Date().toISOString().slice(0, 10);

  function _todayCountFromList(list, dateField) {
    if (!Array.isArray(list)) return 0;
    return list.filter(function(item) {
      var v = item && item[dateField];
      if (!v) return false;
      return String(v).slice(0, 10) === todayISO;
    }).length;
  }

  var symptomCount = 0, medCount = 0, moodCount = 0;

  // 症狀：本地 localStorage（submitSymptomLog 寫 mdpiece_symptoms，
  // 不是寫雲端 /symptoms — 後者目前是 stub，永遠回空陣列）
  try {
    var syms = (typeof getSymptomEntries === 'function') ? getSymptomEntries() : [];
    symptomCount = syms.filter(function(e) {
      return String(e.recordedAt || '').slice(0, 10) === todayISO;
    }).length;
  } catch (e) {}

  // 用藥 log — 只算真的吃了的（taken !== false），跳過/沒吃不計入今日 KPI
  try {
    var m = await fetch(API + '/medications/logs?patient_id=' + pid + '&days=1').then(function(r){return r.json();});
    medCount = (m.logs || []).filter(function(l) {
      return l && l.taken !== false && String(l.taken_at || '').slice(0, 10) === todayISO;
    }).length;
  } catch (e) {}

  // 情緒 daily 聚合
  try {
    var em = await fetch(API + '/emotions/daily?patient_id=' + pid + '&days=1').then(function(r){return r.json();});
    var d = (em.daily || []).find(function(x) { return x.date === todayISO; });
    moodCount = d ? (d.count || 0) : 0;
  } catch (e) {}

  // 寫入 DOM
  var setText = function(id, val) { var el = document.getElementById(id); if (el) el.textContent = val; };
  setText('hd-symptom', symptomCount);
  setText('hd-med', medCount);
  setText('hd-mood', moodCount);

  // 進度：三大類各打過至少 1 次算 1 分（上限 3），再加實際筆數封頂 3 → 共 6 分
  var hits = (symptomCount > 0 ? 1 : 0) + (medCount > 0 ? 1 : 0) + (moodCount > 0 ? 1 : 0);
  var extras = Math.min(3, (symptomCount + medCount + moodCount) - hits);
  if (extras < 0) extras = 0;
  var score = hits + extras;
  var pct = Math.min(100, Math.round((score / 6) * 100));
  setText('home-digest-progress', score + ' / 6 個碎片');
  var bar = document.getElementById('home-digest-bar-fill');
  if (bar) bar.style.width = pct + '%';
}

// === 今日待辦 ============================================================
// 「待辦」由兩部分組成：
//   1. 系統自動生成（auto）— 從現有資料推斷：回診倒數、活躍藥物、今天還沒打卡的事
//   2. 使用者手動加（user）— 存 localStorage，per-user
// 註：所有系統生成項目都附「以醫師說明為準」小字；既有 disclaimer 不動。
var TODO_STORE_VERSION = 1;
function _todoKey() {
  var u = (typeof getCurrentUser === 'function') ? (getCurrentUser() || {}) : {};
  var pid = u.id_number || u.username || 'guest';
  return 'mdpiece_todos_' + pid;
}
function _loadUserTodos() {
  try {
    var raw = localStorage.getItem(_todoKey());
    if (!raw) return [];
    var p = JSON.parse(raw);
    return Array.isArray(p.items) ? p.items : [];
  } catch (e) { return []; }
}
function _saveUserTodos(items) {
  try {
    localStorage.setItem(_todoKey(), JSON.stringify({ v: TODO_STORE_VERSION, items: items }));
  } catch (e) {}
}
function addUserTodo(title, desc) {
  title = String(title || '').trim().slice(0, 80);
  if (!title) return false;
  var items = _loadUserTodos();
  items.unshift({
    id: 'user-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6),
    title: title,
    desc: String(desc || '').trim().slice(0, 200),
    done: false,
    createdAt: Date.now(),
    source: 'user',
  });
  _saveUserTodos(items);
  return true;
}
function toggleUserTodo(id) {
  var items = _loadUserTodos();
  var i = items.findIndex(function(t) { return t.id === id; });
  if (i < 0) return;
  items[i].done = !items[i].done;
  items[i].doneAt = items[i].done ? Date.now() : null;
  _saveUserTodos(items);
}
function removeUserTodo(id) {
  _saveUserTodos(_loadUserTodos().filter(function(t) { return t.id !== id; }));
}
async function _genAutoTodos() {
  var out = [];
  var todayISO = new Date().toISOString().slice(0, 10);
  var pid = (typeof getStablePatientId === 'function') ? getStablePatientId() : null;
  if (!pid) return out;

  // 回診倒數（7 天內）
  try {
    var visit = (typeof loadNextVisit === 'function') ? loadNextVisit() : '';
    if (visit) {
      var d = _daysBetween(visit);
      if (d >= 0 && d <= 7) {
        out.push({
          id: 'auto-visit',
          source: 'auto-visit', category: 'visit',
          title: d === 0 ? '今天有回診' : '回診倒數 ' + d + ' 天',
          desc: '日期：' + visit.replace(/-/g, '/'),
          icon: 'calendar-check-2',
          link: null,
          warn: '請以醫師預約單為準',
        });
      }
    }
  } catch (e) {}

  // 活躍藥物提醒（取前 3 個）
  try {
    var r = await fetch(API + '/medications/?patient_id=' + pid).then(function(x){return x.json();});
    var meds = (r.medications || []).filter(function(m) { return m.active !== 0; });
    meds.slice(0, 3).forEach(function(m) {
      out.push({
        id: 'auto-med-' + m.id,
        source: 'auto-med', category: 'med',
        title: '今日服藥：' + (m.name || ''),
        desc: m.dosage || '',
        icon: 'pill',
        link: 'medications',
        warn: '服用方式以醫師處方為準',
      });
    });
  } catch (e) {}

  // 情緒：今天還沒打卡
  try {
    var rr = await fetch(API + '/emotions/daily?patient_id=' + pid + '&days=1').then(function(x){return x.json();});
    var daily = rr.daily || [];
    var today = daily.find(function(d) { return d.date === todayISO && d.count > 0; });
    if (!today) {
      out.push({
        id: 'auto-mood',
        source: 'auto-mood', category: 'mood',
        title: '今天還沒打卡情緒',
        desc: '一分鐘紀錄今日電量',
        icon: 'battery-charging',
        link: 'emotions',
        warn: null,
      });
    }
  } catch (e) {}

  return out;
}
function renderTodoCard() {
  return ''
    + '<section class="home-todo" aria-label="今日待辦">'
    +   '<div class="home-todo-head">'
    +     '<span class="home-todo-prefix">今日待辦</span>'
    +     '<button type="button" class="home-todo-add" onclick="openTodoComposer()" title="新增個人待辦">'
    +       '<i data-lucide="plus" style="width:14px;height:14px"></i>'
    +       '<span>新增</span>'
    +     '</button>'
    +   '</div>'
    +   '<div class="home-todo-note">'
    +     '<i data-lucide="info" style="width:12px;height:12px"></i>'
    +     '<span>本區為輔助提醒，最終以醫師說明、藥單為準</span>'
    +   '</div>'
    +   '<div id="home-todo-list" class="home-todo-list">'
    +     '<div class="home-todo-loading">// 載入中…</div>'
    +   '</div>'
    +   '<div class="home-todo-composer" id="home-todo-composer" hidden>'
    +     '<input type="text" id="home-todo-input" class="home-todo-input" maxlength="80" placeholder="想記下什麼？例：問醫師血壓藥能不能換時段">'
    +     '<button type="button" class="home-todo-submit" onclick="submitTodoComposer()">加入</button>'
    +     '<button type="button" class="home-todo-cancel" onclick="closeTodoComposer()" aria-label="取消">✕</button>'
    +   '</div>'
    + '</section>';
}
async function refreshTodoList() {
  var el = document.getElementById('home-todo-list');
  if (!el) return;
  var auto, user;
  try {
    auto = await _genAutoTodos();
  } catch (e) { auto = []; }
  user = _loadUserTodos();
  // 完成 > 24h 的個人項目自動隱藏，避免堆積
  var cutoff = Date.now() - 24 * 3600 * 1000;
  user = user.filter(function(t) { return !t.done || (t.doneAt && t.doneAt > cutoff); });

  var rows = '';
  auto.forEach(function(t) {
    rows += ''
      + '<div class="todo-item todo-auto" data-cat="' + t.category + '">'
      +   '<span class="todo-icon"><i data-lucide="' + (t.icon || 'circle') + '"></i></span>'
      +   '<div class="todo-body">'
      +     '<div class="todo-title">' + escapeHtml(t.title) + '</div>'
      +     (t.desc ? '<div class="todo-desc">' + escapeHtml(t.desc) + '</div>' : '')
      +     (t.warn ? '<div class="todo-warn"><i data-lucide="alert-triangle" style="width:11px;height:11px"></i> ' + escapeHtml(t.warn) + '</div>' : '')
      +   '</div>'
      +   (t.link
          ? '<button type="button" class="todo-go" onclick="navigateTo(\'' + t.link + '\',null)" title="前往">→</button>'
          : '<span class="todo-tag-auto">auto</span>')
      + '</div>';
  });

  if (user.length) {
    user.forEach(function(t) {
      rows += ''
        + '<div class="todo-item todo-user' + (t.done ? ' is-done' : '') + '" data-id="' + t.id + '">'
        +   '<button type="button" class="todo-check" onclick="onTodoToggle(\'' + t.id + '\')" aria-label="' + (t.done ? '取消完成' : '標記完成') + '">'
        +     (t.done ? '<i data-lucide="check-square" style="width:16px;height:16px"></i>' : '<i data-lucide="square" style="width:16px;height:16px"></i>')
        +   '</button>'
        +   '<div class="todo-body">'
        +     '<div class="todo-title">' + escapeHtml(t.title) + '</div>'
        +     (t.desc ? '<div class="todo-desc">' + escapeHtml(t.desc) + '</div>' : '')
        +   '</div>'
        +   '<button type="button" class="todo-del" onclick="onTodoRemove(\'' + t.id + '\')" title="刪除" aria-label="刪除這筆">'
        +     '<i data-lucide="trash-2" style="width:13px;height:13px"></i>'
        +   '</button>'
        + '</div>';
    });
  }

  if (!rows) {
    rows = '<div class="todo-empty">// 今天沒有待辦事項，可以從上方「新增」加自己想記的事</div>';
  }
  el.innerHTML = rows;
  if (typeof lucide !== 'undefined') lucide.createIcons();
}
function onTodoToggle(id) { toggleUserTodo(id); refreshTodoList(); }
function onTodoRemove(id) { removeUserTodo(id); refreshTodoList(); }
function openTodoComposer() {
  var c = document.getElementById('home-todo-composer');
  if (!c) return;
  c.hidden = false;
  var inp = document.getElementById('home-todo-input');
  if (inp) { inp.value = ''; setTimeout(function(){ inp.focus(); }, 30); inp.onkeydown = function(e){
    if (e.key === 'Enter') { e.preventDefault(); submitTodoComposer(); }
    else if (e.key === 'Escape') { closeTodoComposer(); }
  }; }
}
function closeTodoComposer() {
  var c = document.getElementById('home-todo-composer');
  if (c) c.hidden = true;
}
function submitTodoComposer() {
  var inp = document.getElementById('home-todo-input');
  if (!inp) return;
  if (addUserTodo(inp.value, '')) {
    closeTodoComposer();
    refreshTodoList();
    if (typeof showToast === 'function') showToast('已加入待辦', 'success');
  } else {
    inp.focus();
  }
}

// 結束本期回診週期：把這段期間的紀錄整合進「我的碎片」，產出報告快照，然後清除原始紀錄。
// `early=true` 代表使用者在預定回診日之前主動結束週期（提前回診）。
function _finalizeVisit(opts) {
  opts = opts || {};
  var early = !!opts.early;

  // 1. 計算並保存快照（保留為「我的碎片」歷史，等同於提前產出 repo）
  try {
    if (typeof piecesComputeStats === 'function' && typeof piecesSaveSnapshot === 'function') {
      var s = piecesComputeStats();
      var snap = {
        savedAt: new Date().toISOString(),
        since: s.since instanceof Date ? s.since.toISOString() : s.since,
        days: s.days,
        symptomCount: s.symptomCount,
        symptomEntries: s.symptomEntries,
        avgIntensity: s.avgIntensity,
        memoCount: s.memoCount,
        memoForDoctor: s.memoForDoctor,
        vitalCount: s.vitalCount,
        topCats: s.topCats,
        timeline: s.timeline,
        completedVisit: true,
        earlyVisit: early
      };
      piecesSaveSnapshot(snap);
    }
  } catch (e) { /* 失敗也繼續清資料，避免卡住流程 */ }

  // 2. 清除原始紀錄（只清時間序列資料，保留設定/基本資料）
  try { localStorage.removeItem('mdpiece_symptoms'); } catch (e) {}
  try { localStorage.removeItem('mdpiece_memos_v1'); } catch (e) {}
  try { localStorage.removeItem('mdpiece_vitals_entries'); } catch (e) {}

  // 3. 更新回診日期：lastVisit = 今天、nextVisit = ''
  try {
    var todayIso = new Date().toISOString().slice(0, 10);
    if (typeof saveVisitDates === 'function') {
      saveVisitDates({ lastVisit: todayIso, nextVisit: '' });
    }
  } catch (e) {}
  saveNextVisit('');
  refreshNextVisitChip();

  // 4. UI 反饋
  if (typeof showToast === 'function') {
    showToast(early ? '已提前結束本期，紀錄與報告已整合到我的碎片' : '已標記為回診，紀錄已整合到我的碎片', 'success');
  }
  // 5. 直接帶到「我的碎片」頁讓使用者看到結果
  setTimeout(function() {
    if (typeof navigateTo === 'function') navigateTo('pieces', null);
  }, 400);
}

// 已回診：到了或過了預定回診日才會出現的按鈕。
function markVisitCompleted() {
  var msg =
    '標記為「已回診」後：\n' +
    '・這段期間的症狀、Memo、生理紀錄會被整合進「我的碎片」\n' +
    '・原始紀錄會被清除，無法復原\n' +
    '・上次回診日會更新為今天\n\n' +
    '確定要繼續嗎？';
  if (!confirm(msg)) return;
  _finalizeVisit({ early: false });
}

// 提前回診：在預定回診日之前主動結束本期週期、提前產出報告快照。
function markVisitEarly() {
  var iso = loadNextVisit();
  var d = iso ? _daysBetween(iso) : null;
  var lead = (d != null && d > 0) ? ('原訂下次回診還有 ' + d + ' 天，現在提前結束本期。\n\n') : '';
  var msg =
    '提前結束本期回診週期？\n\n' +
    lead +
    '・這段期間的症狀、Memo、生理紀錄會立即整合到「我的碎片」並產出報告\n' +
    '・原始紀錄會被清除，無法復原\n' +
    '・上次回診日會更新為今天，下次回診日將被清空\n\n' +
    '確定要繼續嗎？';
  if (!confirm(msg)) return;
  _finalizeVisit({ early: true });
}

function homeCard(page, icon, title, desc, color) {
  return `<div class="pzl-card pzl-${color}" onclick="navigateTo('${page}',null)">
    <div class="pzl-tab"></div>
    <div class="pzl-icon"><i data-lucide="${icon}"></i></div>
    <h4>${title}</h4>
    <p>${desc}</p></div>`;
}

function home() {
  const user = getCurrentUser();
  const hour = new Date().getHours();
  const greetKey = hour < 12 ? 'home.greet.morning' : hour < 18 ? 'home.greet.afternoon' : 'home.greet.evening';
  const greeting = _T(greetKey);
  const _lang = (window.MDPiece_i18n && window.MDPiece_i18n.getLang && window.MDPiece_i18n.getLang()) || 'zh-TW';
  const greetSep = _lang === 'zh-TW' ? '，' : ', ';
  const today = new Date();
  const dateStr = today.getFullYear() + '/' + String(today.getMonth()+1).padStart(2,'0') + '/' + String(today.getDate()).padStart(2,'0');
  const dayStr = _T('home.weekday.prefix') + _T('home.weekday.' + today.getDay());
  const name = user ? user.nickname : _T('home.greet.fallbackName');
  const ac = (user && user.avatar_color) ? user.avatar_color : '#5B9FE8';
  const heroAvatarIsDefault = !(user && user.avatar_url);
  const heroAvatarSrc = heroAvatarIsDefault ? 'icons/xiaohe.jpg' : user.avatar_url;
  const heroAvatarClass = 'home-logo home-logo-avatar' + (heroAvatarIsDefault ? ' home-logo-default' : '');
  const avatarAlt = _Tf('home.avatarAlt', { name: name });

  // 年長版：簡化成「問候 + 全功能 tile 網格」一頁式
  if (getMode() === 'senior') {
    const seniorTiles = [
      ['symptoms',    'scan-search',           'nav.symptoms'],
      ['medications', 'pill',                  'nav.medications'],
      ['vitals',      'activity',              'nav.vitals'],
      ['emotions',    'battery-charging',      'nav.emotions'],
      ['diet',        'utensils-crossed',      'nav.diet'],
      ['memo',        'sticky-note',           'nav.memo'],
      ['previsit',    'clipboard-check',       'nav.previsit'],
      ['education',   'book-heart',            'nav.education'],
      ['story',       'book-open',             'nav.story'],
      ['labs',        'trending-up',           'nav.labs'],
      ['pieces',      'puzzle',                'nav.pieces'],
      ['chat',        'message-circle-heart',  'nav.chat'],
      ['settings',    'settings',              'nav.settings'],
      ['account',     'user-cog',              'nav.account'],
    ];
    const tilesHtml = seniorTiles.map(function(t) {
      return '<button class="home-senior-tile" onclick="navigateTo(\'' + t[0] + '\',null)">' +
             '<span class="hst-icon"><i data-lucide="' + t[1] + '"></i></span>' +
             '<span class="hst-label">' + _T(t[2]) + '</span>' +
             '</button>';
    }).join('');
    return '' +
      '<div class="home-page home-senior">' +
        '<div class="home-senior-hero">' +
          '<h2 class="home-senior-greet">' + greeting + greetSep + name + '</h2>' +
          '<p class="home-senior-date">' + dateStr + '　' + dayStr + '</p>' +
        '</div>' +
        '<div class="home-senior-grid">' + tilesHtml + '</div>' +
      '</div>';
  }

  return `
    <div class="home-page">
      <svg class="home-deco home-deco-1" viewBox="0 0 48 48"><path d="M12 0h24v12c-4 0-6 3-6 6s2 6 6 6v12h-12c0-4-3-6-6-6s-6 2-6 6H0V24c4 0 6-3 6-6s-2-6-6-6V0h12z" fill="currentColor"/></svg>
      <svg class="home-deco home-deco-2" viewBox="0 0 48 48"><path d="M12 0h24v12c-4 0-6 3-6 6s2 6 6 6v12h-12c0-4-3-6-6-6s-6 2-6 6H0V24c4 0 6-3 6-6s-2-6-6-6V0h12z" fill="currentColor"/></svg>
      <svg class="home-deco home-deco-3" viewBox="0 0 48 48"><path d="M12 0h24v12c-4 0-6 3-6 6s2 6 6 6v12h-12c0-4-3-6-6-6s-6 2-6 6H0V24c4 0 6-3 6-6s-2-6-6-6V0h12z" fill="currentColor"/></svg>

      <!-- Hero: Logo + Greeting split -->
      <div class="home-hero">
        <div class="home-hero-left">
          <img src="${heroAvatarSrc}" alt="${avatarAlt}" class="${heroAvatarClass}" />
        </div>
        <div class="home-hero-right">
          <h2 class="home-title">${greeting}${greetSep}${name}</h2>
          <p class="home-calm">${getGreetingMessage()}</p>
          <div class="home-date-row">
            <span class="home-datestr">${dateStr}</span>
            <span class="home-day">${dayStr}</span>
          </div>
          <div class="home-visit-row" id="home-visit-row">
            ${renderNextVisitChip()}
          </div>
        </div>
      </div>

      <!-- Quick Actions — spread wider -->
      <div class="home-quick">
        <button class="hq-btn hq-symptoms" onclick="navigateTo('symptoms',null)">
          <span class="hq-icon"><i data-lucide="scan-search"></i></span>
          <span>${_T('home.quick.symptoms')}</span>
        </button>
        <button class="hq-btn hq-meds" onclick="navigateTo('medications',null)">
          <span class="hq-icon"><i data-lucide="pill"></i></span>
          <span>${_T('home.quick.meds')}</span>
        </button>
        <button class="hq-btn hq-records" onclick="navigateTo('records',null)">
          <span class="hq-icon"><i data-lucide="id-card"></i></span>
          <span>${_T('home.quick.records')}</span>
        </button>
        <button class="hq-btn hq-edu" onclick="navigateTo('education',null)">
          <span class="hq-icon"><i data-lucide="book-heart"></i></span>
          <span>${_T('home.quick.education')}</span>
        </button>
      </div>

      <!-- Today Digest（今日拼圖統計） -->
      ${renderTodayDigestCard()}

      <!-- Today's Todo (auto + user) -->
      ${renderTodoCard()}

      <!-- Three-column info row -->
      <div class="home-info-row">
        <div class="home-ov">
          <div class="home-ov-head">
            <i data-lucide="calendar-check" style="width:16px;height:16px;color:var(--accent)"></i>
            <span>${_T('home.ov.meds')}</span>
          </div>
          <div id="home-med-summary" class="home-ov-body">
            <p class="home-ov-placeholder">${_T('home.ov.loading')}</p>
          </div>
        </div>
        <div class="home-ov">
          <div class="home-ov-head">
            <i data-lucide="smile" style="width:16px;height:16px;color:var(--rose)"></i>
            <span>${_T('home.ov.mood')}</span>
          </div>
          <div id="home-mood-summary" class="home-ov-body">
            <p class="home-ov-placeholder">${_T('home.ov.loading')}</p>
          </div>
        </div>
        <div class="home-ov">
          <div class="home-ov-head">
            <i data-lucide="sparkles" style="width:16px;height:16px;color:var(--purple)"></i>
            <span>${_T('home.ov.tip')}</span>
          </div>
          <div class="home-ov-body">
            <p class="home-tip-text">${getHealthTip()}</p>
          </div>
        </div>
      </div>

      <!-- Feature grid label -->
      <div class="home-section-label">
        <svg viewBox="0 0 48 48" width="16" height="16"><path d="M12 0h24v12c-4 0-6 3-6 6s2 6 6 6v12h-12c0-4-3-6-6-6s-6 2-6 6H0V24c4 0 6-3 6-6s-2-6-6-6V0h12z" fill="currentColor" opacity="0.5"/></svg>
        ${_T('home.section.label')}
      </div>
      <div class="home-grid">
        ${homeCard('symptoms','scan-search',_T('home.card.symptoms.title'),_T('home.card.symptoms.desc'),'blue')}
        ${homeCard('symptomsAnalyze','sparkles',_T('home.card.symptomsAnalyze.title'),_T('home.card.symptomsAnalyze.desc'),'rose')}
        ${homeCard('records','id-card',_T('home.card.records.title'),_T('home.card.records.desc'),'purple')}
        ${homeCard('doctors','stethoscope',_T('home.card.doctors.title'),_T('home.card.doctors.desc'),'rose')}
        ${homeCard('medications','pill',_T('home.card.medications.title'),_T('home.card.medications.desc'),'amber')}
        ${homeCard('education','book-heart',_T('home.card.education.title'),_T('home.card.education.desc'),'teal')}
        ${homeCard('chat','message-circle-heart',_T('home.card.chat.title'),_T('home.card.chat.desc'),'rose')}
        ${homeCard('settings','settings',_T('home.card.settings.title'),_T('home.card.settings.desc'),'amber')}
      </div>

      <!-- Footer tagline -->
      <div class="home-footer">
        <svg viewBox="0 0 48 48" width="20" height="20"><path d="M12 0h24v12c-4 0-6 3-6 6s2 6 6 6v12h-12c0-4-3-6-6-6s-6 2-6 6H0V24c4 0 6-3 6-6s-2-6-6-6V0h12z" fill="currentColor" opacity="0.12"/></svg>
        <p>${_T('home.footer.tagline')}</p>
        <p class="home-footer-credit">${_T('home.footer.credit')}</p>
      </div>
    </div>`;
}

function loadHomePage() {
  var user = getCurrentUser();
  var pid = getStablePatientId();

  // 載入今日待辦（系統自動 + 使用者個人）
  refreshTodoList();
  // 載入今日拼圖統計
  refreshTodayDigest();
  // 更新 sidebar 各 nav-item 今日打卡 badge
  refreshNavBadges();

  fetch(API + '/medications/?patient_id=' + pid)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var el = document.getElementById('home-med-summary');
      if (!el) return;
      var meds = (data.medications || []).filter(function(m) { return m.active !== 0; });
      if (!meds.length) {
        el.innerHTML =
          '<p class="home-ov-empty">' + _T('home.med.empty') + '</p>' +
          '<button class="home-med-go" onclick="navigateTo(\'medications\',null)">' + _T('home.med.add') + '</button>';
        return;
      }
      el.innerHTML =
        '<div class="home-med-count">' + meds.length + '</div>' +
        '<div class="home-med-label">' + _T('home.med.tracking') + '</div>' +
        '<button class="home-med-go" onclick="navigateTo(\'medications\',null)">' + _T('home.med.go') + '</button>';
    })
    .catch(function() {
      var el = document.getElementById('home-med-summary');
      if (el) el.innerHTML = '<p class="home-ov-empty">' + _T('home.med.error') + '</p>';
    });

  fetch(API + '/emotions/daily?patient_id=' + pid + '&days=7')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var el = document.getElementById('home-mood-summary');
      if (!el) return;
      var daily = (data && data.daily) || [];
      if (!daily.length) {
        el.innerHTML = '<p class="home-ov-empty">' + _T('home.mood.empty') + '</p>'
          + '<button class="home-med-go" onclick="navigateTo(\'emotions\',null)">' + _T('home.mood.go') + '</button>';
        return;
      }
      var last = daily[daily.length - 1];
      var avg = data.overall_average;
      var lastPct = _moodPercent(last.average_score);
      var avgPct = (avg != null) ? _moodPercent(avg) : null;
      el.innerHTML =
        '<div><span class="home-mood-emoji">' + (last.emoji || '🙂') + '</span>' +
        '<span class="home-mood-score">' + lastPct + '%</span></div>' +
        '<div class="home-med-label">' + _Tf('home.mood.latestAvg', { avg: (avgPct != null ? avgPct + '%' : '—') }) + '</div>' +
        '<button class="home-med-go" onclick="navigateTo(\'emotions\',null)">' + _T('home.mood.update') + '</button>';
    })
    .catch(function() {
      var el = document.getElementById('home-mood-summary');
      if (el) el.innerHTML = '<p class="home-ov-empty">' + _T('home.mood.error') + '</p>';
    });
}

// ─── 症狀分析 ──────────────────────────────────────────────

function symptoms() {
  const stats = getPeriodStats();
  const v = getVisitDates();
  const today = new Date();
  const periodDays = Math.max(1, Math.ceil((today - stats.periodStart) / 86400000));
  const totalCount = Object.values(stats.byCategory).reduce((s, c) => s + c.count, 0);
  let topId = null, topCount = 0;
  for (const cid in stats.byCategory) {
    if (stats.byCategory[cid].count > topCount) { topId = cid; topCount = stats.byCategory[cid].count; }
  }
  const topCat = topId ? findSymptomCat(topId) : null;
  const nextVisitDay = v.nextVisit ? Math.ceil((new Date(v.nextVisit) - today) / 86400000) : null;
  const todayStr = today.toISOString().slice(0, 10);
  const todayEntries = stats.entries.filter(e => e.recordedAt.slice(0, 10) === todayStr);

  return `
    <div class="sym-page">

      ${renderHowto('symptoms')}

      <section class="term-section">
        <header class="ts-head">
          <span class="ts-prompt">本期概況</span>
          <span class="ts-tag">本期摘要</span>
        </header>
        <div class="ts-body">
          <div class="ts-stat-grid">
            <div class="ts-stat">
              <span class="ts-stat-label">${_T('sym.stat.days')}</span>
              <span class="ts-stat-num">${periodDays}</span>
              <span class="ts-stat-unit">days</span>
            </div>
            <div class="ts-stat">
              <span class="ts-stat-label">${_T('sym.stat.logged')}</span>
              <span class="ts-stat-num">${totalCount}</span>
              <span class="ts-stat-unit">${_T('sym.stat.times')}</span>
            </div>
            <div class="ts-stat">
              <span class="ts-stat-label">${_T('sym.stat.top')}</span>
              <span class="ts-stat-num sm">${topCat ? _symField(topCat, 'zh') : '—'}</span>
              <span class="ts-stat-unit">${topCat ? topCount + ' ' + _T('sym.stat.times') : _T('sym.stat.empty')}</span>
            </div>
            <div class="ts-stat">
              <span class="ts-stat-label">${_T('sym.stat.nextVisit')}</span>
              <span class="ts-stat-num">${nextVisitDay !== null ? Math.max(0, nextVisitDay) : '—'}</span>
              <span class="ts-stat-unit">${nextVisitDay !== null ? 'days' : _T('sym.stat.notSet')}</span>
            </div>
          </div>
          <button class="sym-link-btn" onclick="openVisitDatePrompt()">
            <i data-lucide="calendar-cog"></i><span>${_T('sym.btn.setVisit')}</span>
          </button>
        </div>
      </section>

      <section class="term-section">
        <header class="ts-head">
          <span class="ts-prompt">點位置</span>
          <span class="ts-tag">點哪裡不舒服</span>
        </header>
        <div class="ts-body">
          <p class="sym-instruct">滑鼠移到身體上的位置會跟著跑紅點；點下去就鎖定，然後可以叫 AI 分析這個部位可能的狀況。</p>
          <div class="sym-body-map" id="sym-body-map">
            ${renderBodyMapSvg()}
            <div class="sym-body-legend">
              <span class="sym-body-current" id="sym-body-current">尚未選擇部位</span>
              <button type="button" class="sym-body-clear" onclick="symBodyClear()">清除</button>
            </div>
            <div class="sym-body-ai" id="sym-body-ai" style="display:none">
              <button type="button" class="sym-body-ai-btn" onclick="symBodyAiAnalyze()">
                <i data-lucide="sparkles" style="width:14px;height:14px"></i>
                <span>用 AI 分析這個位置可能的狀況</span>
              </button>
              <p class="sym-body-ai-warn">
                <i data-lucide="info" style="width:11px;height:11px"></i>
                AI 推測僅供與醫師討論參考，不是診斷
              </p>
              <div class="sym-body-ai-result" id="sym-body-ai-result"></div>
            </div>
          </div>
        </div>
      </section>

      <section class="term-section">
        <header class="ts-head">
          <span class="ts-prompt">紀錄症狀</span>
          <span class="ts-tag">選分類</span>
        </header>
        <div class="ts-body">
          <p class="sym-instruct">${_T('sym.choose.instruct')}</p>
          <div class="sym-category-grid">
            ${SYMPTOM_CATEGORIES.map(c => `
              <button class="sym-cat-card" onclick="openSymptomLog('${c.id}')" type="button">
                <div class="scc-icon scc-${c.color}"><i data-lucide="${c.icon}"></i></div>
                <div class="scc-name">${_symField(c, 'zh')}</div>
                <div class="scc-short">${_symField(c, 'short')}</div>
              </button>
            `).join('')}
            ${getCustomSymptomCats().map(c => `
              <button class="sym-cat-card sym-cat-card-custom" onclick="openSymptomLog('${c.id}')" type="button">
                <span class="scc-badge">${_T('sym.card.custom.badge')}</span>
                <button type="button" class="scc-del" onclick="event.stopPropagation(); removeCustomSymptomCatAndRefresh('${c.id}')" title="${_T('sym.card.custom.delTitle')}" aria-label="刪除自訂症狀「${escapeHtml(c.zh)}」">×</button>
                <div class="scc-icon scc-${c.color}"><i data-lucide="${c.icon}"></i></div>
                <div class="scc-name">${escapeHtml(c.zh)}</div>
                <div class="scc-short">${c.short}</div>
              </button>
            `).join('')}
            <button class="sym-cat-card sym-cat-card-other" onclick="openOtherSymptomLog()" type="button">
              <div class="scc-icon scc-other"><i data-lucide="plus"></i></div>
              <div class="scc-name">${_T('sym.card.other.name')}</div>
              <div class="scc-short">${_T('sym.card.other.short')}</div>
            </button>
          </div>
        </div>
      </section>

      <section class="term-section" id="sym-logform" style="display:none">
        <header class="ts-head">
          <span class="ts-prompt">填寫紀錄</span>
          <span class="ts-tag" id="logform-cat-tag">—</span>
        </header>
        <div class="ts-body" id="logform-body"></div>
      </section>

      <section class="term-section">
        <header class="ts-head">
          <span class="ts-prompt">今日紀錄</span>
          <span class="ts-tag">${_Tf('sym.today.tag', { n: todayEntries.length })}</span>
        </header>
        <div class="ts-body">
          ${todayEntries.length === 0 ? `
            <div class="empty-state empty-state-cozy">
              <div class="empty-state-icon"><i data-lucide="scan-search"></i></div>
              <p class="empty-state-title">${_T('sym.today.empty.title')}</p>
              <p class="empty-state-desc">${_T('sym.today.empty.desc')}</p>
              <button type="button" class="empty-state-cta" onclick="document.querySelector('.sym-category-grid')?.scrollIntoView({behavior:'smooth', block:'center'})">
                <i data-lucide="arrow-up" style="width:14px;height:14px"></i>
                <span>${_T('sym.today.empty.cta')}</span>
              </button>
            </div>
          ` : `
            <ul class="sym-entry-list">
              ${todayEntries.slice().reverse().map(e => {
                const c = findSymptomCat(e.categoryId);
                const time = new Date(e.recordedAt).toTimeString().slice(0, 5);
                return `
                  <li class="sym-entry">
                    <span class="se-time">${time}</span>
                    <span class="se-cat scc-${c?.color || 'mint'}">${c ? _symField(c, 'zh') : e.categoryId}</span>
                    <span class="se-bar">${renderIntensityBar(e.intensity)}</span>
                    <span class="se-meta">${_Tf('sym.entry.meta', { i: e.intensity, n: e.frequency || 1 })}</span>
                    <button class="se-del" onclick="deleteSymptomEntryAndRefresh('${e.id}')" title="${_T('sym.entry.del')}">×</button>
                    ${e.notes ? `<span class="se-notes">${escapeHtml(e.notes)}</span>` : ''}
                  </li>
                `;
              }).join('')}
            </ul>
          `}
        </div>
      </section>

      <section class="term-section">
        <header class="ts-head">
          <span class="ts-prompt">過去 ${periodDays} 天摘要</span>
          <span class="ts-tag">累計</span>
        </header>
        <div class="ts-body">${renderPeriodSummary(stats)}</div>
      </section>

    </div>
  `;
}

// ── Symptom data & helpers ─────────────────────────────────
// Each category carries both zh-TW and English fields (en, shortEn, detailEn,
// contrastEn). Use _symField(c, 'zh' | 'short' | 'detail' | 'contrast') to
// pull the localized version based on current language.
const SYMPTOM_CATEGORIES = [
  { id:'headache', zh:'頭痛', en:'Headache', icon:'brain', color:'pink',
    short:'頭部明顯的疼痛感',
    shortEn:'Distinct pain in the head',
    detail:'可能集中在前額、太陽穴、後腦勺或整個頭部，鈍痛或抽痛皆有可能。',
    detailEn:'May focus on the forehead, temples, back of the head, or the whole head — dull ache or throbbing both possible.',
    contrast:'不同於「頭暈」（不穩）和「暈眩」（轉動）—— 頭痛是真的會「痛」。',
    contrastEn:'Different from "lightheadedness" (unsteady) or "vertigo" (spinning) — headache actually hurts.' },
  { id:'dizziness', zh:'頭暈', en:'Lightheadedness', icon:'wind', color:'aqua',
    short:'輕飄飄、頭重腳輕、快暈倒',
    shortEn:'Floating, heavy-headed, about to faint',
    detail:'比較像快要昏倒或站不穩。常見原因：低血糖、脫水、貧血、姿勢性低血壓。',
    detailEn:'Feels like nearly fainting or unsteady. Common causes: low blood sugar, dehydration, anemia, postural hypotension.',
    contrast:'不同於「暈眩」—— 頭暈不會看到周圍在轉。',
    contrastEn:'Different from "vertigo" — lightheadedness doesn\'t spin.' },
  { id:'vertigo', zh:'暈眩', en:'Vertigo', icon:'rotate-cw', color:'mint',
    short:'天旋地轉，自己或周圍在轉動',
    shortEn:'Spinning sensation — you or the room turning',
    detail:'常與內耳問題（梅尼爾氏症、耳石脫落 BPPV）或前庭神經有關。',
    detailEn:'Often linked to inner ear issues (Ménière\'s, BPPV) or the vestibular nerve.',
    contrast:'不同於「頭暈」—— 暈眩有清楚的「轉動感」。',
    contrastEn:'Different from "lightheadedness" — vertigo has a clear spinning feel.' },
  { id:'neuralgia', zh:'神經痛', en:'Nerve Pain', icon:'zap', color:'pink',
    short:'像觸電、燒灼、針刺、刀割的痛',
    shortEn:'Electric, burning, stabbing, or knife-like pain',
    detail:'沿神經分佈，發作性、尖銳。常見：坐骨神經痛、三叉神經痛、糖尿病神經病變。',
    detailEn:'Follows a nerve path, episodic and sharp. Common: sciatica, trigeminal neuralgia, diabetic neuropathy.',
    contrast:'不同於「肌肉痠痛」—— 神經痛更尖銳、有電擊感。',
    contrastEn:'Different from "muscle ache" — nerve pain is sharper, with an electric quality.' },
  { id:'joint', zh:'關節痛', en:'Joint Pain', icon:'bone', color:'blue',
    short:'關節（膝、肘、手指、肩）的疼痛、僵硬、紅腫',
    shortEn:'Pain, stiffness, or swelling in joints (knee, elbow, fingers, shoulder)',
    detail:'可能伴隨活動受限、晨僵。常見：退化性關節炎、類風濕、痛風。',
    detailEn:'May come with reduced range of motion or morning stiffness. Common: osteoarthritis, rheumatoid arthritis, gout.',
    contrast:'不同於「肌肉痠痛」—— 關節痛集中在關節處，活動時更明顯。',
    contrastEn:'Different from "muscle ache" — joint pain centers on the joint and worsens with movement.' },
  { id:'muscle', zh:'肌肉痠痛', en:'Muscle Ache', icon:'dumbbell', color:'aqua',
    short:'肌肉的痠痛、僵硬、無力',
    shortEn:'Soreness, stiffness, or weakness in muscles',
    detail:'常見於運動後、姿勢不良、感冒、或纖維肌痛。',
    detailEn:'Common after exercise, from poor posture, with a cold, or in fibromyalgia.' },
  { id:'fever', zh:'發燒', en:'Fever', icon:'thermometer', color:'pink',
    short:'體溫 ≥ 37.5°C，可能伴隨畏寒、出汗',
    shortEn:'Body temp ≥ 37.5°C, possibly with chills or sweating',
    detail:'若 ≥ 38.5°C 或持續 3 天以上應就醫。記錄時可在備註寫下實測體溫。',
    detailEn:'If ≥ 38.5°C or lasting 3+ days, see a doctor. Note the measured temperature in the notes field.' },
  { id:'fatigue', zh:'疲勞無力', en:'Fatigue', icon:'battery-low', color:'aqua',
    short:'極度倦怠、提不起勁，休息也難恢復',
    shortEn:'Extreme tiredness, low energy, hard to recover with rest',
    detail:'與一般累不同，是持續性的，可能與貧血、甲狀腺、慢性病有關。',
    detailEn:'Different from regular tiredness — it\'s persistent. May relate to anemia, thyroid, or chronic conditions.' },
  { id:'nausea', zh:'噁心嘔吐', en:'Nausea / Vomiting', icon:'cloud-rain', color:'mint',
    short:'想吐或實際嘔吐',
    shortEn:'Feeling sick or actually vomiting',
    detail:'可能與腸胃問題、藥物副作用、暈眩或頭痛同時出現。',
    detailEn:'May come with GI issues, medication side effects, vertigo, or headache.' },
  { id:'cough', zh:'咳嗽', en:'Cough', icon:'megaphone', color:'blue',
    short:'反射性將氣道分泌物或刺激物排出',
    shortEn:'Reflex to clear secretions or irritants from the airway',
    detail:'可分為乾咳與有痰咳。超過 3 週為慢性咳嗽，建議就醫。',
    detailEn:'Dry or productive. Chronic cough lasts 3+ weeks — see a doctor.' },
  { id:'chest', zh:'胸痛胸悶', en:'Chest Pain / Tightness', icon:'heart-pulse', color:'pink',
    short:'胸口悶、壓迫感、刺痛',
    shortEn:'Tightness, pressure, or stabbing in the chest',
    detail:'若伴隨喘、冒冷汗、痛感放射到左肩或下巴，立即就醫。',
    detailEn:'If accompanied by shortness of breath, cold sweats, or pain radiating to the left shoulder or jaw, seek care immediately.',
    contrast:'⚠️ 警示症狀，記得儘快諮詢醫師。',
    contrastEn:'⚠️ Red-flag symptom — consult a doctor as soon as possible.' },
  { id:'breath', zh:'呼吸困難', en:'Shortness of Breath', icon:'activity', color:'aqua',
    short:'喘不過氣、呼吸費力',
    shortEn:'Trouble breathing, labored breath',
    detail:'可能與氣喘、心臟、肺部問題有關。記錄發生時的活動狀態（休息中？運動後？）。',
    detailEn:'May relate to asthma, heart, or lung conditions. Note what you were doing (resting? after exercise?).' },
  { id:'insomnia', zh:'失眠', en:'Insomnia', icon:'moon', color:'mint',
    short:'睡不著、易醒、太早醒',
    shortEn:'Trouble falling asleep, waking up often, waking too early',
    detail:'長期失眠影響身心，建議在備註記下入睡時間與睡眠品質。',
    detailEn:'Long-term insomnia affects body and mind. Note your sleep time and quality.' },
];

// Pull the localized field from a SYMPTOM_CATEGORIES entry. Falls back to the
// Chinese version if the English field is missing.
function _symField(c, key) {
  if (!c) return '';
  var lang = (window.MDPiece_i18n && window.MDPiece_i18n.getLang) ? window.MDPiece_i18n.getLang() : 'zh-TW';
  if (lang !== 'en') return c[key] || '';
  var enKey = key === 'zh' ? 'en' : key + 'En';
  return c[enKey] || c[key] || '';
}

// ─── 自訂症狀（其他病症）──────────────────────────
// 使用者第一次輸入後存到 localStorage，下次直接出現在卡片列。
const CUSTOM_SYM_KEY = 'mdpiece_custom_symptom_categories';
const CUSTOM_SYM_COLORS = ['mint','aqua','pink','blue'];

function getCustomSymptomCats() {
  try { return JSON.parse(localStorage.getItem(CUSTOM_SYM_KEY) || '[]'); }
  catch { return []; }
}
function saveCustomSymptomCats(list) {
  localStorage.setItem(CUSTOM_SYM_KEY, JSON.stringify(list));
}
function addCustomSymptomCat(name) {
  const trimmed = (name || '').trim();
  if (!trimmed) return null;
  const list = getCustomSymptomCats();
  // 已存在就直接回傳（避免重複）
  const dup = list.find(c => c.zh === trimmed);
  if (dup) return dup;
  const id = 'custom_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5);
  const color = CUSTOM_SYM_COLORS[list.length % CUSTOM_SYM_COLORS.length];
  const cat = {
    id, zh: trimmed, icon: 'plus-circle', color,
    short: '自訂症狀',
    detail: '使用者自訂症狀。建議在備註寫下發生時的細節（部位、誘因、持續時間）。',
    custom: true,
  };
  list.push(cat);
  saveCustomSymptomCats(list);
  return cat;
}
function removeCustomSymptomCat(id) {
  const list = getCustomSymptomCats().filter(c => c.id !== id);
  saveCustomSymptomCats(list);
}
function findSymptomCat(id) {
  return SYMPTOM_CATEGORIES.find(x => x.id === id)
    || getCustomSymptomCats().find(x => x.id === id)
    || null;
}

function getSymptomEntries() {
  try { return JSON.parse(localStorage.getItem('mdpiece_symptoms') || '[]'); }
  catch { return []; }
}
function saveSymptomEntry(entry) {
  const all = getSymptomEntries();
  all.push(entry);
  localStorage.setItem('mdpiece_symptoms', JSON.stringify(all));
}
function deleteSymptomEntry(id) {
  localStorage.setItem('mdpiece_symptoms',
    JSON.stringify(getSymptomEntries().filter(e => e.id !== id)));
}
function getVisitDates() {
  try { return JSON.parse(localStorage.getItem('mdpiece_visit_dates') || '{}'); }
  catch { return {}; }
}
function saveVisitDates(d) {
  localStorage.setItem('mdpiece_visit_dates', JSON.stringify(d));
}
function getPeriodStart() {
  const v = getVisitDates();
  if (v.lastVisit) {
    const d = new Date(v.lastVisit);
    if (!isNaN(d.getTime())) return d;
  }
  const fallback = new Date(); fallback.setDate(fallback.getDate() - 30);
  return fallback;
}
// 回診倒數：從上次回診日到今天，給後端報告 / 前端 UI 用。
// 沒設過上次回診 → 退回預設 30 天。Clamp 到 [1, 365]。
function getReportDays() {
  const v = getVisitDates();
  if (v.lastVisit) {
    const d = new Date(v.lastVisit);
    if (!isNaN(d.getTime())) {
      const days = Math.ceil((Date.now() - d.getTime()) / 86400000);
      return Math.max(1, Math.min(365, days));
    }
  }
  return 30;
}
function getPeriodStats() {
  const start = getPeriodStart();
  const entries = getSymptomEntries().filter(e => new Date(e.recordedAt) >= start);
  const byCategory = {};
  for (const e of entries) {
    if (!byCategory[e.categoryId]) byCategory[e.categoryId] = { count: 0, intensitySum: 0 };
    byCategory[e.categoryId].count += (e.frequency || 1);
    byCategory[e.categoryId].intensitySum += (e.intensity || 0) * (e.frequency || 1);
  }
  return { entries, byCategory, periodStart: start };
}

// ─── 身體圖：點擊定位疼痛部位 ───────────────────────────
// 8 個主要區域。click → 寫進 _symBodyPart，並把 part 名稱帶進
// 下方症狀紀錄表單的 notes 欄。
var _symBodyPart = '';
var _SYM_BODY_PARTS = [
  { id: 'head',     label: '頭部',   cx: 55, cy: 22 },
  { id: 'neck',     label: '頸部',   cx: 55, cy: 40 },
  { id: 'chest',    label: '胸口',   cx: 55, cy: 60 },
  { id: 'abdomen',  label: '腹部',   cx: 55, cy: 92 },
  { id: 'l-arm',    label: '左手',   cx: 23, cy: 80 },
  { id: 'r-arm',    label: '右手',   cx: 87, cy: 80 },
  { id: 'l-leg',    label: '左腿',   cx: 46, cy: 165 },
  { id: 'r-leg',    label: '右腿',   cx: 64, cy: 165 },
];
function renderBodyMapSvg() {
  var hotspots = _SYM_BODY_PARTS.map(function(p) {
    return ''
      + '<g class="sym-body-hotspot" data-part="' + p.id + '" '
      +    'onclick="symBodyPick(\'' + p.id + '\',\'' + p.label + '\')">'
      +   '<circle cx="' + p.cx + '" cy="' + p.cy + '" r="11" fill="rgba(201,127,75,0.0)" stroke="rgba(201,127,75,0.0)" stroke-width="1.5" />'
      +   '<title>' + p.label + '</title>'
      + '</g>';
  }).join('');
  return ''
    + '<svg viewBox="0 0 110 210" xmlns="http://www.w3.org/2000/svg" class="sym-body-svg"'
    +    ' onmousemove="symBodyHover(event)"'
    +    ' onmouseleave="symBodyHoverLeave()"'
    +    ' onclick="symBodyClickAt(event)"'
    +    ' ontouchmove="symBodyHover(event.touches[0]); event.preventDefault()"'
    +    ' ontouchend="symBodyClickAt(event.changedTouches[0])"'
    + '>'
    +   '<defs>'
    +     '<linearGradient id="symBodyGrad" x1="0" y1="0" x2="0" y2="1">'
    +       '<stop offset="0%" stop-color="#FFF6E6"/>'
    +       '<stop offset="100%" stop-color="#F2D6B0"/>'
    +     '</linearGradient>'
    +     '<radialGradient id="symBodyPain" cx="50%" cy="50%" r="50%">'
    +       '<stop offset="0%"   stop-color="#B8553F" stop-opacity="0.55"/>'
    +       '<stop offset="60%"  stop-color="#B8553F" stop-opacity="0.18"/>'
    +       '<stop offset="100%" stop-color="#B8553F" stop-opacity="0"/>'
    +     '</radialGradient>'
    +   '</defs>'
    // 身體輪廓
    +   '<g fill="url(#symBodyGrad)" stroke="#5C3A32" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round" pointer-events="none">'
    +     '<ellipse cx="55" cy="22" rx="13" ry="15"/>'
    +     '<path d="M 49 35 Q 55 39 61 35 L 61 43 Q 55 45 49 43 Z"/>'
    +     '<path d="M 32 50 Q 32 45 38 44 Q 46 42 55 42 Q 64 42 72 44 Q 78 45 78 50 L 76 78 Q 74 92 73 100 L 72 122 Q 72 128 68 130 L 42 130 Q 38 128 38 122 L 37 100 Q 36 92 34 78 Z"/>'
    +     '<path d="M 32 50 Q 26 53 23 62 Q 19 80 17 102 Q 16 114 21 116 Q 26 116 28 111 Q 31 96 32 82 Q 33 68 33 54 Z"/>'
    +     '<path d="M 78 50 Q 84 53 87 62 Q 91 80 93 102 Q 94 114 89 116 Q 84 116 82 111 Q 79 96 78 82 Q 77 68 77 54 Z"/>'
    +     '<path d="M 42 130 Q 40 144 40 160 L 38 196 Q 38 198 41 198 L 51 198 Q 53 198 53 196 L 53 160 Q 53 144 53 132 Z"/>'
    +     '<path d="M 57 132 Q 57 144 57 160 L 57 196 Q 57 198 59 198 L 69 198 Q 72 198 72 196 L 70 160 Q 70 144 68 130 Z"/>'
    +   '</g>'
    // 點擊熱區（覆蓋在輪廓上層，hover 變亮 — 但整個 SVG 也接 click）
    +   hotspots
    +   '<g id="sym-body-cursor" pointer-events="none" style="display:none">'
    +     '<circle id="sym-body-cursor-glow" cx="0" cy="0" r="10" fill="url(#symBodyPain)" opacity="0.7"/>'
    +     '<circle id="sym-body-cursor-dot"  cx="0" cy="0" r="3" fill="#B8553F" stroke="#FFFAF0" stroke-width="0.6" opacity="0.85"/>'
    +   '</g>'
    +   '<g id="sym-body-marker" pointer-events="none" style="display:none">'
    +     '<circle id="sym-body-marker-glow" cx="0" cy="0" r="14" fill="url(#symBodyPain)"/>'
    +     '<circle id="sym-body-marker-dot"  cx="0" cy="0" r="5" fill="#B8553F" stroke="#FFFAF0" stroke-width="1.2"/>'
    +   '</g>'
    + '</svg>';
}

// 把 client (滑鼠/觸控) 座標換成 SVG viewBox 座標
function _svgCoords(svg, ev) {
  var pt = svg.createSVGPoint();
  pt.x = ev.clientX; pt.y = ev.clientY;
  var ctm = svg.getScreenCTM();
  if (!ctm) return null;
  var p = pt.matrixTransform(ctm.inverse());
  return { x: p.x, y: p.y };
}
function symBodyHover(ev) {
  var svg = document.querySelector('.sym-body-svg');
  if (!svg || !ev) return;
  var c = _svgCoords(svg, ev);
  if (!c) return;
  var cur = document.getElementById('sym-body-cursor');
  var glow = document.getElementById('sym-body-cursor-glow');
  var dot  = document.getElementById('sym-body-cursor-dot');
  if (!cur || !glow || !dot) return;
  cur.style.display = '';
  glow.setAttribute('cx', c.x); glow.setAttribute('cy', c.y);
  dot.setAttribute('cx', c.x);  dot.setAttribute('cy', c.y);
}
function symBodyHoverLeave() {
  var cur = document.getElementById('sym-body-cursor');
  if (cur) cur.style.display = 'none';
}
// 點擊任意位置：算最近區域 + 鎖定 marker，並準備 AI 分析按鈕
function symBodyClickAt(ev) {
  if (!ev) return;
  var svg = document.querySelector('.sym-body-svg');
  if (!svg) return;
  // 若 click 落在 hotspot 的 <g> 內，瀏覽器會先觸發那邊的 onclick；
  // 為了避免雙觸發，這裡判斷如果 _symBodyPart 剛剛被 symBodyPick 設過（< 80ms 內）就略過。
  if (_symBodyJustPicked && (Date.now() - _symBodyJustPicked) < 80) return;
  var c = _svgCoords(svg, ev);
  if (!c) return;
  // 找最近的 _SYM_BODY_PARTS
  var best = null, bestDist = Infinity;
  _SYM_BODY_PARTS.forEach(function(p) {
    var dx = p.cx - c.x, dy = p.cy - c.y;
    var d = Math.sqrt(dx * dx + dy * dy);
    if (d < bestDist) { bestDist = d; best = p; }
  });
  if (!best) return;
  // 鎖定 marker 在「實際點擊位置」而非 hotspot 中心，讓使用者覺得精準
  _symBodyPart = best.label;
  _symBodyClickXY = { x: c.x, y: c.y };
  var g = document.getElementById('sym-body-marker');
  var glow = document.getElementById('sym-body-marker-glow');
  var dot  = document.getElementById('sym-body-marker-dot');
  if (g && glow && dot) {
    glow.setAttribute('cx', c.x); glow.setAttribute('cy', c.y);
    dot.setAttribute('cx', c.x);  dot.setAttribute('cy', c.y);
    g.style.display = '';
  }
  document.querySelectorAll('.sym-body-hotspot').forEach(function(el) {
    el.classList.toggle('is-active', el.getAttribute('data-part') === best.id);
  });
  var cur = document.getElementById('sym-body-current');
  if (cur) cur.textContent = '已選：' + best.label;
  // 顯示 AI 分析按鈕區
  var ai = document.getElementById('sym-body-ai');
  if (ai) ai.style.display = '';
  var aiResult = document.getElementById('sym-body-ai-result');
  if (aiResult) aiResult.innerHTML = '';
}
var _symBodyJustPicked = 0;
var _symBodyClickXY = null;
function symBodyPick(partId, label) {
  _symBodyPart = label;
  _symBodyJustPicked = Date.now();
  var p = _SYM_BODY_PARTS.find(function(x) { return x.id === partId; });
  if (!p) return;
  _symBodyClickXY = { x: p.cx, y: p.cy };
  // 更新標記位置
  var g = document.getElementById('sym-body-marker');
  var glow = document.getElementById('sym-body-marker-glow');
  var dot  = document.getElementById('sym-body-marker-dot');
  if (g && glow && dot) {
    glow.setAttribute('cx', p.cx); glow.setAttribute('cy', p.cy);
    dot.setAttribute('cx', p.cx);  dot.setAttribute('cy', p.cy);
    g.style.display = '';
  }
  // 更新 legend 文字
  var cur = document.getElementById('sym-body-current');
  if (cur) cur.textContent = '已選：' + label;
  // 高亮熱區
  document.querySelectorAll('.sym-body-hotspot').forEach(function(el) {
    el.classList.toggle('is-active', el.getAttribute('data-part') === partId);
  });
  // 顯示 AI 分析按鈕
  var ai = document.getElementById('sym-body-ai');
  if (ai) ai.style.display = '';
  var aiResult = document.getElementById('sym-body-ai-result');
  if (aiResult) aiResult.innerHTML = '';
}
function symBodyClear() {
  _symBodyPart = '';
  _symBodyClickXY = null;
  var g = document.getElementById('sym-body-marker');
  if (g) g.style.display = 'none';
  var cur = document.getElementById('sym-body-current');
  if (cur) cur.textContent = '尚未選擇部位';
  document.querySelectorAll('.sym-body-hotspot').forEach(function(el) {
    el.classList.remove('is-active');
  });
  var ai = document.getElementById('sym-body-ai');
  if (ai) ai.style.display = 'none';
  var aiResult = document.getElementById('sym-body-ai-result');
  if (aiResult) aiResult.innerHTML = '';
}

// AI 分析「點選位置」— 把 部位 + 細座標換算成 sub-region 名稱
// 後送 POST /symptoms/analyze，符合既有 SymptomAnalysisRequest 介面
async function symBodyAiAnalyze() {
  if (!_symBodyPart) return;
  var resultEl = document.getElementById('sym-body-ai-result');
  if (!resultEl) return;

  // 把點擊位置換算成「細部敘述」— 用簡單的相對位置規則，幫 AI 更聚焦
  var subRegion = _symBodyPart;
  if (_symBodyClickXY) {
    var x = _symBodyClickXY.x, y = _symBodyClickXY.y;
    // 頭部細分（y < 35）
    if (y < 35) {
      if (y < 18) subRegion = '額頭';
      else if (y > 28) subRegion = '下巴';
      else if (x < 50) subRegion = '左側太陽穴 / 左眼周圍';
      else if (x > 60) subRegion = '右側太陽穴 / 右眼周圍';
      else subRegion = '頭部中央';
    }
    // 頸部
    else if (y < 50) {
      subRegion = '頸部' + (x < 55 ? '左側' : (x > 55 ? '右側' : '中央'));
    }
    // 胸口（50 ≤ y < 78）
    else if (y < 78) {
      if (x < 48) subRegion = '左胸 / 心臟區域';
      else if (x > 62) subRegion = '右胸';
      else subRegion = '胸口中央 / 胸骨';
    }
    // 上腹/腰（78 ≤ y < 110）
    else if (y < 110) {
      if (x < 48) subRegion = '左上腹 / 左側肋下';
      else if (x > 62) subRegion = '右上腹 / 右側肋下';
      else subRegion = '上腹 / 胃部';
    }
    // 下腹（110 ≤ y < 132）
    else if (y < 132) {
      if (x < 48) subRegion = '下腹左側';
      else if (x > 62) subRegion = '下腹右側';
      else subRegion = '下腹 / 肚臍附近';
    }
    // 手臂 (x < 30 or x > 80)
    else if (x < 30) subRegion = '左前臂 / 左手腕';
    else if (x > 80) subRegion = '右前臂 / 右手腕';
    // 腿
    else if (y > 130 && y < 170) subRegion = (x < 55 ? '左大腿' : '右大腿');
    else if (y >= 170) subRegion = (x < 55 ? '左小腿 / 左腳踝' : '右小腿 / 右腳踝');
  }

  resultEl.innerHTML = '<div class="sbai-loading"><i data-lucide="loader" class="sbai-spin"></i> AI 分析中…（' + subRegion + '）</div>';
  if (typeof lucide !== 'undefined') lucide.createIcons();

  var pid = (typeof getStablePatientId === 'function') ? getStablePatientId() : null;
  try {
    var res = await fetch(API + '/symptoms/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symptoms: [subRegion + ' 不適 / 疼痛 / 需要評估'],
        patient_id: pid,
      }),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    var data = await res.json();
    _renderBodyAiResult(resultEl, subRegion, data);
  } catch (e) {
    resultEl.innerHTML = '<div class="sbai-err">AI 分析暫時無法使用，可以先用下面的症狀分類紀錄。<br><span class="sbai-err-detail">' + escapeHtml(String(e.message || e)) + '</span></div>';
  }
}

function _renderBodyAiResult(el, subRegion, data) {
  var urgency = data.urgency || 'low';
  var urgencyMap = {
    emergency: { label: '緊急', tone: 'emergency', icon: 'alert-octagon' },
    high:      { label: '較高',  tone: 'high',      icon: 'alert-triangle' },
    medium:    { label: '中等',  tone: 'medium',    icon: 'alert-circle' },
    low:       { label: '輕微',  tone: 'low',       icon: 'info' },
  };
  var u = urgencyMap[urgency] || urgencyMap.low;
  var conditions = Array.isArray(data.conditions) ? data.conditions.slice(0, 4) : [];
  var condHtml = conditions.length
    ? '<ul class="sbai-conds">' + conditions.map(function(c) {
        var name = typeof c === 'string' ? c : (c.name || c.condition || c.title || JSON.stringify(c));
        var desc = (typeof c === 'object' && c.description) ? c.description : '';
        return '<li><strong>' + escapeHtml(String(name)) + '</strong>' + (desc ? '<span class="sbai-cond-desc">' + escapeHtml(String(desc)) + '</span>' : '') + '</li>';
      }).join('') + '</ul>'
    : '<p class="sbai-empty">AI 沒有特別指向的可能，建議直接諮詢醫師。</p>';

  el.innerHTML = ''
    + '<div class="sbai-card">'
    +   '<div class="sbai-head">'
    +     '<span class="sbai-region">' + escapeHtml(subRegion) + '</span>'
    +     '<span class="sbai-urgency sbai-urgency-' + u.tone + '">'
    +       '<i data-lucide="' + u.icon + '" style="width:12px;height:12px"></i> 緊急度 · ' + u.label
    +     '</span>'
    +   '</div>'
    +   '<div class="sbai-block">'
    +     '<div class="sbai-block-label">可能狀況（僅供與醫師討論）</div>'
    +     condHtml
    +   '</div>'
    +   '<div class="sbai-block">'
    +     '<div class="sbai-block-label">建議科別</div>'
    +     '<div class="sbai-dept">' + escapeHtml(data.recommended_department || '家醫科') + '</div>'
    +   '</div>'
    +   (data.advice ? '<div class="sbai-block"><div class="sbai-block-label">建議</div><p class="sbai-advice">' + escapeHtml(data.advice) + '</p></div>' : '')
    +   '<p class="sbai-disclaimer"><i data-lucide="info" style="width:11px;height:11px"></i> ' + escapeHtml(data.disclaimer || '此分析僅供參考，不取代醫師診斷；如有不適請立即就醫。') + '</p>'
    + '</div>';
  if (typeof lucide !== 'undefined') lucide.createIcons();
}
// 若有選擇身體部位，把它放在 notes 開頭（不覆蓋使用者後續輸入）
function _prefillBodyPartNote() {
  if (!_symBodyPart) return;
  var t = document.getElementById('lf-notes');
  if (t && !t.value) t.value = '[部位：' + _symBodyPart + '] ';
}

function openSymptomLog(catId) {
  const c = findSymptomCat(catId);
  if (!c) return;
  const form = document.getElementById('sym-logform');
  document.getElementById('logform-cat-tag').textContent = c.id + '.entry';
  const contrastText = _symField(c, 'contrast');
  document.getElementById('logform-body').innerHTML = `
    <div class="lf-explain">
      <div class="lf-icon scc-${c.color}"><i data-lucide="${c.icon}"></i></div>
      <div class="lf-info">
        <h3>${_symField(c, 'zh')}</h3>
        <p class="lf-detail">${_symField(c, 'detail')}</p>
        ${contrastText ? `<p class="lf-contrast"><strong>${_T('sym.log.unsure')}</strong>${contrastText}</p>` : ''}
      </div>
    </div>
    <div class="lf-form">
      <label class="lf-label">${_T('sym.log.label.intensity')}</label>
      <div class="lf-slider-wrap">
        <input type="range" id="lf-intensity" min="1" max="10" value="5" oninput="updateIntensityBar(this.value)" />
        <div class="lf-bar" id="lf-bar">${renderIntensityBar(5)}</div>
        <span class="lf-bar-value" id="lf-bar-value">5</span>
      </div>
      <label class="lf-label">${_T('sym.log.label.frequency')}</label>
      <div class="lf-freq-wrap">
        <button class="lf-freq-btn" onclick="adjustFreq(-1)" type="button">−</button>
        <span class="lf-freq-num" id="lf-freq">1</span>
        <button class="lf-freq-btn" onclick="adjustFreq(1)" type="button">+</button>
        <span class="lf-freq-unit">${_T('sym.log.unit.times')}</span>
      </div>
      <label class="lf-label">${_T('sym.log.label.notes')}</label>
      <textarea id="lf-notes" placeholder="${_T('sym.log.placeholder.notes')}" rows="2"></textarea>
      <div class="lf-actions">
        <button class="primary-btn" onclick="submitSymptomLog('${catId}')" type="button">
          <i data-lucide="check"></i><span>${_T('sym.log.btn.add')}</span>
        </button>
        <button class="secondary-btn" onclick="cancelSymptomLog()" type="button">${_T('sym.log.btn.cancel')}</button>
      </div>
    </div>
  `;
  form.style.display = 'block';
  if (typeof lucide !== 'undefined') lucide.createIcons();
  _prefillBodyPartNote();
  form.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function cancelSymptomLog() {
  const f = document.getElementById('sym-logform');
  if (f) f.style.display = 'none';
}

// ─── 其他症狀（自訂）的兩段式表單 ──────────────────
function openOtherSymptomLog() {
  const form = document.getElementById('sym-logform');
  document.getElementById('logform-cat-tag').textContent = 'custom.entry';
  document.getElementById('logform-body').innerHTML = `
    <div class="lf-explain">
      <div class="lf-icon scc-other"><i data-lucide="plus"></i></div>
      <div class="lf-info">
        <h3>${_T('sym.other.title')}</h3>
        <p class="lf-detail">${_T('sym.other.detail')}</p>
      </div>
    </div>
    <div class="lf-form">
      <label class="lf-label">${_T('sym.other.label.name')}</label>
      <input id="lf-custom-name" type="text" class="lf-text-input" maxlength="20"
        placeholder="${_T('sym.other.placeholder.name')}" autocomplete="off" />
      <label class="lf-label">${_T('sym.other.label.intensity')}</label>
      <div class="lf-slider-wrap">
        <input type="range" id="lf-intensity" min="1" max="10" value="5" oninput="updateIntensityBar(this.value)" />
        <div class="lf-bar" id="lf-bar">${renderIntensityBar(5)}</div>
        <span class="lf-bar-value" id="lf-bar-value">5</span>
      </div>
      <label class="lf-label">${_T('sym.log.label.frequency')}</label>
      <div class="lf-freq-wrap">
        <button class="lf-freq-btn" onclick="adjustFreq(-1)" type="button">−</button>
        <span class="lf-freq-num" id="lf-freq">1</span>
        <button class="lf-freq-btn" onclick="adjustFreq(1)" type="button">+</button>
        <span class="lf-freq-unit">${_T('sym.log.unit.times')}</span>
      </div>
      <label class="lf-label">${_T('sym.other.label.notesAdv')}</label>
      <textarea id="lf-notes" placeholder="${_T('sym.other.placeholder.notes')}" rows="2"></textarea>
      <div class="lf-actions">
        <button class="primary-btn" onclick="submitOtherSymptomLog()" type="button">
          <i data-lucide="check"></i><span>${_T('sym.log.btn.add')}</span>
        </button>
        <button class="secondary-btn" onclick="cancelSymptomLog()" type="button">${_T('sym.log.btn.cancel')}</button>
      </div>
    </div>
  `;
  form.style.display = 'block';
  if (typeof lucide !== 'undefined') lucide.createIcons();
  _prefillBodyPartNote();
  form.scrollIntoView({ behavior: 'smooth', block: 'start' });
  setTimeout(() => { const i = document.getElementById('lf-custom-name'); if (i) i.focus(); }, 100);
}

function submitOtherSymptomLog() {
  const name = (document.getElementById('lf-custom-name').value || '').trim();
  if (!name) {
    showToast && showToast(_T('sym.toast.needName'), 'warning');
    document.getElementById('lf-custom-name').focus();
    return;
  }
  const cat = addCustomSymptomCat(name);
  if (!cat) return;
  const intensity = parseInt(document.getElementById('lf-intensity').value);
  const frequency = parseInt(document.getElementById('lf-freq').textContent);
  const notes = document.getElementById('lf-notes').value.trim();
  saveSymptomEntry({
    id: 'sym-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8),
    categoryId: cat.id, intensity, frequency, notes,
    recordedAt: new Date().toISOString()
  });
  showToast && showToast(_T('sym.toast.added'), 'success');
  showPage('symptoms');
}

function removeCustomSymptomCatAndRefresh(id) {
  if (!confirm(_T('sym.confirm.delCustom'))) return;
  removeCustomSymptomCat(id);
  showPage('symptoms');
}
function updateIntensityBar(v) {
  document.getElementById('lf-bar').innerHTML = renderIntensityBar(v);
  document.getElementById('lf-bar-value').textContent = v;
}
function adjustFreq(delta) {
  const el = document.getElementById('lf-freq');
  el.textContent = Math.max(1, parseInt(el.textContent || '1') + delta);
}
function submitSymptomLog(catId) {
  const intensity = parseInt(document.getElementById('lf-intensity').value);
  const frequency = parseInt(document.getElementById('lf-freq').textContent);
  const notes = document.getElementById('lf-notes').value.trim();
  saveSymptomEntry({
    id: 'sym-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8),
    categoryId: catId, intensity, frequency, notes,
    recordedAt: new Date().toISOString()
  });
  showPage('symptoms');
}
function deleteSymptomEntryAndRefresh(id) {
  if (!confirm(_T('sym.confirm.delEntry'))) return;
  deleteSymptomEntry(id);
  showPage('symptoms');
}
function renderIntensityBar(v) {
  v = parseInt(v) || 0;
  const blocks = ['▁','▂','▂','▃','▃','▄','▄','▅','▆','█'];
  let out = '';
  for (let i = 0; i < 10; i++) {
    out += i < v
      ? `<span class="ib-on">${blocks[i]}</span>`
      : `<span class="ib-off">${blocks[i]}</span>`;
  }
  return out;
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
// 患者端期間累計（純文字摘要，不含趨勢圖 — 趨勢圖屬於醫師端）
function renderPeriodSummary(stats) {
  const sorted = Object.entries(stats.byCategory).sort((a, b) => b[1].count - a[1].count);
  if (sorted.length === 0) {
    return `<p class="sym-empty">${_T('sym.summary.empty')}</p>`;
  }
  return `
    <p class="sym-instruct">${_T('sym.summary.instruct')}</p>
    <ul class="sym-summary-list">
      ${sorted.map(([id, s]) => {
        const c = findSymptomCat(id);
        const avg = (s.intensitySum / s.count).toFixed(1);
        const color = c?.color || 'mint';
        return `
          <li class="sym-summary-row">
            <span class="ssr-name scc-${color}">${c ? _symField(c, 'zh') : id}</span>
            <span class="ssr-count">${_Tf('sym.summary.times', { n: s.count })}</span>
            <span class="ssr-avg">${_Tf('sym.summary.avg', { v: avg })}</span>
          </li>
        `;
      }).join('')}
    </ul>
  `;
}
function openVisitDatePrompt() {
  const v = getVisitDates();
  // 移除舊的（如果有）
  const old = document.getElementById('visit-date-modal');
  if (old) old.remove();

  const overlay = document.createElement('div');
  overlay.id = 'visit-date-modal';
  overlay.className = 'visit-modal-overlay';
  // 把當前 app 主題複製到 overlay，讓 modal 顯示對應的深/淺色
  const appTheme = document.getElementById('app-wrapper')?.dataset.theme || 'light';
  overlay.dataset.theme = appTheme;
  // 注意：日期值用 setAttribute 設定（避免 XSS），不要插值進 innerHTML
  overlay.innerHTML = `
    <div class="visit-modal" role="dialog" aria-labelledby="visit-modal-title">
      <header class="visit-modal-head">
        <h3 id="visit-modal-title"><i data-lucide="calendar-cog"></i> ${_T('sym.visit.title')}</h3>
        <button class="visit-modal-close" type="button" aria-label="${_T('sym.visit.close')}">×</button>
      </header>
      <div class="visit-modal-body">
        <label class="visit-modal-field">
          <span>${_T('sym.visit.label.last')}</span>
          <input type="date" id="vm-last" />
          <button type="button" class="visit-modal-clear" data-clear="vm-last">${_T('sym.visit.btn.clear')}</button>
        </label>
        <label class="visit-modal-field">
          <span>${_T('sym.visit.label.next')}</span>
          <input type="date" id="vm-next" />
          <button type="button" class="visit-modal-clear" data-clear="vm-next">${_T('sym.visit.btn.clear')}</button>
        </label>
        <p class="visit-modal-hint">${_T('sym.visit.hint')}</p>
      </div>
      <footer class="visit-modal-foot">
        <button type="button" class="visit-modal-cancel">${_T('sym.visit.btn.cancel')}</button>
        <button type="button" class="visit-modal-save"><i data-lucide="check"></i> ${_T('sym.visit.btn.save')}</button>
      </footer>
    </div>
  `;
  document.body.appendChild(overlay);
  // 用 .value 賦值，瀏覽器會驗證日期字串、不會被當 HTML 處理
  overlay.querySelector('#vm-last').value = v.lastVisit || '';
  overlay.querySelector('#vm-next').value = v.nextVisit || '';
  if (typeof lucide !== 'undefined') lucide.createIcons();

  const close = () => overlay.remove();
  overlay.querySelector('.visit-modal-close').onclick = close;
  overlay.querySelector('.visit-modal-cancel').onclick = close;
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  overlay.querySelectorAll('.visit-modal-clear').forEach(btn => {
    btn.onclick = () => { document.getElementById(btn.dataset.clear).value = ''; };
  });
  overlay.querySelector('.visit-modal-save').onclick = () => {
    const lastVisit = document.getElementById('vm-last').value || null;
    const nextVisit = document.getElementById('vm-next').value || null;
    saveVisitDates({ lastVisit, nextVisit });
    close();
    // 留在原頁，重新渲染當前頁以反映新日期
    const currentPage = document.getElementById('app')?.getAttribute('data-page') || 'symptoms';
    const slugToPage = { 'your-pieces': 'pieces', 'symptoms': 'symptoms' };
    showPage(slugToPage[currentPage] || 'symptoms');
  };
}

// ═══════════════════════════════════════════════════════════
// 生理紀錄（VITALS）— 9 預設 + 自訂、BP 雙欄、BMI 自動算、歷史
// ═══════════════════════════════════════════════════════════

const VITAL_METRICS = [
  { id:'weight',  zh:'體重', icon:'weight',      unit:'kg',    range:[10,300], step:0.1, color:'mint' },
  { id:'height',  zh:'身高', icon:'ruler',       unit:'cm',    range:[50,250], step:0.5, color:'aqua' },
  { id:'bmi',     zh:'BMI',  icon:'gauge',       unit:'',      calc:true,                color:'pink' },
  { id:'bp',      zh:'血壓', icon:'heart-pulse', unit:'mmHg',  dual:true,                color:'pink' },
  { id:'glucose', zh:'血糖', icon:'droplet',     unit:'mg/dL', range:[40,500], step:1,   color:'blue' },
  { id:'heart',   zh:'心率', icon:'activity',    unit:'bpm',   range:[30,220], step:1,   color:'pink' },
  { id:'temp',    zh:'體溫', icon:'thermometer', unit:'°C',    range:[33,42],  step:0.1, color:'pink' },
  { id:'spo2',    zh:'血氧', icon:'wind',        unit:'%',     range:[70,100], step:1,   color:'aqua' },
  { id:'waist',   zh:'腰圍', icon:'circle',      unit:'cm',    range:[40,200], step:0.5, color:'mint' },
];

const DEFAULT_TRACKED = ['weight','bp','heart','glucose'];

function getTrackedMetricIds() {
  try {
    const raw = localStorage.getItem('mdpiece_vitals_tracked');
    if (raw === null) return DEFAULT_TRACKED.slice();
    return JSON.parse(raw);
  } catch { return DEFAULT_TRACKED.slice(); }
}
function setTrackedMetricIds(ids) {
  localStorage.setItem('mdpiece_vitals_tracked', JSON.stringify(ids));
}
function getCustomMetrics() {
  try { return JSON.parse(localStorage.getItem('mdpiece_vitals_custom') || '[]'); }
  catch { return []; }
}
function saveCustomMetric(m) {
  const arr = getCustomMetrics();
  arr.push(m);
  localStorage.setItem('mdpiece_vitals_custom', JSON.stringify(arr));
}
function deleteCustomMetric(id) {
  localStorage.setItem('mdpiece_vitals_custom',
    JSON.stringify(getCustomMetrics().filter(m => m.id !== id)));
  // also remove from tracked
  setTrackedMetricIds(getTrackedMetricIds().filter(x => x !== id));
}
function getAllMetrics() {
  return VITAL_METRICS.concat(getCustomMetrics().map(m => ({ ...m, custom: true, color: m.color || 'blue' })));
}
function findMetric(id) {
  return getAllMetrics().find(m => m.id === id);
}

function getVitalEntries() {
  try { return JSON.parse(localStorage.getItem('mdpiece_vitals_entries') || '[]'); }
  catch { return []; }
}
function saveVitalEntry(e) {
  const arr = getVitalEntries();
  arr.push(e);
  localStorage.setItem('mdpiece_vitals_entries', JSON.stringify(arr));
}
function deleteVitalEntry(id) {
  localStorage.setItem('mdpiece_vitals_entries',
    JSON.stringify(getVitalEntries().filter(e => e.id !== id)));
}
function getLatestEntry(metricId) {
  const arr = getVitalEntries().filter(e => e.metricId === metricId);
  if (arr.length === 0) return null;
  arr.sort((a, b) => new Date(b.recordedAt) - new Date(a.recordedAt));
  return arr[0];
}
function calculateBMI() {
  const w = getLatestEntry('weight'), h = getLatestEntry('height');
  if (!w || !h) return null;
  const wKg = parseFloat(w.value);
  const hM = parseFloat(h.value) / 100;
  if (!wKg || !hM) return null;
  return (wKg / (hM * hM)).toFixed(1);
}

function vitals() {
  const tracked = getTrackedMetricIds();
  const allMetrics = getAllMetrics();
  const trackedMetrics = tracked.map(id => allMetrics.find(m => m.id === id)).filter(Boolean);
  const totalEntries = getVitalEntries().length;
  const allEntries = getVitalEntries();
  const latestAcross = allEntries.sort((a,b) => new Date(b.recordedAt) - new Date(a.recordedAt))[0];
  const lastUpdate = latestAcross ? new Date(latestAcross.recordedAt) : null;
  const lastUpdateStr = lastUpdate ? `${(lastUpdate.getMonth()+1)}/${lastUpdate.getDate()} ${lastUpdate.toTimeString().slice(0,5)}` : '—';
  // 今日進度：追蹤項目中今日已記錄的 distinct metric 數
  const todayKey = new Date().toISOString().slice(0,10);
  const todayMetricIds = new Set(allEntries.filter(e => (e.recordedAt || '').slice(0,10) === todayKey).map(e => e.metricId));
  const todayCovered = tracked.filter(id => todayMetricIds.has(id)).length;
  const totalToday = tracked.length || 0;
  const pctToday = totalToday ? Math.min(100, Math.round((todayCovered / totalToday) * 100)) : 0;
  const todayStatus = totalToday === 0
    ? '先到下方勾選你要追蹤的指標'
    : (todayCovered === totalToday ? '今日追蹤全部完成 ✨' : `${todayCovered} / ${totalToday} 項已記錄 · 還剩 ${totalToday - todayCovered}`);

  return `
    <div class="sym-page">

      <div class="page-app-hero page-app-hero-blue">
        <div class="page-app-hero-head">
          <span class="page-app-hero-eyebrow">TODAY · 今日生理紀錄</span>
          <span class="page-app-hero-warn"><i data-lucide="info" style="width:11px;height:11px"></i> 異常數值請就醫確認</span>
        </div>
        <div class="page-app-hero-title">${todayStatus}</div>
        <div class="page-app-hero-bar"><div class="page-app-hero-bar-fill" style="width:${pctToday}%"></div></div>
      </div>

      <section class="term-section">
        <header class="ts-head">
          <span class="ts-prompt">本期概況</span>
          <span class="ts-tag">生理紀錄總覽</span>
        </header>
        <div class="ts-body">
          <div class="ts-stat-grid">
            <div class="ts-stat">
              <span class="ts-stat-label">追蹤中</span>
              <span class="ts-stat-num">${trackedMetrics.length}</span>
              <span class="ts-stat-unit">項指標</span>
            </div>
            <div class="ts-stat">
              <span class="ts-stat-label">總紀錄</span>
              <span class="ts-stat-num">${totalEntries}</span>
              <span class="ts-stat-unit">筆</span>
            </div>
            <div class="ts-stat">
              <span class="ts-stat-label">自訂指標</span>
              <span class="ts-stat-num">${getCustomMetrics().length}</span>
              <span class="ts-stat-unit">項</span>
            </div>
            <div class="ts-stat">
              <span class="ts-stat-label">上次更新</span>
              <span class="ts-stat-num sm">${lastUpdateStr}</span>
              <span class="ts-stat-unit">${lastUpdate ? '已記錄' : '尚無紀錄'}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="term-section">
        <header class="ts-head">
          <span class="ts-prompt">選要追蹤的項目</span>
          <span class="ts-tag">${tracked.length} selected</span>
        </header>
        <div class="ts-body">
          <p class="sym-instruct">勾選你要追蹤的指標（可隨時調整）：</p>
          <div class="vt-toggle-grid">
            ${allMetrics.map(m => {
              const on = tracked.includes(m.id);
              return `
                <button class="vt-toggle ${on ? 'on' : ''}" onclick="toggleVitalTracked('${m.id}')" type="button">
                  <span class="vt-toggle-icon scc-${m.color}"><i data-lucide="${m.icon}"></i></span>
                  <span class="vt-toggle-name">${m.zh}${m.unit ? ` <small>${m.unit}</small>` : ''}</span>
                  <span class="vt-toggle-check">${on ? '✓' : ''}</span>
                  ${m.custom ? `<button type="button" class="vt-cm-del" onclick="deleteCustomMetricAndRefresh(event,'${m.id}')" title="刪除自訂指標" aria-label="刪除自訂指標「${escapeHtml(m.zh || m.id)}」">×</button>` : ''}
                </button>
              `;
            }).join('')}
          </div>
          <div class="vt-add-custom">
            <span class="vt-add-prompt">$ add-metric</span>
            <input id="vt-custom-name" placeholder="名稱（例：尿酸、步數、視力）" maxlength="20" />
            <select id="vt-custom-unit" class="vt-unit-select">
              <option value="">— 無單位 —</option>
              <optgroup label="醫療數值">
                <option value="mg/dL">mg/dL（血糖、膽固醇）</option>
                <option value="mmol/L">mmol/L（血糖）</option>
                <option value="mmHg">mmHg（血壓）</option>
                <option value="bpm">bpm（每分鐘心跳）</option>
                <option value="IU">IU（國際單位）</option>
              </optgroup>
              <optgroup label="百分比">
                <option value="%">%（百分比、血氧）</option>
              </optgroup>
              <optgroup label="重量">
                <option value="kg">kg（公斤）</option>
                <option value="g">g（公克）</option>
                <option value="lb">lb（磅）</option>
              </optgroup>
              <optgroup label="長度">
                <option value="cm">cm（公分）</option>
                <option value="mm">mm（毫米）</option>
                <option value="m">m（公尺）</option>
              </optgroup>
              <optgroup label="體積／容量">
                <option value="ml">ml（毫升）</option>
                <option value="cc">cc（立方公分）</option>
                <option value="L">L（公升）</option>
                <option value="杯">杯</option>
                <option value="瓶">瓶</option>
              </optgroup>
              <optgroup label="溫度">
                <option value="°C">°C（攝氏）</option>
                <option value="°F">°F（華氏）</option>
              </optgroup>
              <optgroup label="次數／數量">
                <option value="次">次</option>
                <option value="步">步</option>
                <option value="顆">顆</option>
                <option value="片">片</option>
                <option value="包">包</option>
              </optgroup>
              <optgroup label="時間">
                <option value="分鐘">分鐘</option>
                <option value="小時">小時</option>
                <option value="天">天</option>
              </optgroup>
              <optgroup label="能量">
                <option value="kcal">kcal（大卡）</option>
              </optgroup>
              <optgroup label="評級">
                <option value="級">級</option>
                <option value="分">分（評分）</option>
                <option value="星">星</option>
              </optgroup>
            </select>
            <button class="primary-btn vt-small-btn" onclick="addCustomMetricUI()" type="button">
              <i data-lucide="plus"></i><span>新增</span>
            </button>
          </div>
        </div>
      </section>

      <section class="term-section" id="vt-logform" style="display:none">
        <header class="ts-head">
          <span class="ts-prompt">加一筆紀錄</span>
          <span class="ts-tag" id="vt-logform-tag">—</span>
        </header>
        <div class="ts-body" id="vt-logform-body"></div>
      </section>

      <section class="term-section">
        <header class="ts-head">
          <span class="ts-prompt">最近一次紀錄</span>
          <span class="ts-tag">各項最新值</span>
        </header>
        <div class="ts-body">
          ${trackedMetrics.length === 0 ? `
            <p class="sym-empty">// 還沒有追蹤任何指標 — 上面勾選一個開始。</p>
          ` : `
            <div class="vt-snapshot-grid">
              ${trackedMetrics.map(m => renderVitalSnapshotCard(m)).join('')}
            </div>
          `}
        </div>
      </section>

      <section class="term-section">
        <header class="ts-head">
          <span class="ts-prompt">近 30 筆紀錄</span>
          <span class="ts-tag">歷史</span>
        </header>
        <div class="ts-body">
          ${renderVitalHistory()}
        </div>
      </section>

    </div>
  `;
}

function renderVitalSnapshotCard(m) {
  const latest = getLatestEntry(m.id);
  let valDisplay, timeStr = '尚無紀錄', isBmi = m.id === 'bmi';
  if (m.id === 'bmi') {
    const bmi = calculateBMI();
    if (bmi) {
      valDisplay = `<span class="vt-val">${bmi}</span>`;
      timeStr = '依最新身高/體重計算';
    } else {
      valDisplay = `<span class="vt-val sm">—</span>`;
      timeStr = '需要身高與體重';
    }
  } else if (latest) {
    if (m.dual) {
      valDisplay = `<span class="vt-val">${latest.value}/${latest.value2}</span><span class="vt-unit">${m.unit}</span>`;
    } else {
      valDisplay = `<span class="vt-val">${latest.value}</span><span class="vt-unit">${m.unit || ''}</span>`;
    }
    const d = new Date(latest.recordedAt);
    const today = new Date(); today.setHours(0,0,0,0);
    const dDay = new Date(d); dDay.setHours(0,0,0,0);
    const diffDays = Math.round((today - dDay) / 86400000);
    if (diffDays === 0) timeStr = `今天 ${d.toTimeString().slice(0,5)}`;
    else if (diffDays === 1) timeStr = `昨天 ${d.toTimeString().slice(0,5)}`;
    else timeStr = `${diffDays} 天前`;
  } else {
    valDisplay = `<span class="vt-val sm">—</span>`;
  }
  return `
    <div class="vt-snap scc-${m.color}-bd">
      <div class="vt-snap-head">
        <span class="vt-snap-icon scc-${m.color}"><i data-lucide="${m.icon}"></i></span>
        <span class="vt-snap-name">${m.zh}</span>
      </div>
      <div class="vt-snap-body">
        ${valDisplay}
      </div>
      <div class="vt-snap-foot">
        <span class="vt-snap-time">${timeStr}</span>
        <button class="vt-rec-btn" onclick="openVitalLog('${m.id}')" type="button">
          ${isBmi ? '計算' : '記一筆'}
        </button>
      </div>
    </div>
  `;
}

function renderVitalHistory() {
  const all = getVitalEntries().slice().sort((a, b) => new Date(b.recordedAt) - new Date(a.recordedAt));
  if (all.length === 0) {
    return '<p class="sym-empty">// 還沒有任何紀錄 — 點上面快覽卡片的「記一筆」開始。</p>';
  }
  const filterMetric = window.__vtFilter || 'all';
  const filtered = filterMetric === 'all' ? all : all.filter(e => e.metricId === filterMetric);
  const allMetrics = getAllMetrics();
  const filterOptions = '<option value="all">全部指標</option>' +
    allMetrics.map(m => `<option value="${m.id}" ${filterMetric === m.id ? 'selected' : ''}>${m.zh}</option>`).join('');
  const rows = filtered.slice(0, 30).map(e => {
    const m = allMetrics.find(x => x.id === e.metricId);
    const d = new Date(e.recordedAt);
    const dateStr = `${d.getFullYear()}/${(d.getMonth()+1).toString().padStart(2,'0')}/${d.getDate().toString().padStart(2,'0')} ${d.toTimeString().slice(0,5)}`;
    const valStr = m?.dual ? `${e.value}/${e.value2}` : `${e.value}`;
    return `
      <li class="vt-hist-row">
        <span class="vh-date">${dateStr}</span>
        <span class="vh-name scc-${m?.color || 'blue'}">${m?.zh || e.metricId}</span>
        <span class="vh-val"><strong>${valStr}</strong> <small>${m?.unit || ''}</small></span>
        ${e.notes ? `<span class="vh-notes">${escapeHtml(e.notes)}</span>` : ''}
        <button class="se-del" onclick="deleteVitalEntryAndRefresh('${e.id}')" title="刪除">×</button>
      </li>
    `;
  }).join('');
  return `
    <div class="vt-hist-filter">
      <label class="vt-hist-label">$ filter</label>
      <select class="vt-hist-select" onchange="setVitalFilter(this.value)">
        ${filterOptions}
      </select>
      <span class="vt-hist-count">${filtered.length} 筆</span>
    </div>
    <ul class="vt-hist-list">${rows}</ul>
  `;
}

function setVitalFilter(v) {
  window.__vtFilter = v;
  showPage('vitals');
}

function toggleVitalTracked(id) {
  const cur = getTrackedMetricIds();
  const next = cur.includes(id) ? cur.filter(x => x !== id) : cur.concat(id);
  setTrackedMetricIds(next);
  showPage('vitals');
}

function addCustomMetricUI() {
  const name = document.getElementById('vt-custom-name').value.trim();
  const unit = document.getElementById('vt-custom-unit').value.trim();
  if (!name) {
    if (typeof showToast === 'function') showToast('請先輸入指標名稱', 'warning');
    document.getElementById('vt-custom-name').focus();
    return;
  }
  const id = 'custom-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6);
  const colors = ['blue','aqua','mint','pink'];
  saveCustomMetric({
    id, zh: name, icon: 'tag', unit,
    color: colors[Math.floor(Math.random() * colors.length)]
  });
  // auto-track newly added
  setTrackedMetricIds(getTrackedMetricIds().concat(id));
  showPage('vitals');
}

function deleteCustomMetricAndRefresh(ev, id) {
  ev.stopPropagation();
  if (!confirm('刪除此自訂指標？已記錄的歷史會保留。')) return;
  deleteCustomMetric(id);
  showPage('vitals');
}

function openVitalLog(metricId) {
  const m = findMetric(metricId);
  if (!m) return;
  const form = document.getElementById('vt-logform');
  document.getElementById('vt-logform-tag').textContent = m.id + '.entry';
  let body = `
    <div class="lf-explain">
      <div class="lf-icon scc-${m.color}"><i data-lucide="${m.icon}"></i></div>
      <div class="lf-info">
        <h3>${m.zh}${m.unit ? ` <small style="opacity:0.7">${m.unit}</small>` : ''}</h3>
        <p class="lf-detail">輸入目前數值，可選填備註（例如：飯前/飯後、運動後）。</p>
      </div>
    </div>
    <div class="lf-form">
  `;
  if (m.id === 'bmi') {
    const bmi = calculateBMI();
    body += `
      <p class="vt-bmi-note">BMI 由最新身高與體重自動計算 — 不需要手動輸入。</p>
      <div class="vt-bmi-result">
        ${bmi ? `<span class="vt-val">${bmi}</span>` : '<span class="vt-val sm">尚無資料</span>'}
        <span class="vt-bmi-meta">${bmi ? interpretBMI(parseFloat(bmi)) : '請先記錄身高與體重'}</span>
      </div>
      <div class="lf-actions">
        ${bmi ? `<button class="primary-btn" onclick="saveBmiSnapshot('${bmi}')" type="button">
          <i data-lucide="bookmark"></i><span>記下這次的 BMI</span>
        </button>` : ''}
        <button class="secondary-btn" onclick="cancelVitalLog()" type="button">取消</button>
      </div>
    `;
  } else if (m.dual) {
    body += `
      <label class="lf-label">收縮壓 / 舒張壓 (${m.unit})</label>
      <div class="vt-dual-wrap">
        <input type="number" id="vt-val1" placeholder="例 120" min="40" max="260" step="1" />
        <span class="vt-dual-sep">/</span>
        <input type="number" id="vt-val2" placeholder="例 80" min="30" max="160" step="1" />
        <span class="vt-dual-unit">${m.unit}</span>
      </div>
      <label class="lf-label">備註（選填）</label>
      <textarea id="vt-notes" placeholder="例如：起床後測量、有運動..." rows="2"></textarea>
      <div class="lf-actions">
        <button class="primary-btn" onclick="submitVitalEntry('${m.id}')" type="button">
          <i data-lucide="check"></i><span>新增紀錄</span>
        </button>
        <button class="secondary-btn" onclick="cancelVitalLog()" type="button">取消</button>
      </div>
    `;
  } else {
    body += `
      <label class="lf-label">數值${m.unit ? ` (${m.unit})` : ''}</label>
      <input type="number" id="vt-val1" placeholder="輸入數值" ${m.range ? `min="${m.range[0]}" max="${m.range[1]}"` : ''} ${m.step ? `step="${m.step}"` : 'step="any"'} />
      <label class="lf-label">備註（選填）</label>
      <textarea id="vt-notes" placeholder="例如：飯前、運動後..." rows="2"></textarea>
      <div class="lf-actions">
        <button class="primary-btn" onclick="submitVitalEntry('${m.id}')" type="button">
          <i data-lucide="check"></i><span>新增紀錄</span>
        </button>
        <button class="secondary-btn" onclick="cancelVitalLog()" type="button">取消</button>
      </div>
    `;
  }
  body += `</div>`;
  document.getElementById('vt-logform-body').innerHTML = body;
  form.style.display = 'block';
  if (typeof lucide !== 'undefined') lucide.createIcons();
  form.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function cancelVitalLog() {
  const f = document.getElementById('vt-logform');
  if (f) f.style.display = 'none';
}

function submitVitalEntry(metricId) {
  const m = findMetric(metricId);
  if (!m) return;
  const v1 = document.getElementById('vt-val1').value;
  if (!v1) {
    if (typeof showToast === 'function') showToast('請先輸入數值', 'warning');
    document.getElementById('vt-val1').focus();
    return;
  }
  const entry = {
    id: 'vt-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8),
    metricId,
    value: parseFloat(v1),
    recordedAt: new Date().toISOString()
  };
  if (m.dual) {
    const v2 = document.getElementById('vt-val2').value;
    if (!v2) {
      if (typeof showToast === 'function') showToast('請完整輸入收縮 / 舒張壓', 'warning');
      document.getElementById('vt-val2').focus();
      return;
    }
    entry.value2 = parseFloat(v2);
  }
  const notes = document.getElementById('vt-notes').value.trim();
  if (notes) entry.notes = notes;
  saveVitalEntry(entry);
  showPage('vitals');
}

function saveBmiSnapshot(bmi) {
  saveVitalEntry({
    id: 'vt-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8),
    metricId: 'bmi',
    value: parseFloat(bmi),
    notes: 'auto-calculated',
    recordedAt: new Date().toISOString()
  });
  showPage('vitals');
}

function deleteVitalEntryAndRefresh(id) {
  if (!confirm('刪除這筆紀錄？')) return;
  deleteVitalEntry(id);
  showPage('vitals');
}

function interpretBMI(v) {
  if (v < 18.5) return '體重過輕';
  if (v < 24)   return '健康範圍';
  if (v < 27)   return '體重過重';
  if (v < 30)   return '輕度肥胖';
  if (v < 35)   return '中度肥胖';
  return '重度肥胖';
}

// ─── 症狀分析（獨立頁） ────────────────────────────────────
//
// 把症狀清單丟給 AI，回緊急程度 / 可能病因 / 建議科別 / 處置建議。
// 來源 1：使用者直接打字（comma 分隔）
// 來源 2：「從最近紀錄帶入」按鈕 — 從 getPeriodStats() 取近期 top symptoms
// 顯示：urgency badge、conditions list、recommended dept、advice、disclaimer
// 並列出 GET /symptoms/history/{patient_id} 的歷史分析

function symptomsAnalyze() {
  return `
    <div class="card">
      <h2>症狀分析</h2>
      <p style="margin-top:8px;color:var(--text-dim)">把現在的症狀寫下來，MD.Piece 會幫你分析可能病因、緊急程度與建議就診科別。</p>
      <p style="margin-top:4px;font-size:0.85rem;color:var(--text-muted)">⚠️ 結果僅供參考，<strong>不取代醫師診斷</strong>。如有嚴重不適請立即就醫或撥 119。</p>
    </div>

    <div class="card">
      <h3>輸入症狀</h3>
      <div style="margin-top:8px;display:flex;flex-direction:column;gap:8px">
        <textarea id="symptom-analyze-input"
          rows="3"
          placeholder="例：頭痛, 發燒 38.5度, 喉嚨痛, 全身痠痛"
          style="width:100%;padding:10px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text);font-family:inherit;resize:vertical"></textarea>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button class="primary" onclick="runSymptomAnalysis()">
            <i data-lucide="sparkles" style="width:14px;height:14px;vertical-align:middle"></i> 開始分析
          </button>
          <button class="secondary" onclick="fillSymptomsFromRecent()">
            <i data-lucide="history" style="width:14px;height:14px;vertical-align:middle"></i> 從最近紀錄帶入
          </button>
          <button class="secondary" onclick="document.getElementById('symptom-analyze-input').value=''">
            清空
          </button>
        </div>
      </div>
      <div id="symptom-analyze-result" style="margin-top:16px"></div>
    </div>

    <div class="card">
      <h3><i data-lucide="clock" style="width:18px;height:18px;vertical-align:middle"></i> 分析歷史</h3>
      <div id="symptom-analyze-history" style="margin-top:12px"><p style="color:var(--text-muted)">載入中...</p></div>
    </div>
  `;
}

function _symptomUrgency(level) {
  const map = {
    emergency: { label: "🚨 緊急", color: "#d6457e", bg: "rgba(214,69,126,0.12)" },
    high:      { label: "⚠️ 高",   color: "#e8889c", bg: "rgba(232,136,156,0.12)" },
    medium:    { label: "● 中",    color: "#d49a55", bg: "rgba(212,154,85,0.12)" },
    low:       { label: "● 低",    color: "#5b9fe8", bg: "rgba(91,159,232,0.12)" },
  };
  return map[level] || map.low;
}

function fillSymptomsFromRecent() {
  try {
    const stats = getPeriodStats();
    const top = [];
    for (const cid in stats.byCategory) {
      const cat = findSymptomCat(cid);
      if (cat) top.push({ name: cat.label || cat.name || cid, count: stats.byCategory[cid].count });
    }
    top.sort((a, b) => b.count - a.count);
    const names = top.slice(0, 5).map(t => t.name);
    if (!names.length) {
      showToast("最近沒有症狀紀錄可帶入", "info");
      return;
    }
    document.getElementById("symptom-analyze-input").value = names.join(", ");
  } catch (e) {
    showToast("帶入失敗", "error");
  }
}

var _saTypingTimer = null;
async function runSymptomAnalysis() {
  const input = document.getElementById("symptom-analyze-input").value;
  if (!input.trim()) {
    showToast("請先輸入症狀", "info");
    return;
  }
  const symptoms = input.split(/[,，、]/).map(s => s.trim()).filter(Boolean);
  if (!symptoms.length) {
    showToast("請輸入有效的症狀", "info");
    return;
  }
  const el = document.getElementById("symptom-analyze-result");
  el.innerHTML =
    '<div style="text-align:center;padding:20px;color:var(--text-muted)">' +
    '<div id="sa-typing-mascot" style="display:flex;justify-content:center">' + chatMascotSvg('typing', 0) + '</div>' +
    '<p style="margin-top:8px">小禾正在分析... 約 5-15 秒</p>' +
    '</div>';
  if (_saTypingTimer) { clearInterval(_saTypingTimer); _saTypingTimer = null; }
  let _saFrame = 0;
  _saTypingTimer = setInterval(() => {
    const w = document.getElementById('sa-typing-mascot');
    if (!w) { clearInterval(_saTypingTimer); _saTypingTimer = null; return; }
    _saFrame = (_saFrame + 1) % 2;
    w.innerHTML = chatMascotSvg('typing', _saFrame);
  }, 140);

  const pid = getStablePatientId();
  try {
    const res = await fetch(`${API}/symptoms/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symptoms, patient_id: pid }),
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error("HTTP " + res.status + ": " + txt.slice(0, 200));
    }
    const data = await res.json();
    if (_saTypingTimer) { clearInterval(_saTypingTimer); _saTypingTimer = null; }
    el.innerHTML = renderSymptomAnalysis(data);
    if (window.lucide && lucide.createIcons) try { lucide.createIcons(); } catch (_) {}
    // 重新載入歷史
    loadSymptomAnalysisHistory();
  } catch (e) {
    if (_saTypingTimer) { clearInterval(_saTypingTimer); _saTypingTimer = null; }
    el.innerHTML =
      '<div style="padding:14px;background:rgba(232,136,156,0.1);border-left:3px solid var(--danger);border-radius:var(--radius-sm)">' +
      '<strong>分析失敗</strong><br>' +
      '<span style="font-size:0.85rem;color:var(--text-muted)">' + escapeHtml(e.message || "未知錯誤") + '</span>' +
      '</div>';
  }
}

function renderSymptomAnalysis(data) {
  const u = _symptomUrgency(data.urgency);
  const conditions = (data.conditions || [])
    .map(c => {
      const name = escapeHtml(c.name || "");
      const desc = c.description ? `<div class="sa-cond-desc">${escapeHtml(c.description)}</div>` : '';
      const likelihood = c.likelihood ? `<span class="sa-cond-likelihood">可能性 ${escapeHtml(c.likelihood)}</span>` : '';
      const lookupBtn = c.name
        ? ` <button type="button" class="sa-cond-lookup"
              data-disease="${escapeHtml(c.name)}"
              onclick="navigateToDiseaseSearch(this.dataset.disease)"
              title="到疾病百科查詢更詳細的說明、用藥、風險">
              <i data-lucide="stethoscope" style="width:12px;height:12px"></i> 查更多
            </button>`
        : '';
      return `<li class="sa-cond"><div class="sa-cond-head"><strong>${name}</strong>${likelihood}${lookupBtn}</div>${desc}</li>`;
    })
    .join("");

  return `
    <div class="sa-urgency" style="border-left-color:${u.color};background:${u.bg}">
      <div class="sa-urgency-label" style="color:${u.color}">緊急程度：${u.label}</div>
    </div>
    <div class="sa-grid">
      <section class="sa-section">
        <h4 class="sa-section-title">可能的原因</h4>
        <ul class="sa-cond-list">${conditions || '<li class="sa-empty">需要醫師進一步評估</li>'}</ul>
      </section>
      <section class="sa-section">
        <h4 class="sa-section-title">建議看哪一科</h4>
        <p class="sa-text">${escapeHtml(data.recommended_department || "家醫科")}</p>
      </section>
      <section class="sa-section">
        <h4 class="sa-section-title">建議怎麼做</h4>
        <p class="sa-text">${escapeHtml(data.advice || "")}</p>
      </section>
      <p class="sa-disclaimer">
        ${escapeHtml(data.disclaimer || "這份分析僅供參考，不是診斷。如果不舒服或不確定，請直接就醫。")}
      </p>
    </div>
  `;
}

function loadSymptomAnalysisHistory() {
  const pid = getStablePatientId();
  const el = document.getElementById("symptom-analyze-history");
  if (!el) return;
  fetch(`${API}/symptoms/history/${pid}`)
    .then(r => r.ok ? r.json() : { history: [] })
    .then(data => {
      const items = (data.history || []).slice(0, 5);
      if (!items.length) {
        el.innerHTML = '<p style="color:var(--text-muted);font-size:0.9rem">尚無分析紀錄。完成第一次分析後會出現在這裡。</p>';
        return;
      }
      el.innerHTML = items.map(it => {
        const sx = (it.symptoms || []).join("、");
        const u = _symptomUrgency((it.ai_response || {}).urgency);
        const dept = (it.ai_response || {}).recommended_department || "—";
        const date = it.created_at ? new Date(it.created_at).toLocaleString("zh-TW", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
        return `
          <div style="padding:12px;background:var(--bg-glass);border-radius:var(--radius-sm);margin-bottom:8px">
            <div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start;flex-wrap:wrap">
              <div style="flex:1;min-width:0">
                <div style="font-size:0.9rem;color:var(--text)">${escapeHtml(sx)}</div>
                <div style="font-size:0.78rem;color:var(--text-muted);margin-top:4px">${escapeHtml(date)}・建議 ${escapeHtml(dept)}</div>
              </div>
              <span style="font-size:0.78rem;font-weight:600;color:${u.color}">${u.label}</span>
              <button type="button"
                onclick="deleteSymptomHistoryItem('${escapeHtml(it.id || "")}')"
                aria-label="刪除這筆紀錄"
                title="刪除這筆紀錄"
                style="background:none;border:none;cursor:pointer;padding:4px;color:var(--text-muted);display:inline-flex;align-items:center">
                <i data-lucide="trash-2" style="width:16px;height:16px"></i>
              </button>
            </div>
          </div>
        `;
      }).join("");
      if (window.lucide && lucide.createIcons) try { lucide.createIcons(); } catch (_) {}
    })
    .catch(() => {
      el.innerHTML = '<p style="color:var(--text-muted);font-size:0.9rem">無法載入歷史紀錄。</p>';
    });
}

async function deleteSymptomHistoryItem(logId) {
  if (!logId) return;
  if (!confirm("確定要刪除這筆分析紀錄？")) return;
  const pid = getStablePatientId();
  try {
    const res = await fetch(`${API}/symptoms/history/${pid}/${logId}`, { method: "DELETE" });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error("HTTP " + res.status + ": " + txt.slice(0, 200));
    }
    loadSymptomAnalysisHistory();
  } catch (e) {
    showToast("刪除失敗：" + (e.message || "未知錯誤"), "error");
  }
}

// 舊 inline 版（保留向後相容；新獨立頁是 symptomsAnalyze 上方）
async function analyzeSymptoms() {
  const input = document.getElementById("symptom-input").value;
  if (!input.trim()) return;
  const symptoms = input.split(",").map(s => s.trim()).filter(Boolean);
  const el = document.getElementById("analysis-result");
  el.innerHTML = '<div class="loading">分析中...</div>';

  try {
    const res = await fetch(`${API}/symptoms/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symptoms }),
    });
    const data = await res.json();

    const urgencyMap = {
      emergency: { label: "緊急", cls: "urgency-emergency" },
      high: { label: "高", cls: "urgency-high" },
      medium: { label: "中", cls: "urgency-medium" },
      low: { label: "低", cls: "urgency-low" },
    };
    const urg = urgencyMap[data.urgency] || urgencyMap.low;

    const conditions = (data.conditions || [])
      .map(c => `<li><strong>${c.name}</strong> — 可能性：${c.likelihood}</li>`)
      .join("");

    el.innerHTML = `
      <div class="ai-result-card">
        <div class="urgency-badge ${urg.cls}">緊急程度：${urg.label}</div>
        <h4>可能病因</h4>
        <ul>${conditions}</ul>
        <h4>建議科別</h4>
        <p>${data.recommended_department || "家醫科"}</p>
        <h4>建議</h4>
        <p>${data.advice || ""}</p>
        <div class="disclaimer">${data.disclaimer || "此分析僅供參考，不構成醫療診斷。如有不適請立即就醫。"}</div>
      </div>`;
  } catch (e) {
    el.innerHTML = '<div class="advice-box">分析失敗，請確認後端是否啟動。</div>';
  }
}

async function quickAdvice() {
  const input = document.getElementById("symptom-input").value.split(",")[0].trim();
  if (!input) return;
  const res = await fetch(`${API}/symptoms/advice?symptom=${encodeURIComponent(input)}`);
  const data = await res.json();
  document.getElementById("analysis-result").innerHTML =
    `<div class="advice-box"><strong>${data.symptom}</strong>：${data.advice}</div>`;
}

// ─── 醫師列表 ──────────────────────────────────────────────

function doctors() {
  return `
    <div class="card">
      <h2>${_T('doctors.add.title')}</h2>
      <input id="d-name" placeholder="${_T('doctors.placeholder.name')}" />
      <input id="d-specialty" placeholder="${_T('doctors.placeholder.specialty')}" />
      <input id="d-phone" placeholder="${_T('doctors.placeholder.phone')}" />
      <button class="primary" onclick="addDoctor()">${_T('doctors.add.submit')}</button>
    </div>
    <div class="card">
      <h2>${_T('doctors.list.title')}</h2>
      <div id="doctor-list"><p>${_T('doctors.list.loading')}</p></div>
    </div>`;
}

async function loadDoctors() {
  const res = await fetch(`${API}/doctors/`);
  const data = await res.json();
  const el = document.getElementById("doctor-list");
  if (!data.doctors?.length) {
    el.innerHTML = `<p>${_T('doctors.list.empty')}</p>`;
    return;
  }
  el.innerHTML = data.doctors.map(d => `
    <div class="record-card">
      <strong>${d.name}</strong> — ${d.specialty}
      ${d.phone ? `<span style="color:var(--text-dim)"> | ${d.phone}</span>` : ""}
      <button class="btn-delete" onclick="deleteDoctor('${d.id}')">${_T('doctors.delete')}</button>
    </div>
  `).join("");
}

async function addDoctor() {
  const name = document.getElementById("d-name").value;
  const specialty = document.getElementById("d-specialty").value;
  const phone = document.getElementById("d-phone").value || undefined;
  if (!name || !specialty) return;
  await fetch(`${API}/doctors/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, specialty, phone }),
  });
  loadDoctors();
  document.getElementById("d-name").value = "";
  document.getElementById("d-specialty").value = "";
  document.getElementById("d-phone").value = "";
}

async function deleteDoctor(id) {
  if (!confirm(_T('doctors.delete.confirm'))) return;
  await fetch(`${API}/doctors/${id}`, { method: "DELETE" });
  loadDoctors();
}

// ─── 我的基本資料 ──────────────────────────────────────────
// 存 localStorage：性別 / 生日 / 身高 / 體重 / 血型 / 過敏 / 慢性病 / 緊急聯絡人
// 看診時可一鍵複製給醫師，不取代帳號的暱稱頭像（那放在 /account）。

const BASIC_INFO_KEY = 'mdpiece_basic_info';

function getBasicInfo() {
  try { return JSON.parse(localStorage.getItem(BASIC_INFO_KEY)) || {}; }
  catch { return {}; }
}

function setBasicInfo(info) {
  localStorage.setItem(BASIC_INFO_KEY, JSON.stringify(info));
}

function calcAge(birthday) {
  if (!birthday) return '';
  const b = new Date(birthday);
  if (isNaN(b)) return '';
  const now = new Date();
  let age = now.getFullYear() - b.getFullYear();
  const m = now.getMonth() - b.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < b.getDate())) age--;
  return age >= 0 ? age + ' ' + _T('rec.unit.years') : '';
}

function calcBMI(h, w) {
  const hn = parseFloat(h), wn = parseFloat(w);
  if (!hn || !wn) return '';
  const bmi = wn / Math.pow(hn / 100, 2);
  return bmi.toFixed(1);
}

function records() {
  const info = getBasicInfo();
  const v = (k) => (info[k] || '').toString().replace(/"/g, '&quot;');
  return `
    <section class="card">
      <h2><i data-lucide="id-card"></i> ${_T('rec.title')}</h2>
      <p class="sub-hint">${_T('rec.subhint')}</p>
      <form class="basic-info-form" onsubmit="event.preventDefault(); saveBasicInfo();">
        <div class="bi-grid">
          <label class="bi-field">
            <span>${_T('rec.field.gender')}</span>
            <select id="bi-gender">
              <option value="">${_T('rec.opt.skip')}</option>
              <option value="male" ${info.gender === 'male' ? 'selected' : ''}>${_T('rec.opt.male')}</option>
              <option value="female" ${info.gender === 'female' ? 'selected' : ''}>${_T('rec.opt.female')}</option>
              <option value="other" ${info.gender === 'other' ? 'selected' : ''}>${_T('rec.opt.other')}</option>
            </select>
          </label>
          <label class="bi-field">
            <span>${_T('rec.field.birthday')}</span>
            <input id="bi-birthday" type="date" value="${v('birthday')}" onchange="document.getElementById('bi-age-display').textContent = (function(b){return calcAge(b);})(this.value)" />
            <small class="bi-hint" id="bi-age-display">${calcAge(info.birthday)}</small>
          </label>
          <label class="bi-field">
            <span>${_T('rec.field.blood')}</span>
            <select id="bi-blood">
              <option value="">${_T('rec.opt.skip')}</option>
              ${['A','B','O','AB','A+','A-','B+','B-','O+','O-','AB+','AB-'].map(t =>
                `<option value="${t}" ${info.blood === t ? 'selected' : ''}>${t}</option>`).join('')}
            </select>
          </label>
          <label class="bi-field">
            <span>${_T('rec.field.height')}</span>
            <input id="bi-height" type="number" min="0" max="300" step="0.1" value="${v('height')}"
              oninput="document.getElementById('bi-bmi-display').textContent = calcBMI(this.value, document.getElementById('bi-weight').value) ? 'BMI ' + calcBMI(this.value, document.getElementById('bi-weight').value) : ''" />
          </label>
          <label class="bi-field">
            <span>${_T('rec.field.weight')}</span>
            <input id="bi-weight" type="number" min="0" max="500" step="0.1" value="${v('weight')}"
              oninput="document.getElementById('bi-bmi-display').textContent = calcBMI(document.getElementById('bi-height').value, this.value) ? 'BMI ' + calcBMI(document.getElementById('bi-height').value, this.value) : ''" />
            <small class="bi-hint" id="bi-bmi-display">${calcBMI(info.height, info.weight) ? 'BMI ' + calcBMI(info.height, info.weight) : ''}</small>
          </label>
        </div>

        <label class="bi-field">
          <span>${_T('rec.field.allergies')}</span>
          <textarea id="bi-allergies" rows="2" placeholder="${_T('rec.placeholder.allergies')}" oninput="updateDetectedDiseases()">${v('allergies')}</textarea>
        </label>
        <label class="bi-field">
          <span>${_T('rec.field.conditions')}</span>
          <textarea id="bi-conditions" rows="2" placeholder="${_T('rec.placeholder.conditions')}" oninput="updateDetectedDiseases()">${v('conditions')}</textarea>
        </label>
        <label class="bi-field">
          <span>${_T('rec.field.currentDisease')}</span>
          <textarea id="bi-current-disease" rows="2" placeholder="${_T('rec.placeholder.currentDisease')}" oninput="updateDetectedDiseases()">${v('current_disease')}</textarea>
          <div id="bi-detected-diseases" class="bi-hint" style="margin-top:6px;font-size:.78rem;line-height:1.6;color:var(--text-dim)"></div>
        </label>
        <label class="bi-field">
          <span>${_T('rec.field.meds')}</span>
          <textarea id="bi-meds" rows="2" placeholder="${_T('rec.placeholder.meds')}">${v('meds')}</textarea>
        </label>

        <div class="bi-grid">
          <label class="bi-field">
            <span>${_T('rec.field.doctorName')}</span>
            <input id="bi-doctor-name" type="text" maxlength="30" placeholder="${_T('rec.placeholder.doctorName')}" value="${v('doctor_name')}" />
          </label>
          <label class="bi-field">
            <span>${_T('rec.field.hospital')}</span>
            <input id="bi-hospital" type="text" maxlength="50" placeholder="${_T('rec.placeholder.hospital')}" value="${v('hospital')}" />
          </label>
        </div>

        <div class="bi-grid">
          <label class="bi-field">
            <span>${_T('rec.field.emergencyName')}</span>
            <input id="bi-emergency-name" type="text" maxlength="30" value="${v('emergency_name')}" />
          </label>
          <label class="bi-field">
            <span>${_T('rec.field.emergencyPhone')}</span>
            <input id="bi-emergency-phone" type="tel" maxlength="20" value="${v('emergency_phone')}" />
          </label>
        </div>

        <p class="acct-msg" id="bi-msg" hidden></p>
        <div class="bi-actions">
          <button type="submit" class="primary"><i data-lucide="save"></i> ${_T('rec.btn.save')}</button>
          <button type="button" class="btn-quiet" onclick="copyBasicInfo()"><i data-lucide="clipboard-copy"></i> ${_T('rec.btn.copy')}</button>
        </div>
      </form>
    </section>`;
}

function loadRecordsPage() {
  if (typeof lucide !== 'undefined') lucide.createIcons();
  if (typeof updateDetectedDiseases === 'function') updateDetectedDiseases();
}

// 從基本資料三個自由文字欄位即時辨識疾病，並把易讀名稱顯示成 pill
function updateDetectedDiseases() {
  var pillsEl = document.getElementById('bi-detected-diseases');
  if (!pillsEl) return;
  var current = document.getElementById('bi-current-disease');
  var conditions = document.getElementById('bi-conditions');
  var allergies = document.getElementById('bi-allergies');
  var combined = [
    current && current.value,
    conditions && conditions.value,
    allergies && allergies.value
  ].filter(Boolean).join('\n');
  var codes = (typeof detectIcd10FromText === 'function') ? detectIcd10FromText(combined) : [];
  if (!codes.length) {
    pillsEl.innerHTML = '<span style="color:var(--text-dim)">提示：寫日常用語就行（例：「糖尿病、高血壓、骨鬆」），系統會自動帶進「衛教」頁的我的疾病書架。</span>';
    return;
  }
  pillsEl.innerHTML = '<i data-lucide="sparkles" style="width:12px;height:12px;vertical-align:middle"></i> 自動辨識：' +
    codes.map(function(c) {
      var name = (typeof bestNameForIcd10 === 'function') ? bestNameForIcd10(c) : c;
      return '<span style="display:inline-block;margin:2px 4px 2px 0;padding:2px 10px;border-radius:10px;background:var(--bg-soft);color:var(--text);font-size:.78rem">' +
             escapeHtml(name) + '</span>';
    }).join('');
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function saveBasicInfo() {
  const info = {
    gender: document.getElementById('bi-gender').value,
    birthday: document.getElementById('bi-birthday').value,
    blood: document.getElementById('bi-blood').value,
    height: document.getElementById('bi-height').value,
    weight: document.getElementById('bi-weight').value,
    allergies: document.getElementById('bi-allergies').value.trim(),
    conditions: document.getElementById('bi-conditions').value.trim(),
    current_disease: document.getElementById('bi-current-disease').value.trim(),
    meds: document.getElementById('bi-meds').value.trim(),
    doctor_name: document.getElementById('bi-doctor-name').value.trim(),
    hospital: document.getElementById('bi-hospital').value.trim(),
    emergency_name: document.getElementById('bi-emergency-name').value.trim(),
    emergency_phone: document.getElementById('bi-emergency-phone').value.trim(),
  };
  setBasicInfo(info);

  // 自動辨識疾病 → user.icd10_codes，衛教頁的「我的疾病書架」就會出現
  if (typeof detectIcd10FromText === 'function') {
    var combined = [info.current_disease, info.conditions, info.allergies].filter(Boolean).join('\n');
    var codes = detectIcd10FromText(combined);
    var u = getCurrentUser();
    // 只在真的有登入帳號時才寫回 user 物件，避免造出 id-less 假 user
    // 干擾 /auth/user/{id} 等帳號 API。Guest/demo 的書架還是會走
    // resolvePatientIcd10Codes 的 basicInfo fallback，所以不會壞掉。
    if (u && u.id) {
      u.icd10_codes = codes;
      setCurrentUser(u);
    }
  }

  const msg = document.getElementById('bi-msg');
  if (msg) {
    msg.textContent = _T('rec.msg.savedLocal');
    msg.hidden = false;
    setTimeout(() => { msg.hidden = true; }, 2000);
  }
  showToast && showToast(_T('rec.toast.saved'), 'success');
}

function copyBasicInfo() {
  const info = getBasicInfo();
  const u = getCurrentUser() || {};
  const lines = [_T('rec.copy.header')];
  if (u.nickname) lines.push(_T('rec.copy.name') + u.nickname);
  const genderMap = { male: _T('rec.opt.male'), female: _T('rec.opt.female'), other: _T('rec.opt.other') };
  if (info.gender) lines.push(_T('rec.copy.gender') + (genderMap[info.gender] || info.gender));
  if (info.birthday) {
    const age = calcAge(info.birthday);
    lines.push(_T('rec.copy.birthday') + info.birthday + (age ? '（' + age + '）' : ''));
  }
  if (info.blood) lines.push(_T('rec.copy.blood') + info.blood);
  if (info.height) lines.push(_T('rec.copy.height') + info.height + ' cm');
  if (info.weight) lines.push(_T('rec.copy.weight') + info.weight + ' kg');
  const bmi = calcBMI(info.height, info.weight);
  if (bmi) lines.push('BMI：' + bmi);
  if (info.allergies) lines.push(_T('rec.copy.allergies') + info.allergies);
  if (info.conditions) lines.push(_T('rec.copy.conditions') + info.conditions);
  if (info.current_disease) lines.push(_T('rec.copy.currentDisease') + info.current_disease);
  if (info.meds) lines.push(_T('rec.copy.meds') + info.meds);
  if (info.doctor_name || info.hospital) {
    lines.push(_T('rec.copy.doctorName') + [info.doctor_name, info.hospital].filter(Boolean).join('｜'));
  }
  if (info.emergency_name || info.emergency_phone) {
    lines.push(_T('rec.copy.emergency') + [info.emergency_name, info.emergency_phone].filter(Boolean).join(' '));
  }
  if (lines.length === 1) {
    showToast && showToast(_T('rec.toast.empty'), 'warning');
    return;
  }
  const text = lines.join('\n');
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(
      () => showToast && showToast(_T('rec.toast.copied'), 'success'),
      () => showToast && showToast(_T('rec.toast.copyFail'), 'warning')
    );
  } else {
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); showToast && showToast(_T('rec.toast.copied'), 'success'); }
    catch { showToast && showToast(_T('rec.toast.copyFail'), 'warning'); }
    document.body.removeChild(ta);
  }
}

// ─── Toast 通知 ──────────────────────────────────────────

function showToast(msg, type) {
  type = type || "info";
  var existing = document.getElementById("toast-container");
  if (!existing) {
    existing = document.createElement("div");
    existing.id = "toast-container";
    existing.style.cssText = "position:fixed;top:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px";
    document.body.appendChild(existing);
  }
  var colors = { success: "#00D4AA", error: "#D94D4D", info: "#2B5CE6", warning: "#E8A84B" };
  var toast = document.createElement("div");
  toast.style.cssText = "padding:12px 20px;border-radius:8px;color:white;font-size:0.9rem;box-shadow:0 4px 12px rgba(0,0,0,0.2);transition:opacity 0.3s;max-width:360px;background:" + (colors[type] || colors.info);
  toast.textContent = msg;
  existing.appendChild(toast);
  setTimeout(function() { toast.style.opacity = "0"; setTimeout(function() { toast.remove(); }, 300); }, 3000);
}

// ─── 藥物管理 ─────────────────────────────────────────────

var _medsList = [];
var _medsPatientId = null;

function medications() {
  var user = getCurrentUser();
  _medsPatientId = getStablePatientId();
  return `
    <div class="card">
      <h2>${_T('meds.title')}</h2>
      <p style="margin-top:8px;color:var(--text-dim)">${_T('meds.intro.prefix')}<strong>${_T('meds.intro.bold')}</strong>${_T('meds.intro.suffix')}</p>
    </div>
    ${renderHowto('meds')}
    <div class="card">
      <h3><i data-lucide="camera" style="width:18px;height:18px;vertical-align:middle"></i> ${_T('meds.recognize.title')}</h3>
      <p style="margin-top:4px;color:var(--text-dim);font-size:0.9rem">${_T('meds.recognize.desc.prefix')}<strong>${_T('meds.recognize.desc.bold')}</strong>${_T('meds.recognize.desc.suffix')}</p>
      <div style="margin-top:10px;padding:10px 12px;background:rgba(100,140,200,0.08);border-radius:var(--radius-sm);border:1px solid rgba(100,140,200,0.2);font-size:0.85rem;color:var(--text-dim)">
        <strong style="color:var(--text-main);font-size:0.85rem">${_T('meds.tips.title')}</strong>
        <ul style="margin:6px 0 0 16px;padding:0;line-height:1.6">
          <li>${_T('meds.tips.1.prefix')}<strong>${_T('meds.tips.1.bold')}</strong>${_T('meds.tips.1.suffix')}</li>
          <li>${_T('meds.tips.2')}</li>
          <li>${_T('meds.tips.3.prefix')}<strong>${_T('meds.tips.3.bold')}</strong>${_T('meds.tips.3.suffix')}</li>
          <li>${_T('meds.tips.4')}</li>
        </ul>
      </div>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
        <button class="primary" onclick="document.getElementById('med-camera').click()">
          <i data-lucide="camera" style="width:14px;height:14px;vertical-align:middle"></i> ${_T('meds.btn.capture')}
        </button>
        <button class="secondary" onclick="document.getElementById('med-upload').click()">
          <i data-lucide="upload" style="width:14px;height:14px;vertical-align:middle"></i> ${_T('meds.btn.upload')}
        </button>
        <button class="secondary" onclick="renderManualMedForm('', _T('meds.manual.hint'))">
          <i data-lucide="pencil" style="width:14px;height:14px;vertical-align:middle"></i> ${_T('meds.btn.manual')}
        </button>
        <input type="file" id="med-camera" accept="image/*" capture="environment" style="display:none" onchange="handleMedPhoto(this)" />
        <input type="file" id="med-upload" accept="image/*" style="display:none" onchange="handleMedPhoto(this)" />
      </div>
      <div id="med-photo-preview" style="margin-top:12px"></div>
      <div id="med-recognize-result" style="margin-top:12px"></div>
    </div>
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <h3>${_T('meds.list.title')}</h3>
        <button class="secondary" onclick="loadMedicationsPage()" style="padding:4px 12px;font-size:0.85rem">${_T('meds.list.refresh')}</button>
      </div>
      <div id="med-list" style="margin-top:12px"><p style="color:var(--text-muted)">${_T('meds.list.loading')}</p></div>
    </div>
    <div class="card" id="med-checkin-card" style="display:none">
      <h3><i data-lucide="bell" style="width:18px;height:18px;vertical-align:middle"></i> ${_T('meds.checkin.title')}</h3>
      <div id="med-checkin-body" style="margin-top:8px"></div>
    </div>
    <div class="card">
      <h3><i data-lucide="trending-up" style="width:18px;height:18px;vertical-align:middle"></i> ${_T('meds.improvement.title')}</h3>
      <p style="margin-top:4px;color:var(--text-dim);font-size:0.9rem">${_T('meds.improvement.desc')}</p>
      <div id="med-improvement-summary" style="margin-top:8px"></div>
      <div id="med-improvement-chart" style="position:relative;height:140px;margin-top:8px">
        <canvas id="improvement-canvas" style="width:100%;height:100%"></canvas>
      </div>
    </div>
    <div class="card">
      <h3><i data-lucide="bar-chart-3" style="width:18px;height:18px;vertical-align:middle"></i> ${_T('meds.stats.title')}</h3>
      <div id="med-stats" style="margin-top:12px"><p style="color:var(--text-muted)">${_T('meds.list.loading')}</p></div>
      <div id="med-chart" style="position:relative;height:200px;margin-top:16px">
        <canvas id="adherence-canvas" style="width:100%;height:100%"></canvas>
      </div>
    </div>
    <div class="card">
      <h3><i data-lucide="file-text" style="width:18px;height:18px;vertical-align:middle"></i> ${_T('meds.report.title')}</h3>
      <p style="margin-top:4px;color:var(--text-dim);font-size:0.9rem">${_T('meds.report.desc')}</p>
      <div style="display:flex;gap:8px;margin-top:8px">
        <select id="report-days" style="padding:6px 10px;border-radius:var(--radius-sm);border:1px solid var(--border-glass)">
          <option value="7">${_T('meds.report.days7')}</option>
          <option value="14">${_T('meds.report.days14')}</option>
          <option value="30" selected>${_T('meds.report.days30')}</option>
          <option value="90">${_T('meds.report.days90')}</option>
        </select>
        <button class="primary" onclick="generateMedReport()">${_T('meds.report.generate')}</button>
      </div>
      <div id="med-report" style="margin-top:12px"></div>
    </div>`;
}

function loadMedicationsPage() {
  // 平行抓取「藥物清單」與「今日服藥次數」，兩者都到了再 render，
  // 避免 hero 顯示舊的 _medsTodayLogs 值。
  var todayISO = new Date().toISOString().slice(0, 10);
  var pList = fetch(API + "/medications/?patient_id=" + _medsPatientId)
    .then(function(r) { return r.json(); });
  var pLogs = fetch(API + "/medications/logs?patient_id=" + _medsPatientId + "&days=1")
    .then(function(r) { return r.json(); })
    .catch(function() { return { logs: [] }; });
  Promise.all([pList, pLogs])
    .then(function(arr) {
      var data = arr[0] || {};
      var logsData = arr[1] || { logs: [] };
      _medsList = (data.medications || []).filter(function(m) { return m.active !== 0; });
      _medsTodayLogs = (logsData.logs || []).filter(function(l) {
        return l && l.taken_at && String(l.taken_at).slice(0, 10) === todayISO && l.taken !== false;
      }).length;
      renderMedList();
    })
    .catch(function() { showToast("載入藥物列表失敗", "error"); });

  fetch(API + "/medications/stats?patient_id=" + _medsPatientId + "&days=30")
    .then(function(r) { return r.json(); })
    .then(function(data) { renderMedStats(data); })
    .catch(function() {});

  fetch(API + "/medications/check-in/due?patient_id=" + _medsPatientId)
    .then(function(r) { return r.json(); })
    .then(function(data) { renderMedCheckIn(data); })
    .catch(function() {});

  fetch(API + "/medications/daily-improvement?patient_id=" + _medsPatientId + "&days=30")
    .then(function(r) { return r.json(); })
    .then(function(data) { renderMedImprovement(data); })
    .catch(function() {});
}

function renderMedCheckIn(data) {
  var card = document.getElementById("med-checkin-card");
  var body = document.getElementById("med-checkin-body");
  if (!card || !body) return;
  if (!data || !data.due) { card.style.display = "none"; return; }
  card.style.display = "block";
  var msg = data.message || "請更新今日的服藥紀錄";
  body.innerHTML =
    '<div class="med-checkin-banner">' +
    '<span><i data-lucide="alert-circle" style="width:16px;height:16px;vertical-align:middle;color:#e8889c"></i> ' + msg + '</span>' +
    '<button class="primary" onclick="document.getElementById(\'med-list\').scrollIntoView({behavior:\'smooth\'})">立即記錄</button>' +
    '</div>';
  if (typeof lucide !== "undefined") lucide.createIcons();
}

function renderMedImprovement(data) {
  var sumEl = document.getElementById("med-improvement-summary");
  var canvas = document.getElementById("improvement-canvas");
  if (!sumEl || !canvas) return;
  var daily = (data && data.daily) || [];
  var summary = (data && data.summary) || {};
  if (!daily.length) {
    sumEl.innerHTML = '<p style="color:var(--text-muted);font-size:0.9rem">尚無資料，紀錄服藥與療效後即可看到趨勢。</p>';
    var c0 = canvas.getContext("2d");
    c0.clearRect(0, 0, canvas.width, canvas.height);
    return;
  }
  var trendMap = {
    improving:        { cls: "up",   label: "↑ 改善中",   color: "#4caf90" },
    declining:        { cls: "down", label: "↓ 下降中",   color: "#e8889c" },
    stable:           { cls: "flat", label: "→ 平穩",     color: "#5b9fe8" },
    insufficient_data:{ cls: "flat", label: "· 資料累積中", color: "#5b9fe8" },
  };
  var t = trendMap[summary.trend] || trendMap.stable;
  var last = daily[daily.length - 1];
  var deltaTxt = summary.overall_delta != null
    ? (summary.overall_delta > 0 ? "+" : "") + summary.overall_delta
    : "—";
  sumEl.innerHTML =
    '<div class="med-improvement-meta">' +
    '<span class="med-improvement-trend ' + t.cls + '">' + t.label + '</span>' +
    '<span>最近：<strong style="color:var(--text)">' + last.improvement_score + '</strong> 分</span>' +
    '<span>期間變化：<strong style="color:var(--text)">' + deltaTxt + '</strong></span>' +
    '<span>' + daily.length + ' 天有紀錄</span>' +
    '</div>';

  var dpr = window.devicePixelRatio || 1;
  var ctx = canvas.getContext("2d");
  var rect = canvas.getBoundingClientRect();
  var w = canvas.width = rect.width * dpr;
  var h = canvas.height = rect.height * dpr;
  ctx.clearRect(0, 0, w, h);
  var pad = 14 * dpr;

  // baseline (50 分) 與框
  ctx.strokeStyle = "rgba(120,140,170,0.18)";
  ctx.lineWidth = 1 * dpr;
  ctx.beginPath();
  var midY = h - pad - (h - 2 * pad) * 0.5;
  ctx.setLineDash([4 * dpr, 4 * dpr]);
  ctx.moveTo(pad, midY); ctx.lineTo(w - pad, midY); ctx.stroke();
  ctx.setLineDash([]);

  var pts = daily.map(function(d, i) {
    return {
      x: pad + (w - 2 * pad) * (daily.length === 1 ? 0.5 : i / (daily.length - 1)),
      y: h - pad - (h - 2 * pad) * (d.improvement_score / 100),
    };
  });

  // 漸層填色
  var grad = ctx.createLinearGradient(0, pad, 0, h - pad);
  var rgb = t.color === "#4caf90" ? "76,175,144" : t.color === "#e8889c" ? "232,136,156" : "91,159,232";
  grad.addColorStop(0, "rgba(" + rgb + ",0.28)");
  grad.addColorStop(1, "rgba(" + rgb + ",0)");
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.moveTo(pts[0].x, h - pad);
  pts.forEach(function(p) { ctx.lineTo(p.x, p.y); });
  ctx.lineTo(pts[pts.length - 1].x, h - pad);
  ctx.closePath();
  ctx.fill();

  // 折線
  ctx.strokeStyle = t.color;
  ctx.lineWidth = 2 * dpr;
  ctx.lineJoin = "round";
  ctx.beginPath();
  pts.forEach(function(p, i) { i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y); });
  ctx.stroke();

  // 圓點
  ctx.fillStyle = t.color;
  pts.forEach(function(p) { ctx.beginPath(); ctx.arc(p.x, p.y, 3 * dpr, 0, 2 * Math.PI); ctx.fill(); });

  // y 軸標示
  ctx.fillStyle = "rgba(120,140,170,0.7)";
  ctx.font = (10 * dpr) + "px system-ui";
  ctx.textAlign = "left";
  ctx.fillText("100", 2 * dpr, pad + 4 * dpr);
  ctx.fillText("50",  2 * dpr, midY + 4 * dpr);
  ctx.fillText("0",   2 * dpr, h - pad + 4 * dpr);
}

// 把藥分到 早 / 中 / 晚 / 其他 四個時段；同一顆早晚都吃的藥會出現在「早」與「晚」兩格
// labels/hints come from i18n at render time so language toggle updates them
var MED_SLOT_DEFS = [
  { key: "morning", icon: "sunrise" },
  { key: "noon",    icon: "sun"     },
  { key: "evening", icon: "moon"    },
  { key: "other",   icon: "clock"   },
];

// 今日服藥 hero（位於藥物清單最上方）
// 計算邏輯：
//   expected = 所有非 PRN 活躍藥物的「固定時段數」總和（today 預期該吃幾顆）
//   taken    = 今日已標記服用的紀錄筆數（從 _medsTodayLogs 拿）
//   進度條 = taken / max(1, expected)
function _renderMedTodayHero(meds) {
  var expected = 0;
  meds.forEach(function(m) {
    if (m.is_other) return; // PRN/間隔型不計入預期次數
    var slots = (m.slots && m.slots.length) ? m.slots.length : 1;
    expected += slots;
  });
  var taken = (typeof _medsTodayLogs === 'number') ? _medsTodayLogs : 0;
  var remaining = Math.max(0, expected - taken);
  var pct = expected > 0 ? Math.min(100, Math.round((taken / expected) * 100)) : 0;
  var statusLine = expected > 0
    ? (taken + ' / ' + expected + ' 完成' + (remaining > 0 ? ' · 還剩 ' + remaining + ' 顆' : ' · 今日已完成 ✨'))
    : ('今日記錄 ' + taken + ' 次 · 你有 ' + meds.length + ' 種藥');
  return ''
    + '<div class="med-today-hero">'
    +   '<div class="med-today-hero-head">'
    +     '<span class="med-today-eyebrow">TODAY · 今日服藥</span>'
    +     '<span class="med-today-warn"><i data-lucide="info" style="width:11px;height:11px"></i> 以醫師處方為準</span>'
    +   '</div>'
    +   '<div class="med-today-title">' + statusLine + '</div>'
    +   '<div class="med-today-bar"><div class="med-today-bar-fill" style="width:' + pct + '%"></div></div>'
    + '</div>';
}
var _medsTodayLogs = 0;

function _medSlotLabel(key) { return _T('meds.slot.' + key + '.label'); }
function _medSlotHint(key)  { return _T('meds.slot.' + key + '.hint');  }

function _bucketMeds(meds) {
  var buckets = { morning: [], noon: [], evening: [], other: [] };
  (meds || []).forEach(function(med) {
    if (med.is_other) {
      buckets.other.push(med);
      return;
    }
    var slots = (med.slots && med.slots.length) ? med.slots : ["morning"];
    slots.forEach(function(s) {
      if (buckets[s]) buckets[s].push(med);
    });
  });
  return buckets;
}

function renderMedList() {
  var el = document.getElementById("med-list");
  if (!_medsList.length) {
    el.innerHTML =
      '<div class="empty-state empty-state-cozy">' +
        '<div class="empty-state-icon"><i data-lucide="pill"></i></div>' +
        '<p class="empty-state-title">' + _T('meds.list.empty.title') + '</p>' +
        '<p class="empty-state-desc">' + _T('meds.list.empty.desc') + '</p>' +
        '<button type="button" class="empty-state-cta" onclick="document.getElementById(\'med-camera\')?.click()">' +
          '<i data-lucide="camera" style="width:14px;height:14px"></i>' +
          '<span>' + _T('meds.list.empty.cta') + '</span>' +
        '</button>' +
      '</div>';
    if (window.lucide && lucide.createIcons) try { lucide.createIcons(); } catch (_) {}
    return;
  }

  var buckets = _bucketMeds(_medsList);
  var html = _renderMedTodayHero(_medsList) + '<div class="med-slots">';

  MED_SLOT_DEFS.forEach(function(def) {
    var meds = buckets[def.key];
    var isOther = def.key === "other";
    if (!meds.length) {
      // 沒有藥的時段也顯示空殼，讓使用者一眼知道結構
      html +=
        '<section class="med-slot med-slot-empty">' +
          '<header class="med-slot-head">' +
            '<span class="med-slot-icon"><i data-lucide="' + def.icon + '"></i></span>' +
            '<div><div class="med-slot-label">' + _medSlotLabel(def.key) + '</div>' +
            '<div class="med-slot-hint">' + _medSlotHint(def.key) + '</div></div>' +
          '</header>' +
          '<p class="med-slot-empty-msg">' + _T('meds.slot.empty') + '</p>' +
        '</section>';
      return;
    }
    html +=
      '<section class="med-slot">' +
        '<header class="med-slot-head">' +
          '<span class="med-slot-icon"><i data-lucide="' + def.icon + '"></i></span>' +
          '<div><div class="med-slot-label">' + _medSlotLabel(def.key) + ' <span class="med-slot-count">' + meds.length + '</span></div>' +
          '<div class="med-slot-hint">' + _medSlotHint(def.key) + '</div></div>' +
        '</header>' +
        '<div class="med-slot-grid">';
    meds.forEach(function(med) {
      html += _renderMedCard(med, def.key, isOther);
    });
    html += '</div></section>';
  });

  html += '</div>';
  el.innerHTML = html;
  if (window.lucide && window.lucide.createIcons) {
    try { window.lucide.createIcons(); } catch (e) {}
  }
}

function _renderMedCard(med, slotKey, isOther) {
  var name = escapeHtml(med.name || _T('meds.card.unnamed'));
  var dosage = med.dosage ? '<span class="med-card-dosage">' + escapeHtml(med.dosage) + '</span>' : '';
  var freq = med.frequency ? '<div class="med-card-freq">' + escapeHtml(med.frequency) + '</div>' : '';
  var meta = "";
  if (isOther) {
    if (med.interval_hours) {
      meta += '<span class="med-card-tag med-card-tag-interval">' + _Tf('meds.card.tag.interval', { h: med.interval_hours }) + '</span>';
    }
    if (med.is_prn) {
      meta += '<span class="med-card-tag med-card-tag-prn">' + _T('meds.card.tag.prn') + '</span>';
    }
    if (!meta) {
      meta = '<span class="med-card-tag">' + _T('meds.card.tag.intervalType') + '</span>';
    }
  } else if (med.category) {
    meta = '<span class="med-card-tag">' + escapeHtml(med.category) + '</span>';
  }

  var safeName = (med.name || "").replace(/'/g, "\\'");
  return (
    '<button type="button" class="med-card" data-id="' + med.id + '" data-slot="' + slotKey + '"' +
      ' onclick="tapMedTake(\'' + med.id + '\',\'' + slotKey + '\')">' +
      '<div class="med-card-row">' +
        '<div class="med-card-title">' +
          '<strong>' + name + '</strong>' + dosage +
        '</div>' +
        meta +
      '</div>' +
      freq +
      '<div class="med-card-actions" onclick="event.stopPropagation()">' +
        '<span class="med-card-take">' + _T('meds.card.take') + '</span>' +
        '<button class="med-card-mini med-card-mini-info" onclick="openMedDetail(\'' + med.id + '\')" title="看這顆藥的使用狀況與療效" aria-label="查看詳情"><i data-lucide="bar-chart-3" style="width:13px;height:13px"></i></button>' +
        '<button class="med-card-mini" onclick="logMedTaken(\'' + med.id + '\',false)" title="' + _T('meds.card.skipTitle') + '">✗</button>' +
        '<button class="med-card-mini" onclick="showEffectForm(\'' + med.id + '\',\'' + safeName + '\')" title="' + _T('meds.card.effectTitle') + '">★</button>' +
        '<button class="med-card-mini" data-name="' + escapeHtml(med.name || '') + '" onclick="openDrugSearchFor(this.dataset.name)" title="查詢藥物百科（副作用 / 用法 / 衛教）">?</button>' +
      '</div>' +
    '</button>'
  );
}

// === 單顆藥的「使用狀況 + 療效」詳情 modal ================================
// 設計參考：Medisafe / MyTherapy / Mango Health 的 per-medication detail。
// 五個區塊：①服藥率 hero ②4 個數字 stat ③ 30 天日曆 ④療效走勢 ⑤副作用 + 近期紀錄
function openMedDetail(medId) {
  var med = (_medsList || []).find(function(m){ return String(m.id) === String(medId); });
  if (!med) { if (typeof showToast === 'function') showToast('找不到這顆藥的資料', 'error'); return; }

  // 先 render 殼，再 fetch 細節
  var existing = document.getElementById('med-detail-modal');
  if (existing) existing.remove();
  var modal = document.createElement('div');
  modal.id = 'med-detail-modal';
  modal.className = 'med-detail-modal';
  modal.innerHTML = ''
    + '<div class="mdm-backdrop" onclick="closeMedDetail()"></div>'
    + '<div class="mdm-panel" role="dialog" aria-modal="true" aria-label="藥物詳情">'
    +   '<header class="mdm-head">'
    +     '<button type="button" class="mdm-close" onclick="closeMedDetail()" aria-label="關閉">'
    +       '<i data-lucide="x" style="width:18px;height:18px"></i>'
    +     '</button>'
    +     '<div class="mdm-title-wrap">'
    +       '<div class="mdm-pill"><i data-lucide="pill" style="width:18px;height:18px"></i></div>'
    +       '<div>'
    +         '<h3 class="mdm-title">' + escapeHtml(med.name || '未命名藥物') + (med.dosage ? '<span class="mdm-dose"> · ' + escapeHtml(med.dosage) + '</span>' : '') + '</h3>'
    +         '<p class="mdm-sub">' + escapeHtml((med.frequency || '') + (med.category ? '　·　' + med.category : '')) + '</p>'
    +       '</div>'
    +     '</div>'
    +   '</header>'
    +   '<div class="mdm-body" id="mdm-body">'
    +     '<div class="mdm-loading"><i data-lucide="loader" class="mdm-spin"></i> 整理這顆藥的紀錄中…</div>'
    +   '</div>'
    +   '<footer class="mdm-foot">'
    +     '<button type="button" class="mdm-action mdm-action-primary" onclick="showEffectForm(\'' + medId + '\',\'' + (med.name || '').replace(/\'/g, "\\\\'") + '\'); closeMedDetail();">'
    +       '<i data-lucide="star" style="width:14px;height:14px"></i> 紀錄這次的效果'
    +     '</button>'
    +     '<button type="button" class="mdm-action" data-name="' + escapeHtml(med.name || '') + '" onclick="openDrugSearchFor(this.dataset.name); closeMedDetail();">'
    +       '<i data-lucide="book-open" style="width:14px;height:14px"></i> 看藥的說明'
    +     '</button>'
    +   '</footer>'
    + '</div>';
  document.body.appendChild(modal);
  requestAnimationFrame(function(){ modal.classList.add('is-open'); });
  if (typeof lucide !== 'undefined') lucide.createIcons();
  document.addEventListener('keydown', _medDetailEsc);
  _loadMedDetail(medId, med);
}
function _medDetailEsc(e) { if (e.key === 'Escape') closeMedDetail(); }
function closeMedDetail() {
  var modal = document.getElementById('med-detail-modal');
  if (!modal) return;
  modal.classList.remove('is-open');
  document.removeEventListener('keydown', _medDetailEsc);
  setTimeout(function(){ if (modal.parentNode) modal.parentNode.removeChild(modal); }, 200);
}
async function _loadMedDetail(medId, med) {
  var pid = _medsPatientId || (typeof getStablePatientId === 'function' ? getStablePatientId() : null);
  if (!pid) return;
  // 三筆 fetch 同時起跑（30 天 logs / 全部 effects / 整體 stats）
  var pLogs = fetch(API + '/medications/logs?patient_id=' + pid + '&medication_id=' + medId + '&days=30')
    .then(function(r){return r.json();}).catch(function(){ return { logs: [] }; });
  var pEffects = fetch(API + '/medications/effects?patient_id=' + pid + '&medication_id=' + medId)
    .then(function(r){return r.json();}).catch(function(){ return { effects: [] }; });
  var pStats = fetch(API + '/medications/stats?patient_id=' + pid + '&days=30')
    .then(function(r){return r.json();}).catch(function(){ return { medications: [] }; });

  var arr;
  try { arr = await Promise.all([pLogs, pEffects, pStats]); }
  catch (e) { arr = [{logs:[]}, {effects:[]}, {medications:[]}]; }

  var logs    = (arr[0] && arr[0].logs)    || [];
  var effects = (arr[1] && arr[1].effects) || [];
  var perMedStats = ((arr[2] && arr[2].medications) || []).find(function(m){ return String(m.id) === String(medId); }) || {};

  // 統計（最近 30 天）
  var taken   = logs.filter(function(l){ return l && l.taken !== false; }).length;
  var skipped = logs.filter(function(l){ return l && l.taken === false; }).length;
  var expectedPerDay = (med.is_other ? 0 : (med.slots && med.slots.length ? med.slots.length : 1));
  var expected30 = expectedPerDay * 30;
  var missed = Math.max(0, expected30 - taken - skipped);
  var rate = expected30 > 0 ? Math.round(taken / expected30 * 100) : 0;
  var avgEffect = perMedStats.avg_effectiveness != null
    ? Number(perMedStats.avg_effectiveness).toFixed(1)
    : (effects.length
        ? (effects.reduce(function(s,e){return s + (e.effectiveness || 0);}, 0) / effects.length).toFixed(1)
        : '—');

  // 日曆熱區（30 天）
  var calCells = [];
  var today = new Date(); today.setHours(0,0,0,0);
  var byDay = {};
  logs.forEach(function(l) {
    var d = (l.taken_at || '').slice(0, 10);
    if (!d) return;
    if (!byDay[d]) byDay[d] = { taken: 0, skipped: 0 };
    if (l.taken === false) byDay[d].skipped++; else byDay[d].taken++;
  });
  for (var i = 29; i >= 0; i--) {
    var d = new Date(today); d.setDate(d.getDate() - i);
    var key = d.toISOString().slice(0,10);
    var st = byDay[key];
    var label, tone;
    if (!st) { tone = 'none'; label = '無紀錄'; }
    else if (expectedPerDay && st.taken >= expectedPerDay) { tone = 'ok'; label = '完成'; }
    else if (st.taken > 0) { tone = 'partial'; label = '部分'; }
    else if (st.skipped > 0) { tone = 'miss'; label = '漏掉/跳過'; }
    else { tone = 'none'; label = '無紀錄'; }
    calCells.push('<div class="mdm-cal-cell mdm-cal-' + tone + '" title="' + (d.getMonth()+1) + '/' + d.getDate() + '：' + label + '"></div>');
  }

  // 副作用 tag cloud（彙整出現次數）
  var sideMap = {};
  effects.forEach(function(e) {
    var raw = (e.side_effects || '').trim();
    if (!raw) return;
    raw.split(/[,，、;；\s]+/).forEach(function(t) {
      t = t.trim(); if (!t) return;
      sideMap[t] = (sideMap[t] || 0) + 1;
    });
  });
  var sideEntries = Object.keys(sideMap).map(function(k){return [k, sideMap[k]];}).sort(function(a,b){return b[1]-a[1];}).slice(0, 8);
  var sideHtml = sideEntries.length
    ? sideEntries.map(function(p){ return '<span class="mdm-side-tag">' + escapeHtml(p[0]) + ' <small>×' + p[1] + '</small></span>'; }).join('')
    : '<p class="mdm-empty">目前還沒有紀錄副作用。吃完藥按「紀錄這次的效果」就能留下感覺。</p>';

  // 療效走勢（迷你折線）
  var effectChart = _renderMedEffectChart(effects);

  // 近期 8 筆紀錄
  var recentMerged = logs.slice(0, 8).map(function(l) {
    var t = new Date(l.taken_at || l.created_at);
    var mm = (t.getMonth()+1) + '/' + t.getDate();
    var hh = String(t.getHours()).padStart(2,'0') + ':' + String(t.getMinutes()).padStart(2,'0');
    var status = l.taken === false ? '<span class="mdm-rec-skip">跳過</span>' : '<span class="mdm-rec-ok">已服用</span>';
    return '<li class="mdm-rec-item"><span class="mdm-rec-when">' + mm + '　' + hh + '</span>' + status + '</li>';
  }).join('');

  var body = document.getElementById('mdm-body');
  if (!body) return;
  body.innerHTML = ''
    // 頂端 hero — 大字服藥率 + 4 個 stat
    + '<section class="mdm-section mdm-hero">'
    +   '<div class="mdm-hero-ring">'
    +     '<svg viewBox="0 0 100 100" width="110" height="110">'
    +       '<circle cx="50" cy="50" r="42" fill="none" stroke="rgba(31,61,88,0.08)" stroke-width="9"/>'
    +       '<circle cx="50" cy="50" r="42" fill="none" stroke="var(--accent)" stroke-width="9" stroke-linecap="round" '
    +         'stroke-dasharray="264" stroke-dashoffset="' + (264 - 264 * rate / 100) + '" transform="rotate(-90 50 50)"/>'
    +     '</svg>'
    +     '<div class="mdm-hero-ring-num"><span>' + rate + '</span><small>%</small></div>'
    +   '</div>'
    +   '<div class="mdm-hero-side">'
    +     '<div class="mdm-hero-label">最近 30 天的服藥情形</div>'
    +     '<div class="mdm-stat-grid">'
    +       '<div class="mdm-stat"><span class="mdm-stat-num">' + taken + '</span><span class="mdm-stat-lbl">已服用</span></div>'
    +       '<div class="mdm-stat"><span class="mdm-stat-num">' + missed + '</span><span class="mdm-stat-lbl">漏掉</span></div>'
    +       '<div class="mdm-stat"><span class="mdm-stat-num">' + skipped + '</span><span class="mdm-stat-lbl">跳過</span></div>'
    +       '<div class="mdm-stat"><span class="mdm-stat-num">' + avgEffect + '</span><span class="mdm-stat-lbl">平均療效</span></div>'
    +     '</div>'
    +   '</div>'
    + '</section>'

    + '<section class="mdm-section">'
    +   '<h4 class="mdm-section-title">每日狀況</h4>'
    +   '<div class="mdm-cal">' + calCells.join('') + '</div>'
    +   '<div class="mdm-cal-legend">'
    +     '<span><i class="mdm-dot mdm-cal-ok"></i> 完成</span>'
    +     '<span><i class="mdm-dot mdm-cal-partial"></i> 部分</span>'
    +     '<span><i class="mdm-dot mdm-cal-miss"></i> 漏掉/跳過</span>'
    +     '<span><i class="mdm-dot mdm-cal-none"></i> 無紀錄</span>'
    +   '</div>'
    + '</section>'

    + '<section class="mdm-section">'
    +   '<h4 class="mdm-section-title">療效走勢</h4>'
    +   effectChart
    + '</section>'

    + '<section class="mdm-section">'
    +   '<h4 class="mdm-section-title">曾紀錄的副作用</h4>'
    +   '<div class="mdm-side-cloud">' + sideHtml + '</div>'
    + '</section>'

    + '<section class="mdm-section">'
    +   '<h4 class="mdm-section-title">最近的紀錄</h4>'
    +   (recentMerged ? '<ul class="mdm-rec-list">' + recentMerged + '</ul>' : '<p class="mdm-empty">這 30 天還沒有紀錄。</p>')
    + '</section>'
    + '<p class="mdm-foot-warn"><i data-lucide="info" style="width:11px;height:11px"></i> 數字來自你自己的打卡和評分，最終以醫師意見為主。</p>';
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

// 療效走勢迷你折線（最近 14 筆評分）
function _renderMedEffectChart(effects) {
  var pts = (effects || []).slice(0, 14).reverse();
  if (!pts.length) return '<p class="mdm-empty">還沒紀錄過效果。吃完藥按「紀錄這次的效果」打 1~5 分就會出現走勢。</p>';
  var W = 280, H = 90, PAD = 12;
  var n = pts.length;
  var xs = function(i) { return n === 1 ? W/2 : PAD + (W - 2*PAD) * (i / (n - 1)); };
  var ys = function(v) { return H - PAD - (H - 2*PAD) * ((v - 1) / 4); };
  var path = pts.map(function(p, i){ return (i === 0 ? 'M ' : 'L ') + xs(i).toFixed(1) + ' ' + ys(p.effectiveness || 1).toFixed(1); }).join(' ');
  var dots = pts.map(function(p, i){
    return '<circle cx="' + xs(i).toFixed(1) + '" cy="' + ys(p.effectiveness || 1).toFixed(1) + '" r="3.2" fill="var(--accent)"/>';
  }).join('');
  return '<svg class="mdm-effect-chart" viewBox="0 0 ' + W + ' ' + H + '" width="100%" height="' + H + '">'
    + '<line x1="' + PAD + '" y1="' + ys(1) + '" x2="' + (W-PAD) + '" y2="' + ys(1) + '" stroke="rgba(31,61,88,0.08)"/>'
    + '<line x1="' + PAD + '" y1="' + ys(3) + '" x2="' + (W-PAD) + '" y2="' + ys(3) + '" stroke="rgba(31,61,88,0.06)" stroke-dasharray="2 3"/>'
    + '<line x1="' + PAD + '" y1="' + ys(5) + '" x2="' + (W-PAD) + '" y2="' + ys(5) + '" stroke="rgba(31,61,88,0.08)"/>'
    + '<text x="2" y="' + (ys(5)+3) + '" font-size="9" fill="var(--text-muted)">★5</text>'
    + '<text x="2" y="' + (ys(1)+3) + '" font-size="9" fill="var(--text-muted)">★1</text>'
    + '<path d="' + path + '" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    + dots
    + '</svg>'
    + '<p class="mdm-effect-hint">最近 ' + n + ' 次評分</p>';
}

// 點卡片即打卡：固定時段藥（早/中/晚）直接寫入；
// 「其他」型藥（每 X 小時 / PRN）也走同一條 POST /log，
// 後端會在 < 4 小時內回 409 dose_too_soon，由 logMedTaken 攔下並彈警告。
function tapMedTake(medId, slotKey) {
  logMedTaken(medId, true);
}

// 把藥袋／藥單照片預處理：
//   1) EXIF 自動轉正（手機直拍常帶 rotation flag）
//   2) 直接縮到 2400px 長邊內、JPEG 0.9（避開 12MP 全尺寸 canvas 在手機上 OOM）
// 之前 v53 加的「裁黑邊」需要在 12MP canvas 上跑 getImageData（48MB Uint8 array），
// 舊一點的手機會 OOM 導致整段 fallback 走 raw 檔，原檔太大（5-10MB）就過不了
// Vercel 4.5MB 上傳上限 → 使用者看到「沒辦法上傳」。
// 裁黑邊功能先拿掉，等之後改用 worker / 在縮圖後再裁。
function _compressMedPhoto(file) {
  function loadBitmap(blob) {
    if (typeof createImageBitmap !== "function") {
      return Promise.reject(new Error("createImageBitmap not supported"));
    }
    try {
      // imageOrientation: 'from-image' 會自動套 EXIF rotation
      return createImageBitmap(blob, { imageOrientation: "from-image" });
    } catch (_) {
      return createImageBitmap(blob);
    }
  }

  function loadImage(blob) {
    return new Promise(function(resolve, reject) {
      var url = URL.createObjectURL(blob);
      var img = new Image();
      img.onload = function() {
        URL.revokeObjectURL(url);
        resolve(img);
      };
      img.onerror = function() {
        URL.revokeObjectURL(url);
        reject(new Error("Image load failed"));
      };
      img.src = url;
    });
  }

  function drawAndExport(source, srcW, srcH) {
    var maxEdge = 2400;
    var w = srcW, h = srcH;
    if (Math.max(w, h) > maxEdge) {
      var scale = maxEdge / Math.max(w, h);
      w = Math.round(w * scale);
      h = Math.round(h * scale);
    }
    var canvas = document.createElement("canvas");
    canvas.width = w; canvas.height = h;
    var ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff";  // 白底 — 處理透明 PNG / JPEG 黑底
    ctx.fillRect(0, 0, w, h);
    ctx.drawImage(source, 0, 0, w, h);
    return canvas.toDataURL("image/jpeg", 0.9);
  }

  return new Promise(function(resolve) {
    function fallbackRawFile() {
      // 最後手段：直接送原檔（檔案太大時 server 會回 413，前端顯示「上傳失敗」）
      var reader = new FileReader();
      reader.onload = function(e) { resolve({ dataUrl: e.target.result, mediaType: file.type || "image/jpeg" }); };
      reader.onerror = function() { resolve(null); };
      reader.readAsDataURL(file);
    }

    loadBitmap(file)
      .then(function(bm) {
        try {
          var dataUrl = drawAndExport(bm, bm.width, bm.height);
          resolve({ dataUrl: dataUrl, mediaType: "image/jpeg" });
        } catch (e) {
          fallbackRawFile();
        }
      })
      .catch(function() {
        // createImageBitmap 不支援 → 退回 Image element（現代瀏覽器都會自動套 EXIF）
        loadImage(file)
          .then(function(img) {
            try {
              var dataUrl = drawAndExport(img, img.width, img.height);
              resolve({ dataUrl: dataUrl, mediaType: "image/jpeg" });
            } catch (e) {
              fallbackRawFile();
            }
          })
          .catch(fallbackRawFile);
      });
  });
}

// 把照片轉指定角度（順時針 deg），回傳新的 dataUrl
function _rotateMedPhoto(dataUrl, deg) {
  return new Promise(function(resolve, reject) {
    var img = new Image();
    img.onload = function() {
      var w = img.naturalWidth, h = img.naturalHeight;
      var rad = (deg % 360) * Math.PI / 180;
      var swap = (deg % 180) !== 0;
      var canvas = document.createElement("canvas");
      canvas.width = swap ? h : w;
      canvas.height = swap ? w : h;
      var ctx = canvas.getContext("2d");
      ctx.fillStyle = "#fff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.translate(canvas.width / 2, canvas.height / 2);
      ctx.rotate(rad);
      ctx.drawImage(img, -w / 2, -h / 2);
      resolve(canvas.toDataURL("image/jpeg", 0.9));
    };
    img.onerror = function() { reject(new Error("rotate load failed")); };
    img.src = dataUrl;
  });
}

// 拿目前預覽的 dataUrl 旋轉 90° 後重跑辨識
window.rotateMedPreview = function() {
  var img = document.querySelector("#med-photo-preview img");
  if (!img || !img.src) return;
  var src = img.src;
  _rotateMedPhoto(src, 90).then(function(rotated) {
    _renderMedPreviewAndRecognize(rotated, "image/jpeg");
  }).catch(function() {
    showToast("旋轉失敗，請重新上傳照片", "error");
  });
};

// 在瀏覽器跑 Tesseract.js OCR — 中文（繁）+ 英文，支援藥單上的中英並列藥名
// 失敗 / Tesseract 沒載入時 resolve("")，由 backend fallback 走原本 LLM vision
// onProgress(msg) 會在每個階段呼叫，方便 UI 顯示進度
function _runClientOcr(dataUrl, onProgress) {
  return new Promise(function(resolve) {
    function fail(reason) {
      console.warn("Tesseract OCR skipped:", reason);
      resolve("");
    }
    if (typeof Tesseract === "undefined" || !Tesseract.recognize) {
      // tesseract.js 載入失敗（網路 / CDN 擋）— 直接退回 backend OCR
      return fail("Tesseract not loaded");
    }
    if (onProgress) onProgress("下載中文辨識引擎...");
    try {
      Tesseract.recognize(dataUrl, "chi_tra+eng", {
        logger: function(m) {
          if (!onProgress) return;
          if (m.status === "loading tesseract core") onProgress("載入辨識引擎...");
          else if (m.status === "loading language traineddata") onProgress("下載中文語言包...");
          else if (m.status === "initializing api" || m.status === "initialized api") onProgress("初始化辨識引擎...");
          else if (m.status === "recognizing text") {
            var pct = Math.round((m.progress || 0) * 100);
            onProgress("正在辨識文字 " + pct + "%");
          }
        },
      })
        .then(function(result) {
          var text = (result && result.data && result.data.text) || "";
          // 若 OCR 出來太少字（< 20 char）視為失敗，讓 backend 用 vision LLM 救
          resolve(text.trim().length >= 20 ? text.trim() : "");
        })
        .catch(function(e) { fail("Tesseract.recognize error: " + (e && e.message)); });
    } catch (e) {
      fail("Tesseract sync error: " + (e && e.message));
    }
  });
}


function _renderMedPreviewAndRecognize(dataUrl, mediaType) {
  var base64Data = dataUrl.split(",")[1];

  document.getElementById("med-photo-preview").innerHTML =
    '<img src="' + dataUrl + '" style="max-width:100%;max-height:240px;border-radius:var(--radius-sm);border:1px solid var(--border-glass)" />' +
    '<div style="display:flex;gap:8px;align-items:center;margin-top:6px;flex-wrap:wrap">' +
    '<button type="button" class="secondary" onclick="rotateMedPreview()" style="padding:4px 10px;font-size:0.8rem">' +
    '<i data-lucide="rotate-cw" style="width:12px;height:12px;vertical-align:middle"></i> 旋轉 90°</button>' +
    '<span style="font-size:0.75rem;color:var(--text-muted)">' +
    '已壓縮為 ' + (Math.round(base64Data.length * 0.75 / 1024)) + ' KB，' +
    '若照片倒著，請按「旋轉」校正。</span>' +
    '</div>';
  if (window.lucide && lucide.createIcons) { try { lucide.createIcons(); } catch (_) {} }

  document.getElementById("med-recognize-result").innerHTML =
    '<div style="text-align:center;padding:16px;color:var(--text-muted)" id="med-rec-status">' +
    '<div class="loading-spinner"></div>' +
    '<p style="margin-top:8px">準備辨識藥袋／藥單...</p>' +
    '<p style="margin-top:4px;font-size:0.75rem;opacity:0.7">第一次辨識較慢，最多約 30 秒</p>' +
    '</div>';

  return _runClientOcr(dataUrl, function(progressMsg) {
    var s = document.getElementById("med-rec-status");
    if (s) {
      s.innerHTML =
        '<div class="loading-spinner"></div>' +
        '<p style="margin-top:8px">' + escapeHtml(progressMsg) + '</p>' +
        '<p style="margin-top:4px;font-size:0.75rem;opacity:0.7">md.piece 掃描中，大約 15-30 秒</p>';
    }
  }).then(function(ocrText) {
    var s2 = document.getElementById("med-rec-status");
    if (s2) {
      s2.innerHTML =
        '<div class="loading-spinner"></div>' +
        '<p style="margin-top:8px">MD.Piece 整理欄位中...</p>';
    }
    var body = { patient_id: _medsPatientId, image_base64: base64Data, media_type: mediaType };
    if (ocrText && ocrText.length >= 20) body.ocr_text = ocrText;
    return fetch(API + "/medications/recognize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  })
    .then(function(r) {
      return r.text().then(function(t) {
        var parsed; try { parsed = JSON.parse(t); } catch (e) { parsed = { detail: t }; }
        return { ok: r.ok, status: r.status, data: parsed };
      });
    })
    .then(function(res) {
      if (!res.ok) {
        var msg = (res.data && (res.data.detail || res.data.message)) || ("HTTP " + res.status);
        if (typeof msg !== "string") msg = JSON.stringify(msg);
        renderManualMedForm("", "辨識失敗：" + msg + "。你可以改用手動填寫下方資料。");
        return;
      }
      var data = res.data || {};
      var parsed = data.parsed || [];

      if (parsed.length > 0) {
        renderRecognizedEditable(parsed, [], data.raw_text || "", []);
        return;
      }

      var providerNote = "";
      if (data.errors && data.errors.length) {
        var lines = data.errors.map(function(e) {
          return "• " + (e.provider || "?") + "：" + (e.error || "未知錯誤");
        }).join("\n");
        providerNote = "\n\n（嘗試過的辨識服務）\n" + lines;
      }
      renderManualMedForm(
        (data.raw_text || "") + providerNote,
        "無法辨識藥物，你可以直接手動填寫下方資料，按「加入我的藥物」即可寫入。"
      );
    })
    .catch(function(err) {
      renderManualMedForm(
        "",
        "辨識服務連線失敗（" + (err && err.message || "網路錯誤") + "），你可以改用手動填寫下方資料。"
      );
    });
}

function handleMedPhoto(input) {
  if (!input.files || !input.files[0]) return;
  var file = input.files[0];

  document.getElementById("med-photo-preview").innerHTML =
    '<div style="text-align:center;padding:8px;color:var(--text-muted);font-size:0.85rem">壓縮並上傳照片...</div>';
  document.getElementById("med-recognize-result").innerHTML = "";

  _compressMedPhoto(file).then(function(prepared) {
    if (!prepared) {
      renderManualMedForm("", "讀取照片失敗，請改用手動填寫下方資料。");
      return;
    }
    _renderMedPreviewAndRecognize(prepared.dataUrl, prepared.mediaType);
  });

  input.value = "";
}

function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// 辨識成功但寫入失敗 / 部分失敗 → 提供逐筆可編輯卡片
function renderRecognizedEditable(parsed, errors, rawText, alreadySaved) {
  var errMap = {};
  (errors || []).forEach(function(e) { errMap[e.name] = e.error; });
  var savedNames = {};
  (alreadySaved || []).forEach(function(m) { savedNames[m.name] = true; });

  var SLOT_LABEL = { morning: "早", noon: "中午", evening: "晚", other: "其他" };
  var inputStyle = "padding:6px;border-radius:4px;border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)";
  var rows = parsed.map(function(m, i) {
    var isSaved = savedNames[m.name];
    var errMsg = errMap[m.name];
    var bgTint = isSaved ? "rgba(85,184,138,0.08)" : (errMsg ? "rgba(220,80,80,0.08)" : "var(--bg-glass)");
    var borderTint = isSaved ? "var(--success)" : (errMsg ? "var(--danger)" : "var(--border-glass)");
    var sched = m.schedule || {};
    var slotTags = "";
    if (sched.is_other) {
      var bits = [];
      if (sched.interval_hours) bits.push("每 " + sched.interval_hours + " 小時");
      if (sched.is_prn) bits.push("需要時");
      slotTags = '<span class="rec-slot-tag rec-slot-other">其他' + (bits.length ? "・" + bits.join("・") : "") + '</span>';
    } else if (sched.slots && sched.slots.length) {
      slotTags = sched.slots.map(function(s) {
        return '<span class="rec-slot-tag rec-slot-' + s + '">' + (SLOT_LABEL[s] || s) + '</span>';
      }).join("");
    }
    return (
      '<div class="rec-med-card" data-idx="' + i + '" style="padding:10px;background:' + bgTint + ';border:1px solid ' + borderTint + ';border-radius:var(--radius-sm);display:grid;gap:6px">' +
        (isSaved ? '<div style="color:var(--success);font-size:0.8rem">已寫入 ✓</div>' :
         errMsg ? '<div style="color:var(--danger);font-size:0.8rem">寫入失敗：' + escapeHtml(errMsg) + '</div>' : '') +
        (slotTags ? '<div class="rec-slot-tags">預計分類：' + slotTags + '</div>' : '') +
        '<input class="rec-name" type="text" value="' + escapeHtml(m.name) + '" placeholder="藥名 *（必填）" style="' + inputStyle + '" />' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">' +
          '<input class="rec-dosage" type="text" value="' + escapeHtml(m.dosage) + '" placeholder="劑量（例：500mg）" style="' + inputStyle + '" />' +
          '<input class="rec-frequency" type="text" value="' + escapeHtml(m.frequency) + '" placeholder="頻率（例：一天三次）" style="' + inputStyle + '" />' +
        '</div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">' +
          '<input class="rec-usage" type="text" value="' + escapeHtml(m.usage) + '" placeholder="用法（飯前/飯後/睡前）" style="' + inputStyle + '" />' +
          '<input class="rec-duration" type="text" value="' + escapeHtml(m.duration) + '" placeholder="療程（例：7 天）" style="' + inputStyle + '" />' +
        '</div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">' +
          '<input class="rec-category" type="text" value="' + escapeHtml(m.category) + '" placeholder="分類" style="' + inputStyle + '" />' +
          '<input class="rec-purpose" type="text" value="' + escapeHtml(m.purpose) + '" placeholder="用途" style="' + inputStyle + '" />' +
        '</div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">' +
          '<input class="rec-hospital" type="text" value="' + escapeHtml(m.hospital) + '" placeholder="醫院/診所" style="' + inputStyle + '" />' +
          '<input class="rec-prescribed-date" type="text" value="' + escapeHtml(m.prescribed_date) + '" placeholder="開立日期（YYYY-MM-DD）" style="' + inputStyle + '" />' +
        '</div>' +
        '<textarea class="rec-instructions" rows="2" placeholder="備註 / 注意事項" style="' + inputStyle + ';resize:vertical">' + escapeHtml(m.instructions) + '</textarea>' +
        (isSaved ? '' : '<button class="primary" onclick="submitRecognizedOne(this)" style="padding:6px 10px;font-size:0.85rem">加入這筆到我的藥物</button>') +
      '</div>'
    );
  }).join("");

  var header = errors && errors.length
    ? '<p style="color:var(--warning);margin:0 0 8px">辨識成功但部分寫入失敗，請確認內容後重新送出。</p>'
    : '<p style="color:var(--text-dim);margin:0 0 8px">已辨識出以下藥物，請確認內容後一鍵加入我的藥物。</p>';

  var html =
    '<div style="padding:12px;background:rgba(160,140,220,0.06);border-radius:var(--radius-sm);border:1px solid var(--border-glass)">' +
      header +
      (rawText ? '<details style="margin-bottom:8px"><summary style="font-size:0.85rem;color:var(--text-muted);cursor:pointer">原始辨識文字</summary><pre style="font-size:0.8rem;white-space:pre-wrap;margin-top:4px;max-height:120px;overflow:auto">' + escapeHtml(rawText) + '</pre></details>' : '') +
      '<div id="rec-med-cards" style="display:grid;gap:10px">' + rows + '</div>' +
      '<div style="display:flex;gap:8px;margin-top:12px">' +
        '<button class="primary" onclick="submitAllRecognized()">全部加入我的藥物</button>' +
        '<button class="secondary" onclick="document.getElementById(\'med-recognize-result\').innerHTML=\'\'">取消</button>' +
      '</div>' +
    '</div>';
  document.getElementById("med-recognize-result").innerHTML = html;
}

function _collectRecCard(card) {
  var val = function(sel) { var el = card.querySelector(sel); return el ? (el.value || "").trim() : ""; };
  // 資料庫目前只有 dosage/frequency/category/purpose/instructions 欄位，
  // 新增的 usage/duration/hospital/prescribed_date 先合併到 frequency / instructions
  // 以保留資訊又不用改 schema
  var frequency = val(".rec-frequency");
  var usage = val(".rec-usage");
  var freqCombined = [frequency, usage].filter(Boolean).join("・");

  var instructions = val(".rec-instructions");
  var duration = val(".rec-duration");
  var hospital = val(".rec-hospital");
  var pdate = val(".rec-prescribed-date");
  var extra = [];
  if (duration) extra.push("療程：" + duration);
  if (hospital) extra.push("醫院：" + hospital);
  if (pdate) extra.push("開立日期：" + pdate);
  var instCombined = [instructions, extra.join("；")].filter(Boolean).join("\n");

  return {
    patient_id: _medsPatientId,
    name: val(".rec-name"),
    dosage: val(".rec-dosage") || null,
    frequency: freqCombined || null,
    category: val(".rec-category") || null,
    purpose: val(".rec-purpose") || null,
    instructions: instCombined || null,
  };
}

function submitRecognizedOne(btn) {
  var card = btn.closest(".rec-med-card");
  var body = _collectRecCard(card);
  if (!body.name) { showToast("藥物名稱不能空白", "warning"); return; }
  btn.disabled = true; btn.textContent = "加入中...";
  fetch(API + "/medications/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })
    .then(function(r) {
      return r.text().then(function(t) {
        var p; try { p = JSON.parse(t); } catch (e) { p = { detail: t }; }
        return { ok: r.ok, status: r.status, data: p };
      });
    })
    .then(function(res) {
      if (!res.ok) {
        var msg = (res.data && (res.data.detail || res.data.message)) || ("HTTP " + res.status);
        showToast("加入失敗：" + msg, "error");
        btn.disabled = false; btn.textContent = "重試加入";
        return;
      }
      var deduped = res.data && res.data._deduped;
      card.style.background = "rgba(85,184,138,0.08)";
      card.style.borderColor = "var(--success)";
      btn.outerHTML = '<div style="color:var(--success);font-size:0.85rem;text-align:center">' + (deduped ? '已存在 ✓' : '已寫入 ✓') + '</div>';
      showToast(deduped ? "「" + body.name + "」已在藥物清單中" : "已加入「" + body.name + "」", deduped ? "info" : "success");
      loadMedicationsPage();
    })
    .catch(function(err) {
      showToast("加入失敗：" + (err && err.message || "網路錯誤"), "error");
      btn.disabled = false; btn.textContent = "重試加入";
    });
}

function submitAllRecognized() {
  var cards = document.querySelectorAll("#rec-med-cards .rec-med-card");
  var pending = [];
  cards.forEach(function(c) {
    var hasSaveBtn = c.querySelector("button.primary");
    if (hasSaveBtn) pending.push(c);
  });
  if (!pending.length) { showToast("沒有需要加入的項目", "info"); return; }
  var okCount = 0, dupCount = 0, failCount = 0, done = 0;
  pending.forEach(function(card) {
    var btn = card.querySelector("button.primary");
    var body = _collectRecCard(card);
    if (!body.name) { failCount++; done++; if (done === pending.length) _afterBulkAdd(okCount, dupCount, failCount); return; }
    btn.disabled = true; btn.textContent = "加入中...";
    fetch(API + "/medications/", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }).catch(function() { return { ok: r.ok, data: {} }; }); })
      .then(function(res) {
        if (res.ok) {
          var deduped = res.data && res.data._deduped;
          if (deduped) dupCount++; else okCount++;
          card.style.background = "rgba(85,184,138,0.08)";
          card.style.borderColor = "var(--success)";
          btn.outerHTML = '<div style="color:var(--success);font-size:0.85rem;text-align:center">' + (deduped ? '已存在 ✓' : '已寫入 ✓') + '</div>';
        } else {
          failCount++;
          btn.disabled = false; btn.textContent = "重試加入";
        }
      })
      .catch(function() { failCount++; btn.disabled = false; btn.textContent = "重試加入"; })
      .finally(function() {
        done++;
        if (done === pending.length) _afterBulkAdd(okCount, dupCount, failCount);
      });
  });
}

function _afterBulkAdd(ok, dup, fail) {
  dup = dup || 0;
  var parts = [];
  if (ok) parts.push("加入 " + ok + " 種");
  if (dup) parts.push(dup + " 種已存在");
  if (fail) parts.push(fail + " 種失敗");
  var level = fail ? (ok || dup ? "warning" : "error") : (ok ? "success" : "info");
  showToast(parts.length ? parts.join("、") + " ✓" : "沒有變更", level);
  if (ok || dup) loadMedicationsPage();
}

function renderManualMedForm(rawText, hint) {
  var html =
    '<div style="padding:12px;background:rgba(230,180,80,0.08);border-radius:var(--radius-sm);border:1px solid var(--warning)">' +
      '<p style="color:var(--warning);margin:0 0 8px">' + escapeHtml(hint) + '</p>' +
      (rawText ? '<details style="margin-bottom:8px"><summary style="font-size:0.85rem;color:var(--text-muted);cursor:pointer">原始辨識文字（可複製參考）</summary><pre style="font-size:0.8rem;white-space:pre-wrap;margin-top:4px;max-height:120px;overflow:auto">' + escapeHtml(rawText) + '</pre></details>' : '') +
      '<div style="display:grid;gap:8px">' +
        '<label style="font-size:0.85rem;color:var(--text-dim)">藥名 <span style="color:var(--danger)">*</span>' +
          '<input id="manual-med-name" type="text" placeholder="例：Panadol 普拿疼" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">劑量' +
            '<input id="manual-med-dosage" type="text" placeholder="例：500mg / 1顆" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">頻率' +
            '<input id="manual-med-frequency" type="text" placeholder="例：一天三次" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
        '</div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">用法' +
            '<input id="manual-med-usage" type="text" placeholder="飯前 / 飯後 / 睡前" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">療程' +
            '<input id="manual-med-duration" type="text" placeholder="例：7 天 / 長期" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
        '</div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">分類' +
            '<input id="manual-med-category" type="text" placeholder="例：止痛藥" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">用途' +
            '<input id="manual-med-purpose" type="text" placeholder="例：緩解頭痛" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
        '</div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">醫院 / 診所' +
            '<input id="manual-med-hospital" type="text" placeholder="例：台大醫院" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">開立日期' +
            '<input id="manual-med-prescribed-date" type="text" placeholder="YYYY-MM-DD" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
        '</div>' +
        '<label style="font-size:0.85rem;color:var(--text-dim)">備註 / 注意事項' +
          '<textarea id="manual-med-instructions" rows="2" placeholder="例：避免與葡萄柚汁併用" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text);resize:vertical"></textarea></label>' +
      '</div>' +
      '<div style="display:flex;gap:8px;margin-top:12px">' +
        '<button class="primary" onclick="submitManualMed()">加入我的藥物</button>' +
        '<button class="secondary" onclick="document.getElementById(\'med-recognize-result\').innerHTML=\'\'">取消</button>' +
      '</div>' +
    '</div>';
  document.getElementById("med-recognize-result").innerHTML = html;
}

function submitManualMed() {
  var g = function(id) { var el = document.getElementById(id); return el ? (el.value || "").trim() : ""; };
  var name = g("manual-med-name");
  if (!name) { showToast("請至少填寫藥物名稱", "warning"); return; }

  var frequency = g("manual-med-frequency");
  var usage = g("manual-med-usage");
  var freqCombined = [frequency, usage].filter(Boolean).join("・");

  var instructions = g("manual-med-instructions");
  var duration = g("manual-med-duration");
  var hospital = g("manual-med-hospital");
  var pdate = g("manual-med-prescribed-date");
  var extra = [];
  if (duration) extra.push("療程：" + duration);
  if (hospital) extra.push("醫院：" + hospital);
  if (pdate) extra.push("開立日期：" + pdate);
  var instCombined = [instructions, extra.join("；")].filter(Boolean).join("\n");

  var body = {
    patient_id: _medsPatientId,
    name: name,
    dosage: g("manual-med-dosage") || null,
    frequency: freqCombined || null,
    category: g("manual-med-category") || null,
    purpose: g("manual-med-purpose") || null,
    instructions: instCombined || null,
  };
  fetch(API + "/medications/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })
    .then(function(r) {
      return r.text().then(function(t) {
        var parsed; try { parsed = JSON.parse(t); } catch (e) { parsed = { detail: t }; }
        return { ok: r.ok, status: r.status, data: parsed };
      });
    })
    .then(function(res) {
      if (!res.ok) {
        var msg = (res.data && (res.data.detail || res.data.message)) || ("HTTP " + res.status);
        showToast("加入失敗：" + msg, "error");
        var box = document.getElementById("med-recognize-result");
        box.insertAdjacentHTML("beforeend",
          '<p style="color:var(--danger);margin-top:8px;font-size:0.85rem">伺服器回應：' + msg + '</p>');
        return;
      }
      showToast("已加入藥物 ✓", "success");
      document.getElementById("med-recognize-result").innerHTML =
        '<p style="color:var(--success)">已成功加入「' + name + '」到我的藥物。</p>';
      document.getElementById("med-photo-preview").innerHTML = "";
      loadMedicationsPage();
    })
    .catch(function(err) { showToast("加入失敗：" + (err && err.message || "網路錯誤"), "error"); });
}

function logMedTaken(medId, taken, opts) {
  opts = opts || {};
  var skipReason = "";
  if (!taken && !opts.skipReason) {
    skipReason = prompt("為什麼跳過這次服藥？（可留空）") || "";
  } else if (opts.skipReason) {
    skipReason = opts.skipReason;
  }

  var body = {
    patient_id: _medsPatientId,
    medication_id: medId,
    taken: taken,
    skip_reason: skipReason || null,
    force: !!opts.force
  };

  fetch(API + "/medications/log", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })
    .then(function(r) {
      return r.text().then(function(t) {
        var p; try { p = JSON.parse(t); } catch (e) { p = { detail: t }; }
        return { ok: r.ok, status: r.status, data: p };
      });
    })
    .then(function(res) {
      if (res.status === 409 && res.data && res.data.detail && res.data.detail.code === "dose_too_soon") {
        // 4 小時內重複服「其他」型藥 → 跳警告，由患者決定要不要強制記錄
        showDoseSafetyDialog(medId, res.data.detail);
        return;
      }
      if (!res.ok) {
        var msg = (res.data && (res.data.detail || res.data.message)) || ("HTTP " + res.status);
        showToast("記錄失敗：" + (typeof msg === "string" ? msg : JSON.stringify(msg)), "error");
        return;
      }
      showToast(taken ? "已記錄服藥 ✓" : "已記錄跳過", taken ? "success" : "info");
      loadMedicationsPage();
    })
    .catch(function() { showToast("記錄失敗", "error"); });
}

// 4 小時間隔警告 modal：超過閾值時，攔下 logMedTaken，
// 解釋短時間重複服藥的風險，再給「我了解風險，仍要記錄」的退路。
function showDoseSafetyDialog(medId, detail) {
  closeDoseSafetyDialog();
  var safety = (detail && detail.safety) || {};
  var hours = safety.hours_since_last;
  var required = safety.required_hours || detail.min_hours || 4;
  var remaining = safety.hours_remaining;
  var msg = (detail && detail.message) || "距離上次服藥太近，可能造成藥效過量風險。";

  var html =
    '<div class="dose-safety-backdrop" id="dose-safety-modal" onclick="closeDoseSafetyDialog()">' +
      '<div class="dose-safety-card" onclick="event.stopPropagation()">' +
        '<div class="dose-safety-head">' +
          '<span class="dose-safety-icon">⚠️</span>' +
          '<h3>服藥風險警告</h3>' +
        '</div>' +
        '<p class="dose-safety-msg">' + escapeHtml(msg) + '</p>' +
        '<dl class="dose-safety-meta">' +
          (hours != null ? '<div><dt>距離上次服藥</dt><dd>' + Number(hours).toFixed(1) + ' 小時</dd></div>' : '') +
          '<div><dt>建議間隔</dt><dd>至少 ' + required + ' 小時</dd></div>' +
          (remaining != null ? '<div><dt>還需等待</dt><dd>' + Number(remaining).toFixed(1) + ' 小時</dd></div>' : '') +
        '</dl>' +
        '<div class="dose-safety-actions">' +
          '<button type="button" class="secondary" onclick="closeDoseSafetyDialog()">取消，再等等</button>' +
          '<button type="button" class="dose-safety-force" onclick="confirmForceLog(\'' + medId + '\')">' +
            '我了解風險，仍要記錄' +
          '</button>' +
        '</div>' +
        '<p class="dose-safety-foot">若症狀無法忍受，請聯繫醫師或藥師，不要自行加量。</p>' +
      '</div>' +
    '</div>';

  var holder = document.createElement("div");
  holder.innerHTML = html;
  document.body.appendChild(holder.firstChild);
}

function closeDoseSafetyDialog() {
  var el = document.getElementById("dose-safety-modal");
  if (el) el.remove();
}

function confirmForceLog(medId) {
  closeDoseSafetyDialog();
  logMedTaken(medId, true, { force: true });
}

function showEffectForm(medId, medName) {
  var eff = prompt(medName + " 療效如何？（1=沒效果 ~ 5=非常有效）", "3");
  if (!eff) return;
  var effNum = parseInt(eff);
  if (effNum < 1 || effNum > 5 || isNaN(effNum)) { showToast("請輸入 1-5 的數字", "warning"); return; }
  var sideEffects = prompt("有任何副作用嗎？（沒有就留空）") || "";
  var changes = prompt("症狀有什麼改善？（沒有就留空）") || "";

  fetch(API + "/medications/effects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      patient_id: _medsPatientId, medication_id: medId,
      effectiveness: effNum, side_effects: sideEffects, symptom_changes: changes
    })
  })
    .then(function(r) { return r.json(); })
    .then(function() { showToast("療效紀錄已儲存", "success"); })
    .catch(function() { showToast("紀錄失敗", "error"); });
}

function renderMedStats(data) {
  var el = document.getElementById("med-stats");
  var s = data.summary;
  el.innerHTML =
    '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px">' +
    '<div class="stat-box"><div class="stat-num">' + s.total_medications + '</div><div class="stat-label">' + _T('meds.stats.totalLabel') + '</div></div>' +
    '<div class="stat-box"><div class="stat-num">' + s.adherence_rate + '%</div><div class="stat-label">' + _T('meds.stats.adherenceLabel') + '</div></div>' +
    '<div class="stat-box"><div class="stat-num">' + s.total_logs + '</div><div class="stat-label">' + _T('meds.stats.logsLabel') + '</div></div>' +
    '<div class="stat-box"><div class="stat-num">' + s.days + _T('meds.stats.daysUnit') + '</div><div class="stat-label">' + _T('meds.stats.daysLabel') + '</div></div>' +
    '</div>';

  // 畫服藥率折線圖
  if (data.adherence_trend && data.adherence_trend.length > 1) {
    drawAdherenceChart(data.adherence_trend);
  }
}

function drawAdherenceChart(trend) {
  var canvas = document.getElementById("adherence-canvas");
  if (!canvas) return;
  var ctx = canvas.getContext("2d");
  var rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * 2;
  canvas.height = rect.height * 2;
  ctx.scale(2, 2);
  var w = rect.width, h = rect.height;
  var pad = { top: 20, right: 10, bottom: 30, left: 40 };
  var cw = w - pad.left - pad.right;
  var ch = h - pad.top - pad.bottom;

  ctx.clearRect(0, 0, w, h);

  // 背景格線
  ctx.strokeStyle = "rgba(255,255,255,0.08)";
  ctx.lineWidth = 0.5;
  for (var i = 0; i <= 4; i++) {
    var y = pad.top + (ch / 4) * i;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + cw, y); ctx.stroke();
  }

  // Y 軸標籤
  ctx.fillStyle = "#6E6860";
  ctx.font = "10px 'Noto Sans TC'";
  ctx.textAlign = "right";
  for (var i = 0; i <= 4; i++) {
    ctx.fillText((100 - i * 25) + "%", pad.left - 4, pad.top + (ch / 4) * i + 4);
  }

  // 折線
  ctx.beginPath();
  ctx.strokeStyle = "#00D4AA";
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  trend.forEach(function(d, idx) {
    var x = pad.left + (cw / (trend.length - 1)) * idx;
    var y = pad.top + ch - (d.rate / 100 * ch);
    if (idx === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // 資料點
  trend.forEach(function(d, idx) {
    var x = pad.left + (cw / (trend.length - 1)) * idx;
    var y = pad.top + ch - (d.rate / 100 * ch);
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fillStyle = d.rate >= 80 ? "var(--success)" : d.rate >= 50 ? "var(--warning)" : "var(--danger)";
    ctx.fill();
  });

  // X 軸日期
  ctx.fillStyle = "#6E6860";
  ctx.font = "9px 'Noto Sans TC'";
  ctx.textAlign = "center";
  var step = Math.max(1, Math.floor(trend.length / 6));
  trend.forEach(function(d, idx) {
    if (idx % step === 0 || idx === trend.length - 1) {
      var x = pad.left + (cw / (trend.length - 1)) * idx;
      ctx.fillText(d.date.slice(5), x, h - 4);
    }
  });
}

function generateMedReport() {
  var days = document.getElementById("report-days").value;
  document.getElementById("med-report").innerHTML =
    '<div style="text-align:center;padding:30px;color:var(--text-muted)">' +
    '<div class="loading-spinner"></div><p style="margin-top:8px">正在產出回診報告...</p></div>';

  fetch(API + "/medications/report?patient_id=" + _medsPatientId + "&days=" + days)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      document.getElementById("med-report").innerHTML =
        '<div style="padding:16px;background:var(--bg-glass);border-radius:var(--radius-sm);border:1px solid var(--border-glass)">' +
        markdownToHtml(data.report) + '</div>';
    })
    .catch(function() {
      document.getElementById("med-report").innerHTML =
        '<p style="color:var(--danger)">報告生成失敗，請稍後再試。</p>';
    });
}

// ─── 衛教專欄（書架 / 翻開筆記本 兩層 UI）─────────────────────

var _eduDiseases = [];
var _eduSelectedDisease = null;
var _eduSelectedBook = null;
var _eduSelectedDimension = null;  // 給疾病百科用：當前選到的維度
var _eduSelectedTopic = null;      // 給一般書本用：當前選到的章節 key

// 衛教主題 20 本書，分四層書架。
// 點開書 → 直接進入筆記本跨頁：左頁是章節清單、右頁就是內容。
var EDU_BOOKS = [
  // ── 第一層：免疫專區 ──
  { key: "rheum_overview", title: "自體免疫總論", nameEn: "Autoimmune Disease", tag: "AID", color: "c-purple", size: "tall", icon: "shield-alert",
    shelf: 0, intro: "免疫系統為什麼會誤把自己當敵人？了解風濕免疫疾病的共通語言。",
    topics: [
      { key: "what_is_autoimm", label: "什麼是自體免疫疾病", desc: "免疫失衡如何造成多系統發炎" },
      { key: "common_sx",       label: "常見警訊",         desc: "晨僵、雷諾現象、皮疹、不明發燒" },
      { key: "labs_panel",      label: "免疫抽血看什麼",   desc: "ANA、RF、anti-CCP、補體、ENA panel" },
      { key: "flare",           label: "什麼是疾病活動度", desc: "DAS28、SLEDAI、BASDAI 簡介" },
      { key: "vac_immune",      label: "疫苗與免疫抑制",   desc: "活性疫苗禁忌、流感與肺炎接種時機" },
      { key: "preg_plan",       label: "懷孕計畫",         desc: "穩定期再受孕，藥物分級與替換" }
    ] },
  { key: "rheum_ra", title: "類風濕關節炎", nameEn: "Rheumatoid Arthritis", tag: "RA", color: "c-rose", size: "tall", icon: "hand",
    shelf: 0, intro: "RA 是免疫系統把自己的關節當敵人。早期治療能保住關節功能。",
    topics: [
      { key: "ra_recognize",  label: "認識 RA",       desc: "對稱性多關節腫痛、晨僵超過 30 分鐘" },
      { key: "ra_diagnosis",  label: "診斷與分級",    desc: "2010 ACR/EULAR 分類標準" },
      { key: "ra_labs",       label: "抽血指標",      desc: "RF、anti-CCP、ESR、CRP 怎麼看" },
      { key: "ra_dmards",     label: "傳統 DMARD",    desc: "MTX、HCQ、SSZ、Leflunomide" },
      { key: "ra_biologics",  label: "生物製劑",      desc: "TNFi、IL-6i、JAKi 的選擇" },
      { key: "ra_joint_care", label: "關節保護與運動",desc: "省力動作、副木、水中運動" },
      { key: "ra_pregnancy",  label: "RA 與懷孕",     desc: "備孕、孕期、哺乳的藥物調整" }
    ] },
  { key: "rheum_sle", title: "紅斑性狼瘡", nameEn: "Lupus Erythematosus", tag: "SLE", color: "c-red", size: "tall", icon: "flame",
    shelf: 0, intro: "SLE 像千面女郎，可影響皮膚、關節、腎臟、神經、血液。",
    topics: [
      { key: "sle_what",      label: "什麼是 SLE",      desc: "為什麼會發病、誰是高風險族群" },
      { key: "sle_criteria",  label: "分類標準",        desc: "2019 EULAR/ACR 分類條目" },
      { key: "sle_labs",      label: "抽血指標",        desc: "ANA、anti-dsDNA、anti-Sm、補體 C3/C4" },
      { key: "sle_lupus_neph",label: "狼瘡腎炎",        desc: "蛋白尿、腎切片、I–VI 級分類" },
      { key: "sle_meds",      label: "用藥地圖",        desc: "HCQ、類固醇、MMF、Belimumab、Anifrolumab" },
      { key: "sle_sun",       label: "防曬與生活",      desc: "UV 觸發、SPF50+、避免日正當中" },
      { key: "sle_pregnancy", label: "SLE 與懷孕",      desc: "穩定 6 個月以上、低劑量 ASA" }
    ] },
  { key: "rheum_as", title: "僵直性脊椎炎", nameEn: "Ankylosing Spondylitis", tag: "AS", color: "c-indigo", size: "medium", icon: "spine",
    shelf: 0, intro: "年輕男性的下背痛不是閃到腰——可能是 AS 在敲門。",
    topics: [
      { key: "as_back_pain", label: "發炎性下背痛",   desc: "晨僵、活動後改善、夜間痛醒" },
      { key: "as_hlab27",    label: "HLA-B27 與影像", desc: "薦腸關節炎 X 光、MRI 骨髓水腫" },
      { key: "as_exercise",  label: "運動與姿勢",     desc: "伸展、深呼吸、避免長時間彎腰" },
      { key: "as_meds",      label: "NSAID 與生物製劑",desc: "TNFi、IL-17i 的健保條件" },
      { key: "as_comorb",    label: "相關共病",       desc: "葡萄膜炎、銀屑病、發炎性腸道" },
      { key: "as_daily",     label: "生活與工作",     desc: "辦公桌、開車、睡姿建議" }
    ] },
  { key: "rheum_gout", title: "痛風與高尿酸", nameEn: "Gout & Hyperuricemia", tag: "Gout", color: "c-amber", size: "short", icon: "zap",
    shelf: 0, intro: "痛起來像被火燒——但只要好好控尿酸，就不必再忍。",
    topics: [
      { key: "gout_attack", label: "急性發作怎麼辦",   desc: "冰敷、抬高、NSAID 或秋水仙素" },
      { key: "gout_diet",   label: "飲食地雷",         desc: "海鮮、內臟、含糖飲料、酒類" },
      { key: "gout_safe",   label: "可以放心吃的",     desc: "乳製品、咖啡、櫻桃、足量水" },
      { key: "gout_uric",   label: "降尿酸藥物",       desc: "Allopurinol、Febuxostat、Benzbromarone" },
      { key: "gout_tophi",  label: "痛風石與腎結石",   desc: "尿酸鹽結晶造成的長期傷害" },
      { key: "gout_metab",  label: "與代謝症候群",     desc: "高血壓、糖尿病、脂肪肝的連動" }
    ] },
  { key: "rheum_sjogren", title: "乾燥症", nameEn: "Sjögren Syndrome", tag: "SS", color: "c-cyan", size: "medium", icon: "droplet",
    shelf: 0, intro: "口乾、眼乾不只是老化——也可能是免疫系統打到外分泌腺。",
    topics: [
      { key: "sj_self_check", label: "口乾眼乾自我評估", desc: "Schirmer test、唾液流速、SSI 量表" },
      { key: "sj_labs",       label: "診斷工具",         desc: "anti-SSA/Ro、anti-SSB/La、唇腺切片" },
      { key: "sj_eye_care",   label: "眼睛照護",         desc: "人工淚液、淚管栓塞、Cyclosporine" },
      { key: "sj_mouth_care", label: "口腔照護",         desc: "人工唾液、Pilocarpine、含氟漱口" },
      { key: "sj_systemic",   label: "全身性表現",       desc: "周邊神經病變、肺間質、腎小管酸中毒" },
      { key: "sj_lymphoma",   label: "淋巴瘤風險",       desc: "腫大唾液腺與長期追蹤" }
    ] },
  { key: "rheum_fibro", title: "纖維肌痛症", nameEn: "Fibromyalgia", tag: "FM", color: "c-pink", size: "short", icon: "waves",
    shelf: 0, intro: "全身廣泛性疼痛、卻找不到發炎——纖維肌痛症需要被看見。",
    topics: [
      { key: "fm_what",      label: "中樞性敏感化",   desc: "為什麼疼痛訊號被放大" },
      { key: "fm_criteria",  label: "診斷標準",       desc: "2016 ACR：WPI + SSS 評分" },
      { key: "fm_sleep",     label: "睡眠與情緒",     desc: "睡眠衛生與認知行為治療" },
      { key: "fm_exercise",  label: "漸進式運動",     desc: "水中、瑜珈、太極的劑量" },
      { key: "fm_meds",      label: "藥物選擇",       desc: "Pregabalin、Duloxetine、Amitriptyline" }
    ] },
  { key: "rheum_biologics", title: "生物製劑指南", nameEn: "Biologic Therapy", tag: "Bio", color: "c-blue", size: "tall", icon: "syringe",
    shelf: 0, intro: "生物製劑、JAK 抑制劑：聽起來高科技，其實已是免疫疾病的日常。",
    topics: [
      { key: "bio_what",     label: "什麼是生物製劑", desc: "與小分子標靶藥的差別" },
      { key: "bio_classes",  label: "藥物類別速查",   desc: "TNFi / IL-6 / IL-17 / JAKi / B-cell" },
      { key: "bio_nhi",      label: "健保給付條件",   desc: "DAS28、申請與續用、半年評估" },
      { key: "bio_self_inj", label: "居家自行注射",   desc: "皮下注射步驟、針頭處理、儲存" },
      { key: "bio_infect",   label: "感染預防",       desc: "結核、B 肝、帶狀皰疹疫苗" },
      { key: "bio_vaccine",  label: "疫苗時機",       desc: "活性疫苗禁忌與最佳接種時間" },
      { key: "bio_side",     label: "副作用辨識",     desc: "注射部位反應、過敏、肝腎追蹤" }
    ] },

  // ── 第二層：認識與辨識 ──
  { key: "diseases", title: "疾病百科", nameEn: "Disease Encyclopedia", tag: "Dx", color: "c-brown",  size: "tall",   icon: "book-open-text",
    shelf: 1, intro: "查找疾病、了解病程、認識六大衛教維度。",
    dynamic: "diseases" },
  { key: "symptoms", title: "症狀辨識", nameEn: "Symptom Recognition", tag: "Sx", color: "c-rust",   size: "medium", icon: "search-check",
    shelf: 1, intro: "學會分辨身體傳來的訊號，知道該不該擔心。",
    topics: [
      { key: "fever",     label: "發燒處理", desc: "什麼時候只是小感冒、什麼時候要就醫" },
      { key: "headache",  label: "頭痛分辨", desc: "緊張型、偏頭痛與危險性頭痛" },
      { key: "chest_pain",label: "胸痛訊號", desc: "心臟、肌肉、消化道的胸痛差異" },
      { key: "abd_pain",  label: "腹痛位置", desc: "依疼痛部位推測可能的器官" },
      { key: "dizzy",     label: "頭暈與眩暈", desc: "姿勢性、耳石症、血壓變化" },
      { key: "joint_pain",label: "關節腫痛",   desc: "對稱、晨僵、紅熱——免疫科的警訊" },
      { key: "rash",      label: "皮膚紅疹", desc: "蕁麻疹、過敏、感染、自體免疫的辨別" }
    ] },
  { key: "labs", title: "檢驗報告", nameEn: "Laboratory Report", tag: "Lab", color: "c-blue", size: "short", icon: "flask-conical",
    shelf: 1, intro: "把抽血、影像、心電圖的數字翻譯成你聽得懂的話。",
    topics: [
      { key: "cbc",      label: "血液常規 CBC", desc: "白血球、紅血球、血紅素、血小板" },
      { key: "lipid",    label: "血脂三項", desc: "總膽固醇、LDL、HDL、三酸甘油脂" },
      { key: "liver",    label: "肝功能",  desc: "AST、ALT、Bilirubin、ALP" },
      { key: "kidney",   label: "腎功能",  desc: "Creatinine、BUN、eGFR、尿蛋白" },
      { key: "hba1c",    label: "糖化血色素", desc: "HbA1c 與三個月平均血糖" },
      { key: "thyroid",  label: "甲狀腺功能", desc: "TSH、T3、T4 解讀" },
      { key: "esr_crp",  label: "ESR / CRP",  desc: "發炎指標的解讀與限制" }
    ] },

  // ── 第三層：治療與管理 ──
  { key: "medications", title: "藥物指南", nameEn: "Medication Guide", tag: "Rx", color: "c-pink", size: "tall", icon: "pill",
    shelf: 2, intro: "藥不是敵人，是隊友。學會跟藥物相處。",
    topics: [
      { key: "schedule",  label: "用藥時間", desc: "飯前、飯後、睡前的差別" },
      { key: "missed",    label: "忘記吃藥怎麼辦", desc: "什麼時候補、什麼時候別補" },
      { key: "interact",  label: "藥物交互作用", desc: "葡萄柚、保健食品、酒類" },
      { key: "side_eff",  label: "常見副作用", desc: "出現後該停藥還是先觀察" },
      { key: "store",     label: "藥物保存", desc: "冰箱藥、避光、效期管理" },
      { key: "stop",      label: "可以自己停藥嗎", desc: "降血壓、抗生素、類固醇的提醒" },
      { key: "steroid",   label: "類固醇正解", desc: "副作用、減量、月亮臉與骨鬆" }
    ] },
  { key: "nutrition", title: "飲食營養", nameEn: "Nutrition & Diet", tag: "Diet", color: "c-green", size: "medium", icon: "salad",
    shelf: 2, intro: "把廚房變成第二個藥房，從每一餐照顧自己。",
    topics: [
      { key: "balance",   label: "六大類食物", desc: "我的餐盤怎麼分配" },
      { key: "lowsalt",   label: "低鹽飲食", desc: "高血壓、心衰、腎臟病" },
      { key: "lowcarb",   label: "控醣飲食", desc: "糖尿病、減重者的主食安排" },
      { key: "lowfat",    label: "低脂飲食", desc: "高血脂、膽結石、脂肪肝" },
      { key: "highprot",  label: "高蛋白飲食", desc: "術後、銀髮、肌少症" },
      { key: "antiinflam",label: "抗發炎飲食", desc: "地中海、Omega-3、適合自體免疫" },
      { key: "fluid",     label: "水分管理", desc: "腎臟病與心衰的喝水拿捏" }
    ] },
  { key: "exercise", title: "運動復健", nameEn: "Exercise & Rehab", tag: "Rehab", color: "c-lime", size: "short", icon: "activity",
    shelf: 2, intro: "從沙發起身的第一步，就是復原的開始。",
    topics: [
      { key: "aerobic",   label: "有氧運動", desc: "走路、游泳、騎車的劑量" },
      { key: "strength",  label: "肌力訓練", desc: "彈力帶、自體重的家居版本" },
      { key: "balance",   label: "平衡訓練", desc: "預防跌倒的每日 5 分鐘" },
      { key: "stretch",   label: "伸展放鬆", desc: "下背痛、肩頸緊繃的自救" },
      { key: "joint_save",label: "關節保護式運動", desc: "RA / OA 友善動作" },
      { key: "post_op",   label: "術後復健", desc: "膝關節、髖關節置換後" },
      { key: "stroke",    label: "中風復健", desc: "黃金期與居家照護動作" }
    ] },

  // ── 第四層：預防與支持 ──
  { key: "mental", title: "心理健康", nameEn: "Mental Health", tag: "MH", color: "c-purple", size: "medium", icon: "brain",
    shelf: 3, intro: "情緒也是身體的一部份，照顧它，身體才完整。",
    topics: [
      { key: "anxiety",   label: "焦慮自助", desc: "深呼吸、定向、漸進式放鬆" },
      { key: "depress",   label: "認識憂鬱", desc: "持續兩週的訊號與就醫時機" },
      { key: "sleep",     label: "睡眠衛生", desc: "不靠安眠藥的入睡技巧" },
      { key: "chronic_pain_mind", label: "慢性疼痛的心理", desc: "疼痛—情緒—睡眠的循環" },
      { key: "stress",    label: "壓力管理", desc: "工作、家庭、照顧者的喘息" }
    ] },
  { key: "emergency", title: "急救應變", nameEn: "Emergency Care", tag: "ER", color: "c-red", size: "tall", icon: "siren",
    shelf: 3, intro: "三分鐘決定一切——學會正確呼救與第一時間處理。",
    topics: [
      { key: "cpr",       label: "CPR 心肺復甦", desc: "壓胸節奏與 AED 使用" },
      { key: "choke",     label: "哈姆立克法", desc: "成人、兒童與嬰兒的差別" },
      { key: "bleed",     label: "止血包紮", desc: "壓迫止血與抬高患肢" },
      { key: "burn",      label: "燒燙傷處理", desc: "沖、脫、泡、蓋、送" },
      { key: "stroke_sx", label: "中風辨識 FAST", desc: "Face / Arm / Speech / Time" },
      { key: "anaphyl",   label: "過敏性休克", desc: "EpiPen 與 119 的時機" }
    ] },
  { key: "prevent", title: "預防保健", nameEn: "Prevention & Wellness", tag: "Prev", color: "c-cyan", size: "medium", icon: "shield-check",
    shelf: 3, intro: "在生病之前先一步——疫苗、篩檢與生活習慣。",
    topics: [
      { key: "vaccine",   label: "成人疫苗", desc: "流感、肺炎鏈球菌、帶狀皰疹" },
      { key: "screen",    label: "癌症篩檢", desc: "四癌篩檢、低劑量肺部 CT" },
      { key: "checkup",   label: "成人健檢", desc: "40 歲以上每三年一次" },
      { key: "smoke",     label: "戒菸戒酒", desc: "戒菸門診與替代療法" },
      { key: "weight",    label: "體重管理", desc: "BMI、腰圍、體脂與內臟脂肪" }
    ] },
  { key: "chronic", title: "慢性病管理", nameEn: "Chronic Disease", tag: "CD", color: "c-indigo", size: "tall", icon: "clipboard-check",
    shelf: 3, intro: "慢性病不是結束，是每天和身體和解的開始。",
    topics: [
      { key: "diary",     label: "自我監測日誌", desc: "血壓、血糖、體重的紀錄要點" },
      { key: "goal",      label: "與醫師討論目標", desc: "個人化目標而非教科書數字" },
      { key: "comorb",    label: "多重共病", desc: "高血壓 + 糖尿病 + 高血脂的整合照護" },
      { key: "follow",    label: "回診準備", desc: "把問題寫下來、把藥袋帶上" },
      { key: "burnout",   label: "照顧疲勞", desc: "病人與家屬的喘息空間" }
    ] },
  { key: "women_kids", title: "婦幼保健", nameEn: "Maternal & Child", tag: "M&C", color: "c-rose", size: "short", icon: "baby",
    shelf: 3, intro: "孕期、哺乳、成長——給媽媽與孩子的暖心提醒。",
    topics: [
      { key: "preg",      label: "孕期保健", desc: "葉酸、產檢時程、體重增加" },
      { key: "breastfeed",label: "哺乳指南", desc: "親餵、瓶餵、副食品銜接" },
      { key: "vac_kid",   label: "兒童疫苗", desc: "公費與自費接種時程" },
      { key: "growth",    label: "生長發育", desc: "身高體重曲線、語言發展" },
      { key: "fever_kid", label: "兒童發燒處理", desc: "退燒藥與就醫指標" }
    ] },
  { key: "elder", title: "銀髮照護", nameEn: "Elder Care", tag: "Eld", color: "c-amber", size: "medium", icon: "heart-handshake",
    shelf: 3, intro: "陪伴長輩好好變老——失能、失智、跌倒、營養。",
    topics: [
      { key: "fall",      label: "預防跌倒", desc: "居家環境與肌力訓練" },
      { key: "dementia",  label: "失智照護", desc: "早期徵兆與互動技巧" },
      { key: "sarcop",    label: "肌少症", desc: "蛋白質補充與阻力訓練" },
      { key: "polyphar",  label: "多重用藥", desc: "藥袋大整理與重複用藥" },
      { key: "advcare",   label: "預立醫療", desc: "ACP、AD 與安寧的選擇" }
    ] },

  // ── 第五層：精神系列 ──
  { key: "psych_mood", title: "情緒障礙", nameEn: "Mood Disorders", tag: "Mood", color: "c-purple", size: "tall", icon: "cloud-rain",
    shelf: 4, intro: "情緒不只是「想開一點」——是大腦化學物質的失衡，可以治療。",
    topics: [
      { key: "mdd",           label: "重度憂鬱症",     desc: "DSM-5 診斷、抗憂鬱藥、心理治療" },
      { key: "persistent_dep",label: "持續性憂鬱症",   desc: "兩年以上的低落，不是性格問題" },
      { key: "bipolar",       label: "雙相情緒障礙",   desc: "高低起伏與情緒穩定劑" },
      { key: "seasonal",      label: "季節性情緒障礙", desc: "冬季憂鬱、光照治療" },
      { key: "postpartum",    label: "產後憂鬱",       desc: "與產後情緒低落 baby blues 的差別" }
    ] },
  { key: "psych_anxiety", title: "焦慮譜系", nameEn: "Anxiety Spectrum", tag: "Anx", color: "c-rose", size: "tall", icon: "wind",
    shelf: 4, intro: "焦慮不是膽小，是大腦的警報系統太敏感——可以調回正常音量。",
    topics: [
      { key: "gad",           label: "廣泛性焦慮症",   desc: "對所有事情都擔心個沒完" },
      { key: "panic",         label: "恐慌症",         desc: "突發心悸、瀕死感的處理" },
      { key: "social",        label: "社交焦慮症",     desc: "在人前說話、聚餐就崩潰" },
      { key: "phobia",        label: "特定恐懼症",     desc: "怕蟲、怕高、怕針的暴露療法" },
      { key: "ocd",           label: "強迫症 OCD",     desc: "強迫思考、強迫行為、ERP" },
      { key: "ptsd",          label: "創傷後壓力症",   desc: "閃回、過度警覺、EMDR" }
    ] },
  { key: "psych_severe", title: "思覺失調與成癮", nameEn: "Psychosis & Addiction", tag: "Psy", color: "c-indigo", size: "tall", icon: "sparkles",
    shelf: 4, intro: "幻覺、妄想、戒不掉的物質——都是大腦的疾病，不是道德問題。",
    topics: [
      { key: "schizophrenia", label: "思覺失調症",     desc: "幻覺、妄想、抗精神病藥" },
      { key: "delusional",    label: "妄想症",         desc: "局部的、固定的錯誤信念" },
      { key: "alcohol",       label: "酒癮戒治",       desc: "戒斷症狀與治療藥物" },
      { key: "smoking",       label: "菸癮戒治",       desc: "戒菸門診、尼古丁替代、伐尼克蘭" },
      { key: "sedative",      label: "安眠藥依賴",     desc: "苯二氮平類的減量計畫" }
    ] },
  { key: "psych_neurodev", title: "神經發展疾患", nameEn: "Neurodevelopmental", tag: "ND", color: "c-cyan", size: "tall", icon: "puzzle",
    shelf: 4, intro: "從小到大跟著的大腦差異——自閉、ADHD 不是「長大就好」，但有方法好好相處。",
    topics: [
      { key: "asd_adult",     label: "成人自閉症光譜", desc: "高功能、亞斯伯格、社交特質與支持" },
      { key: "adhd_adult",    label: "成人 ADHD",      desc: "拖延、衝動、注意力與藥物管理" },
      { key: "tourette",      label: "妥瑞症",         desc: "抽動、聲音抽動、共病焦慮" },
      { key: "id",            label: "智能發展障礙",   desc: "輕中重度的支持需求與資源" },
      { key: "ld_adult",      label: "學習障礙",       desc: "閱讀、書寫、數學的特定學障" },
      { key: "dcd",           label: "動作協調障礙",   desc: "笨手笨腳、書寫困難的辨識" }
    ] },

  // ── 第六層：小兒系列 ──
  { key: "peds_common", title: "兒童常見病", nameEn: "Common Pediatric", tag: "Peds", color: "c-amber", size: "tall", icon: "thermometer",
    shelf: 5, intro: "孩子的常見不舒服——這本書幫你判斷在家照顧 vs. 該去看醫生。",
    topics: [
      { key: "kid_fever",     label: "兒童發燒",       desc: "幾度算發燒、退燒藥、何時急診" },
      { key: "ge_dehydration",label: "腸胃炎與脫水",   desc: "電解質補充、口服補液、警訊" },
      { key: "uri",           label: "上呼吸道感染",   desc: "感冒、喉嚨痛、流感的辨別" },
      { key: "om",            label: "中耳炎",         desc: "抗生素時機、反覆感染處理" },
      { key: "ad_kid",        label: "異位性皮膚炎",   desc: "保濕、外用類固醇、避開誘因" }
    ] },
  { key: "peds_allergy", title: "過敏與氣喘", nameEn: "Allergy & Asthma", tag: "Allg", color: "c-cyan", size: "medium", icon: "wind",
    shelf: 5, intro: "鼻塞、咳嗽、起疹子——孩子過敏不少見，可以從生活控制起來。",
    topics: [
      { key: "ar",            label: "鼻過敏",         desc: "鼻塞、流鼻水、抗組織胺與鼻噴劑" },
      { key: "food_allergy",  label: "食物過敏",       desc: "蛋奶、花生、海鮮的辨識與處理" },
      { key: "kid_asthma",    label: "兒童氣喘",       desc: "急救噴劑、保養藥、行動計畫" },
      { key: "urticaria",     label: "蕁麻疹",         desc: "急性、慢性蕁麻疹的處理" },
      { key: "atopic_triad",  label: "異位性三聯症",   desc: "氣喘 + 鼻過敏 + 異位性皮膚炎" }
    ] },
  { key: "peds_growth", title: "生長與發展", nameEn: "Growth & Development", tag: "G&D", color: "c-rose", size: "tall", icon: "baby",
    shelf: 5, intro: "孩子長得好不好？這本書幫你對照里程碑、安排疫苗與營養。",
    topics: [
      { key: "growth_chart",  label: "身高體重曲線",   desc: "百分位、生長遲滯與性早熟" },
      { key: "language",      label: "語言發展里程碑", desc: "1 歲、2 歲、3 歲該會的話" },
      { key: "motor",         label: "動作發展",       desc: "翻身、爬、走、跑的關鍵期" },
      { key: "kid_vaccine",   label: "兒童疫苗時程",   desc: "公費 + 自費的完整時程表" },
      { key: "kid_nutrition", label: "副食品與飲食",   desc: "副食品銜接、挑食、肥胖" }
    ] },
  { key: "peds_mental", title: "兒童精神與學習", nameEn: "Pediatric Mental", tag: "PM", color: "c-pink", size: "medium", icon: "graduation-cap",
    shelf: 5, intro: "上課坐不住、不講話、害怕上學——孩子的內心需要被看見。",
    topics: [
      { key: "kid_adhd",      label: "兒童 ADHD",      desc: "注意力、衝動、過動的評估與藥物" },
      { key: "asd",           label: "自閉症光譜",     desc: "早期跡象、早療資源" },
      { key: "ld",            label: "學習障礙",       desc: "讀寫、數學的特定學障" },
      { key: "kid_anxiety",   label: "兒童焦慮",       desc: "分離焦慮、選擇性緘默" },
      { key: "school_adapt",  label: "校園適應問題",   desc: "拒學、霸凌、轉學的支持" }
    ] },

  // ── 第七層：神經系列 ──
  { key: "neuro_headache", title: "頭痛專區", nameEn: "Headache Care", tag: "HA", color: "c-rose", size: "tall", icon: "brain",
    shelf: 6, intro: "頭痛分很多種——學會辨識，才知道該吃止痛藥還是衝急診。",
    topics: [
      { key: "migraine",      label: "偏頭痛",         desc: "前兆、誘因、急性與預防用藥" },
      { key: "tth",           label: "緊張型頭痛",     desc: "肩頸僵硬與生活壓力" },
      { key: "cluster",       label: "叢集型頭痛",     desc: "「自殺型頭痛」的辨識與治療" },
      { key: "danger_ha",     label: "危險性頭痛",     desc: "忽然劇烈、伴神經學異常要急診" },
      { key: "facial_palsy",  label: "顏面神經麻痺",   desc: "貝爾氏麻痺、類固醇黃金期" }
    ] },
  { key: "neuro_stroke", title: "腦血管疾病", nameEn: "Cerebrovascular", tag: "CVA", color: "c-red", size: "tall", icon: "droplet",
    shelf: 6, intro: "中風是急症——黃金 3 小時，越早治療恢復越好。",
    topics: [
      { key: "ischemic",      label: "缺血性中風",     desc: "血栓溶解、取栓、黃金時間窗" },
      { key: "hemorrhagic",   label: "出血性中風",     desc: "高血壓、動脈瘤的破裂風險" },
      { key: "tia",           label: "短暫性缺血 TIA", desc: "「小中風」是大中風的警訊" },
      { key: "moyamoya",      label: "毛毛樣腦血管疾病", desc: "頸內動脈狹窄、煙霧狀側枝循環、繞道手術" },
      { key: "stroke_rehab",  label: "中風復健",       desc: "黃金期、語言、吞嚥、肢體" },
      { key: "stroke_prev",   label: "中風預防",       desc: "血壓、心房顫動、抗凝血藥" }
    ] },
  { key: "neuro_degen", title: "退化性神經疾病", nameEn: "Neurodegenerative", tag: "Deg", color: "c-amber", size: "medium", icon: "sunset",
    shelf: 6, intro: "失智、帕金森不是必然的老化——早期介入能延緩很多。",
    topics: [
      { key: "alzheimer",     label: "阿茲海默失智",   desc: "記憶為主、Donepezil、Lecanemab" },
      { key: "vascular_dem",  label: "血管型失智",     desc: "與中風相關，控好血管因子" },
      { key: "lbd",           label: "路易氏體失智",   desc: "幻覺、運動障礙合併認知" },
      { key: "parkinson",     label: "帕金森氏症",     desc: "顫抖、僵硬、慢動作與 L-dopa" },
      { key: "als",           label: "漸凍症 ALS",     desc: "運動神經元退化的支持照護" }
    ] },
  { key: "neuro_epilepsy", title: "癲癇與神經免疫", nameEn: "Epilepsy & NeuroImmune", tag: "EpNI", color: "c-cyan", size: "medium", icon: "zap",
    shelf: 6, intro: "突發抽搐或反覆發炎——神經系統也會有自己的「電」與「免疫」問題。",
    topics: [
      { key: "epi_dx",        label: "癲癇診斷與分類", desc: "局部、全身、腦電圖、影像" },
      { key: "aed",           label: "抗癲癇用藥",     desc: "選藥原則與駕車規範" },
      { key: "ms",            label: "多發性硬化症",   desc: "復發緩解、疾病修飾治療" },
      { key: "auto_enc",      label: "自體免疫腦炎",   desc: "近年新發現的可治療腦炎" }
    ] },
  { key: "neuro_pain", title: "神經痛與周邊神經", nameEn: "Neuropathy", tag: "PN", color: "c-blue", size: "tall", icon: "network",
    shelf: 6, intro: "麻、刺、燒灼的痛——那是神經本身在叫救命，跟肌肉酸痛不一樣。",
    topics: [
      { key: "dpn",           label: "糖尿病神經病變", desc: "腳麻、刺痛與血糖控制" },
      { key: "tn",            label: "三叉神經痛",     desc: "臉部劇痛、Carbamazepine" },
      { key: "phn",           label: "帶狀皰疹後神經痛", desc: "皮蛇後遺症與疫苗預防" },
      { key: "cts",           label: "腕隧道症候群",   desc: "手麻、夜間加重、護腕與手術" },
      { key: "cipn",          label: "化療後神經病變", desc: "癌友常見的麻痛照護" }
    ] }
];

// 疾病維度（給疾病百科這本書用）
var EDU_DISEASE_DIMENSIONS = [
  { key: "disease_awareness",     label: "疾病管理",   desc: "了解疾病、治療與費用" },
  { key: "symptom_recognition",   label: "症狀辨認",   desc: "學會辨別身體訊號" },
  { key: "medication_knowledge",  label: "用藥知識",   desc: "藥物不可怕，是好朋友" },
  { key: "self_management",       label: "自我管理",   desc: "飲食、運動、生活調整" },
  { key: "emergency_response",    label: "緊急應變",   desc: "什麼時候該去看醫生" },
  { key: "complication_awareness",label: "併發症認知", desc: "了解風險，更有信心" }
];

function education() {
  return `
    <div class="card" style="margin-bottom:14px">
      <h2 style="display:flex;align-items:center;gap:8px">
        <i data-lucide="book-heart" style="width:22px;height:22px"></i> ${_T('edu.title')}
      </h2>
      <p style="margin-top:6px;color:var(--text-dim)">
        ${_T('edu.intro')}
      </p>
      <div id="edu-breadcrumb" class="edu-breadcrumb" style="margin-top:12px">
        <button class="crumb current" onclick="eduGoToShelf()"><i data-lucide="library" style="width:14px;height:14px;vertical-align:middle"></i> ${_T('edu.crumb.shelf')}</button>
      </div>
    </div>

    <!-- Stage 1 : Bookshelf -->
    <div id="edu-stage-shelf" class="edu-stage active">
      <div id="edu-my-shelf" class="card" style="margin-bottom:14px;display:none">
        <h3 style="display:flex;align-items:center;gap:8px;font-size:1rem;margin:0">
          <i data-lucide="library" style="width:18px;height:18px"></i> 我的疾病書架
        </h3>
        <p style="margin-top:6px;color:var(--text-dim);font-size:.85rem">
          每登錄一個疾病就會多一本書，內含疾病介紹、用藥、副作用、長期風險、自我管理等六大面向。
        </p>
        <div id="edu-my-shelf-row" class="bookshelf-wrap" style="margin-top:10px">
          <div class="shelf">
            <div class="shelf-row" id="edu-my-shelf-books"></div>
            <div class="shelf-plank"></div>
          </div>
        </div>
      </div>
      <div id="edu-my-articles" class="card" style="margin-bottom:14px;display:none">
        <h3 style="display:flex;align-items:center;gap:8px;font-size:1rem;margin:0">
          <i data-lucide="book-marked" style="width:18px;height:18px"></i> 我的疾病衛教文章
        </h3>
        <p style="margin-top:6px;color:var(--text-dim);font-size:.85rem">
          專屬於你登錄疾病的衛教文，依疾病分區整理。
        </p>
        <div id="edu-my-articles-list" style="margin-top:10px"></div>
      </div>
      <div id="edu-related" class="card" style="margin-bottom:14px;display:none">
        <h3 style="display:flex;align-items:center;gap:8px;font-size:1rem;margin:0">
          <i data-lucide="git-branch" style="width:18px;height:18px"></i> 為你推送的相關疾病
        </h3>
        <p id="edu-related-desc" style="margin-top:6px;color:var(--text-dim);font-size:.85rem">
          根據你登錄的疾病，自動整理臨床上常一起出現的共病，提早了解可以更安心。
        </p>
        <div id="edu-related-list" style="margin-top:12px;display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px"></div>
      </div>
      <div id="edu-featured" class="card" style="margin-bottom:14px">
        <h3 style="display:flex;align-items:center;gap:8px;font-size:1rem;margin:0">
          <i data-lucide="sparkles" style="width:18px;height:18px"></i> ${_T('edu.featured.title')}
        </h3>
        <p style="margin-top:6px;color:var(--text-dim);font-size:.85rem">
          ${_T('edu.featured.desc')}
        </p>
        <div id="edu-featured-list" style="margin-top:12px;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px">
          <div style="color:var(--text-dim);font-size:.85rem">${_T('edu.loading')}</div>
        </div>
      </div>
      <div class="bookshelf-wrap">
        <div class="bookshelf-title">${_T('edu.shelf.banner')}</div>
        ${renderBookshelf()}
      </div>
    </div>

    <!-- Stage 2 : Open notebook（左頁 = 章節清單，右頁 = 內容） -->
    <div id="edu-stage-notebook" class="edu-stage">
      <div class="notebook-wrap">
        <div id="edu-notebook" class="notebook"></div>
      </div>
    </div>`;
}

function renderBookshelf() {
  var shelves = [
    { label: _T('edu.shelf.01'), books: [] },
    { label: _T('edu.shelf.02'), books: [] },
    { label: _T('edu.shelf.03'), books: [] },
    { label: _T('edu.shelf.04'), books: [] },
    { label: _T('edu.shelf.05'), books: [] },
    { label: _T('edu.shelf.06'), books: [] },
    { label: _T('edu.shelf.07'), books: [] }
  ];
  EDU_BOOKS.forEach(function(b) { shelves[b.shelf].books.push(b); });

  var html = "";
  shelves.forEach(function(s) {
    html += '<div class="shelf">';
    html += '<div class="shelf-label">' + escapeHtml(s.label) + '</div>';
    html += '<div class="shelf-row">';
    s.books.forEach(function(b) {
      html +=
        '<button class="book ' + b.color + ' ' + b.size + '" ' +
        'onclick="eduOpenBook(\'' + b.key + '\')" title="' + escapeHtml(b.title + (b.nameEn ? "・" + b.nameEn : "")) + '">' +
          '<i data-lucide="' + b.icon + '" class="book-icon" style="width:16px;height:16px"></i>' +
          '<span class="book-spine">' +
            '<span class="book-title">' + escapeHtml(b.title) + '</span>' +
            (b.nameEn ? '<span class="book-subtitle">' + escapeHtml(b.nameEn) + '</span>' : '') +
          '</span>' +
          '<span class="book-tag">' + escapeHtml(b.tag) + '</span>' +
        '</button>';
    });
    html += '</div>';
    html += '<div class="shelf-plank"></div>';
    html += '</div>';
  });
  return html;
}

function loadEducationPage() {
  // 首次載入時抓疾病列表，給「疾病百科」這本書用
  fetch(API + "/education/diseases")
    .then(function(r) { return r.json(); })
    .then(function(data) { _eduDiseases = data.diseases || []; })
    .catch(function() { /* 不擋整體 UI */ });

  loadFeaturedArticles();
  loadMyDiseases();
  loadRelatedDiseases();

  // 確保 lucide icon 出現
  if (typeof lucide !== 'undefined') setTimeout(function() { lucide.createIcons(); }, 30);
}

// ── 我的疾病書架 + 我的疾病衛教文章 ────────────────────────
var _MY_DISEASE_COLORS = ['c-brown', 'c-blue', 'c-green', 'c-red', 'c-purple', 'c-yellow', 'c-teal'];
var _MY_DISEASE_SIZES = ['tall', 'short', 'wide'];

function loadMyDiseases() {
  var shelfCard = document.getElementById('edu-my-shelf');
  var articlesCard = document.getElementById('edu-my-articles');
  if (!shelfCard && !articlesCard) return;

  // 從基本資料的自由文字，抽出未被內建清單辨識到的疾病——這些走 AI 即時生成
  var basicInfo = (typeof getBasicInfo === 'function') ? getBasicInfo() || {} : {};
  var freeText = [basicInfo.current_disease, basicInfo.conditions, basicInfo.allergies].filter(Boolean).join('\n');
  var extras = (typeof extractUnrecognizedDiseases === 'function') ? extractUnrecognizedDiseases(freeText) : [];

  resolvePatientIcd10Codes(function(codes) {
    var hasCodes = codes && codes.length;
    if (!hasCodes && !extras.length) {
      if (shelfCard) shelfCard.style.display = 'none';
      if (articlesCard) articlesCard.style.display = 'none';
      return;
    }
    if (!hasCodes) {
      // 純 extras：直接渲染 AI 生成書本，articles 卡隱藏
      renderMyDiseaseShelf([], extras);
      if (articlesCard) articlesCard.style.display = 'none';
      if (typeof lucide !== 'undefined') lucide.createIcons();
      return;
    }
    fetch(API + '/education/my-diseases?codes=' + encodeURIComponent(codes.join(',')))
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        // 只渲染後端真的支援的疾病——不在 ICD10_MAP 的代碼點下去會跳 400
        var items = ((data && data.items) || []).filter(function(it) { return it && it.is_supported; });
        if (!items.length && !extras.length) {
          if (shelfCard) shelfCard.style.display = 'none';
          if (articlesCard) articlesCard.style.display = 'none';
          return;
        }
        renderMyDiseaseShelf(items, extras);
        renderMyDiseaseArticles(items);
        if (typeof lucide !== 'undefined') lucide.createIcons();
      })
      .catch(function() {
        if (extras.length) {
          renderMyDiseaseShelf([], extras);
          if (articlesCard) articlesCard.style.display = 'none';
          if (typeof lucide !== 'undefined') lucide.createIcons();
        } else {
          if (shelfCard) shelfCard.style.display = 'none';
          if (articlesCard) articlesCard.style.display = 'none';
        }
      });
  });
}

// 從基本資料自由文字裡撈出「沒被內建清單辨識到」的疾病字串
// 流程：先把所有 DISEASE_KEYWORDS 命中的子字串挖掉，剩下的依中英文標點切塊，過濾雜訊。
var _EXTRA_STOPWORDS = {
  '有':1,'無':1,'沒有':1,'已經':1,'目前':1,'近期':1,'常常':1,'我有':1,'我':1,
  '本人':1,'病人':1,'患者':1,'醫師':1,'吃':1,'吃藥':1,'服用':1,'使用':1,'治療':1,
  '中':1,'了':1,'過':1,'過敏':1,'藥物':1,'食物':1,'青黴素':1,'盤尼西林':1,
  '不明':1,'健康':1,'正常':1,'無特殊':1,'無病史':1,'未知':1,'其他':1,
};
function extractUnrecognizedDiseases(text) {
  if (!text) return [];
  var s = String(text);
  // 先把所有已知關鍵字（含同義詞）從文字中挖掉，避免「糖尿病、龐貝氏症」誤把「糖尿病」當 extra
  if (typeof DISEASE_KEYWORDS !== 'undefined') {
    DISEASE_KEYWORDS.forEach(function(p) {
      var kw = p[0];
      if (!kw) return;
      // 大小寫不敏感地挖掉所有命中（sle/SLE 都算）
      var re = new RegExp(_escapeForRegex(kw), 'gi');
      s = s.replace(re, '|');
    });
  }
  // 中英文標點 + 空白 + 連接詞 切塊
  var chunks = s.split(/[、，；。.,;:：\n\r\t（）()\[\]\|\s]+|和|與|跟|另外|還有|以及/);
  var seen = {};
  var out = [];
  chunks.forEach(function(c) {
    c = (c || '').trim();
    if (!c) return;
    if (c.length < 2 || c.length > 18) return;
    if (!/[A-Za-z一-鿿㐀-䶿]/.test(c)) return;
    if (_EXTRA_STOPWORDS[c]) return;
    // 必須結尾像疾病字眼，避免「只有」「年了」「目前」等敘述被當成疾病
    if (!/(病|症|炎|癌|瘤|症候群|不全|衰竭|病變|麻痺|結石|出血|梗塞|腫瘤|硬化|增生|過敏症|缺乏|缺乏症|阻塞|血栓|纖維化|畸形|失調|障礙|疝氣)$/.test(c)) return;
    if (seen[c]) return;
    seen[c] = true;
    out.push(c);
  });
  // 最多 8 個，避免雜訊塞爆書架
  return out.slice(0, 8);
}

// 全局：未列入內建清單的疾病（onclick 用 index 找回名稱，避免 escape 風險）
var _eduExtraDiseases = [];

function renderMyDiseaseShelf(items, extras) {
  extras = extras || [];
  var card = document.getElementById('edu-my-shelf');
  var row = document.getElementById('edu-my-shelf-books');
  if (!card || !row) return;
  if (!items.length && !extras.length) { card.style.display = 'none'; return; }

  _eduExtraDiseases = extras.slice();

  var html = items.map(function(it, idx) {
    var color = _MY_DISEASE_COLORS[idx % _MY_DISEASE_COLORS.length];
    var size  = _MY_DISEASE_SIZES[idx % _MY_DISEASE_SIZES.length];
    var nameSafe = escapeHtml(it.name);
    var icd10Safe = escapeHtml(it.icd10);
    return '<button class="book ' + color + ' ' + size + '" ' +
           'onclick="eduOpenMyDiseaseBook(\'' + icd10Safe + '\',\'' + nameSafe + '\')" ' +
           'title="' + nameSafe + '（' + icd10Safe + '）">' +
             '<i data-lucide="book-heart" class="book-icon" style="width:16px;height:16px"></i>' +
             '<span class="book-spine">' +
               '<span class="book-title">' + nameSafe + '</span>' +
               '<span class="book-subtitle">' + icd10Safe + '</span>' +
             '</span>' +
             '<span class="book-tag">My</span>' +
           '</button>';
  }).join('');

  // 未列入內建清單的疾病——用 sparkles 圖示 + AI tag 區別
  html += extras.map(function(name, j) {
    var i = items.length + j;
    var color = _MY_DISEASE_COLORS[i % _MY_DISEASE_COLORS.length];
    var size  = _MY_DISEASE_SIZES[i % _MY_DISEASE_SIZES.length];
    var nameSafe = escapeHtml(name);
    return '<button class="book ' + color + ' ' + size + '" ' +
           'onclick="eduOpenExtraDisease(' + j + ')" ' +
           'title="' + nameSafe + '（AI 即時生成衛教）">' +
             '<i data-lucide="sparkles" class="book-icon" style="width:16px;height:16px"></i>' +
             '<span class="book-spine">' +
               '<span class="book-title">' + nameSafe + '</span>' +
               '<span class="book-subtitle">AI 生成</span>' +
             '</span>' +
             '<span class="book-tag">AI</span>' +
           '</button>';
  }).join('');

  row.innerHTML = html;
  card.style.display = '';
}

function eduOpenMyDiseaseBook(icd10, name) {
  // 使用既有的疾病百科書本流程：開書 → 預選疾病 → 右頁列出六大維度
  if (typeof eduOpenBook === 'function') eduOpenBook('diseases');
  setTimeout(function() {
    if (typeof eduPickDisease === 'function') eduPickDisease(icd10, name);
  }, 50);
}

// 開啟「未列入內建清單」的疾病：合成一本書，6 個章節走 /education/generate 的 topic 模式
function eduOpenExtraDisease(idx) {
  var name = _eduExtraDiseases[idx];
  if (!name) return;
  _eduOpenBookObject({
    key: 'extra:' + name,
    title: name,
    icon: 'sparkles',
    intro: '「' + name + '」不在內建清單，內容由 MD.Piece 即時為你生成；請以實際醫師判讀為準。',
    topics: [
      { key: 'awareness',     label: '認識這個疾病',     desc: '是什麼、誰會得、治療概觀' },
      { key: 'symptoms',      label: '症狀辨識',         desc: '常見症狀與身體訊號' },
      { key: 'meds',          label: '用藥與副作用',     desc: '常用藥物作用、注意事項' },
      { key: 'self',          label: '自我管理',         desc: '飲食、運動、生活調整' },
      { key: 'emergency',     label: '緊急應變',         desc: '何時要立刻就醫' },
      { key: 'complications', label: '長期風險與併發症', desc: '長期影響與追蹤建議' },
    ],
  });
}

function renderMyDiseaseArticles(items) {
  var card = document.getElementById('edu-my-articles');
  var list = document.getElementById('edu-my-articles-list');
  if (!card || !list) return;

  // 只把有實際文章的疾病顯示在這裡；沒有文章的疾病在書架上仍可展開六大維度
  var withArticles = items.filter(function(it) { return (it.articles || []).length > 0; });
  if (!withArticles.length) { card.style.display = 'none'; return; }

  list.innerHTML = withArticles.map(function(it) {
    var arts = (it.articles || []).slice(0, 6).map(function(a) {
      var tagHtml = (a.tags || []).slice(0, 2).map(function(t) {
        return '<span style="display:inline-block;padding:1px 6px;border-radius:8px;background:var(--bg-soft);font-size:.7rem;color:var(--text-dim);margin-right:4px">' + escapeHtml(t) + '</span>';
      }).join('');
      return '<button class="article-card" onclick="eduOpenArticle(\'' + escapeHtml(a.slug) + '\')" ' +
             'style="text-align:left;padding:10px;border-radius:8px;border:1px solid var(--border);' +
             'background:var(--bg-card);cursor:pointer;display:flex;flex-direction:column;gap:4px">' +
             '<div style="font-weight:600;font-size:.9rem;line-height:1.4">' + escapeHtml(a.title) + '</div>' +
             (a.summary ? '<div style="font-size:.78rem;color:var(--text-dim);line-height:1.5">' + escapeHtml(a.summary) + '</div>' : '') +
             (tagHtml ? '<div style="margin-top:2px">' + tagHtml + '</div>' : '') +
             '</button>';
    }).join('');

    var more = (it.article_count > 6)
      ? '<button onclick="eduOpenMyDiseaseBook(\'' + escapeHtml(it.icd10) + '\',\'' + escapeHtml(it.name) + '\')" ' +
        'style="margin-top:6px;padding:6px 10px;border-radius:8px;border:1px solid var(--border);background:var(--bg-soft);' +
        'cursor:pointer;font-size:.78rem;color:var(--text-dim)">在書架展開更多 →</button>'
      : '';

    return '<section style="margin-top:10px;padding:10px;border-radius:10px;background:var(--bg-soft)">' +
           '<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px">' +
           '<strong style="font-size:.95rem">' + escapeHtml(it.name) + '</strong>' +
           '<span style="font-size:.7rem;color:var(--text-dim)">ICD-10：' + escapeHtml(it.icd10) + '</span>' +
           '<span style="margin-left:auto;font-size:.7rem;color:var(--text-dim)">共 ' + it.article_count + ' 篇</span>' +
           '</div>' +
           '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px">' + arts + '</div>' +
           more +
           '</section>';
  }).join('');
  card.style.display = '';
}

// ── 為登錄疾病的患者自動推送相關疾病衛教 ──────────────────
function loadRelatedDiseases() {
  var card = document.getElementById("edu-related");
  var list = document.getElementById("edu-related-list");
  if (!card || !list) return;

  resolvePatientIcd10Codes(function(codes) {
    if (!codes || !codes.length) {
      card.style.display = "none";
      return;
    }
    fetch(API + "/education/related?codes=" + encodeURIComponent(codes.join(",")) + "&limit=6")
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        if (!data || !data.items || !data.items.length) {
          card.style.display = "none";
          return;
        }
        list.innerHTML = data.items.map(renderRelatedDiseaseCard).join("");
        card.style.display = "";
        if (typeof lucide !== 'undefined') lucide.createIcons();
      })
      .catch(function() { card.style.display = "none"; });
  });
}

// 取得登錄使用者的 icd10_codes：先看 localStorage user 物件，再退回 /patients/{id}
function resolvePatientIcd10Codes(callback) {
  var user = (typeof getCurrentUser === 'function') ? getCurrentUser() : null;
  if (user && Array.isArray(user.icd10_codes) && user.icd10_codes.length) {
    callback(user.icd10_codes);
    return;
  }
  // 患者不需要懂 ICD-10——從「我的基本資料」自由文字自動辨識
  if (typeof getBasicInfo === 'function' && typeof detectIcd10FromText === 'function') {
    var info = getBasicInfo() || {};
    var combined = [info.current_disease, info.conditions, info.allergies].filter(Boolean).join('\n');
    var detected = detectIcd10FromText(combined);
    if (detected.length) {
      // 寫回 localStorage user，下次直接命中（也避免每次重新跑辨識）
      if (user && user.id) { user.icd10_codes = detected; setCurrentUser(user); }
      callback(detected);
      return;
    }
  }
  var pid = (typeof getStablePatientId === 'function') ? getStablePatientId() : (user && user.id);
  if (!pid) { callback([]); return; }
  fetch(API + "/patients/" + encodeURIComponent(pid))
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(p) {
      callback((p && Array.isArray(p.icd10_codes)) ? p.icd10_codes : []);
    })
    .catch(function() { callback([]); });
}

// ── 從日常用語自動辨識疾病 → ICD-10 ─────────────────────
// 患者寫「糖尿病、高血壓」就自動對應到 E11、I10，不必懂任何代碼。
// 排序由長到短，避免「糖尿病」誤蓋「第二型糖尿病」。
var DISEASE_KEYWORDS = [
  ['第一型糖尿病','E10'], ['I型糖尿病','E10'], ['1型糖尿病','E10'],
  ['第二型糖尿病','E11'], ['II型糖尿病','E11'], ['2型糖尿病','E11'],
  ['糖尿病','E11'],
  ['高血脂症','E78'], ['高血脂','E78'], ['膽固醇高','E78'], ['血脂高','E78'],
  ['甲狀腺功能低下','E03'], ['甲狀腺低下','E03'], ['甲低','E03'],
  ['甲狀腺功能亢進','E05'], ['甲狀腺亢進','E05'], ['甲亢','E05'],
  ['原發性高血壓','I10'], ['高血壓','I10'],
  ['慢性缺血性心臟病','I25'], ['缺血性心臟病','I25'], ['冠狀動脈心臟病','I25'], ['冠心病','I25'],
  ['心臟衰竭','I50'], ['心衰竭','I50'], ['心衰','I50'],
  ['心房顫動','I48'], ['心房纖顫','I48'],
  ['腦中風','I63'], ['腦梗塞','I63'], ['中風','I63'],
  // 呼吸 / 過敏
  ['過敏性鼻炎','J30'], ['過敏鼻炎','J30'], ['鼻過敏','J30'],
  ['氣喘','J45'],
  ['慢性阻塞性肺病','J44'], ['肺氣腫','J44'], ['COPD','J44'],
  // 消化
  ['克隆氏症','K50'], ['克隆症','K50'],
  ['潰瘍性結腸炎','K51'],
  ['肝纖維化','K74'], ['肝硬化','K74'],
  ['乳糜瀉','K90'], ['麩質不耐','K90'],
  // 自體免疫 / 風濕
  ['系統性紅斑性狼瘡','M32'], ['紅斑性狼瘡','M32'], ['狼瘡','M32'], ['SLE','M32'],
  ['修格蘭氏症候群','M35'], ['修格蘭氏症','M35'], ['修格蘭','M35'], ['修格連','M35'], ['乾燥症候群','M35'], ['乾燥症','M35'], ['Sjogren','M35'], ['Sjögren','M35'],
  ['僵直性脊椎炎','M45'], ['僵脊','M45'], ['AS','M45'],
  ['全身性硬化症','M34'], ['硬皮症','M34'],
  ['皮肌炎','M33'], ['多發性肌炎','M33'],
  ['結節性多動脈炎','M30'], ['川崎病','M30'],
  ['顯微多血管炎','M31'], ['韋格納肉芽腫','M31'], ['好酸性肉芽腫多血管炎','M31'], ['巨細胞動脈炎','M31'], ['顳動脈炎','M31'], ['血管炎','M31'],
  ['血清陽性類風濕性關節炎','M05'],
  ['類風濕性關節炎','M06'], ['類風濕關節炎','M06'], ['類風濕','M06'], ['風濕性關節炎','M06'],
  ['乾癬性關節炎','M07'], ['銀屑病關節炎','M07'],
  ['反應性關節炎','M02'],
  ['痛風','M10'],
  ['假性痛風','M11'], ['焦磷酸鈣沉積症','M11'],
  ['纖維肌痛症','M79'], ['纖維肌痛','M79'],
  ['抗磷脂質症候群','D68'], ['抗磷脂症候群','D68'], ['APS','D68'],
  ['結節病','D86'], ['類肉瘤病','D86'], ['Sarcoidosis','D86'],
  ['雷諾氏現象','I73'], ['雷諾氏症','I73'], ['雷諾現象','I73'], ['Raynaud','I73'],
  ['結節性紅斑','L52'],
  ['骨質疏鬆症','M81'], ['骨質疏鬆','M81'], ['骨鬆','M81'],
  // 皮膚過敏
  ['乾癬','L40'], ['牛皮癬','L40'], ['psoriasis','L40'],
  ['異位性皮膚炎','L20'], ['atopic','L20'],
  ['蕁麻疹','L50'], ['風疹塊','L50'],
  // 腎
  ['慢性腎臟病','N18'], ['腎臟病','N18'], ['腎衰竭','N18'], ['腎病變','N18'], ['洗腎','N18'], ['腎病','N18'],
  // 神經 / 免疫神經
  ['巴金森氏症','G20'], ['巴金森','G20'], ['帕金森','G20'],
  ['多發性硬化症','G35'], ['多發硬化','G35'], ['MS','G35'],
  ['阿茲海默症','G30'], ['阿茲海默','G30'], ['失智症','G30'], ['失智','G30'],
  ['額顳葉失智','G31'], ['額顳葉型失智','G31'], ['路易氏體失智','G31'], ['路易氏失智','G31'], ['路易體失智','G31'],
  ['肌萎縮性脊髓側索硬化症','G12'], ['漸凍人症','G12'], ['漸凍人','G12'], ['漸凍症','G12'], ['ALS','G12'], ['運動神經元病變','G12'],
  ['癲癇','G40'], ['epilepsy','G40'],
  ['偏頭痛','G43'], ['migraine','G43'],
  ['短暫性腦缺血發作','G45'], ['短暫性腦缺血','G45'], ['小中風','G45'], ['TIA','G45'],
  ['中風後遺症','I69'], ['中風後','I69'], ['偏癱','I69'], ['半身不遂','I69'],
  ['三叉神經痛','G50'],
  ['格林-巴利症候群','G61'], ['格林巴利症候群','G61'], ['格林巴利','G61'], ['吉巴氏症候群','G61'], ['GBS','G61'],
  ['周邊神經病變','G62'], ['末梢神經病變','G62'], ['多發性神經病變','G62'],
  ['睡眠呼吸中止症','G47'], ['睡眠呼吸中止','G47'], ['阻塞性睡眠呼吸中止','G47'], ['睡眠障礙','G47'], ['失眠症','G47'], ['失眠','G47'],
  ['重症肌無力','G70'], ['肌無力','G70'],
  // 血液免疫
  ['免疫性血小板減少紫斑症','D69'], ['免疫性血小板減少','D69'], ['ITP','D69'],
  // 精神
  ['重度憂鬱症','F32'], ['重鬱症','F32'], ['憂鬱症','F32'], ['憂鬱','F32'],
  ['恐慌症','F41'], ['焦慮症','F41'], ['焦慮','F41'],
  // 腫瘤追蹤
  ['乳癌','C50'], ['乳房癌','C50'],
  ['肺癌','C34'],
  ['大腸癌','C18'], ['結腸癌','C18'],
];

function _escapeForRegex(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function detectIcd10FromText(text) {
  if (!text) return [];
  var src = String(text);
  var found = {};
  // 由長到短排序，先比中精確的長詞，再從來源文字裡移掉，避免短詞重複命中
  var sorted = DISEASE_KEYWORDS.slice().sort(function(a, b) { return b[0].length - a[0].length; });
  for (var i = 0; i < sorted.length; i++) {
    var pair = sorted[i];
    var kw = pair[0];
    var icd = pair[1];
    // 大小寫不敏感（讓 sle / COPD / als / tia / itp / aps 都能命中）
    var re = new RegExp(_escapeForRegex(kw), 'gi');
    if (re.test(src)) {
      found[icd] = true;
      src = src.replace(new RegExp(_escapeForRegex(kw), 'gi'), '');
    }
  }
  return Object.keys(found);
}

// 取代碼回去找最簡短易懂的中文名（給 UI 顯示用，「糖尿病」優於「第二型糖尿病」）
function bestNameForIcd10(code) {
  if (!code) return '';
  var prefix = String(code).slice(0, 3).toUpperCase();
  var candidates = [];
  DISEASE_KEYWORDS.forEach(function(p) {
    if (p[1] === prefix) candidates.push(p[0]);
  });
  if (!candidates.length) {
    // 退回完整 ICD10_MAP 名稱（透過 _eduDiseases 緩存）
    var hit = (typeof _eduDiseases !== 'undefined' ? _eduDiseases : []).find(function(d) { return d.icd10 === prefix; });
    return hit ? hit.name : prefix;
  }
  // 偏好較短、最像日常用語的名稱
  candidates.sort(function(a, b) { return a.length - b.length; });
  return candidates[0];
}

function renderRelatedDiseaseCard(item) {
  var articles = item.articles || [];
  var articleHtml = articles.length ? articles.map(function(a) {
    return '<button class="article-mini" onclick="eduOpenArticle(\'' + escapeHtml(a.slug) + '\')" ' +
           'style="text-align:left;padding:8px 10px;border-radius:8px;border:1px solid var(--border);' +
           'background:var(--bg-card);cursor:pointer;display:block;width:100%;margin-top:6px;font-size:.82rem;line-height:1.4">' +
           escapeHtml(a.title) +
           '</button>';
  }).join("") : '<div style="margin-top:6px;font-size:.78rem;color:var(--text-dim)">尚無精選文章，可從「疾病百科」直接打開生成衛教。</div>';

  var moreBtn = (item.article_count > articles.length || !articles.length)
    ? '<button onclick="eduJumpToDisease(\'' + escapeHtml(item.icd10) + '\',\'' + escapeHtml(item.name) + '\')" ' +
      'style="margin-top:8px;padding:6px 10px;border-radius:8px;border:1px solid var(--border);background:var(--bg-soft);' +
      'cursor:pointer;font-size:.78rem;color:var(--text-dim)">展開六大維度 →</button>'
    : '';

  return '<div style="padding:12px;border-radius:10px;border:1px solid var(--border);background:var(--bg-card);display:flex;flex-direction:column">' +
         '<div style="display:flex;align-items:center;gap:6px">' +
         '<strong style="font-size:.95rem">' + escapeHtml(item.name) + '</strong>' +
         '<span style="font-size:.7rem;color:var(--text-dim)">ICD-10：' + escapeHtml(item.icd10) + '</span>' +
         '</div>' +
         '<div style="margin-top:4px;font-size:.78rem;color:var(--text-dim)">' + escapeHtml(item.reason || '') + '</div>' +
         articleHtml +
         moreBtn +
         '</div>';
}

// 從相關疾病卡片直接跳到「疾病百科」書本，並選好該疾病
function eduJumpToDisease(icd10, name) {
  if (typeof eduOpenBook === 'function') eduOpenBook('diseases');
  setTimeout(function() {
    if (typeof eduPickDisease === 'function') eduPickDisease(icd10, name);
  }, 50);
}

// ── 精選文章（GitHub 審稿過的 Markdown 文章）──────────────
var _eduArticles = {};            // slug -> card / full article
var _eduArticleByIcd10Dim = {};   // "I10:disease_awareness" -> slug

function loadFeaturedArticles() {
  var el = document.getElementById("edu-featured-list");
  // 兩支獨立的請求：
  // 1. /education/articles — 全部文章，用來建立 slug 索引給書本章節對照
  // 2. /education/articles/featured — 後端依今日日期輪播好的精選清單
  fetch(API + "/education/articles")
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var arts = (data && data.articles) || [];
      _eduArticles = {};
      _eduArticleByIcd10Dim = {};
      arts.forEach(function(a) {
        _eduArticles[a.slug] = a;
        if (a.icd10 && a.dimension) {
          var key = String(a.icd10).substring(0, 3).toUpperCase() + ":" + a.dimension;
          _eduArticleByIcd10Dim[key] = a.slug;
        }
      });
    })
    .catch(function() { /* 索引建構失敗不阻擋顯示 */ });

  if (!el) return;
  fetch(API + "/education/articles/featured?limit=6")
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var featured = (data && data.articles) || [];
      // 把今日精選也合併進 _eduArticles 索引
      featured.forEach(function(a) {
        _eduArticles[a.slug] = _eduArticles[a.slug] || a;
      });
      if (!featured.length) {
        el.innerHTML = '<div style="color:var(--text-dim);font-size:.85rem">尚無精選文章。</div>';
        return;
      }
      var rotationDate = (data && data.rotation_date) ? data.rotation_date : "";
      var poolSize = (data && data.pool_size) || featured.length;
      el.innerHTML =
        (rotationDate
          ? '<div style="grid-column:1/-1;font-size:.72rem;color:var(--text-dim);margin-bottom:6px">' +
            escapeHtml(rotationDate) + ' 今日輪播（精選池共 ' + poolSize + ' 篇，明天會換另外幾篇）' +
            '</div>'
          : '') +
        featured.map(function(a) {
          var tagHtml = (a.tags || []).slice(0, 3).map(function(t) {
            return '<span style="display:inline-block;padding:2px 8px;border-radius:10px;background:var(--bg-soft);font-size:.72rem;color:var(--text-dim);margin-right:4px">' + escapeHtml(t) + '</span>';
          }).join("");
          var evidenceBadge = '';
          if (a.meets_evidence_standard) {
            evidenceBadge = '<span title="附 ≥2 條 Impact Factor>5 同儕審查文獻" ' +
              'style="display:inline-block;padding:2px 8px;border-radius:10px;background:#dbeafe;color:#1d4ed8;font-size:.7rem;font-weight:600;margin-right:4px">' +
              'IF&gt;5 實證</span>';
          } else if ((a.parsed_sources || []).some(function(s){ return s && s.impact_factor; })) {
            evidenceBadge = '<span title="附文獻來源" style="display:inline-block;padding:2px 8px;border-radius:10px;background:#f1f5f9;color:#475569;font-size:.7rem;margin-right:4px">附文獻</span>';
          }
          return '<button class="article-card" onclick="eduOpenArticle(\'' + escapeHtml(a.slug) + '\')" ' +
                 'style="text-align:left;padding:12px;border-radius:10px;border:1px solid var(--border);background:var(--bg-card);cursor:pointer;display:flex;flex-direction:column;gap:6px">' +
                 '<div style="font-weight:600;line-height:1.4">' + escapeHtml(a.title) + '</div>' +
                 (a.summary ? '<div style="font-size:.82rem;color:var(--text-dim);line-height:1.5">' + escapeHtml(a.summary) + '</div>' : '') +
                 (evidenceBadge || tagHtml ? '<div style="margin-top:4px">' + evidenceBadge + tagHtml + '</div>' : '') +
                 '</button>';
        }).join("");
      if (typeof lucide !== 'undefined') lucide.createIcons();
    })
    .catch(function() {
      if (el) el.innerHTML = '<div style="color:var(--text-dim);font-size:.85rem">載入精選文章失敗。</div>';
    });
}

// 從目前書本 + 章節 key 找有沒有審稿過的文章可以用
function findCuratedArticleSlug(book, topicKey) {
  if (!book) return null;
  // 1. 章節物件上有顯式 article 欄位 → 直接用
  var topic = (book.topics || []).find(function(t) { return t.key === topicKey; });
  if (topic && topic.article && _eduArticles[topic.article]) return topic.article;
  // 2. 疾病百科：用 ICD10 prefix + dimension 自動配對
  if (book.dynamic === "diseases" && _eduSelectedDisease) {
    var key = String(_eduSelectedDisease.icd10).substring(0, 3).toUpperCase() + ":" + topicKey;
    return _eduArticleByIcd10Dim[key] || null;
  }
  return null;
}

function eduOpenArticle(slug) {
  var nb = document.getElementById("edu-notebook");
  if (!nb) return;
  // 重設書本狀態，避免 breadcrumb 顯示舊書名
  _eduSelectedBook = null;
  _eduSelectedDisease = null;
  _eduSelectedDimension = null;
  _eduSelectedTopic = null;

  // 先用快取資料展開（標題、摘要、tag、來源），body 再從完整 API 抓
  var card = _eduArticles[slug];
  nb.classList.remove("single");
  nb.innerHTML = renderArticleSpread(card || { title: "載入中…", slug: slug }, null);
  eduSwitchStage("edu-stage-notebook");
  eduRenderArticleBreadcrumb(card ? card.title : "文章");

  fetch(API + "/education/articles/" + encodeURIComponent(slug))
    .then(function(r) {
      if (!r.ok) throw new Error("not found");
      return r.json();
    })
    .then(function(article) {
      _eduArticles[slug] = article;
      nb.innerHTML = renderArticleSpread(article, article.body || "");
      eduRenderArticleBreadcrumb(article.title);
      if (typeof lucide !== 'undefined') lucide.createIcons();
    })
    .catch(function() {
      nb.innerHTML = '<div class="nb-empty" style="padding:30px">找不到這篇文章。</div>';
    });

  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function renderArticleSpread(article, body) {
  // 優先用後端解析過的 parsed_sources（含 impact_factor / journal / doi）
  var parsed = article.parsed_sources || [];
  var rawSources = article.sources || [];
  var sourceItems = parsed.length ? parsed : rawSources.map(function(s) { return { text: s }; });

  var sources = sourceItems.map(function(s) {
    var text = s.text || "";
    var badges = [];
    if (s.journal) {
      badges.push('<span style="display:inline-block;padding:2px 8px;border-radius:8px;background:#0f172a;color:#fff;font-size:.72rem;font-weight:600">' + escapeHtml(s.journal) + '</span>');
    }
    if (s.impact_factor) {
      var ifColor = s.impact_factor >= 30 ? '#7c2d12' : (s.impact_factor >= 10 ? '#b45309' : '#1d4ed8');
      var ifBg = s.impact_factor >= 30 ? '#fed7aa' : (s.impact_factor >= 10 ? '#fef3c7' : '#dbeafe');
      badges.push('<span style="display:inline-block;padding:2px 8px;border-radius:8px;background:' + ifBg + ';color:' + ifColor + ';font-size:.72rem;font-weight:700">IF=' + s.impact_factor.toFixed(1) + '</span>');
    }
    if (s.year) {
      badges.push('<span style="display:inline-block;padding:2px 8px;border-radius:8px;background:#e2e8f0;color:#334155;font-size:.72rem">' + escapeHtml(s.year) + '</span>');
    }
    var badgesRow = badges.length
      ? '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px">' + badges.join("") + '</div>'
      : '';

    var linkLine = '';
    if (s.doi) {
      var doiUrl = 'https://doi.org/' + s.doi;
      linkLine = '<div style="margin-top:4px;font-size:.78rem">' +
                 '<span style="color:var(--text-dim)">DOI：</span>' +
                 '<a href="' + escapeHtml(doiUrl) + '" target="_blank" rel="noopener" style="color:#2563eb;word-break:break-all">' + escapeHtml(s.doi) + '</a>' +
                 '</div>';
    } else if (s.pmid) {
      linkLine = '<div style="margin-top:4px;font-size:.78rem">' +
                 '<span style="color:var(--text-dim)">PubMed：</span>' +
                 '<a href="https://pubmed.ncbi.nlm.nih.gov/' + encodeURIComponent(s.pmid) + '/" target="_blank" rel="noopener" style="color:#2563eb">' + escapeHtml(s.pmid) + '</a>' +
                 '</div>';
    } else if (s.url) {
      linkLine = '<div style="margin-top:4px;font-size:.78rem">' +
                 '<span style="color:var(--text-dim)">連結：</span>' +
                 '<a href="' + escapeHtml(s.url) + '" target="_blank" rel="noopener" style="color:#2563eb;word-break:break-all">' + escapeHtml(s.url) + '</a>' +
                 '</div>';
    }

    return '<li style="margin-bottom:14px;padding:10px 12px;border:1px solid var(--border);border-radius:8px;background:var(--bg-soft);line-height:1.55;font-size:.85rem;list-style:none">' +
           badgesRow +
           '<div style="color:var(--text)">' + escapeHtml(text) + '</div>' +
           linkLine +
           '</li>';
  }).join("");

  var tags = (article.tags || []).map(function(t) {
    return '<span style="display:inline-block;padding:3px 9px;border-radius:10px;background:var(--bg-soft);font-size:.75rem;color:var(--text-dim);margin:2px">' + escapeHtml(t) + '</span>';
  }).join("");
  var leftHtml =
    '<div class="nb-heading"><i data-lucide="bookmark" style="width:20px;height:20px"></i> 文章資訊</div>' +
    (article.summary ? '<div class="nb-subtle" style="line-height:1.6">' + escapeHtml(article.summary) + '</div>' : '') +
    (tags ? '<div style="margin-top:12px">' + tags + '</div>' : '') +
    (article.reviewed_at ? '<div style="margin-top:16px;font-size:.75rem;color:var(--text-dim)">最後審稿：' + escapeHtml(article.reviewed_at) + '</div>' : '');

  // 文章末尾：實證徽章 + 參考來源清單（放在 body 底下，不擠在左欄）
  var qualifyingCount = parsed.filter(function(s){ return s.impact_factor && s.impact_factor > 5; }).length;
  var evidenceLine = '';
  if (qualifyingCount >= 2) {
    evidenceLine = '<div style="margin-top:24px;padding:10px 12px;border-radius:8px;background:#ecfdf5;color:#065f46;font-size:.82rem;line-height:1.5">' +
      '本文附 ' + qualifyingCount + ' 條 Impact Factor &gt; 5 的同儕審查文獻</div>';
  } else if (rawSources.length) {
    evidenceLine = '<div style="margin-top:24px;padding:10px 12px;border-radius:8px;background:#fef3c7;color:#92400e;font-size:.82rem;line-height:1.5">' +
      '本文附權威指引，惟尚未補齊 IF&gt;5 期刊文獻</div>';
  }
  var sourcesBlock = sources
    ? '<div style="margin-top:24px;padding-top:18px;border-top:1px solid var(--border)">' +
        '<div style="font-size:1rem;font-weight:600;margin-bottom:12px">文獻出處</div>' +
        '<ol style="padding:0;margin:0;list-style:none">' + sources + '</ol>' +
      '</div>'
    : '<div style="margin-top:24px;padding:10px 12px;border-radius:8px;background:#fef2f2;color:#991b1b;font-size:.8rem">本文尚未補齊文獻來源</div>';

  var rightInner = (body == null)
    ? '<div class="nb-empty" style="padding:30px">內容載入中…</div>'
    : '<div class="edu-article-body" style="line-height:1.85">' + markdownToHtml(body) + sourcesBlock + evidenceLine + '</div>';

  return '<div class="nb-page left">' + leftHtml + '</div>' +
         '<div class="nb-page right" id="edu-notebook-right">' + rightInner + '</div>';
}

function eduRenderArticleBreadcrumb(title) {
  var el = document.getElementById("edu-breadcrumb");
  if (!el) return;
  el.innerHTML =
    '<button class="crumb" data-edu-crumb="shelf">' +
    '<i data-lucide="library" style="width:14px;height:14px;vertical-align:middle"></i> 書架</button>' +
    '<span class="sep">›</span>' +
    '<span class="crumb current">' +
    '<i data-lucide="sparkles" style="width:14px;height:14px;vertical-align:middle"></i> ' +
    escapeHtml(title) + '</span>';
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

// ── Stage 切換 ──────────────────────────────────────────────
function eduSwitchStage(stageId) {
  var ids = ["edu-stage-shelf", "edu-stage-notebook"];
  ids.forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.classList.toggle("active", id === stageId);
  });
  if (typeof lucide !== 'undefined') setTimeout(function() { lucide.createIcons(); }, 30);
}

function eduGoToShelf() {
  _eduSelectedBook = null;
  _eduSelectedDisease = null;
  _eduSelectedDimension = null;
  _eduSelectedTopic = null;
  eduRenderBreadcrumb();
  eduSwitchStage("edu-stage-shelf");
}

function eduRenderBreadcrumb() {
  var el = document.getElementById("edu-breadcrumb");
  if (!el) return;
  var html = '<button class="crumb' + (!_eduSelectedBook ? ' current' : '') + '" data-edu-crumb="shelf">' +
             '<i data-lucide="library" style="width:14px;height:14px;vertical-align:middle"></i> 書架</button>';
  if (_eduSelectedBook) {
    html += '<span class="sep">›</span>';
    html += '<span class="crumb current">' +
            '<i data-lucide="' + escapeHtml(_eduSelectedBook.icon) + '" style="width:14px;height:14px;vertical-align:middle"></i> ' +
            escapeHtml(_eduSelectedBook.title) + '</span>';
  }
  el.innerHTML = html;
  // breadcrumb 用事件委派，避免 inline onclick
  if (!el.dataset.boundDelegate) {
    el.addEventListener("click", function(e) {
      var btn = e.target.closest && e.target.closest('[data-edu-crumb]');
      if (!btn) return;
      if (btn.getAttribute("data-edu-crumb") === "shelf") eduGoToShelf();
    });
    el.dataset.boundDelegate = "1";
  }
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

// ── Stage 2: 翻開書本 ──────────────────────────────────────
function eduOpenBook(key) {
  var book = EDU_BOOKS.find(function(b) { return b.key === key; });
  if (!book) return;
  _eduOpenBookObject(book);
}

// 共用：把任何書本物件（含臨時建出來的「其他自填疾病」）攤開到 notebook
function _eduOpenBookObject(book) {
  _eduSelectedBook = book;
  _eduSelectedDisease = null;
  _eduSelectedDimension = null;
  _eduSelectedTopic = null;

  var nb = document.getElementById("edu-notebook");
  nb.classList.remove("single");
  nb.innerHTML = renderNotebookSpread();

  // 用事件委派處理章節點擊（避免 inline onclick + escape 問題）
  if (!nb.dataset.boundDelegate) {
    nb.addEventListener("click", function(e) {
      var btn = e.target.closest && e.target.closest("[data-action]");
      if (!btn || !nb.contains(btn)) return;
      var action = btn.getAttribute("data-action");
      if (action === "pick-disease") {
        eduPickDisease(btn.getAttribute("data-icd10"), btn.getAttribute("data-name"));
      } else if (action === "open-content") {
        eduOpenContent(btn.getAttribute("data-key"), btn.getAttribute("data-label"));
      } else if (action === "back-to-list") {
        _eduSelectedTopic = null;
        _eduSelectedDimension = null;
        document.getElementById("edu-notebook-right").innerHTML = renderRightPagePlaceholder();
        if (typeof lucide !== 'undefined') lucide.createIcons();
      }
    });
    nb.dataset.boundDelegate = "1";
  }

  eduSwitchStage("edu-stage-notebook");
  eduRenderBreadcrumb();
  // 重置筆記本翻開動畫
  nb.style.animation = "none"; nb.offsetHeight; nb.style.animation = "";
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

// 統一的兩頁式筆記本：左頁 = 清單；右頁 = 內容區（id 固定，方便就地替換）
function renderNotebookSpread() {
  var book = _eduSelectedBook;
  if (!book) return "";
  var leftHtml = (book.dynamic === "diseases") ? renderDiseaseLeftPage() : renderTopicsLeftPage(book);
  return '' +
    '<div class="nb-page left">' + leftHtml + '</div>' +
    '<div class="nb-page right" id="edu-notebook-right">' + renderRightPagePlaceholder() + '</div>';
}

function renderTopicsLeftPage(book) {
  var listHtml = book.topics.map(function(t) {
    var sel = (_eduSelectedTopic === t.key) ? ' selected' : '';
    return '<button class="nb-item' + sel + '" data-action="open-content"' +
           ' data-key="' + escapeHtml(t.key) + '"' +
           ' data-label="' + escapeHtml(t.label) + '">' +
           '<strong>' + escapeHtml(t.label) + '</strong>' +
           (t.desc ? '<small>' + escapeHtml(t.desc) + '</small>' : '') +
           '</button>';
  }).join("");
  return '<div class="nb-heading"><i data-lucide="' + escapeHtml(book.icon) + '" style="width:20px;height:20px"></i> ' + escapeHtml(book.title) + '</div>' +
         (book.intro ? '<div class="nb-subtle">' + escapeHtml(book.intro) + '</div>' : '') +
         '<div class="nb-list">' + listHtml + '</div>';
}

function renderRightPagePlaceholder() {
  var book = _eduSelectedBook;
  if (!book) return '';
  if (book.dynamic === "diseases") {
    if (!_eduSelectedDisease) {
      return '<div class="nb-heading"><i data-lucide="layers" style="width:20px;height:20px"></i> 六大衛教維度</div>' +
             '<div class="nb-empty">← 先從左頁挑一個疾病，這裡才會展開六大維度，再點任一維度直接讀內容。</div>';
    }
    // 已選疾病但尚未選維度：顯示維度清單
    var listHtml = EDU_DISEASE_DIMENSIONS.map(function(d) {
      return '<button class="nb-item" data-action="open-content"' +
             ' data-key="' + escapeHtml(d.key) + '"' +
             ' data-label="' + escapeHtml(d.label) + '">' +
             '<strong>' + escapeHtml(d.label) + '</strong><small>' + escapeHtml(d.desc) + '</small></button>';
    }).join("");
    return '<div class="nb-heading"><i data-lucide="layers" style="width:20px;height:20px"></i> 六大衛教維度</div>' +
           '<div class="nb-subtle">' + escapeHtml(_eduSelectedDisease.name) + '（' + escapeHtml(_eduSelectedDisease.icd10) + '）</div>' +
           '<div class="nb-list">' + listHtml + '</div>';
  }
  // 一般書本的初始右頁：書本說明 + 提示
  return '<div class="nb-heading"><i data-lucide="bookmark" style="width:20px;height:20px"></i> 章節導讀</div>' +
         '<div class="nb-subtle">' + escapeHtml(book.intro || "") + '</div>' +
         '<p style="margin-top:14px;color:var(--text-dim);font-size:.9rem;line-height:1.8">' +
         '左邊那一頁列出了這本書的所有章節。點任一章節，內容就會直接寫在這一頁；想換章節就再點別的，或按下方「← 章節清單」回到提示。</p>';
}

function renderDiseaseLeftPage() {
  var byCategory = {};
  _eduDiseases.forEach(function(d) {
    if (!byCategory[d.category]) byCategory[d.category] = [];
    byCategory[d.category].push(d);
  });

  var listHtml = '';
  if (!_eduDiseases.length) {
    listHtml = '<div class="nb-empty">疾病列表載入中… 若持續看到此訊息，請確認後端服務是否已啟動。</div>';
  } else {
    Object.keys(byCategory).forEach(function(cat) {
      listHtml += '<div style="margin-top:8px;font-size:.78rem;color:var(--text-dim);letter-spacing:1px">' + escapeHtml(cat) + '</div>';
      byCategory[cat].forEach(function(d) {
        var sel = (_eduSelectedDisease && _eduSelectedDisease.icd10 === d.icd10) ? ' selected' : '';
        listHtml += '<button class="nb-item' + sel + '" data-action="pick-disease"' +
                    ' data-icd10="' + escapeHtml(d.icd10) + '"' +
                    ' data-name="' + escapeHtml(d.name) + '">' +
                    '<strong>' + escapeHtml(d.name) + '</strong><small>ICD-10：' + escapeHtml(d.icd10) + '</small>' +
                    '</button>';
      });
    });
  }

  return '<div class="nb-heading"><i data-lucide="list" style="width:20px;height:20px"></i> 疾病列表</div>' +
         '<div class="nb-subtle">挑一個疾病，右頁就會展開六大衛教維度</div>' +
         '<div class="nb-list">' + listHtml + '</div>';
}

function eduPickDisease(icd10, name) {
  _eduSelectedDisease = { icd10: icd10, name: name };
  _eduSelectedDimension = null;
  // 重新渲染整個跨頁（左頁要更新 selected 狀態，右頁要顯示維度清單）
  document.getElementById("edu-notebook").innerHTML = renderNotebookSpread();
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

// 在右頁就地寫入內容（不再切換 stage）
function eduOpenContent(key, label) {
  if (!_eduSelectedBook) return;
  var book = _eduSelectedBook;

  var titleText, fetchBody;
  if (book.dynamic === "diseases") {
    if (!_eduSelectedDisease) { showToast("請先選擇疾病", "warning"); return; }
    _eduSelectedDimension = key;
    titleText = _eduSelectedDisease.name + " — " + label;
    fetchBody = { icd10_code: _eduSelectedDisease.icd10, dimension: key };
  } else {
    _eduSelectedTopic = key;
    titleText = book.title + " — " + label;
    fetchBody = { dimension: key, topic: book.title + "：" + label };
    // 重新渲染左頁讓 selected 狀態反映目前章節
    var nb = document.getElementById("edu-notebook");
    if (nb) nb.innerHTML = renderNotebookSpread();
  }


  var rightEl = document.getElementById("edu-notebook-right");
  if (!rightEl) return;
  rightEl.innerHTML =
    '<div class="nb-content-head">' +
      '<div class="nb-content-title">' + escapeHtml(titleText) + '</div>' +
      '<button class="secondary" data-action="back-to-list" style="padding:4px 10px;font-size:.8rem">← 章節清單</button>' +
    '</div>' +
    '<div id="edu-content-body" style="font-size:.94rem;line-height:1.85">' +
      '<div style="text-align:center;padding:40px;color:var(--text-muted)">' +
        '<div class="loading-spinner"></div>' +
        '<p style="margin-top:12px">正在為您準備溫暖的衛教內容…</p>' +
      '</div>' +
    '</div>';

  if (typeof lucide !== 'undefined') lucide.createIcons();

  // 1) 先看有沒有人工審稿過的文章可以對應到這個章節 → 直接出文章
  var curatedSlug = findCuratedArticleSlug(book, key);
  if (curatedSlug) {
    fetch(API + "/education/articles/" + encodeURIComponent(curatedSlug))
      .then(function(r) { if (!r.ok) throw new Error("not found"); return r.json(); })
      .then(function(article) {
        _eduArticles[article.slug] = article;
        eduRenderCuratedArticleInRight(article, titleText);
      })
      .catch(function() {
        // 文章 fetch 失敗就降級到 LLM 生成
        eduGenerateContent(fetchBody, book, label);
      });
    return;
  }

  // 2) 沒有對應文章 → 走原本的 Claude 即時生成
  eduGenerateContent(fetchBody, book, label);
}

function eduGenerateContent(fetchBody, book, label) {
  fetch(API + "/education/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fetchBody)
  })
    .then(function(r) {
      if (!r.ok) throw new Error("API error");
      return r.json();
    })
    .then(function(data) {
      var content = data.content || data.report || "";
      if (!content) throw new Error("空內容");
      var body = document.getElementById("edu-content-body");
      if (body) body.innerHTML = markdownToHtml(content);
    })
    .catch(function() {
      var body = document.getElementById("edu-content-body");
      if (body) body.innerHTML = eduFallbackContent(book, label);
    });
}

function eduRenderCuratedArticleInRight(article, titleText) {
  var rightEl = document.getElementById("edu-notebook-right");
  if (!rightEl) return;
  var sourcesHtml = (article.sources || []).map(function(s) {
    return '<li style="margin-bottom:6px;line-height:1.5;font-size:.85rem">' + escapeHtml(s) + '</li>';
  }).join("");
  var sourcesBlock = sourcesHtml
    ? '<details style="margin-top:22px;padding:10px 12px;border:1px solid var(--border);border-radius:8px;background:var(--bg-soft)">' +
        '<summary style="cursor:pointer;font-size:.85rem;font-weight:600">參考來源（' + (article.sources || []).length + '）</summary>' +
        '<ol style="margin-top:10px;padding-left:20px;color:var(--text-dim)">' + sourcesHtml + '</ol>' +
      '</details>'
    : '';
  var reviewedBlock = article.reviewed_at
    ? '<div style="margin-top:14px;font-size:.75rem;color:var(--text-dim)">最後人工審稿：' + escapeHtml(article.reviewed_at) + '</div>'
    : '';
  var summaryBlock = article.summary
    ? '<div style="margin:12px 0;padding:10px 12px;border-left:3px solid var(--accent);background:var(--bg-soft);font-size:.9rem;line-height:1.6">' + escapeHtml(article.summary) + '</div>'
    : '';

  rightEl.innerHTML =
    '<div class="nb-content-head">' +
      '<div class="nb-content-title">' + escapeHtml(titleText) +
        ' <span style="margin-left:6px;display:inline-block;padding:2px 8px;border-radius:10px;background:#e8f5e9;color:#2e7d32;font-size:.7rem;font-weight:600;vertical-align:middle">✓ 已審稿</span>' +
      '</div>' +
      '<button class="secondary" data-action="back-to-list" style="padding:4px 10px;font-size:.8rem">← 章節清單</button>' +
    '</div>' +
    summaryBlock +
    '<div class="edu-article-body" style="font-size:.94rem;line-height:1.85">' + markdownToHtml(article.body || "") + '</div>' +
    sourcesBlock +
    reviewedBlock;

  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function eduFallbackContent(book, label) {
  return '' +
    '<h3>' + escapeHtml(book.title) + '：' + escapeHtml(label) + '</h3>' +
    '<p>這一頁正在編寫中——之後會由 MD.Piece 根據最新文獻自動填上溫暖、易懂的內容。</p>' +
    '<p>在那之前，你可以：</p>' +
    '<ul>' +
      '<li>回到書架挑另一本書，先看看其他主題。</li>' +
      '<li>把你想知道的細節寫進「醫療 Chat」，由 MD.Piece 直接回答。</li>' +
    '</ul>' +
    '<p style="color:var(--text-dim);margin-top:14px">' + escapeHtml(book.intro || '') + '</p>';
}

// ─── 你的碎片（Pieces）— 上次回診以來的紀錄統整 ─────────────
// 這頁把症狀／Memo／生理／藥物等碎片拼起來，保留為「上次紀錄」
// 下次回診時可作為帶去診間的摘要。

const PIECES_SNAPSHOT_KEY = 'mdpiece_pieces_snapshot';

function piecesLoadSnapshot() {
  try {
    var raw = localStorage.getItem(PIECES_SNAPSHOT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) { return null; }
}

function piecesSaveSnapshot(snap) {
  try { localStorage.setItem(PIECES_SNAPSHOT_KEY, JSON.stringify(snap)); }
  catch (e) {}
}

function piecesComputeStats() {
  var v = (typeof getVisitDates === 'function') ? getVisitDates() : {};
  var since = null;
  if (v.lastVisit) {
    var d = new Date(v.lastVisit);
    if (!isNaN(d.getTime())) since = d;
  }
  if (!since) {
    since = new Date(); since.setDate(since.getDate() - 30);
  }

  // 症狀
  var allSymp = (typeof getSymptomEntries === 'function') ? getSymptomEntries() : [];
  var symp = allSymp.filter(function(e) { return new Date(e.recordedAt) >= since; });
  var byCat = {};
  var intensitySum = 0, freqSum = 0;
  symp.forEach(function(e) {
    var f = e.frequency || 1;
    byCat[e.categoryId] = (byCat[e.categoryId] || 0) + f;
    intensitySum += (e.intensity || 0) * f;
    freqSum += f;
  });
  var topCats = Object.keys(byCat).map(function(id) {
    var cat = (typeof findSymptomCat === 'function') ? findSymptomCat(id) : null;
    return { id: id, count: byCat[id], zh: cat ? cat.zh : id, icon: cat ? cat.icon : 'circle', color: cat ? cat.color : 'mint' };
  }).sort(function(a, b) { return b.count - a.count; }).slice(0, 4);
  var avgIntensity = freqSum ? (intensitySum / freqSum) : 0;

  // Memo
  var memos = (typeof memoLoad === 'function') ? memoLoad() : [];
  var memosInRange = memos.filter(function(m) { return new Date(m.createdAt || m.time || 0) >= since; });
  var memoForDoctor = memosInRange.filter(function(m) { return m.toDoctor || m.forDoctor; }).length;

  // 生理
  var vitals = (typeof getVitalEntries === 'function') ? getVitalEntries() : [];
  var vitalsInRange = vitals.filter(function(e) { return new Date(e.recordedAt || e.time || 0) >= since; });
  var lastVital = vitals.length ? vitals[vitals.length - 1] : null;

  // 時間
  var today = new Date();
  var days = Math.max(1, Math.ceil((today - since) / 86400000));

  // 時間軸（最近 8 筆，跨類別）
  var timeline = [];
  symp.forEach(function(e) { timeline.push({ kind:'symptom', t: e.recordedAt, label: getCategoryName(e.categoryId), meta: '強度 ' + (e.intensity || '?') }); });
  memosInRange.forEach(function(m) { timeline.push({ kind:'memo', t: m.createdAt || m.time, label: m.text ? (String(m.text).slice(0, 28)) : '照片留言', meta: m.toDoctor || m.forDoctor ? '給醫師' : '給自己' }); });
  vitalsInRange.forEach(function(e) { timeline.push({ kind:'vital', t: e.recordedAt || e.time, label: e.metricLabel || e.metricId || '生理數值', meta: (e.value !== undefined ? e.value : '') + (e.unit ? ' ' + e.unit : '') }); });
  timeline.sort(function(a, b) { return new Date(b.t) - new Date(a.t); });
  timeline = timeline.slice(0, 10);

  return {
    since: since,
    days: days,
    symptomCount: freqSum,
    symptomEntries: symp.length,
    avgIntensity: avgIntensity,
    topCats: topCats,
    memoCount: memosInRange.length,
    memoForDoctor: memoForDoctor,
    vitalCount: vitalsInRange.length,
    lastVital: lastVital,
    timeline: timeline,
    visitDates: v
  };
}

function getCategoryName(id) {
  if (typeof findSymptomCat !== 'function') return id;
  var c = findSymptomCat(id);
  return c ? c.zh : id;
}

function piecesFormatDate(d) {
  if (!d) return '—';
  var x = new Date(d);
  if (isNaN(x.getTime())) return '—';
  return x.getFullYear() + '/' + String(x.getMonth() + 1).padStart(2, '0') + '/' + String(x.getDate()).padStart(2, '0');
}
function piecesFormatTime(d) {
  if (!d) return '—';
  var x = new Date(d);
  if (isNaN(x.getTime())) return '—';
  return piecesFormatDate(d) + ' ' + String(x.getHours()).padStart(2, '0') + ':' + String(x.getMinutes()).padStart(2, '0');
}

function pieces() {
  var s = piecesComputeStats();
  var prev = piecesLoadSnapshot();

  var topCatsHtml = s.topCats.length
    ? s.topCats.map(function(c) {
        return '<li class="pz-cat"><span class="pz-cat-icon scc-' + c.color + '"><i data-lucide="' + c.icon + '"></i></span>'
          + '<span class="pz-cat-name">' + c.zh + '</span>'
          + '<span class="pz-cat-count">' + c.count + '</span></li>';
      }).join('')
    : '<li class="pz-empty">尚無症狀紀錄</li>';

  var timelineHtml = s.timeline.length
    ? s.timeline.map(function(t) {
        var ico = t.kind === 'symptom' ? 'scan-search' : (t.kind === 'memo' ? 'sticky-note' : 'activity');
        var kindLabel = t.kind === 'symptom' ? '症狀' : (t.kind === 'memo' ? 'Memo' : '生理');
        return '<li class="pz-tl-item pz-tl-' + t.kind + '">'
          + '<span class="pz-tl-dot"><i data-lucide="' + ico + '"></i></span>'
          + '<div class="pz-tl-body">'
          +   '<div class="pz-tl-head"><strong>' + (t.label || '—') + '</strong><span class="pz-tl-kind">' + kindLabel + '</span></div>'
          +   '<div class="pz-tl-meta">' + (t.meta || '') + ' · ' + piecesFormatTime(t.t) + '</div>'
          + '</div></li>';
      }).join('')
    : '<li class="pz-empty">這段期間還沒有紀錄。從症狀紀錄、Memo 或生理紀錄開始拼起你的碎片吧。</li>';

  var prevHtml = prev
    ? '<div class="pz-prev">'
      + '<div class="pz-prev-head"><i data-lucide="bookmark"></i><strong>上次拼圖快照</strong>'
      +   '<span class="pz-prev-date">' + piecesFormatTime(prev.savedAt) + '</span></div>'
      + '<div class="pz-prev-stats">'
      +   '<span>症狀 <b>' + (prev.symptomCount || 0) + '</b></span>'
      +   '<span>Memo <b>' + (prev.memoCount || 0) + '</b></span>'
      +   '<span>生理 <b>' + (prev.vitalCount || 0) + '</b></span>'
      +   '<span>區間 <b>' + (prev.days || 0) + '</b> 天</span>'
      + '</div>'
      + '</div>'
    : '<div class="pz-prev pz-prev-empty"><i data-lucide="bookmark-plus"></i>尚未保存過快照。下次回診前按「保存為這次的拼圖」可以建立第一份。</div>';

  return '\n'
    + '<section class="pieces-page">\n'
    + '  <header class="pz-header">\n'
    + '    <div>\n'
    + '      <p class="pz-eyebrow">// pieces &gt; aggregated_records</p>\n'
    + '      <h2 class="pz-title"><i data-lucide="puzzle"></i> 你的碎片</h2>\n'
    + '      <p class="pz-sub">把上次回診以來的紀錄拼起來，看見完整的你。可保存為「這次的拼圖」帶去下次門診。</p>\n'
    + '    </div>\n'
    + '    <div class="pz-period">\n'
    + '      <span class="pz-period-label">統整期間</span>\n'
    + '      <span class="pz-period-range">' + piecesFormatDate(s.since) + ' — 今天</span>\n'
    + '      <span class="pz-period-days">' + s.days + ' 天</span>\n'
    + '    </div>\n'
    + '  </header>\n'
    + '\n'
    + '  <div class="pz-grid">\n'
    + '    <div class="pz-card pz-card-blue">\n'
    + '      <div class="pz-card-head"><i data-lucide="scan-search"></i><span>症狀紀錄</span></div>\n'
    + '      <div class="pz-card-num">' + s.symptomCount + '</div>\n'
    + '      <div class="pz-card-sub">共 ' + s.symptomEntries + ' 筆 · 平均強度 ' + s.avgIntensity.toFixed(1) + '</div>\n'
    + '      <button class="pz-card-link" onclick="navigateTo(\'symptoms\',null)">前往症狀 →</button>\n'
    + '    </div>\n'
    + '    <div class="pz-card pz-card-rose">\n'
    + '      <div class="pz-card-head"><i data-lucide="sticky-note"></i><span>Memo</span></div>\n'
    + '      <div class="pz-card-num">' + s.memoCount + '</div>\n'
    + '      <div class="pz-card-sub">' + s.memoForDoctor + ' 則標記給醫師</div>\n'
    + '      <button class="pz-card-link" onclick="navigateTo(\'memo\',null)">前往 Memo →</button>\n'
    + '    </div>\n'
    + '    <div class="pz-card pz-card-mint">\n'
    + '      <div class="pz-card-head"><i data-lucide="activity"></i><span>生理紀錄</span></div>\n'
    + '      <div class="pz-card-num">' + s.vitalCount + '</div>\n'
    + '      <div class="pz-card-sub">' + (s.lastVital ? ('最近：' + (s.lastVital.metricLabel || s.lastVital.metricId || '—')) : '尚無紀錄') + '</div>\n'
    + '      <button class="pz-card-link" onclick="navigateTo(\'vitals\',null)">前往生理 →</button>\n'
    + '    </div>\n'
    + '    <div class="pz-card pz-card-amber" id="pz-card-meds">\n'
    + '      <div class="pz-card-head"><i data-lucide="pill"></i><span>藥物追蹤</span></div>\n'
    + '      <div class="pz-card-num" id="pz-meds-num">…</div>\n'
    + '      <div class="pz-card-sub" id="pz-meds-sub">載入中</div>\n'
    + '      <button class="pz-card-link" onclick="navigateTo(\'medications\',null)">前往藥物 →</button>\n'
    + '    </div>\n'
    + '  </div>\n'
    + '\n'
    + '  <div class="pz-row">\n'
    + '    <section class="pz-block">\n'
    + '      <h3 class="pz-block-title"><i data-lucide="bar-chart-3"></i> 症狀分佈 Top 4</h3>\n'
    + '      <ul class="pz-cat-list">' + topCatsHtml + '</ul>\n'
    + '    </section>\n'
    + '    <section class="pz-block">\n'
    + '      <h3 class="pz-block-title"><i data-lucide="calendar-clock"></i> 回診日期</h3>\n'
    + '      <ul class="pz-visit">\n'
    + '        <li><span>上次回診</span><strong>' + piecesFormatDate(s.visitDates.lastVisit) + '</strong></li>\n'
    + '        <li><span>下次回診</span><strong>' + piecesFormatDate(s.visitDates.nextVisit) + '</strong></li>\n'
    + '      </ul>\n'
    + '      <button class="pz-link-btn" onclick="openVisitDatePrompt()"><i data-lucide="calendar-cog"></i> 設定回診日期</button>\n'
    + '    </section>\n'
    + '  </div>\n'
    + '\n'
    + '  <section class="pz-block">\n'
    + '    <h3 class="pz-block-title"><i data-lucide="history"></i> 最近的碎片</h3>\n'
    + '    <ul class="pz-timeline">' + timelineHtml + '</ul>\n'
    + '  </section>\n'
    + '\n'
    + '  ' + prevHtml + '\n'
    + '\n'
    + '  <div class="pz-actions">\n'
    + '    <button class="pz-save-btn" onclick="piecesSaveCurrent()"><i data-lucide="save"></i> 保存為這次的拼圖</button>\n'
    + '    <button class="pz-export-btn" onclick="piecesExport()"><i data-lucide="clipboard-copy"></i> 複製摘要文字</button>\n'
    + '  </div>\n'
    + '</section>\n';
}

function loadPiecesPage() {
  if (typeof lucide !== 'undefined') lucide.createIcons();
  // 抓藥物統計
  try {
    var pid = (typeof getStablePatientId === 'function') ? getStablePatientId() : null;
    if (!pid) return;
    fetch(API + '/medications/?patient_id=' + pid)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var meds = (data.medications || []).filter(function(m) { return m.active !== 0; });
        var num = document.getElementById('pz-meds-num');
        var sub = document.getElementById('pz-meds-sub');
        if (num) num.textContent = meds.length;
        if (sub) sub.textContent = meds.length ? '種藥物正在追蹤' : '尚未建立藥物紀錄';
      })
      .catch(function() {
        var num = document.getElementById('pz-meds-num');
        var sub = document.getElementById('pz-meds-sub');
        if (num) num.textContent = '0';
        if (sub) sub.textContent = '無法連線後端';
      });
  } catch (e) {}
}

function piecesSaveCurrent() {
  var s = piecesComputeStats();
  var snap = {
    savedAt: new Date().toISOString(),
    since: s.since instanceof Date ? s.since.toISOString() : s.since,
    days: s.days,
    symptomCount: s.symptomCount,
    symptomEntries: s.symptomEntries,
    avgIntensity: s.avgIntensity,
    memoCount: s.memoCount,
    memoForDoctor: s.memoForDoctor,
    vitalCount: s.vitalCount,
    topCats: s.topCats
  };
  piecesSaveSnapshot(snap);
  if (typeof showToast === 'function') showToast('已保存這次的拼圖', 'success');
  showPage('pieces');
}

function piecesExport() {
  var s = piecesComputeStats();
  var lines = [];
  lines.push('【你的碎片 · 統整摘要】');
  lines.push('期間：' + piecesFormatDate(s.since) + ' — 今天（' + s.days + ' 天）');
  lines.push('');
  lines.push('症狀紀錄：' + s.symptomCount + ' 次（共 ' + s.symptomEntries + ' 筆，平均強度 ' + s.avgIntensity.toFixed(1) + '）');
  if (s.topCats.length) {
    lines.push('  最常出現：');
    s.topCats.forEach(function(c) { lines.push('    · ' + c.zh + '（' + c.count + ' 次）'); });
  }
  lines.push('Memo：' + s.memoCount + ' 則（' + s.memoForDoctor + ' 則給醫師）');
  lines.push('生理紀錄：' + s.vitalCount + ' 筆');
  lines.push('上次回診：' + piecesFormatDate(s.visitDates.lastVisit));
  lines.push('下次回診：' + piecesFormatDate(s.visitDates.nextVisit));
  var text = lines.join('\n');
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function() {
      if (typeof showToast === 'function') showToast('已複製到剪貼簿', 'success');
    }).catch(function() {
      _piecesShowCopyFallback(text);
    });
  } else {
    _piecesShowCopyFallback(text);
  }
}
// 瀏覽器不支援 Clipboard API 或被拒時，跳出可選取的 textarea 讓使用者手動複製
function _piecesShowCopyFallback(text) {
  var existing = document.getElementById('pieces-copy-fallback');
  if (existing) existing.remove();
  var wrap = document.createElement('div');
  wrap.id = 'pieces-copy-fallback';
  wrap.className = 'pieces-copy-fallback';
  wrap.innerHTML = ''
    + '<div class="pcf-backdrop" onclick="document.getElementById(\'pieces-copy-fallback\').remove()"></div>'
    + '<div class="pcf-panel" role="dialog" aria-modal="true" aria-label="手動複製文字">'
    +   '<h3 class="pcf-title">無法自動複製，請手動選取下方文字</h3>'
    +   '<textarea class="pcf-text" readonly></textarea>'
    +   '<button type="button" class="pcf-close" onclick="document.getElementById(\'pieces-copy-fallback\').remove()">關閉</button>'
    + '</div>';
  document.body.appendChild(wrap);
  var ta = wrap.querySelector('.pcf-text');
  if (ta) { ta.value = text; setTimeout(function(){ ta.focus(); ta.select(); }, 50); }
}

// ─── 系統設定（Settings）───────────────────────────────────
// 控制：字體大小、主題（深/淺/跟隨系統）、顯示模式、動效、提示音、
//       重設 ID 卡、清除快取/重新整理、關於

const SETTINGS_KEYS = {
  fontSize: 'mdpiece_font_size',      // small | normal | large | xlarge
  theme:    'mdpiece_theme_pref',     // dark | light | auto
  motion:   'mdpiece_motion',         // on | reduced
  sound:    'mdpiece_sound',          // on | off
  density:  'mdpiece_density'         // cozy | compact
};

const FONT_SIZE_PX = { small: 14, normal: 16, large: 18, xlarge: 20 };

function getSetting(key, fallback) {
  try { return localStorage.getItem(SETTINGS_KEYS[key]) || fallback; }
  catch (e) { return fallback; }
}

function setSetting(key, value) {
  try { localStorage.setItem(SETTINGS_KEYS[key], value); } catch (e) {}
}

function applyFontSize(size) {
  const px = FONT_SIZE_PX[size] || FONT_SIZE_PX.normal;
  document.documentElement.style.fontSize = px + 'px';
  document.documentElement.setAttribute('data-font-size', size);
}

function applyTheme(pref) {
  const sysDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const resolved = pref === 'auto' ? (sysDark ? 'dark' : 'light') : pref;
  const app = document.getElementById('app-wrapper');
  const lp  = document.getElementById('landing');
  if (app) app.dataset.theme = resolved;
  if (lp) lp.dataset.theme = resolved;
  const aIco = document.getElementById('att-icon');
  if (aIco) aIco.textContent = resolved === 'dark' ? '☾' : '☀';
  const ico = document.getElementById('tt-icon');
  const lab = document.getElementById('tt-label');
  if (ico) ico.textContent = resolved === 'dark' ? '☾' : '☀';
  if (lab) lab.textContent = resolved.toUpperCase();
  // 與既有 toggle 共用 storage key（保持向下相容）
  try { localStorage.setItem('mdpiece_landing_theme', resolved); } catch (e) {}
  window.dispatchEvent(new CustomEvent('landing-theme-change', { detail: resolved }));
}

function applyMotion(motion) {
  document.documentElement.setAttribute('data-motion', motion);
}

function applyDensity(density) {
  document.documentElement.setAttribute('data-density', density);
}

function initUserSettings() {
  applyFontSize(getSetting('fontSize', 'normal'));
  applyMotion(getSetting('motion', 'on'));
  applyDensity(getSetting('density', 'cozy'));
  // 主題：若使用者尚未選擇，沿用既有 mdpiece_landing_theme，否則 auto
  let themePref = null;
  try { themePref = localStorage.getItem(SETTINGS_KEYS.theme); } catch (e) {}
  if (themePref) applyTheme(themePref);
  // 監聽系統主題變化（auto 模式才生效）
  if (window.matchMedia) {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => {
      const pref = (function(){ try { return localStorage.getItem(SETTINGS_KEYS.theme); } catch(e){ return null; } })();
      if (pref === 'auto') applyTheme('auto');
    };
    if (mq.addEventListener) mq.addEventListener('change', onChange);
    else if (mq.addListener) mq.addListener(onChange);
  }
}
initUserSettings();

// ─── 醫起聊天（Chat with 小禾）────────────────────────────────
// Claude Code 風格：終端機框 + 吉祥物 + 打字機輸出
// 後端 endpoint: POST /xiaohe/chat  { user_id, message, mode, version }

const CHAT_HISTORY_KEY = 'mdpiece_chat_history';
const CHAT_MODE_KEY    = 'mdpiece_chat_mode';      // patient / family
const CHAT_VERSION_KEY = 'mdpiece_chat_version';   // normal / elderly
var _chatTyping = false;
var _chatTypeTimer = null;

function chatLoadHistory() {
  try {
    var raw = localStorage.getItem(CHAT_HISTORY_KEY);
    var arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr : [];
  } catch (e) { return []; }
}

// 把 localStorage 內的訊息轉成後端 history 格式（最近 N 輪 user/bot）
function chatBuildApiHistory(maxTurns) {
  var n = maxTurns || 12;
  var hist = chatLoadHistory();
  var out = [];
  for (var i = 0; i < hist.length; i++) {
    var m = hist[i];
    if (!m || !m.text) continue;
    var role = (m.role === 'user') ? 'user' : 'assistant';
    out.push({ role: role, content: String(m.text) });
  }
  return out.slice(-n);
}
function chatSaveHistory(list) {
  try { localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(list.slice(-80))); }
  catch (e) {}
}
function chatGetMode() {
  try { return localStorage.getItem(CHAT_MODE_KEY) || 'patient'; } catch (e) { return 'patient'; }
}
function chatGetVersion() {
  // 自動以使用者「年長版」UI mode 為預設
  try {
    var v = localStorage.getItem(CHAT_VERSION_KEY);
    if (v) return v;
  } catch (e) {}
  return (typeof getMode === 'function' && getMode() === 'senior') ? 'elderly' : 'normal';
}
function chatSetMode(m) {
  try { localStorage.setItem(CHAT_MODE_KEY, m); } catch (e) {}
}
function chatSetVersion(v) {
  try { localStorage.setItem(CHAT_VERSION_KEY, v); } catch (e) {}
}

// 小禾吉祥物 — Claude Code 風 ASCII 顏文字兔
// state: 'idle' | 'typing' | 'thinking'
// frame: 0/1 — typing 狀態下交替的「左手敲 / 右手敲」鍵盤動畫
function chatMascotSvg(state, frame) {
  state = state || 'idle';
  if (state === 'typing') {
    // 三行：耳朵、臉、雙手在鍵盤上交替敲擊
    var bottom = (frame % 2 === 0)
      ? ' o⌨<span class="chat-mascot-keys">▓▓▓</span>'   // 左手按下
      : ' <span class="chat-mascot-keys">▓▓▓</span>⌨o';  // 右手按下
    var ascii = ''
      + ' (\\(\\\n'
      + ' ( •ω•)\n'
      + bottom;
    return ''
      + '<div class="chat-mascot-img-wrap chat-mascot-typing">'
      +   '<pre class="chat-mascot-ascii" aria-label="小禾正在打字">' + ascii + '</pre>'
      + '</div>';
  }
  if (state === 'thinking') {
    var thinkAscii = ''
      + ' (\\(\\\n'
      + ' ( -ㅅ-)\n'
      + ' (  づ<span class="chat-mascot-spark">?</span>';
    return ''
      + '<div class="chat-mascot-img-wrap chat-mascot-thinking">'
      +   '<pre class="chat-mascot-ascii" aria-label="小禾思考中">' + thinkAscii + '</pre>'
      + '</div>';
  }
  // idle
  var idleAscii = ''
    + ' (\\(\\\n'
    + ' ( •ㅅ•)\n'
    + ' (  づ<span class="chat-mascot-spark">♥</span>';
  return ''
    + '<div class="chat-mascot-img-wrap chat-mascot-idle">'
    +   '<pre class="chat-mascot-ascii" aria-label="小禾">' + idleAscii + '</pre>'
    + '</div>';
}

function chatGreeting() {
  var u = (typeof getCurrentUser === 'function') ? (getCurrentUser() || {}) : {};
  var name = u.nickname || '你';
  var v = chatGetVersion();
  if (v === 'elderly') {
    return '你好啊，' + name + '。我是小禾，今天身體有沒有比較舒服？慢慢說，我都聽。';
  }
  return '嗨，' + name + '，我是小禾。今天想聊什麼都可以，身體、心情、或是想寫點東西都行。';
}

function chat() {
  var hist = chatLoadHistory();
  var mode = chatGetMode();
  var ver  = chatGetVersion();

  var msgsHtml = hist.length
    ? hist.map(chatRenderMessage).join('')
    : ''
      + '<div class="chat-msg chat-msg-bot">'
      +   '<div class="chat-bubble">'
      +     '<div class="chat-text">' + chatGreeting() + '</div>'
      +   '</div>'
      + '</div>';

  return ''
    + '<section class="chat-page">'
    + '  <header class="chat-header">'
    + '    <div class="chat-mascot-wrap chat-mascot-wrap-lg" id="chat-mascot">'
    +        chatMascotSvg('idle')
    + '    </div>'
    + '    <div class="chat-header-text">'
    + '      <p class="chat-eyebrow">// chat &gt; xiaohe.ai</p>'
    + '      <h2 class="chat-title">醫起聊天</h2>'
    + '      <p class="chat-sub">小禾陪你聊聊，把感受拼成一段話、一篇文章。</p>'
    + '    </div>'
    + '    <div class="chat-toggles">'
    + '      <div class="chat-seg" role="tablist" aria-label="對話對象">'
    + '        <button type="button" class="chat-seg-btn' + (mode === 'patient' ? ' active' : '') + '" onclick="chatSwitchMode(\'patient\')">我是患者</button>'
    + '        <button type="button" class="chat-seg-btn' + (mode === 'family'  ? ' active' : '') + '" onclick="chatSwitchMode(\'family\')">我是家屬</button>'
    + '      </div>'
    + '      <div class="chat-seg" role="tablist" aria-label="語氣">'
    + '        <button type="button" class="chat-seg-btn' + (ver === 'normal'  ? ' active' : '') + '" onclick="chatSwitchVersion(\'normal\')">一般</button>'
    + '        <button type="button" class="chat-seg-btn' + (ver === 'elderly' ? ' active' : '') + '" onclick="chatSwitchVersion(\'elderly\')">年長版</button>'
    + '      </div>'
    + '    </div>'
    + '  </header>'

    + '  <div class="chat-stream" id="chat-stream">'
    +      msgsHtml
    + '  </div>'

    + '  <div class="chat-suggest" id="chat-suggest">'
    + '    <span class="chat-suggest-label">聊聊：</span>'
    + '    <button type="button" class="chat-chip" onclick="chatQuickAsk(\'幫我把最近三天的不舒服整理成一段話\')">整理近況</button>'
    + '    <button type="button" class="chat-chip" onclick="chatQuickAsk(\'我有點焦慮，可以陪我說說話嗎？\')">陪我聊聊</button>'
    + '    <button type="button" class="chat-chip chat-chip-special" onclick="chatGenerateArticle()">'
    + '      <i data-lucide="sparkles" style="width:14px;height:14px"></i> 生成一篇文章'
    + '    </button>'
    + '    <span class="chat-suggest-sep">·</span>'
    + '    <span class="chat-suggest-label">紀錄：</span>'
    + '    <button type="button" class="chat-chip chat-chip-nav" onclick="navigateTo(\'symptoms\',null)">'
    + '      <i data-lucide="plus" style="width:13px;height:13px"></i> 紀錄症狀'
    + '    </button>'
    + '    <button type="button" class="chat-chip chat-chip-nav" onclick="navigateTo(\'medications\',null)">'
    + '      <i data-lucide="pill" style="width:13px;height:13px"></i> 打藥物卡'
    + '    </button>'
    + '    <button type="button" class="chat-chip chat-chip-nav" onclick="navigateTo(\'emotions\',null)">'
    + '      <i data-lucide="battery-charging" style="width:13px;height:13px"></i> 情緒電量'
    + '    </button>'
    + '    <button type="button" class="chat-chip chat-chip-nav" onclick="navigateTo(\'drugSearch\',null)">'
    + '      <i data-lucide="search" style="width:13px;height:13px"></i> 查藥物'
    + '    </button>'
    + '  </div>'

    + '  <form class="chat-input-bar" id="chat-form" onsubmit="event.preventDefault(); chatSend();">'
    + '    <span class="chat-prompt">$</span>'
    + '    <input id="chat-input" class="chat-input" type="text" autocomplete="off" placeholder="跟小禾說說話… (Enter 送出)" />'
    + '    <button type="button" class="chat-mic" id="chat-mic" onclick="chatToggleMic()" title="按住說話 / 點一下開始辨識">'
    + '      <i data-lucide="mic" style="width:16px;height:16px"></i>'
    + '    </button>'
    + '    <button type="submit" class="chat-send" id="chat-send">'
    + '      <i data-lucide="send" style="width:16px;height:16px"></i>'
    + '      <span>送出</span>'
    + '    </button>'
    + '    <button type="button" class="chat-clear" onclick="chatClear()" title="清空對話">'
    + '      <i data-lucide="trash-2" style="width:14px;height:14px"></i>'
    + '    </button>'
    + '  </form>'
    + '  <p class="chat-disclaimer">小禾不是醫師，僅作為陪伴與資訊參考；身體不適請務必就醫。</p>'
    + '</section>';
}

function chatRenderMessage(m) {
  if (m.role === 'user') {
    return ''
      + '<div class="chat-msg chat-msg-user">'
      +   '<div class="chat-bubble">'
      +     '<div class="chat-text">' + chatEscape(m.text) + '</div>'
      +   '</div>'
      + '</div>';
  }
  if (m.role === 'article') {
    return ''
      + '<div class="chat-msg chat-msg-bot chat-msg-article">'
      +   '<div class="chat-bubble chat-bubble-article">'
      +     '<div class="chat-article-head"><i data-lucide="file-text"></i> 小禾為你寫的一篇</div>'
      +     '<div class="chat-text chat-article-text">' + chatEscape(m.text) + '</div>'
      +   '</div>'
      + '</div>';
  }
  return ''
    + '<div class="chat-msg chat-msg-bot">'
    +   '<div class="chat-bubble">'
    +     '<div class="chat-text">' + chatEscape(m.text) + '</div>'
    +   '</div>'
    + '</div>';
}

function chatEscape(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>');
}

function loadChatPage() {
  var input = document.getElementById('chat-input');
  if (input) {
    input.focus();
    input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatSend();
      }
    });
  }
  chatScrollToBottom();
}

function chatScrollToBottom() {
  var s = document.getElementById('chat-stream');
  if (s) s.scrollTop = s.scrollHeight;
}

function chatSwitchMode(m) {
  chatSetMode(m);
  document.querySelectorAll('.chat-toggles .chat-seg').forEach(function(seg, i) {
    if (i !== 0) return;
    seg.querySelectorAll('.chat-seg-btn').forEach(function(b, j) {
      var want = (j === 0) ? 'patient' : 'family';
      b.classList.toggle('active', want === m);
    });
  });
  showToast(m === 'family' ? '切換為家屬模式' : '切換為患者模式', 'info');
}

function chatSwitchVersion(v) {
  chatSetVersion(v);
  document.querySelectorAll('.chat-toggles .chat-seg').forEach(function(seg, i) {
    if (i !== 1) return;
    seg.querySelectorAll('.chat-seg-btn').forEach(function(b, j) {
      var want = (j === 0) ? 'normal' : 'elderly';
      b.classList.toggle('active', want === v);
    });
  });
  showToast(v === 'elderly' ? '切換為年長版語氣' : '切換為一般語氣', 'info');
}

function chatQuickAsk(text) {
  var input = document.getElementById('chat-input');
  if (input) input.value = text;
  chatSend();
}

function chatClear() {
  if (!confirm('清空對話紀錄？')) return;
  try { localStorage.removeItem(CHAT_HISTORY_KEY); } catch (e) {}
  // 重新渲染
  var stream = document.getElementById('chat-stream');
  if (stream) {
    stream.innerHTML = ''
      + '<div class="chat-msg chat-msg-bot">'
      +   '<div class="chat-bubble">'
      +     '<div class="chat-text">' + chatGreeting() + '</div>'
      +   '</div>'
      + '</div>';
  }
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function chatAppendMessage(role, text) {
  var stream = document.getElementById('chat-stream');
  if (!stream) return null;
  var wrap = document.createElement('div');
  wrap.innerHTML = chatRenderMessage({ role: role, text: text });
  var node = wrap.firstChild;
  stream.appendChild(node);
  if (typeof lucide !== 'undefined') lucide.createIcons();
  chatScrollToBottom();
  return node;
}

function chatShowThinking() {
  var stream = document.getElementById('chat-stream');
  if (!stream) return null;
  var node = document.createElement('div');
  node.className = 'chat-msg chat-msg-bot chat-msg-thinking';
  node.id = 'chat-thinking';
  node.innerHTML = ''
    + '<div class="chat-bubble">'
    +   '<div class="chat-typing-dots"><span></span><span></span><span></span></div>'
    + '</div>';
  stream.appendChild(node);
  chatSetMascotState('thinking');
  chatScrollToBottom();
  return node;
}

function chatRemoveThinking() {
  var n = document.getElementById('chat-thinking');
  if (n && n.parentNode) n.parentNode.removeChild(n);
}

var _chatMascotTypingTimer = null;
function chatSetMascotState(state) {
  var wrap = document.getElementById('chat-mascot');
  if (!wrap) return;
  // 停掉之前可能在跑的 typing 動畫
  if (_chatMascotTypingTimer) {
    clearInterval(_chatMascotTypingTimer);
    _chatMascotTypingTimer = null;
  }
  if (state === 'typing') {
    var frame = 0;
    wrap.innerHTML = chatMascotSvg('typing', frame);
    _chatMascotTypingTimer = setInterval(function () {
      frame = (frame + 1) % 2;
      var w = document.getElementById('chat-mascot');
      if (!w) { clearInterval(_chatMascotTypingTimer); _chatMascotTypingTimer = null; return; }
      w.innerHTML = chatMascotSvg('typing', frame);
    }, 140);
    return;
  }
  wrap.innerHTML = chatMascotSvg(state);
}

// 打字機效果：把文字一個個塞進 element
function chatTypeInto(node, text, opts, onDone) {
  opts = opts || {};
  var speed = opts.speed || 22; // ms per char
  var i = 0;
  if (_chatTypeTimer) { clearInterval(_chatTypeTimer); _chatTypeTimer = null; }
  _chatTyping = true;
  chatSetMascotState('typing');
  node.innerHTML = '<span class="chat-caret">▌</span>';
  _chatTypeTimer = setInterval(function() {
    if (i >= text.length) {
      clearInterval(_chatTypeTimer); _chatTypeTimer = null;
      _chatTyping = false;
      node.innerHTML = chatEscape(text);
      chatSetMascotState('idle');
      if (typeof onDone === 'function') onDone();
      chatScrollToBottom();
      return;
    }
    var partial = text.slice(0, i + 1);
    node.innerHTML = chatEscape(partial) + '<span class="chat-caret">▌</span>';
    chatScrollToBottom();
    i += 1;
  }, speed);
}

// === 語音輸入（webkitSpeechRecognition）=========================================
var _chatRec = null;
var _chatRecActive = false;

function chatToggleMic() {
  var Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Rec) {
    showToast('這個瀏覽器不支援語音輸入（建議用 Chrome/Edge/Safari）', 'warning');
    return;
  }
  if (_chatRecActive && _chatRec) {
    try { _chatRec.stop(); } catch (e) {}
    return;
  }
  var rec = new Rec();
  rec.lang = 'zh-TW';
  rec.continuous = false;
  rec.interimResults = true;
  rec.maxAlternatives = 1;

  var input = document.getElementById('chat-input');
  var btn = document.getElementById('chat-mic');
  if (btn) btn.classList.add('chat-mic-active');
  _chatRecActive = true;
  _chatRec = rec;

  var finalText = '';
  rec.onresult = function (ev) {
    var interim = '';
    for (var i = ev.resultIndex; i < ev.results.length; i++) {
      var r = ev.results[i];
      if (r.isFinal) finalText += r[0].transcript;
      else interim += r[0].transcript;
    }
    if (input) input.value = (finalText + interim).trim();
  };
  rec.onerror = function (ev) {
    if (ev && ev.error === 'not-allowed') {
      showToast('需要允許麥克風權限才能用語音輸入', 'error');
    } else if (ev && ev.error && ev.error !== 'no-speech' && ev.error !== 'aborted') {
      showToast('語音辨識：' + ev.error, 'warning');
    }
  };
  rec.onend = function () {
    _chatRecActive = false;
    _chatRec = null;
    if (btn) btn.classList.remove('chat-mic-active');
    // 講完自動送出（如果有內容）
    if (input && (input.value || '').trim()) chatSend();
  };

  try { rec.start(); }
  catch (e) {
    _chatRecActive = false;
    _chatRec = null;
    if (btn) btn.classList.remove('chat-mic-active');
    showToast('啟動語音失敗：' + (e.message || e), 'error');
  }
}

function chatSend() {
  if (_chatTyping) { showToast('小禾正在說話…等一下下', 'info'); return; }
  var input = document.getElementById('chat-input');
  if (!input) return;
  var text = (input.value || '').trim();
  if (!text) return;
  input.value = '';

  // 在 push 新訊息「之前」抓歷史，讓 history 不含本則 message
  var apiHistory = chatBuildApiHistory(12);

  var hist = chatLoadHistory();
  hist.push({ role: 'user', text: text, t: Date.now() });
  chatSaveHistory(hist);
  chatAppendMessage('user', text);

  chatShowThinking();

  var pid = (typeof getStablePatientId === 'function') ? getStablePatientId() : 'demo';
  var body = {
    user_id: pid,
    message: text,
    mode: chatGetMode(),
    version: chatGetVersion(),
    history: apiHistory
  };

  chatStreamReply(body, /*fallback*/ '抱歉，小禾沒收到回覆，可以再說一次嗎？');
}

// 把後端 SSE 流逐 token 渲染進 bot 氣泡；同時保持小禾打字動畫
function chatStreamReply(body, fallbackText) {
  fetch(API + '/xiaohe/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
    body: JSON.stringify(body)
  }).then(function (resp) {
    if (!resp.ok || !resp.body) throw new Error('stream not available: ' + resp.status);
    chatRemoveThinking();
    chatSetMascotState('typing');
    _chatTyping = true;

    var node = chatAppendMessage('bot', '');
    var textEl = node ? node.querySelector('.chat-text') : null;
    var reader = resp.body.getReader();
    var decoder = new TextDecoder('utf-8');
    var buf = '';
    var fullText = '';

    function pump() {
      return reader.read().then(function (r) {
        if (r.done) return;
        buf += decoder.decode(r.value, { stream: true });
        // SSE 事件以兩個換行分隔
        var parts = buf.split(/\n\n/);
        buf = parts.pop();
        for (var i = 0; i < parts.length; i++) {
          var line = parts[i];
          if (!line) continue;
          // 取出 data: 後的 JSON
          var idx = line.indexOf('data:');
          if (idx < 0) continue;
          var payload = line.slice(idx + 5).trim();
          var obj = null;
          try { obj = JSON.parse(payload); } catch (e) { continue; }
          if (obj.delta && textEl) {
            fullText += obj.delta;
            textEl.innerHTML = chatEscape(fullText);
            chatScrollToBottom();
          }
          if (obj.done) {
            // 結束
          }
        }
        return pump();
      });
    }

    return pump().then(function () {
      _chatTyping = false;
      chatSetMascotState('idle');
      var h = chatLoadHistory();
      h.push({ role: 'bot', text: fullText || fallbackText || '', t: Date.now() });
      chatSaveHistory(h);
    });
  }).catch(function (err) {
    _chatTyping = false;
    chatRemoveThinking();
    chatSetMascotState('idle');
    // 串流失敗 → 退回非串流的 chat
    chatNonStreamFallback(body, fallbackText);
  });
}

// 串流不通時的 fallback：用原本的 /xiaohe/chat 並以 typewriter 效果顯示
function chatNonStreamFallback(body, fallbackText) {
  fetch(API + '/xiaohe/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
    .then(function (r) { return r.json().catch(function () { return {}; }); })
    .then(function (data) {
      var reply = (data && data.reply) ? String(data.reply)
        : (fallbackText || '網路有點忙，等一下再試試看。');
      var node = chatAppendMessage('bot', '');
      var textEl = node ? node.querySelector('.chat-text') : null;
      if (!textEl) return;
      chatTypeInto(textEl, reply, {}, function () {
        var h = chatLoadHistory();
        h.push({ role: 'bot', text: reply, t: Date.now() });
        chatSaveHistory(h);
      });
    })
    .catch(function () {
      var node = chatAppendMessage('bot', '');
      var textEl = node ? node.querySelector('.chat-text') : null;
      if (textEl) chatTypeInto(textEl, '網路有點忙，等一下再試試看。');
    });
}

// 「生成一篇文章」— 把最近的對話交給小禾，請它整理成一篇短文，
// 然後以打字機方式產出（像 Claude Code 打字打一打產出文章）
function chatGenerateArticle() {
  if (_chatTyping) { showToast('小禾正在說話…等一下下', 'info'); return; }
  var hist = chatLoadHistory();
  var recent = hist.slice(-12).map(function(m) {
    var who = m.role === 'user' ? '我' : '小禾';
    return who + '：' + m.text;
  }).join('\n');

  var prompt = ''
    + '請依據下面這段對話，幫我寫一篇 200~350 字的短文，'
    + '主題是「最近的我」，溫暖、口語化、第一人稱、分 2~3 段，'
    + '結尾給自己一句鼓勵。如果對話內容不足，就以一般問候與健康提醒為主。\n\n'
    + '【對話】\n' + (recent || '（尚無對話）');

  // 把使用者意圖也記下來
  hist.push({ role: 'user', text: '幫我把這段對話寫成一篇文章', t: Date.now() });
  chatSaveHistory(hist);
  chatAppendMessage('user', '幫我把這段對話寫成一篇文章');

  chatShowThinking();
  var pid = (typeof getStablePatientId === 'function') ? getStablePatientId() : 'demo';
  fetch(API + '/xiaohe/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: pid, message: prompt,
      mode: chatGetMode(), version: chatGetVersion(),
      history: chatBuildApiHistory(12)
    })
  })
    .then(function(r) { return r.json().catch(function() { return {}; }); })
    .then(function(data) {
      chatRemoveThinking();
      var article = (data && data.reply) ? String(data.reply)
        : '今天先好好喝杯水，深呼吸三次。明天再來把感受寫下來，我會等你。';
      var node = chatAppendMessage('article', '');
      var textEl = node ? node.querySelector('.chat-article-text') : null;
      if (!textEl) return;
      chatTypeInto(textEl, article, { speed: 18 }, function() {
        var h = chatLoadHistory();
        h.push({ role: 'article', text: article, t: Date.now() });
        chatSaveHistory(h);
      });
    })
    .catch(function() {
      chatRemoveThinking();
      var fallback = '網路有點忙，等一下再試試看寫文章。';
      var node = chatAppendMessage('bot', '');
      var textEl = node ? node.querySelector('.chat-text') : null;
      if (textEl) chatTypeInto(textEl, fallback);
    });
}

function settings() {
  var user = getCurrentUser();
  var fs   = getSetting('fontSize', 'normal');
  var th;
  try { th = localStorage.getItem(SETTINGS_KEYS.theme) || 'auto'; } catch (e) { th = 'auto'; }
  var md   = getMode();
  var mo   = getSetting('motion', 'on');
  var so   = getSetting('sound', 'on');
  var de   = getSetting('density', 'cozy');
  var name = user ? (user.nickname || _T('set.guest')) : _T('set.guest');
  var idno = user && user.id_number ? user.id_number : '—';
  var ac   = (user && user.avatar_color) ? user.avatar_color : '#4A90C2';

  function seg(group, opts, current) {
    return opts.map(function(o) {
      var act = o.value === current ? ' active' : '';
      return '<button type="button" class="set-seg-btn' + act + '"'
        + ' data-group="' + group + '" data-value="' + o.value + '"'
        + ' onclick="onSettingChange(\'' + group + '\',\'' + o.value + '\')">'
        + o.label + '</button>';
    }).join('');
  }

  function row(title, desc, control) {
    return '<div class="set-row">'
      + '<div class="set-row-text"><strong>' + title + '</strong>'
      + (desc ? '<p>' + desc + '</p>' : '') + '</div>'
      + '<div class="set-row-ctrl">' + control + '</div>'
      + '</div>';
  }

  function sw(id, key, on, onVal, offVal) {
    return '<label class="set-switch">'
      + '<input type="checkbox" id="' + id + '"' + (on ? ' checked' : '')
      + ' onchange="onSwitchChange(\'' + key + '\', this.checked ? \'' + onVal + '\' : \'' + offVal + '\')" />'
      + '<span class="set-switch-track"><span class="set-switch-thumb"></span></span>'
      + '</label>';
  }

  return ''
    + '<section class="set-page">'
    + '  <header class="set-hero">'
    + '    <div class="set-hero-icon" style="--ac:' + ac + '"><i data-lucide="settings-2"></i></div>'
    + '    <div class="set-hero-text">'
    + '      <p class="set-eyebrow">' + _T('set.eyebrow') + '</p>'
    + '      <h2>' + _T('set.title') + '</h2>'
    + '      <p class="set-sub">' + _T('set.sub') + '</p>'
    + '    </div>'
    + '    <div class="set-hero-user">'
    + '      <span>' + _T('set.user.label') + '</span>'
    + '      <strong>' + name + '</strong>'
    + '      <code>' + idno + '</code>'
    + '    </div>'
    + '  </header>'

    // Display
    + '  <div class="set-group">'
    + '    <h3 class="set-group-title"><i data-lucide="monitor"></i> ' + _T('set.group.display') + '</h3>'
    +      row(_T('set.row.fontSize.t'), _T('set.row.fontSize.d'),
            '<div class="set-seg">' + seg('fontSize', [
              {value:'small',  label:_T('set.opt.font.small')},
              {value:'normal', label:_T('set.opt.font.normal')},
              {value:'large',  label:_T('set.opt.font.large')},
              {value:'xlarge', label:_T('set.opt.font.xlarge')}
            ], fs) + '</div>')
    +      row(_T('set.row.theme.t'), _T('set.row.theme.d'),
            '<div class="set-seg">' + seg('theme', [
              {value:'light', label:_T('set.opt.theme.light')},
              {value:'dark',  label:_T('set.opt.theme.dark')},
              {value:'auto',  label:_T('set.opt.theme.auto')}
            ], th) + '</div>')
    +      row(_T('set.row.mode.t'), _T('set.row.mode.d'),
            '<div class="set-seg">' + seg('mode', [
              {value:'standard', label:_T('set.opt.mode.standard')},
              {value:'senior',   label:_T('set.opt.mode.senior')}
            ], md) + '</div>')
    +      row(_T('set.row.density.t'), _T('set.row.density.d'),
            '<div class="set-seg">' + seg('density', [
              {value:'cozy',    label:_T('set.opt.density.cozy')},
              {value:'compact', label:_T('set.opt.density.compact')}
            ], de) + '</div>')
    + '  </div>'

    // Accessibility
    + '  <div class="set-group">'
    + '    <h3 class="set-group-title"><i data-lucide="accessibility"></i> ' + _T('set.group.access') + '</h3>'
    +      row(_T('set.row.motion.t'), _T('set.row.motion.d'),
            sw('sw-motion', 'motion', mo === 'on', 'on', 'reduced'))
    +      row(_T('set.row.sound.t'), _T('set.row.sound.d'),
            sw('sw-sound', 'sound', so === 'on', 'on', 'off'))
    + '  </div>'

    // Account & data
    + '  <div class="set-group">'
    + '    <h3 class="set-group-title"><i data-lucide="database"></i> ' + _T('set.group.data') + '</h3>'
    +      row(_T('set.row.cache.t'), _T('set.row.cache.d'),
            '<button class="set-btn" onclick="settingsClearCache()"><i data-lucide="refresh-cw"></i> ' + _T('set.row.cache.btn') + '</button>')
    +      row(_T('set.row.reset.t'), _T('set.row.reset.d'),
            '<button class="set-btn set-btn-warn" onclick="settingsResetCard()"><i data-lucide="id-card"></i> ' + _T('set.row.reset.btn') + '</button>')
    +      row(_T('set.row.logout.t'), _T('set.row.logout.d'),
            '<button class="set-btn set-btn-danger" onclick="logout()"><i data-lucide="log-out"></i> ' + _T('set.row.logout.btn') + '</button>')
    + '  </div>'

    // About
    + '  <div class="set-group">'
    + '    <h3 class="set-group-title"><i data-lucide="info"></i> ' + _T('set.group.about') + '</h3>'
    + '    <div class="set-about">'
    + '      <p>' + _T('set.about.tagline') + '</p>'
    + '      <dl class="set-about-grid">'
    + '        <dt>' + _T('set.about.version') + '</dt><dd><code>v2.0</code></dd>'
    + '        <dt>' + _T('set.about.author') + '</dt><dd>余家馨</dd>'
    + '        <dt>' + _T('set.about.website') + '</dt><dd><a href="https://www.mdpiece.life/" target="_blank" rel="noopener">www.mdpiece.life</a></dd>'
    + '        <dt>' + _T('set.about.source') + '</dt><dd><a href="https://github.com/' + GITHUB_REPO + '" target="_blank" rel="noopener">' + GITHUB_REPO + '</a></dd>'
    + '      </dl>'
    + '    </div>'
    + '  </div>'
    + '</section>';
}

function loadSettingsPage() {
  // 確保 Lucide 圖示渲染
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function onSettingChange(group, value) {
  if (group === 'fontSize') {
    setSetting('fontSize', value);
    applyFontSize(value);
  } else if (group === 'theme') {
    try { localStorage.setItem(SETTINGS_KEYS.theme, value); } catch (e) {}
    applyTheme(value);
  } else if (group === 'mode') {
    setMode(value);
  } else if (group === 'density') {
    setSetting('density', value);
    applyDensity(value);
  }
  // 更新該群組按鈕的 active 狀態
  document.querySelectorAll('.set-seg-btn[data-group="' + group + '"]').forEach(function(b) {
    b.classList.toggle('active', b.dataset.value === value);
  });
  if (typeof showToast === 'function') showToast('已儲存設定', 'success');
}

function onSwitchChange(key, value) {
  setSetting(key, value);
  if (key === 'motion') applyMotion(value);
  if (typeof showToast === 'function') showToast('已儲存設定', 'success');
}

function settingsClearCache() {
  if (!confirm('將清除本機快取並重新載入頁面，繼續嗎？')) return;
  try {
    if ('caches' in window) {
      caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k)))).finally(() => location.reload());
    } else {
      location.reload();
    }
  } catch (e) { location.reload(); }
}

function settingsResetCard() {
  if (!confirm('確定要重新發卡？\n\n會清除目前 ID 卡與本機暫存資料，\n下次進入會重新註冊。')) return;
  try {
    localStorage.removeItem('mdpiece_user');
    localStorage.removeItem('mdpiece_demo_pid');
  } catch (e) {}
  window.location.reload();
}

function markdownToHtml(md) {
  if (!md) return "";
  return md
    .replace(/^### (.+)$/gm, '<h4 style="margin-top:16px;margin-bottom:8px;color:var(--accent)">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 style="margin-top:20px;margin-bottom:8px">$1</h3>')
    .replace(/^# (.+)$/gm, '<h2 style="margin-top:24px;margin-bottom:12px">$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^- (.+)$/gm, '<li style="margin-left:20px;margin-bottom:4px">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li style="margin-left:20px;margin-bottom:4px"><strong>$1.</strong> $2</li>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
}


// ─── 報告數值（Lab Values）─────────────────────────────────
// 隱私：紀錄只存 sessionStorage（關分頁即消失），後端 stateless 不寫 DB

const LABS_HISTORY_KEY = 'mdpiece_labs_history';
const LABS_STATUS_META = {
  low:      { label: '偏低',     emoji: '🟡', cls: 'labs-st-warn' },
  normal:   { label: '正常',     emoji: '🟢', cls: 'labs-st-ok' },
  high:     { label: '偏高',     emoji: '🟡', cls: 'labs-st-warn' },
  critical: { label: '嚴重異常', emoji: '🔴', cls: 'labs-st-bad' },
  unknown:  { label: '無法判讀', emoji: '⚪', cls: 'labs-st-unk' },
};

function labsLoadHistory() {
  try { return JSON.parse(sessionStorage.getItem(LABS_HISTORY_KEY) || '[]'); }
  catch (e) { return []; }
}

function labsSaveHistory(arr) {
  try { sessionStorage.setItem(LABS_HISTORY_KEY, JSON.stringify(arr.slice(0, 30))); }
  catch (e) { /* quota exceeded — ignore */ }
}

function loadLabsPage() {
  labsRenderHistory();
}

function labsRenderHistory() {
  const listEl = document.getElementById('labs-history-list');
  if (!listEl) return;
  const items = labsLoadHistory();
  if (!items.length) {
    listEl.innerHTML = '<p class="labs-empty">尚無查詢紀錄。紀錄僅存於此分頁，關閉後即清除。</p>';
    return;
  }
  listEl.innerHTML = items.map((it, idx) => {
    const meta = LABS_STATUS_META[it.status] || LABS_STATUS_META.unknown;
    const time = new Date(it.at).toLocaleString('zh-TW', { hour12: false });
    return '' +
      '<article class="labs-history-item ' + meta.cls + '" onclick="labsShowFromHistory(' + idx + ')">' +
        '<span class="labs-history-emoji">' + meta.emoji + '</span>' +
        '<div class="labs-history-body">' +
          '<div class="labs-history-top">' +
            '<strong>' + escapeHtml(it.name) + '</strong>' +
            '<span class="labs-history-value">' + escapeHtml(it.value) +
              (it.unit ? ' ' + escapeHtml(it.unit) : '') + '</span>' +
          '</div>' +
          '<div class="labs-history-meta">' + meta.label + ' · ' + time + '</div>' +
        '</div>' +
      '</article>';
  }).join('');
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function labsShowFromHistory(idx) {
  const items = labsLoadHistory();
  const it = items[idx];
  if (!it) return;
  labsRenderResult(it.result, { name: it.name, value: it.value, unit: it.unit });
}

function labsClearHistory() {
  if (!confirm('確定要清除所有查詢紀錄嗎？')) return;
  sessionStorage.removeItem(LABS_HISTORY_KEY);
  labsRenderHistory();
  const r = document.getElementById('lab-result');
  if (r) { r.style.display = 'none'; r.innerHTML = ''; }
}

async function labsCheck() {
  const name  = document.getElementById('lab-name').value.trim();
  const value = document.getElementById('lab-value').value.trim();
  const unit  = document.getElementById('lab-unit').value.trim();
  const ageS  = document.getElementById('lab-age').value.trim();
  const sex   = document.getElementById('lab-sex').value;

  if (!name || !value) {
    if (typeof showToast === 'function') showToast('請輸入檢驗項目與數值', 'warning');
    document.getElementById(!name ? 'lab-name' : 'lab-value').focus();
    return;
  }

  const resultEl = document.getElementById('lab-result');
  resultEl.style.display = 'block';
  resultEl.innerHTML = '<p class="labs-loading"><i data-lucide="loader" class="labs-spin"></i> MD.Piece 解讀中…</p>';
  if (typeof lucide !== 'undefined') lucide.createIcons();

  try {
    const body = { name, value };
    if (unit) body.unit = unit;
    if (ageS) body.age = parseInt(ageS, 10);
    if (sex)  body.sex = sex;

    const res = await fetch(`${API}/labs/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '查詢失敗');
    }
    const data = await res.json();

    labsRenderResult(data, { name, value, unit });

    const hist = labsLoadHistory();
    hist.unshift({ name, value, unit, status: data.status, result: data, at: Date.now() });
    labsSaveHistory(hist);
    labsRenderHistory();
  } catch (e) {
    resultEl.innerHTML = '<p class="labs-error">查詢失敗：' + escapeHtml(e.message || '未知錯誤') + '</p>';
  }
}

// ── 拍攝整份報告，一次列出所有項目正常/異常 ───────────────
function handleLabPhoto(input) {
  if (!input.files || !input.files[0]) return;
  var file = input.files[0];
  var preview = document.getElementById('lab-scan-preview');
  var result = document.getElementById('lab-scan-result');
  var hint = document.getElementById('lab-scan-hint');
  if (preview) preview.innerHTML = '<div style="color:var(--text-muted);font-size:.85rem">壓縮並上傳照片…</div>';
  if (result) result.innerHTML = '';
  if (hint) hint.textContent = '';

  _compressMedPhoto(file).then(function(prepared) {
    if (!prepared) {
      if (preview) preview.innerHTML = '<div class="labs-error">讀取照片失敗，請改用上方手動輸入。</div>';
      input.value = '';
      return;
    }
    var dataUrl = prepared.dataUrl;
    var mediaType = prepared.mediaType || 'image/jpeg';
    var base64 = (dataUrl.split(',')[1] || '');

    if (preview) {
      preview.innerHTML =
        '<img src="' + dataUrl + '" alt="檢驗報告預覽" ' +
        'style="max-width:100%;max-height:280px;border-radius:8px;border:1px solid var(--border)" />';
    }
    if (result) {
      result.innerHTML = '<p class="labs-loading"><i data-lucide="loader" class="labs-spin"></i> MD.Piece 正在判讀整份報告…通常 10–30 秒</p>';
      if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    fetch(API + '/labs/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_base64: base64, media_type: mediaType })
    })
      .then(function(r) {
        return r.text().then(function(t) {
          var parsed; try { parsed = JSON.parse(t); } catch (e) { parsed = { detail: t }; }
          return { ok: r.ok, status: r.status, data: parsed };
        });
      })
      .then(function(res) {
        if (!res.ok) {
          var msg = (res.data && (res.data.detail || res.data.message)) || ('HTTP ' + res.status);
          if (typeof msg !== 'string') msg = JSON.stringify(msg);
          if (result) result.innerHTML = '<p class="labs-error">辨識失敗：' + escapeHtml(msg) + '</p>';
          return;
        }
        labsRenderScanResult(res.data || {});
        labsAppendScannedToHistory((res.data && res.data.items) || []);
      })
      .catch(function(err) {
        if (result) result.innerHTML = '<p class="labs-error">辨識服務連線失敗：' + escapeHtml((err && err.message) || '網路錯誤') + '</p>';
      });
  });
  input.value = '';
}

function labsRenderScanResult(data) {
  var resultEl = document.getElementById('lab-scan-result');
  if (!resultEl) return;
  var items = data.items || [];
  if (!items.length) {
    var note = '';
    if (data.errors && data.errors.length) {
      note = '<details style="margin-top:8px;font-size:.78rem;color:var(--text-dim)"><summary>查看讀取失敗紀錄</summary>' +
        '<ul style="margin-top:6px;padding-left:18px">' +
        data.errors.map(function(e) { return '<li>' + escapeHtml((e.provider || '?') + '：' + (e.error || '')) + '</li>'; }).join('') +
        '</ul></details>';
    }
    resultEl.innerHTML = '<p class="labs-error">沒有從這張照片讀到檢驗項目。可以再拍清楚一點，或改用上方手動查詢。</p>' + note;
    return;
  }
  var summary = data.summary || {};
  var headLines = [
    '<strong>共讀到 ' + items.length + ' 項</strong>',
  ];
  if (summary.abnormal) headLines.push('<span class="labs-st-warn" style="padding:2px 8px;border-radius:10px">異常 ' + summary.abnormal + ' 項</span>');
  if (summary.needs_doctor) headLines.push('<span class="labs-st-bad" style="padding:2px 8px;border-radius:10px">建議就醫</span>');

  var sortRank = { critical: 0, high: 1, low: 2, unknown: 3, normal: 4 };
  function rankOf(s) { var r = sortRank[s]; return (r === undefined) ? 9 : r; }
  items = items.slice().sort(function(a, b) { return rankOf(a.status) - rankOf(b.status); });

  var listHtml = items.map(function(it, idx) {
    var meta = LABS_STATUS_META[it.status] || LABS_STATUS_META.unknown;
    var unitTxt = it.unit ? ' ' + escapeHtml(it.unit) : '';
    var seeDoc = it.see_doctor
      ? '<span style="margin-left:6px;padding:1px 6px;border-radius:8px;background:#fee;color:#a30;font-size:.7rem">建議就醫</span>'
      : '';
    return '' +
      '<details class="labs-scan-item ' + meta.cls + '"' + (idx < 3 ? ' open' : '') + ' ' +
      'style="margin-top:6px;padding:8px 10px;border-radius:8px;border:1px solid var(--border);background:var(--bg-card)">' +
        '<summary style="cursor:pointer;display:flex;align-items:center;gap:8px;flex-wrap:wrap">' +
          '<span>' + meta.emoji + '</span>' +
          '<strong>' + escapeHtml(it.name) + '</strong>' +
          '<span style="color:var(--text-dim)">' + escapeHtml(it.value) + unitTxt + '</span>' +
          '<span style="margin-left:auto;font-size:.78rem;color:var(--text-dim)">' + escapeHtml(meta.label) + '</span>' +
          seeDoc +
        '</summary>' +
        '<div style="margin-top:8px;font-size:.85rem;line-height:1.6">' +
          '<div><strong>參考範圍</strong>：' + escapeHtml(it.normal_range || '—') + '</div>' +
          (it.meaning ? '<div style="margin-top:4px"><strong>代表意義</strong>：' + escapeHtml(it.meaning) + '</div>' : '') +
          (it.advice  ? '<div style="margin-top:4px"><strong>建議</strong>：' + escapeHtml(it.advice) + '</div>' : '') +
        '</div>' +
      '</details>';
  }).join('');

  resultEl.innerHTML =
    '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:4px">' + headLines.join(' · ') + '</div>' +
    '<div style="margin-top:8px">' + listHtml + '</div>' +
    '<p class="labs-result-disclaimer" style="margin-top:8px">' + escapeHtml(data.disclaimer || '本判讀僅供參考，請以實際檢驗單位與醫師判讀為準') + '</p>';

  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function labsAppendScannedToHistory(items) {
  if (!items || !items.length) return;
  var hist = labsLoadHistory();
  items.forEach(function(it) {
    hist.unshift({
      name: it.name,
      value: String(it.value || ''),
      unit: it.unit || '',
      status: it.status || 'unknown',
      result: {
        item: it.name,
        normal_range: it.normal_range || '未知',
        status: it.status || 'unknown',
        meaning: it.meaning || '',
        advice: it.advice || '',
        see_doctor: !!it.see_doctor,
        disclaimer: '本結果僅供參考，請以實際檢驗單位與醫師判讀為準',
      },
      at: Date.now(),
      from_scan: true,
    });
  });
  labsSaveHistory(hist);
  labsRenderHistory();
}

function labsRenderResult(data, input) {
  const meta = LABS_STATUS_META[data.status] || LABS_STATUS_META.unknown;
  const resultEl = document.getElementById('lab-result');
  resultEl.style.display = 'block';
  resultEl.className = 'card labs-result ' + meta.cls;
  resultEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  resultEl.innerHTML = '' +
    '<div class="labs-result-head">' +
      '<span class="labs-result-emoji">' + meta.emoji + '</span>' +
      '<div>' +
        '<div class="labs-result-item">' + escapeHtml(data.item || input.name) + '</div>' +
        '<div class="labs-result-input">你輸入：' + escapeHtml(input.value) +
          (input.unit ? ' ' + escapeHtml(input.unit) : '') + '</div>' +
      '</div>' +
      '<span class="labs-result-status">' + meta.label + '</span>' +
    '</div>' +
    '<div class="labs-result-row"><strong>參考範圍</strong><span>' + escapeHtml(data.normal_range || '—') + '</span></div>' +
    '<div class="labs-result-block"><strong>這個指標代表</strong><p>' + escapeHtml(data.meaning || '—') + '</p></div>' +
    '<div class="labs-result-block"><strong>建議</strong><p>' + escapeHtml(data.advice || '—') + '</p></div>' +
    (data.see_doctor
      ? '<div class="labs-result-warn"><i data-lucide="alert-triangle" style="width:16px;height:16px;vertical-align:middle"></i> 建議盡快就醫評估</div>'
      : '') +
    '<p class="labs-result-disclaimer">' + escapeHtml(data.disclaimer || '本結果僅供參考，請以實際檢驗單位與醫師判讀為準') + '</p>';
  if (typeof lucide !== 'undefined') lucide.createIcons();
}


// ─── 情緒紀錄 ────────────────────────────────────────────
// 五階情緒打卡 + 7 天迷你折線圖 + 自動觸發 silent-guardian 警示

var EMOTION_LEVELS = [
  { score: 5, pct: 100, emoji: '😄', label: '滿電',   color: '#86C7B8' },
  { score: 4, pct:  75, emoji: '🙂', label: '充飽中', color: '#B5D6C4' },
  { score: 3, pct:  50, emoji: '😐', label: '中等',   color: '#D6CFC2' },
  { score: 2, pct:  25, emoji: '😟', label: '低電量', color: '#E0B89A' },
  { score: 1, pct:   0, emoji: '😢', label: '沒電',   color: '#C97B7B' },
];

function _moodPercent(score) {
  if (score == null) return null;
  // score 1~5 → 0%~100%（線性）
  return Math.round((Math.max(1, Math.min(5, score)) - 1) * 25);
}

function _moodColor(score) {
  if (score == null) return 'transparent';
  var rounded = Math.max(1, Math.min(5, Math.round(score)));
  var lvl = EMOTION_LEVELS.find(function(l) { return l.score === rounded; });
  return lvl ? lvl.color : '#D6CFC2';
}

function _moodEmoji(score) {
  if (score == null) return '';
  var rounded = Math.max(1, Math.min(5, Math.round(score)));
  var lvl = EMOTION_LEVELS.find(function(l) { return l.score === rounded; });
  return lvl ? lvl.emoji : '';
}

// SVG 電池圖示，依 percent 0-100 填充
function _batteryGlyph(percent, color) {
  var p = Math.max(0, Math.min(100, percent || 0));
  var fillW = 24 * (p / 100);
  return '<svg class="mood-batt" viewBox="0 0 32 18" aria-hidden="true">' +
    '<rect x="1" y="2" width="26" height="14" rx="2.5" ry="2.5" fill="none" stroke="currentColor" stroke-width="1.6"/>' +
    '<rect x="28" y="6" width="3" height="6" rx="1" fill="currentColor"/>' +
    '<rect x="2.5" y="3.5" width="' + fillW + '" height="11" rx="1.5" fill="' + (color || 'currentColor') + '"/>' +
  '</svg>';
}

function emotions() {
  return (
    '<section class="emotions-wrap">' +
      '<header class="emotions-head">' +
        '<h2><i data-lucide="battery-charging" style="width:22px;height:22px"></i> 情緒電力</h2>' +
        '<p>把今天的「心情電量」打卡留下，連續低電量會自動提醒你的醫師。</p>' +
      '</header>' +
      renderHowto('emotions') +

      // ── 環形電量 hero（顯示最近一筆，可即時更新）──────
      '<div class="emotions-card mood-ring-hero">' +
        '<div class="mood-ring-wrap">' +
          '<svg class="mood-ring" viewBox="0 0 200 200" width="180" height="180">' +
            '<defs>' +
              '<linearGradient id="mood-grad" x1="0" y1="0" x2="1" y2="1">' +
                '<stop offset="0%" stop-color="#4A90C2"/>' +
                '<stop offset="100%" stop-color="#6FB7DE"/>' +
              '</linearGradient>' +
            '</defs>' +
            '<circle cx="100" cy="100" r="80" fill="none" stroke="rgba(92,58,50,0.10)" stroke-width="14"/>' +
            '<circle id="mood-ring-arc" cx="100" cy="100" r="80" fill="none" stroke="url(#mood-grad)" stroke-width="14" stroke-linecap="round"' +
              ' stroke-dasharray="502" stroke-dashoffset="502" transform="rotate(-90 100 100)" style="transition:stroke-dashoffset 0.7s cubic-bezier(.4,0,.2,1)"/>' +
          '</svg>' +
          '<div class="mood-ring-center">' +
            '<div class="mood-ring-num"><span id="mood-ring-pct">—</span><span class="mood-ring-unit">%</span></div>' +
            '<div class="mood-ring-label" id="mood-ring-label">— 載入中</div>' +
          '</div>' +
        '</div>' +
        '<div class="mood-ring-meta">' +
          '<span class="mood-ring-eyebrow">最近一次心情</span>' +
          '<p class="mood-ring-hint" id="mood-ring-hint">目前還沒有紀錄，往下打卡開始累積。</p>' +
        '</div>' +
      '</div>' +

      '<div class="emotions-card mood-today">' +
        '<h3>今天剩多少電？</h3>' +
        '<p class="batt-hint mood-default-only">手指在電池上滑動，到第幾格就是幾格電</p>' +
        '<p class="batt-hint mood-senior-only">點下你今天的心情</p>' +
        '<div class="batt-picker mood-default-only" id="batt-picker">' +
          '<div class="batt-shell">' +
            '<div class="batt-body" id="batt-body" role="slider" aria-label="情緒電量" ' +
              'aria-valuemin="1" aria-valuemax="5" aria-valuenow="0" tabindex="0">' +
              EMOTION_LEVELS.slice().reverse().map(function(l) {
                return '<div class="batt-cell" data-score="' + l.score + '" ' +
                  'aria-label="' + l.label + ' ' + l.pct + '%"></div>';
              }).join('') +
            '</div>' +
            '<div class="batt-tip"></div>' +
          '</div>' +
          '<div class="batt-readout">' +
            '<span class="batt-emoji" id="batt-emoji">⚡</span>' +
            '<div class="batt-readout-text">' +
              '<span class="batt-pct" id="batt-pct">— %</span>' +
              '<span class="batt-label" id="batt-label">點電池選電量</span>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '<div class="mood-senior-picker mood-senior-only" id="mood-senior-picker">' +
          EMOTION_LEVELS.slice().reverse().map(function(l) {
            return '<button type="button" class="mood-senior-btn" data-score="' + l.score + '" ' +
              'onclick="selectEmotion(' + l.score + ')" ' +
              'style="--em-color:' + l.color + '">' +
              '<span class="mood-senior-emoji">' + l.emoji + '</span>' +
              '<span class="mood-senior-label">' + l.label + '</span>' +
            '</button>';
          }).join('') +
        '</div>' +
        '<textarea id="emotion-note" rows="2" maxlength="200" placeholder="想多說一點？（選填，最多 200 字）"></textarea>' +
        '<button class="emotions-submit" id="emotion-submit" onclick="submitEmotion()" disabled>' +
          '<i data-lucide="send" style="width:14px;height:14px"></i> 送出今日打卡' +
        '</button>' +
        '<div id="emotion-status" class="emotions-status"></div>' +
      '</div>' +

      '<div class="emotions-card mood-cal-card">' +
        '<div class="mood-card-head">' +
          '<h3>電量日曆</h3>' +
          '<div class="mood-cal-nav">' +
            '<button class="mood-cal-btn" onclick="moodCalShift(-1)" aria-label="上個月">‹</button>' +
            '<span id="mood-cal-label">—</span>' +
            '<button class="mood-cal-btn" onclick="moodCalShift(1)" aria-label="下個月">›</button>' +
          '</div>' +
        '</div>' +
        '<div id="mood-cal" class="mood-cal"></div>' +
        '<div class="mood-cal-legend">' +
          EMOTION_LEVELS.slice().reverse().map(function(l) {
            return '<span class="mood-legend-dot" style="background:' + l.color + '"></span><span class="mood-legend-txt">' + l.pct + '% ' + l.label + '</span>';
          }).join('') +
        '</div>' +
        '<p id="mood-cal-tip" class="mood-cal-tip">點選格子可看當日紀錄</p>' +
      '</div>' +

      '<div class="emotions-card mood-line-card">' +
        '<div class="mood-card-head">' +
          '<h3>電量走勢</h3>' +
          '<div class="mood-line-tabs">' +
            '<button class="mood-tab" data-days="7"  onclick="moodLineRange(7)">7 天</button>' +
            '<button class="mood-tab is-active" data-days="30" onclick="moodLineRange(30)">30 天</button>' +
            '<button class="mood-tab" data-days="90" onclick="moodLineRange(90)">90 天</button>' +
          '</div>' +
        '</div>' +
        '<div id="mood-line" class="mood-line"></div>' +
        '<p id="mood-line-summary" class="mood-line-summary"></p>' +
      '</div>' +

      '<div class="emotions-card mood-table-card">' +
        '<div class="mood-card-head">' +
          '<h3>電量總表</h3>' +
          '<button class="mood-table-toggle" id="mood-table-toggle" onclick="moodTableToggle()">展開全部</button>' +
        '</div>' +
        '<div id="mood-table" class="mood-table-wrap"></div>' +
      '</div>' +
    '</section>'
  );
}

var _emotionSelected = null;
var _battDragging = false;

function selectEmotion(score) {
  var s = Math.max(1, Math.min(5, Math.round(score)));
  if (_emotionSelected === s) return;
  _emotionSelected = s;
  var lvl = EMOTION_LEVELS.find(function(l) { return l.score === s; });
  if (!lvl) return;

  var picker = document.getElementById('batt-picker');
  if (picker) {
    picker.classList.add('is-set');
    picker.style.setProperty('--batt-color', lvl.color);
  }
  document.querySelectorAll('#batt-body .batt-cell').forEach(function(c) {
    var cs = Number(c.getAttribute('data-score'));
    c.classList.toggle('is-filled', cs <= s);
  });
  var body = document.getElementById('batt-body');
  if (body) body.setAttribute('aria-valuenow', String(s));

  var emoji = document.getElementById('batt-emoji');
  var pct = document.getElementById('batt-pct');
  var label = document.getElementById('batt-label');
  if (emoji) emoji.textContent = lvl.emoji;
  if (pct) pct.textContent = lvl.pct + '%';
  if (label) label.textContent = lvl.label;

  document.querySelectorAll('#mood-senior-picker .mood-senior-btn').forEach(function(b) {
    b.classList.toggle('selected', Number(b.getAttribute('data-score')) === s);
  });

  var btn = document.getElementById('emotion-submit');
  if (btn) btn.disabled = false;

  if (typeof navigator !== 'undefined' && navigator.vibrate) {
    try { navigator.vibrate(8); } catch (_) {}
  }
}

function _resetBattery() {
  _emotionSelected = null;
  var picker = document.getElementById('batt-picker');
  if (picker) {
    picker.classList.remove('is-set');
    picker.style.removeProperty('--batt-color');
  }
  document.querySelectorAll('#batt-body .batt-cell').forEach(function(c) {
    c.classList.remove('is-filled');
  });
  var body = document.getElementById('batt-body');
  if (body) body.setAttribute('aria-valuenow', '0');
  var emoji = document.getElementById('batt-emoji');
  var pct = document.getElementById('batt-pct');
  var label = document.getElementById('batt-label');
  if (emoji) emoji.textContent = '⚡';
  if (pct) pct.textContent = '— %';
  if (label) label.textContent = '點電池選電量';
  document.querySelectorAll('#mood-senior-picker .mood-senior-btn').forEach(function(b) {
    b.classList.remove('selected');
  });
}

function _battScoreAt(clientX) {
  var body = document.getElementById('batt-body');
  if (!body) return null;
  var cells = body.querySelectorAll('.batt-cell');
  if (!cells.length) return null;
  var first = cells[0].getBoundingClientRect();
  var last = cells[cells.length - 1].getBoundingClientRect();
  if (clientX <= first.left) return Number(cells[0].getAttribute('data-score'));
  if (clientX >= last.right) return Number(cells[cells.length - 1].getAttribute('data-score'));
  for (var i = 0; i < cells.length; i++) {
    var r = cells[i].getBoundingClientRect();
    if (clientX >= r.left && clientX <= r.right) {
      return Number(cells[i].getAttribute('data-score'));
    }
  }
  return null;
}

function _initBatteryPicker() {
  var body = document.getElementById('batt-body');
  if (!body || body.dataset.bound === '1') return;
  body.dataset.bound = '1';

  function onDown(e) {
    _battDragging = true;
    if (e.pointerId != null && body.setPointerCapture) {
      try { body.setPointerCapture(e.pointerId); } catch (_) {}
    }
    var s = _battScoreAt(e.clientX);
    if (s != null) selectEmotion(s);
    e.preventDefault();
  }
  function onMove(e) {
    if (!_battDragging) return;
    var s = _battScoreAt(e.clientX);
    if (s != null) selectEmotion(s);
  }
  function onUp() { _battDragging = false; }

  body.addEventListener('pointerdown', onDown);
  body.addEventListener('pointermove', onMove);
  body.addEventListener('pointerup', onUp);
  body.addEventListener('pointercancel', onUp);
  body.addEventListener('pointerleave', onUp);

  body.addEventListener('keydown', function(e) {
    var cur = _emotionSelected || 0;
    if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
      selectEmotion(Math.min(5, cur + 1)); e.preventDefault();
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
      selectEmotion(Math.max(1, cur - 1)); e.preventDefault();
    } else if (e.key >= '1' && e.key <= '5') {
      selectEmotion(Number(e.key)); e.preventDefault();
    }
  });
}

async function submitEmotion() {
  if (_emotionSelected == null) { showToast('請先選一個表情', 'warning'); return; }
  var pid = getStablePatientId();
  if (!pid) { showToast('請先登入', 'warning'); return; }
  var note = (document.getElementById('emotion-note').value || '').trim();
  var btn = document.getElementById('emotion-submit');
  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader"></i> 送出中…';
  if (typeof lucide !== 'undefined') lucide.createIcons();
  try {
    var res = await fetch(API + '/emotions/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-User-Id': pid },
      body: JSON.stringify({ patient_id: pid, score: _emotionSelected, note: note }),
    });
    if (!res.ok) {
      var err = await res.json().catch(function() { return {}; });
      throw new Error(err.detail || '送出失敗');
    }
    document.getElementById('emotion-note').value = '';
    document.getElementById('emotion-status').innerHTML =
      '✓ 已記錄今天的心情，' + new Date().toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' });
    document.getElementById('emotion-status').className = 'emotions-status emotions-status-ok';
    _resetBattery();
    showToast('情緒打卡完成', 'success');
    refreshMoodViews();
  } catch (e) {
    document.getElementById('emotion-status').textContent = '送出失敗：' + (e.message || '');
    document.getElementById('emotion-status').className = 'emotions-status emotions-status-error';
  } finally {
    btn.innerHTML = '<i data-lucide="send" style="width:14px;height:14px"></i> 送出今日打卡';
    if (typeof lucide !== 'undefined') lucide.createIcons();
  }
}

// ─── 心情頁狀態 ────────────────────────────────────────
var _moodCache = { byDate: {}, daily: [], loadedDays: 0 };
var _moodCalCursor = null;   // Date 物件，當前顯示的「月」（1 號）
var _moodLineDays = 30;
var _moodTableExpanded = false;

async function _moodFetch(days) {
  var pid = getStablePatientId();
  if (!pid) return null;
  try {
    var res = await fetch(API + '/emotions/daily?patient_id=' + encodeURIComponent(pid) + '&days=' + days);
    if (!res.ok) return null;
    var data = await res.json();
    var daily = data.daily || [];
    _moodCache.daily = daily;
    _moodCache.loadedDays = days;
    _moodCache.byDate = {};
    daily.forEach(function(d) { _moodCache.byDate[d.date] = d; });
    return data;
  } catch (e) {
    return null;
  }
}

// ─── 月曆熱區 ──────────────────────────────────────────
function _ymKey(d) { return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0'); }
function _dateKey(d) { return _ymKey(d) + '-' + String(d.getDate()).padStart(2, '0'); }

function moodCalShift(delta) {
  if (!_moodCalCursor) _moodCalCursor = new Date();
  _moodCalCursor = new Date(_moodCalCursor.getFullYear(), _moodCalCursor.getMonth() + delta, 1);
  renderMoodCalendar();
}

function renderMoodCalendar() {
  var box = document.getElementById('mood-cal');
  var label = document.getElementById('mood-cal-label');
  if (!box) return;
  if (!_moodCalCursor) _moodCalCursor = new Date();
  var year = _moodCalCursor.getFullYear();
  var month = _moodCalCursor.getMonth();
  if (label) label.textContent = year + ' / ' + String(month + 1).padStart(2, '0');

  var firstDay = new Date(year, month, 1);
  var startWeekday = firstDay.getDay(); // 0 = Sun
  var daysInMonth = new Date(year, month + 1, 0).getDate();
  var todayKey = _dateKey(new Date());

  var weekHead = ['日', '一', '二', '三', '四', '五', '六']
    .map(function(w) { return '<div class="mood-cal-wk">' + w + '</div>'; }).join('');

  var cells = [];
  for (var i = 0; i < startWeekday; i++) cells.push('<div class="mood-cal-cell is-empty"></div>');
  for (var d = 1; d <= daysInMonth; d++) {
    var dateObj = new Date(year, month, d);
    var key = _dateKey(dateObj);
    var rec = _moodCache.byDate[key];
    var bg = rec ? _moodColor(rec.average_score) : 'transparent';
    var emoji = rec ? rec.emoji : '';
    var isToday = key === todayKey;
    var classes = 'mood-cal-cell' + (rec ? ' has-data' : '') + (isToday ? ' is-today' : '');
    var pctTip = rec ? _moodPercent(rec.average_score) : null;
    cells.push(
      '<button class="' + classes + '" style="background:' + bg + '" ' +
        'onclick="moodCalSelect(\'' + key + '\')" ' +
        'aria-label="' + key + (rec ? ' 電量 ' + pctTip + '%' : '') + '">' +
        '<span class="mood-cal-day">' + d + '</span>' +
        (emoji ? '<span class="mood-cal-emoji">' + emoji + '</span>' : '') +
      '</button>'
    );
  }

  box.innerHTML = '<div class="mood-cal-grid">' + weekHead + cells.join('') + '</div>';
}

function moodCalSelect(dateKey) {
  var rec = _moodCache.byDate[dateKey];
  var tip = document.getElementById('mood-cal-tip');
  if (!tip) return;
  if (!rec) {
    tip.textContent = dateKey + ' · 沒有紀錄';
    return;
  }
  var note = rec.note ? '「' + rec.note + '」' : '（無備註）';
  var avgPct = _moodPercent(rec.average_score);
  var loPct = _moodPercent(rec.min_score);
  var hiPct = _moodPercent(rec.max_score);
  tip.innerHTML =
    '<strong>' + dateKey + '</strong> ' + (rec.emoji || '') +
    ' 平均電量 <strong>' + avgPct + '%</strong>' +
    ' · 範圍 ' + loPct + '–' + hiPct + '%' +
    ' · ' + rec.count + ' 筆 · ' + escapeHtml(note);
}

// ─── 折線圖（SVG 自刻）───────────────────────────────
function moodLineRange(days) {
  _moodLineDays = days;
  document.querySelectorAll('.mood-tab').forEach(function(t) {
    t.classList.toggle('is-active', Number(t.getAttribute('data-days')) === days);
  });
  refreshMoodViews();
}

function renderMoodLine() {
  var box = document.getElementById('mood-line');
  var sumEl = document.getElementById('mood-line-summary');
  if (!box) return;
  var daily = _moodCache.daily || [];
  // 只取 _moodLineDays 區間內
  var cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - _moodLineDays + 1);
  var cutoffKey = _dateKey(cutoff);
  var pts = daily.filter(function(d) { return d.date >= cutoffKey; });

  if (!pts.length) {
    box.innerHTML = '<p class="emotions-empty">這段期間沒有任何打卡紀錄。</p>';
    if (sumEl) sumEl.textContent = '';
    return;
  }

  var W = 640, H = 200, PAD_L = 32, PAD_R = 12, PAD_T = 14, PAD_B = 28;
  var innerW = W - PAD_L - PAD_R;
  var innerH = H - PAD_T - PAD_B;

  // 以日期序列建立 x 軸（含缺漏日，畫成斷線）
  var allDates = [];
  for (var i = 0; i < _moodLineDays; i++) {
    var d = new Date();
    d.setDate(d.getDate() - (_moodLineDays - 1 - i));
    allDates.push(_dateKey(d));
  }
  var xStep = innerW / Math.max(1, allDates.length - 1);
  var yFor = function(score) { return PAD_T + innerH - ((score - 1) / 4) * innerH; };

  // 折線（缺漏日用 M 重新起筆）
  var path = '';
  var pointCircles = '';
  var rangeRects = '';
  allDates.forEach(function(k, idx) {
    var rec = _moodCache.byDate[k];
    var x = PAD_L + idx * xStep;
    if (!rec) {
      path += ''; // 跳過
      return;
    }
    var y = yFor(rec.average_score);
    path += (path && _moodCache.byDate[allDates[idx - 1]] ? ' L ' : ' M ') + x.toFixed(1) + ' ' + y.toFixed(1);
    // min-max 範圍帶
    if (rec.min_score !== rec.max_score) {
      var yTop = yFor(rec.max_score);
      var yBot = yFor(rec.min_score);
      rangeRects += '<rect x="' + (x - 3) + '" y="' + yTop + '" width="6" height="' + (yBot - yTop) + '" fill="#86C7B8" opacity="0.18" rx="2"/>';
    }
    pointCircles += '<circle cx="' + x + '" cy="' + y + '" r="3.5" fill="' + _moodColor(rec.average_score) + '" stroke="#fff" stroke-width="1.2"><title>' + k + ' 電量 ' + _moodPercent(rec.average_score) + '%</title></circle>';
  });

  // 橫向格線（0% / 25% / 50% / 75% / 100%）
  var grid = '';
  for (var s = 1; s <= 5; s++) {
    var y = yFor(s);
    var pctLabel = (s - 1) * 25;
    grid += '<line x1="' + PAD_L + '" y1="' + y + '" x2="' + (W - PAD_R) + '" y2="' + y + '" stroke="rgba(160,160,180,0.18)" stroke-dasharray="2 4"/>';
    grid += '<text x="' + (PAD_L - 6) + '" y="' + (y + 3) + '" text-anchor="end" font-size="10" fill="rgba(160,160,180,0.7)" font-family="JetBrains Mono, monospace">' + pctLabel + '%</text>';
  }

  // X 軸日期 label（每隔幾天標一次）
  var labelEvery = _moodLineDays <= 7 ? 1 : (_moodLineDays <= 30 ? 5 : 14);
  var xLabels = '';
  allDates.forEach(function(k, idx) {
    if (idx % labelEvery !== 0 && idx !== allDates.length - 1) return;
    var x = PAD_L + idx * xStep;
    xLabels += '<text x="' + x + '" y="' + (H - 8) + '" text-anchor="middle" font-size="10" fill="rgba(160,160,180,0.8)" font-family="JetBrains Mono, monospace">' + k.slice(5) + '</text>';
  });

  box.innerHTML =
    '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" class="mood-line-svg">' +
      grid +
      rangeRects +
      '<path d="' + path + '" fill="none" stroke="#86C7B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>' +
      pointCircles +
      xLabels +
    '</svg>';

  var scores = pts.map(function(p) { return p.average_score; });
  var avg = scores.reduce(function(a, b) { return a + b; }, 0) / scores.length;
  var lo = Math.min.apply(null, scores);
  var hi = Math.max.apply(null, scores);
  if (sumEl) {
    var avgPct = Math.round((avg - 1) * 25);
    var loPct = (lo - 1) * 25;
    var hiPct = (hi - 1) * 25;
    sumEl.textContent =
      '平均電量 ' + avgPct + '%　·　最低 ' + loPct + '%　·　最高 ' + hiPct + '%　·　' + pts.length + ' 天有紀錄' +
      (avg <= 2.5 ? '　·　偵測到電量偏低，建議跟醫師談談' : '');
  }
}

// ─── 心情總表 ──────────────────────────────────────────
function moodTableToggle() {
  _moodTableExpanded = !_moodTableExpanded;
  var btn = document.getElementById('mood-table-toggle');
  if (btn) btn.textContent = _moodTableExpanded ? '只看近 7 天' : '展開全部';
  renderMoodTable();
}

function renderMoodTable() {
  var box = document.getElementById('mood-table');
  if (!box) return;
  var daily = (_moodCache.daily || []).slice().reverse(); // 新到舊
  if (!daily.length) {
    box.innerHTML = '<p class="emotions-empty">還沒有任何打卡紀錄。</p>';
    return;
  }
  var rows = _moodTableExpanded ? daily : daily.slice(0, 7);
  var trs = rows.map(function(d) {
    var note = d.note ? escapeHtml(d.note) : '<span class="mood-table-muted">—</span>';
    var avgPct = _moodPercent(d.average_score);
    var loPct = _moodPercent(d.min_score);
    var hiPct = _moodPercent(d.max_score);
    return '<tr>' +
      '<td class="mood-td-date">' + d.date.slice(5) + '</td>' +
      '<td class="mood-td-emoji" style="color:' + _moodColor(d.average_score) + '">' + (d.emoji || '') + '</td>' +
      '<td><strong>' + avgPct + '%</strong></td>' +
      '<td>' + loPct + '–' + hiPct + '%</td>' +
      '<td>' + d.count + '</td>' +
      '<td class="mood-td-note">' + note + '</td>' +
    '</tr>';
  }).join('');
  box.innerHTML =
    '<table class="mood-table">' +
      '<thead><tr>' +
        '<th>日期</th><th></th><th>平均電量</th><th>區間</th><th>筆數</th><th>備註</th>' +
      '</tr></thead>' +
      '<tbody>' + trs + '</tbody>' +
    '</table>';
}

async function refreshMoodViews() {
  var needDays = Math.max(_moodLineDays, 90);
  if (_moodCache.loadedDays < needDays) {
    await _moodFetch(needDays);
  }
  renderMoodRing();
  renderMoodCalendar();
  renderMoodLine();
  renderMoodTable();
}

// 環形電量 hero：根據 _moodCache.daily 取最後一筆，更新 SVG arc + 文字。
function renderMoodRing() {
  var arc = document.getElementById('mood-ring-arc');
  var pctEl = document.getElementById('mood-ring-pct');
  var labelEl = document.getElementById('mood-ring-label');
  var hintEl = document.getElementById('mood-ring-hint');
  if (!arc || !pctEl) return;
  var daily = _moodCache.daily || [];
  if (!daily.length) {
    arc.setAttribute('stroke-dashoffset', '502');
    pctEl.textContent = '—';
    if (labelEl) labelEl.textContent = '尚無紀錄';
    if (hintEl) hintEl.textContent = '往下打卡，環形會即時填滿。';
    return;
  }
  // 取最近一筆有打卡的
  var latest = daily[daily.length - 1];
  for (var i = daily.length - 1; i >= 0; i--) {
    if ((daily[i].count || 0) > 0) { latest = daily[i]; break; }
  }
  var pct = (typeof _moodPercent === 'function') ? _moodPercent(latest.average_score) : Math.round(latest.average_score * 20);
  if (!pct && pct !== 0) pct = 0;
  var circumference = 502; // 2π × 80 ≈ 502
  var offset = circumference - (circumference * pct / 100);
  arc.setAttribute('stroke-dashoffset', String(offset));
  pctEl.textContent = pct;
  // 從 EMOTION_LEVELS 找最相近的等級拿 label
  var levelLabel = '電力中等';
  if (typeof EMOTION_LEVELS !== 'undefined') {
    var match = EMOTION_LEVELS.slice().sort(function(a, b) {
      return Math.abs(a.pct - pct) - Math.abs(b.pct - pct);
    })[0];
    if (match) levelLabel = match.label;
  }
  if (labelEl) labelEl.textContent = levelLabel;
  if (hintEl) {
    var when = latest.date ? latest.date.replace(/-/g, '/').slice(5) : '';
    hintEl.textContent = '最近一筆 · ' + when + (latest.count > 1 ? '（當日 ' + latest.count + ' 次平均）' : '');
  }
}

function loadEmotionsPage() {
  _emotionSelected = null;
  _moodCalCursor = new Date();
  _moodCalCursor = new Date(_moodCalCursor.getFullYear(), _moodCalCursor.getMonth(), 1);
  if (typeof lucide !== 'undefined') setTimeout(function() { lucide.createIcons(); }, 30);
  setTimeout(_initBatteryPicker, 0);
  refreshMoodViews();
}


// ─── 飲食紀錄 ───────────────────────────────────────────
// 三段式：基本衛教（蛋白質/水/纖維）+ 疾病禁忌 + 今日推薦食物 + 打卡

var DIET_MEAL_LABEL = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '點心' };
var _dietGuide = null;
var _dietSelectedMeal = 'breakfast';

// 基本衛教預設值（沒登入或 API 失敗時也至少顯示這些）
var DIET_BASELINE_TARGETS = { protein_g: 60, water_ml: 2000, fiber_g: 25 };
var DIET_BASELINE_TIPS = [
  '三餐定時定量，避免暴飲暴食',
  '每餐都有蛋白質、蔬菜與全穀類',
  '減少油炸、加工食品與含糖飲料',
  '餐前 30 分鐘喝一杯水有助消化',
];

// 基本營養素衛教（固定內容，與個人化資料無關）
var DIET_BASIC_NUTRIENTS = [
  {
    name: '蛋白質',
    icon: 'beef',
    daily: '每公斤體重 1.0–1.2 g（運動者 1.4–1.7 g）',
    role: '修復組織、製造酵素與抗體',
    sources: '魚、雞胸、蛋、豆腐、無糖豆漿、希臘優格',
    tip: '每餐都要有一份手掌大的蛋白質，分散吃比一次大量好吸收',
  },
  {
    name: '碳水化合物',
    icon: 'wheat',
    daily: '佔每日總熱量 50–60%',
    role: '主要能量來源，供給大腦與肌肉',
    sources: '糙米、燕麥、地瓜、全麥麵包、水果',
    tip: '選低 GI 全穀類，少吃精緻糖與含糖飲料',
  },
  {
    name: '脂肪（好油）',
    icon: 'droplet',
    daily: '佔每日總熱量 20–30%',
    role: '吸收脂溶性維生素、合成荷爾蒙',
    sources: '橄欖油、酪梨、堅果、鯖魚、鮭魚',
    tip: '多吃 Omega-3，避開油炸與反式脂肪（人造奶油、酥油）',
  },
  {
    name: '膳食纖維',
    icon: 'leaf',
    daily: '每天 25–35 g',
    role: '促進腸道蠕動、穩定血糖、餵養好菌',
    sources: '蔬菜、水果、燕麥、糙米、豆類',
    tip: '一天至少 3 份蔬菜（一份約一個拳頭大）+ 2 份水果',
  },
  {
    name: '水分',
    icon: 'glass-water',
    daily: '每天 2000–2500 ml（依體重 30 ml/kg 估算）',
    role: '代謝廢物、調節體溫、運送養分',
    sources: '白開水、無糖茶、清湯',
    tip: '看尿色：淡黃就夠，深黃要再多喝；別等口渴才喝',
  },
  {
    name: '維生素 & 礦物質',
    icon: 'sparkles',
    daily: '從多色蔬果中自然攝取',
    role: '維生素 D / B 群、鈣、鐵、鋅參與骨骼、造血、免疫',
    sources: '深色蔬菜、彩色水果、海帶、堅果、紅肉、蛋黃',
    tip: '彩虹飲食法：紅黃綠紫白每天都吃一點，比單吃保健品有效',
  },
];

function renderDietTodayHero() {
  // 飲食頁主要是教育 + 推薦，今日 hero 顯示「該吃什麼／避開什麼」入口提示。
  return ''
    + '<div class="page-app-hero page-app-hero-green">'
    +   '<div class="page-app-hero-head">'
    +     '<span class="page-app-hero-eyebrow">TODAY · 今日飲食指南</span>'
    +     '<span class="page-app-hero-warn"><i data-lucide="info" style="width:11px;height:11px"></i> 飲食建議以醫師/營養師為主</span>'
    +   '</div>'
    +   '<div class="page-app-hero-title">看你的病史，今天該吃／避開什麼</div>'
    +   '<div class="page-app-hero-meta">下方有「今日營養目標」與「你要特別注意」兩塊，會根據你登錄的疾病自動調整</div>'
    + '</div>';
}

function renderBasicNutrients() {
  var box = document.getElementById('diet-basic-nutrients');
  if (!box) return;
  box.innerHTML = DIET_BASIC_NUTRIENTS.map(function(n) {
    return ''
      + '<div class="diet-nutrient">'
      +   '<div class="diet-nutrient-head">'
      +     '<i data-lucide="' + n.icon + '" style="width:16px;height:16px"></i>'
      +     '<strong>' + chatEscape(n.name) + '</strong>'
      +     '<span class="diet-nutrient-daily">' + chatEscape(n.daily) + '</span>'
      +   '</div>'
      +   '<div class="diet-nutrient-role">' + chatEscape(n.role) + '</div>'
      +   '<div class="diet-nutrient-sources"><span class="diet-nutrient-label">食物來源</span>' + chatEscape(n.sources) + '</div>'
      +   '<div class="diet-nutrient-tip">' + chatEscape(n.tip) + '</div>'
      + '</div>';
  }).join('');
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function diet() {
  return ''
    + '<section class="diet-wrap">'
    +   '<header class="diet-head">'
    +     '<h2><i data-lucide="utensils-crossed" style="width:22px;height:22px"></i> 飲食紀錄</h2>'
    +     '<p>看今天該吃什麼、避開什麼，順便打卡記下三餐。</p>'
    +   '</header>'

    +   renderDietTodayHero()

    +   '<div class="diet-card diet-basic-nutrients-card">'
    +     '<h3><i data-lucide="apple" style="width:16px;height:16px"></i> 基本營養素衛教</h3>'
    +     '<p class="diet-card-sub">每天身體都需要的六大基本營養素，照著吃就不會差太多。</p>'
    +     '<div id="diet-basic-nutrients" class="diet-nutrient-grid"></div>'
    +   '</div>'

    +   '<div class="diet-card diet-caffeine-card" id="diet-caffeine-card">'
    +     '<h3><i data-lucide="coffee" style="width:16px;height:16px"></i> 咖啡因衛教</h3>'
    +     '<div id="diet-caffeine-body"><p class="diet-empty">載入中…</p></div>'
    +   '</div>'

    +   '<div class="diet-card" id="diet-targets">'
    +     '<h3><i data-lucide="target" style="width:16px;height:16px"></i> 今日營養目標</h3>'
    +     '<div class="diet-target-row" id="diet-target-row">'
    +       '<div class="diet-target-skel">載入中…</div>'
    +     '</div>'
    +     '<ul class="diet-tips" id="diet-tips"></ul>'
    +   '</div>'

    +   '<div class="diet-card" id="diet-warnings-card">'
    +     '<h3><i data-lucide="alert-triangle" style="width:16px;height:16px"></i> 你要特別注意</h3>'
    +     '<div id="diet-warnings"><p class="diet-empty">載入中…</p></div>'
    +   '</div>'

    +   '<div class="diet-card diet-pick-card">'
    +     '<h3><i data-lucide="dices" style="width:16px;height:16px"></i> 吃什麼神器</h3>'
    +     '<p class="diet-pick-sub">選擇障礙嗎？讓 MD.Piece 依你的病史挑一道。</p>'
    +     '<div class="diet-pick-meal-tabs" id="diet-pick-meal-tabs">'
    +       [['any','隨便'],['breakfast','早'],['lunch','午'],['dinner','晚'],['snack','點心']].map(function(p) {
              return '<button class="diet-pick-tab' + (p[0]==='any'?' active':'') + '" '
                + 'data-pick-meal="' + p[0] + '" onclick="dietPickSetMeal(\'' + p[0] + '\')">'
                + p[1] + '</button>';
            }).join('')
    +     '</div>'
    +     '<div class="diet-pick-price-tabs" id="diet-pick-price-tabs">'
    +       [['any','不限預算'],['$','$（≤100）'],['$$','$$（100–200）'],['$$$','$$$（200+）']].map(function(p) {
              return '<button class="diet-pick-tab diet-pick-price' + (p[0]==='any'?' active':'') + '" '
                + 'data-pick-price="' + p[0] + '" onclick="dietPickSetPrice(\'' + p[0] + '\')">'
                + p[1] + '</button>';
            }).join('')
    +     '</div>'
    +     '<div class="diet-pick-cal-tabs" id="diet-pick-cal-tabs">'
    +       [['any','不限熱量'],['low','輕量（≤350）'],['mid','一般（350–650）'],['high','高熱量（650+）']].map(function(p) {
              return '<button class="diet-pick-tab diet-pick-cal' + (p[0]==='any'?' active':'') + '" '
                + 'data-pick-cal="' + p[0] + '" onclick="dietPickSetCal(\'' + p[0] + '\')">'
                + p[1] + '</button>';
            }).join('')
    +     '</div>'
    +     '<div class="diet-pick-flags">'
    +       '<label class="diet-pick-toggle"><input type="checkbox" id="diet-pick-nearby" onchange="dietPickToggleNearby(this.checked)" /> <span>只推附近能取得（超商/便當店/早餐店）</span></label>'
    +       '<label class="diet-pick-toggle"><input type="checkbox" id="diet-pick-avoid-recent" checked onchange="dietPickToggleAvoidRecent(this.checked)" /> <span>避開本週吃過的</span></label>'
    +     '</div>'
    +     '<div class="diet-pick-dislike">'
    +       '<div class="diet-pick-dislike-row" id="diet-pick-dislike-chips"></div>'
    +       '<div class="diet-pick-dislike-input">'
    +         '<input type="text" id="diet-pick-dislike-add" maxlength="20" placeholder="不吃什麼？例：香菜、辣椒" />'
    +         '<button onclick="dietPickAddDislike()" type="button"><i data-lucide="plus" style="width:14px;height:14px"></i></button>'
    +       '</div>'
    +     '</div>'
    +     '<div id="diet-pick-result" class="diet-pick-result diet-pick-empty">'
    +       '<i data-lucide="utensils" style="width:28px;height:28px"></i>'
    +       '<div>按下面的按鈕，幫你抽一道菜</div>'
    +     '</div>'
    +     '<div class="diet-pick-actions">'
    +       '<button class="diet-pick-btn primary" onclick="dietPickMeal(false)">'
    +         '<i data-lucide="dices" style="width:16px;height:16px"></i> 給我一道'
    +       '</button>'
    +       '<button class="diet-pick-btn primary diet-pick-btn-drink" onclick="dietPickDrink(false)">'
    +         '<i data-lucide="coffee" style="width:16px;height:16px"></i> 配杯飲料'
    +       '</button>'
    +       '<button class="diet-pick-btn secondary" id="diet-pick-reroll" onclick="dietPickMeal(true)" disabled>'
    +         '<i data-lucide="refresh-cw" style="width:16px;height:16px"></i> 換一道'
    +       '</button>'
    +       '<button class="diet-pick-btn quiet" id="diet-pick-log" onclick="dietPickLogIt()" disabled>'
    +         '<i data-lucide="check" style="width:16px;height:16px"></i> 就吃這個'
    +       '</button>'
    +     '</div>'
    +     '<div id="diet-drink-result" class="diet-drink-result"></div>'
    +   '</div>'

    +   '<div class="diet-card" id="diet-suggest-card">'
    +     '<h3><i data-lucide="salad" style="width:16px;height:16px"></i> 今天吃什麼</h3>'
    +     '<div class="diet-meal-tabs" id="diet-meal-tabs">'
    +       ['breakfast','lunch','dinner'].map(function(m) {
              return '<button class="diet-meal-tab' + (m===_dietSelectedMeal?' active':'') + '" '
                + 'data-meal="' + m + '" onclick="dietSwitchMeal(\'' + m + '\')">'
                + DIET_MEAL_LABEL[m] + '</button>';
            }).join('')
    +     '</div>'
    +     '<div id="diet-suggest-list" class="diet-suggest-list"><p class="diet-empty">載入中…</p></div>'
    +   '</div>'

    +   '<div class="diet-card diet-log-card">'
    +     '<h3><i data-lucide="pencil" style="width:16px;height:16px"></i> 打卡今天吃了什麼</h3>'
    +     '<div class="diet-log-form">'
    +       '<div class="diet-log-meal-pick" id="diet-log-meal-pick">'
    +         ['breakfast','lunch','dinner','snack'].map(function(m) {
              return '<button class="diet-log-meal' + (m==='breakfast'?' active':'') + '" '
                + 'data-log-meal="' + m + '" onclick="dietPickLogMeal(\'' + m + '\')">'
                + DIET_MEAL_LABEL[m] + '</button>';
            }).join('')
    +       '</div>'
    +       '<textarea id="diet-log-foods" rows="2" maxlength="200" placeholder="例：白飯、滷雞腿、燙青菜（最多 200 字）"></textarea>'
    +       '<input type="text" id="diet-log-note" maxlength="80" placeholder="備註（選填，例：吃完有點脹）" />'
    +       '<button class="diet-log-submit" onclick="dietSubmitLog()">'
    +         '<i data-lucide="check" style="width:14px;height:14px"></i> 送出'
    +       '</button>'
    +       '<div id="diet-log-status" class="diet-log-status"></div>'
    +     '</div>'
    +   '</div>'

    +   '<div class="diet-card">'
    +     '<h3><i data-lucide="list" style="width:16px;height:16px"></i> 今日已記錄</h3>'
    +     '<div id="diet-today-list"><p class="diet-empty">載入中…</p></div>'
    +   '</div>'

    +   '<div class="diet-card diet-weekly-card">'
    +     '<h3><i data-lucide="trending-up" style="width:16px;height:16px"></i> 本週狀況</h3>'
    +     '<p class="diet-card-sub">過去 7 天的飲食規律與分布。完整度＝早午晚各 30%＋點心 10%。</p>'
    +     '<div class="diet-weekly-week-tabs" id="diet-weekly-week-tabs">'
    +       [['0','本週'],['1','上週'],['2','前週'],['3','再前']].map(function(p) {
              return '<button class="diet-weekly-week-tab' + (p[0]==='0'?' active':'') + '" '
                + 'data-week-idx="' + p[0] + '" onclick="dietWeeklySwitchWeek(' + p[0] + ')">'
                + p[1] + '</button>';
            }).join('')
    +     '</div>'
    +     '<div class="diet-weekly-stats" id="diet-weekly-stats">'
    +       '<div class="diet-empty">載入中…</div>'
    +     '</div>'
    +     '<div class="diet-weekly-chart-tabs" id="diet-weekly-chart-tabs">'
    +       [['line','完整度+攝取'],['stack','餐別堆疊'],['multi','早午晚點']].map(function(p) {
              return '<button class="diet-weekly-chart-tab' + (p[0]==='line'?' active':'') + '" '
                + 'data-chart-type="' + p[0] + '" onclick="dietWeeklySwitchChart(\'' + p[0] + '\')">'
                + p[1] + '</button>';
            }).join('')
    +     '</div>'
    +     '<div class="diet-weekly-chart-legend" id="diet-weekly-chart-legend"></div>'
    +     '<div class="diet-weekly-chart-wrap">'
    +       '<canvas id="diet-weekly-canvas" style="width:100%;height:160px"></canvas>'
    +     '</div>'
    +     '<p class="diet-weekly-chart-hint" id="diet-weekly-chart-hint"></p>'
    +     '<div id="diet-weekly-top-foods" class="diet-weekly-top-foods"></div>'
    +     '<p class="diet-weekly-meta" id="diet-weekly-meta"></p>'
    +   '</div>'
    + '</section>';
}

// 吃什麼神器
var _dietPickMealType    = 'any';   // any/breakfast/lunch/dinner/snack
var _dietPickPrice       = 'any';   // any/$/$$/$$$
var _dietPickCal         = 'any';   // any/low/mid/high
var _dietPickNearby      = false;
var _dietPickAvoidRecent = true;
var _dietPickDislikes    = [];      // 個人黑名單，localStorage 持久化
var _dietPickHistory     = [];      // 已被丟掉的菜名
var _dietPickCurrent     = null;
var _dietPickLoading     = false;

var DIET_DISLIKE_KEY = 'mdpiece_diet_dislikes';
var DIET_PICK_HISTORY_KEY  = 'mdpiece_diet_pick_history';
var DIET_DRINK_HISTORY_KEY = 'mdpiece_diet_drink_history';
var DIET_HISTORY_TTL_MS    = 24 * 60 * 60 * 1000; // 一天，避免永遠擋同一道菜
var DIET_HISTORY_CAP       = 30;

function dietPickLoadDislikes() {
  try {
    var raw = localStorage.getItem(DIET_DISLIKE_KEY);
    _dietPickDislikes = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(_dietPickDislikes)) _dietPickDislikes = [];
  } catch (e) { _dietPickDislikes = []; }
}
function dietPickSaveDislikes() {
  try { localStorage.setItem(DIET_DISLIKE_KEY, JSON.stringify(_dietPickDislikes)); } catch (e) {}
}

function _dietLoadHistory(key) {
  try {
    var raw = localStorage.getItem(key);
    if (!raw) return [];
    var arr = JSON.parse(raw);
    if (!Array.isArray(arr)) return [];
    var now = Date.now();
    return arr.filter(function(x) {
      return x && typeof x.name === 'string' && (now - (x.ts || 0)) < DIET_HISTORY_TTL_MS;
    }).map(function(x) { return x.name; });
  } catch (e) { return []; }
}
function _dietSaveHistory(key, names) {
  try {
    var now = Date.now();
    var trimmed = names.slice(-DIET_HISTORY_CAP);
    localStorage.setItem(key, JSON.stringify(trimmed.map(function(n) {
      return { name: n, ts: now };
    })));
  } catch (e) {}
}
function dietPickPushHistory(name) {
  if (!name) return;
  if (_dietPickHistory.indexOf(name) === -1) _dietPickHistory.push(name);
  _dietSaveHistory(DIET_PICK_HISTORY_KEY, _dietPickHistory);
}
function dietDrinkPushHistory(name) {
  if (!name) return;
  if (_dietDrinkHistory.indexOf(name) === -1) _dietDrinkHistory.push(name);
  _dietSaveHistory(DIET_DRINK_HISTORY_KEY, _dietDrinkHistory);
}

function dietPickSetMeal(m) {
  _dietPickMealType = m;
  document.querySelectorAll('#diet-pick-meal-tabs .diet-pick-tab').forEach(function(b) {
    b.classList.toggle('active', b.getAttribute('data-pick-meal') === m);
  });
}

function dietPickSetPrice(p) {
  _dietPickPrice = p;
  document.querySelectorAll('#diet-pick-price-tabs .diet-pick-price').forEach(function(b) {
    b.classList.toggle('active', b.getAttribute('data-pick-price') === p);
  });
}

function dietPickSetCal(c) {
  _dietPickCal = c;
  document.querySelectorAll('#diet-pick-cal-tabs .diet-pick-cal').forEach(function(b) {
    b.classList.toggle('active', b.getAttribute('data-pick-cal') === c);
  });
}

function dietPickToggleNearby(on) {
  _dietPickNearby = !!on;
}

function dietPickToggleAvoidRecent(on) {
  _dietPickAvoidRecent = !!on;
}

function dietPickAddDislike() {
  var input = document.getElementById('diet-pick-dislike-add');
  if (!input) return;
  var v = (input.value || '').trim();
  if (!v) return;
  if (_dietPickDislikes.indexOf(v) === -1) {
    _dietPickDislikes.push(v);
    dietPickSaveDislikes();
    dietPickRenderDislikes();
  }
  input.value = '';
  input.focus();
}

function dietPickRemoveDislike(idx) {
  _dietPickDislikes.splice(idx, 1);
  dietPickSaveDislikes();
  dietPickRenderDislikes();
}

function dietPickRenderDislikes() {
  var box = document.getElementById('diet-pick-dislike-chips');
  if (!box) return;
  if (!_dietPickDislikes.length) {
    box.innerHTML = '<span class="diet-pick-dislike-empty">還沒設定不吃的食材</span>';
    return;
  }
  box.innerHTML = _dietPickDislikes.map(function(d, i) {
    return '<span class="diet-pick-dislike-chip">'
      + chatEscape(d)
      + '<button onclick="dietPickRemoveDislike(' + i + ')" type="button" aria-label="移除">×</button>'
      + '</span>';
  }).join('');
}

function dietPickMeal(isReroll) {
  if (_dietPickLoading) return;
  var pid = getStablePatientId();
  if (!pid) { showToast('請先登入', 'warning'); return; }
  if (isReroll && _dietPickCurrent && _dietPickCurrent.name) {
    dietPickPushHistory(_dietPickCurrent.name);
  }
  _dietPickLoading = true;
  var box = document.getElementById('diet-pick-result');
  if (box) {
    box.className = 'diet-pick-result diet-pick-loading';
    box.innerHTML = '<i data-lucide="loader-2" style="width:24px;height:24px"></i><div>幫你想想…</div>';
    if (typeof lucide !== 'undefined') lucide.createIcons();
  }
  var qs = '?meal_type=' + encodeURIComponent(_dietPickMealType)
         + '&price_tier=' + encodeURIComponent(_dietPickPrice)
         + '&calorie_tier=' + encodeURIComponent(_dietPickCal)
         + '&nearby=' + (_dietPickNearby ? 'true' : 'false')
         + '&avoid_recent=' + (_dietPickAvoidRecent ? 'true' : 'false');
  if (_dietPickHistory.length) qs += '&exclude=' + encodeURIComponent(_dietPickHistory.join(','));
  if (_dietPickDislikes.length) qs += '&dislike=' + encodeURIComponent(_dietPickDislikes.join(','));
  fetch(API + '/diet/pick/' + encodeURIComponent(pid) + qs)
    .then(function(r) { return r.json(); })
    .then(function(g) {
      _dietPickCurrent = g || {};
      // 把這次抽到的也記下來，下一輪「給我一道」不會立刻同款
      if (g && g.name) dietPickPushHistory(g.name);
      renderDietPick(g);
    })
    .catch(function() {
      if (box) {
        box.className = 'diet-pick-result diet-pick-empty';
        box.innerHTML = '<i data-lucide="x" style="width:24px;height:24px"></i><div>抽不到，稍後再試</div>';
        if (typeof lucide !== 'undefined') lucide.createIcons();
      }
    })
    .finally(function() { _dietPickLoading = false; });
}

function renderDietPick(g) {
  var box = document.getElementById('diet-pick-result');
  if (!box) return;
  if (!g || !g.name) {
    box.className = 'diet-pick-result diet-pick-empty';
    box.innerHTML = '<div>沒抽到，再按一次</div>';
    return;
  }
  var components = (g.components || []).map(function(c) {
    return '<span class="diet-pick-chip">' + chatEscape(c) + '</span>';
  }).join('');
  var mealLabelMap = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '點心' };
  var mealBadge = (_dietPickMealType === 'any' && g.meal_type)
    ? '<span class="diet-pick-meal-badge">幫你抽了個 ' + mealLabelMap[g.meal_type] + '</span>'
    : '';
  box.className = 'diet-pick-result diet-pick-show';
  box.innerHTML = ''
    + mealBadge
    + '<div class="diet-pick-name">' + chatEscape(g.name) + '</div>'
    + (g.cuisine || g.where_to_get || g.price_tier || g.price_twd
        ? '<div class="diet-pick-meta">'
          + (g.cuisine ? '<span>' + chatEscape(g.cuisine) + '</span>' : '')
          + (g.where_to_get ? '<span class="diet-pick-where"><i data-lucide="map-pin" style="width:12px;height:12px"></i> ' + chatEscape(g.where_to_get) + '</span>' : '')
          + ((g.price_tier || g.price_twd)
              ? '<span class="diet-pick-price-tag">' + chatEscape(g.price_tier || '') + (g.price_twd ? ' · 約 NT$' + g.price_twd : '') + '</span>'
              : '')
          + ((g.calorie_kcal || g.calorie_tier)
              ? '<span class="diet-pick-cal-tag">' + (g.calorie_kcal ? g.calorie_kcal + ' kcal' : chatEscape(g.calorie_tier || '')) + '</span>'
              : '')
        + '</div>'
        : '')
    + (components ? '<div class="diet-pick-chips">' + components + '</div>' : '')
    + (g.reason ? '<div class="diet-pick-reason">' + chatEscape(g.reason) + '</div>' : '')
    + (g.fallback ? '<div class="diet-pick-fallback">（MD.Piece 暫時不在線，先給你一個常見選擇）</div>' : '');
  var rerollBtn = document.getElementById('diet-pick-reroll');
  var logBtn = document.getElementById('diet-pick-log');
  if (rerollBtn) rerollBtn.disabled = false;
  if (logBtn) logBtn.disabled = false;
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

// ── 喝什麼神器 ──
var _dietDrinkHistory = [];
var _dietDrinkCurrent = null;
var _dietDrinkLoading = false;

function dietPickDrink(isReroll) {
  if (_dietDrinkLoading) return;
  var pid = getStablePatientId();
  if (!pid) { showToast('請先登入', 'warning'); return; }
  if (isReroll && _dietDrinkCurrent && _dietDrinkCurrent.name) {
    dietDrinkPushHistory(_dietDrinkCurrent.name);
  }
  _dietDrinkLoading = true;
  var box = document.getElementById('diet-drink-result');
  if (box) {
    box.className = 'diet-drink-result diet-drink-loading';
    box.innerHTML = '<i data-lucide="loader-2" style="width:18px;height:18px"></i> 想想要配什麼…';
    if (typeof lucide !== 'undefined') lucide.createIcons();
  }
  var qs = '?price_tier=' + encodeURIComponent(_dietPickPrice)
         + '&nearby=' + (_dietPickNearby ? 'true' : 'false')
         + '&avoid_recent=' + (_dietPickAvoidRecent ? 'true' : 'false');
  if (_dietDrinkHistory.length) qs += '&exclude=' + encodeURIComponent(_dietDrinkHistory.join(','));
  if (_dietPickDislikes.length) qs += '&dislike=' + encodeURIComponent(_dietPickDislikes.join(','));
  fetch(API + '/diet/drink/' + encodeURIComponent(pid) + qs)
    .then(function(r) { return r.json(); })
    .then(function(g) {
      _dietDrinkCurrent = g || {};
      if (g && g.name) dietDrinkPushHistory(g.name);
      renderDietDrink(g);
      // 如果這杯有咖啡因，自動拉出咖啡因衛教
      if ((g.caffeine_mg || 0) > 0) fetchCaffeineGuide();
    })
    .catch(function() {
      if (box) box.innerHTML = '<span class="diet-drink-empty">抽不到，稍後再試</span>';
    })
    .finally(function() { _dietDrinkLoading = false; });
}

function renderDietDrink(g) {
  var box = document.getElementById('diet-drink-result');
  if (!box) return;
  if (!g || !g.name) {
    box.className = 'diet-drink-result';
    box.innerHTML = '';
    return;
  }
  var caf = (g.caffeine_mg != null && g.caffeine_mg > 0) ? (g.caffeine_mg + ' mg 咖啡因') : '無咖啡因';
  box.className = 'diet-drink-result diet-drink-show';
  box.innerHTML = ''
    + '<div class="diet-drink-head">'
    +   '<span class="diet-drink-icon"><i data-lucide="coffee" style="width:16px;height:16px"></i></span>'
    +   '<span class="diet-drink-name">' + chatEscape(g.name) + '</span>'
    +   '<button class="diet-drink-record" onclick="dietRecordDrink()" title="記錄到今天"><i data-lucide="check" style="width:14px;height:14px"></i></button>'
    +   '<button class="diet-drink-reroll" onclick="dietPickDrink(true)" title="換一杯"><i data-lucide="refresh-cw" style="width:14px;height:14px"></i></button>'
    + '</div>'
    + '<div class="diet-drink-meta">'
    +   (g.where_to_get ? '<span>' + chatEscape(g.where_to_get) + '</span>' : '')
    +   (g.price_tier ? '<span class="diet-pick-price-tag">' + chatEscape(g.price_tier) + (g.price_twd ? ' · NT$' + g.price_twd : '') + '</span>' : '')
    +   (g.calorie_kcal != null ? '<span class="diet-pick-cal-tag">' + g.calorie_kcal + ' kcal</span>' : '')
    +   '<span class="diet-drink-caf' + (g.caffeine_mg > 100 ? ' high' : '') + '">' + caf + '</span>'
    +   (g.sugar_level && g.sugar_level !== '不適用' ? '<span class="diet-drink-sugar">' + chatEscape(g.sugar_level) + '</span>' : '')
    + '</div>'
    + (g.reason ? '<div class="diet-drink-reason">' + chatEscape(g.reason) + '</div>' : '');
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

async function dietRecordDrink() {
  if (!_dietDrinkCurrent || !_dietDrinkCurrent.name) return;
  var pid = getStablePatientId();
  if (!pid) { showToast('請先登入', 'warning'); return; }
  var btn = document.querySelector('.diet-drink-record');
  if (btn && btn.disabled) return;
  if (btn) btn.disabled = true;
  var meal = (_dietPickMealType && _dietPickMealType !== 'any') ? _dietPickMealType : 'snack';
  var noteParts = [];
  if (_dietDrinkCurrent.caffeine_mg != null && _dietDrinkCurrent.caffeine_mg > 0) {
    noteParts.push('咖啡因 ' + _dietDrinkCurrent.caffeine_mg + ' mg');
  }
  if (_dietDrinkCurrent.where_to_get) noteParts.push(_dietDrinkCurrent.where_to_get);
  try {
    var res = await fetch(API + '/diet/records', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-User-Id': pid },
      body: JSON.stringify({
        patient_id: pid,
        meal_type: meal,
        foods: _dietDrinkCurrent.name,
        note: noteParts.join('｜'),
      }),
    });
    if (!res.ok) {
      var err = await res.json().catch(function() { return {}; });
      throw new Error(err.detail || '記錄失敗');
    }
    showToast('已記錄：' + _dietDrinkCurrent.name, 'success');
    if (btn) {
      btn.classList.add('diet-drink-record-done');
      btn.innerHTML = '<i data-lucide="check-check" style="width:14px;height:14px"></i>';
      btn.title = '已記錄';
      if (typeof lucide !== 'undefined') lucide.createIcons();
    }
    fetchDietTodayRecords();
  } catch (e) {
    if (btn) btn.disabled = false;
    showToast('記錄失敗：' + (e.message || ''), 'error');
  }
}

function fetchCaffeineGuide() {
  var card = document.getElementById('diet-caffeine-card');
  var body = document.getElementById('diet-caffeine-body');
  if (!card || !body) return;
  fetch(API + '/diet/caffeine-guide')
    .then(function(r) { return r.json(); })
    .then(function(g) {
      var sources = (g.common_sources || []).map(function(s) {
        return '<tr><td>' + chatEscape(s.item) + '</td><td>' + s.mg + ' mg</td></tr>';
      }).join('');
      var warns = (g.warnings || []).map(function(w) {
        return ''
          + '<div class="diet-caf-warn">'
          +   '<div class="diet-caf-warn-head"><strong>' + chatEscape(w.group) + '</strong>'
          +     '<span class="diet-caf-warn-limit">' + chatEscape(w.limit) + '</span></div>'
          +   '<div class="diet-caf-warn-note">' + chatEscape(w.note) + '</div>'
          + '</div>';
      }).join('');
      body.innerHTML = ''
        + '<p class="diet-caf-overview">一般成人每日建議 ≤ <strong>' + g.daily_safe_mg + ' mg</strong>，孕期 ≤ <strong>' + g.pregnancy_safe_mg + ' mg</strong>。</p>'
        + '<div class="diet-caf-grid">'
        +   '<div><div class="diet-caf-subtitle">常見飲料咖啡因</div>'
        +     '<table class="diet-caf-table"><tbody>' + sources + '</tbody></table>'
        +   '</div>'
        +   '<div><div class="diet-caf-subtitle">這些族群要注意</div>' + warns + '</div>'
        + '</div>';
      if (typeof lucide !== 'undefined') lucide.createIcons();
    })
    .catch(function() {
      body.innerHTML = '<p class="diet-empty">載入失敗，稍後再試</p>';
    });
}


function dietPickLogIt() {
  if (!_dietPickCurrent || !_dietPickCurrent.name) return;
  // meal_type 優先使用後端回傳的解析後餐別（'any' 已被自動轉成 breakfast/lunch/dinner/snack）
  var meal = _dietPickCurrent.meal_type
    || (_dietPickMealType !== 'any' ? _dietPickMealType : 'lunch');
  dietPickLogMeal(meal);
  var foodsField = document.getElementById('diet-log-foods');
  if (foodsField) {
    var parts = [_dietPickCurrent.name];
    (_dietPickCurrent.components || []).forEach(function(c) { parts.push(c); });
    foodsField.value = parts.join('、');
    foodsField.focus();
    foodsField.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  showToast('幫你填好了，按送出就完成', 'success');
}


function loadDietPage() {
  _dietSelectedMeal = 'breakfast';
  _dietLogMeal = 'breakfast';
  _dietPickMealType = 'any';
  _dietPickPrice = 'any';
  _dietPickCal = 'any';
  _dietPickNearby = false;
  _dietPickAvoidRecent = true;
  // 從 localStorage 讀回 24h 內已被抽過的菜，避免換頁回來又看到同一道
  _dietPickHistory  = _dietLoadHistory(DIET_PICK_HISTORY_KEY);
  _dietDrinkHistory = _dietLoadHistory(DIET_DRINK_HISTORY_KEY);
  _dietPickCurrent  = null;
  _dietDrinkCurrent = null;
  dietPickLoadDislikes();
  setTimeout(function() {
    dietPickRenderDislikes();
    var drinkBox = document.getElementById('diet-drink-result');
    if (drinkBox) drinkBox.innerHTML = '';
  }, 50);
  if (typeof lucide !== 'undefined') setTimeout(function() { lucide.createIcons(); }, 30);
  renderBasicNutrients();
  fetchDietGuide();
  fetchCaffeineGuide();
  fetchDietTodayRecords();
  fetchDietWeekly();
}

function fetchDietGuide() {
  // 先把基本衛教 render 上去，再去打 API；API 回來再用個人化資料蓋過
  renderDietTargets(DIET_BASELINE_TARGETS, DIET_BASELINE_TIPS);
  var pid = getStablePatientId();
  if (!pid) { renderDietWarnings([]); renderDietSuggestions({}); return; }
  fetch(API + '/diet/guide/' + encodeURIComponent(pid))
    .then(function(r) { return r.json(); })
    .then(function(g) {
      _dietGuide = g || {};
      var t = g.daily_targets && Object.keys(g.daily_targets).length ? g.daily_targets : DIET_BASELINE_TARGETS;
      var tips = (g.general_tips && g.general_tips.length) ? g.general_tips : DIET_BASELINE_TIPS;
      renderDietTargets(t, tips);
      renderDietWarnings(g.warnings || []);
      renderDietSuggestions(g.meal_suggestions || {});
    })
    .catch(function(e) {
      // 失敗時保留基本衛教，不要把畫面換成「載入失敗」
    });
}

function renderDietTargets(t, tips) {
  var row = document.getElementById('diet-target-row');
  if (row) {
    row.innerHTML = ''
      + '<div class="diet-target"><span class="diet-target-num">' + (t.protein_g || '—') + '</span><span class="diet-target-unit">g</span><span class="diet-target-label">蛋白質</span></div>'
      + '<div class="diet-target"><span class="diet-target-num">' + (t.water_ml || '—') + '</span><span class="diet-target-unit">ml</span><span class="diet-target-label">水分</span></div>'
      + '<div class="diet-target"><span class="diet-target-num">' + (t.fiber_g || '—') + '</span><span class="diet-target-unit">g</span><span class="diet-target-label">纖維</span></div>';
  }
  var tipsEl = document.getElementById('diet-tips');
  if (tipsEl) {
    tipsEl.innerHTML = (tips || []).map(function(x) { return '<li>' + chatEscape(x) + '</li>'; }).join('');
  }
}

function renderDietWarnings(warnings) {
  var box = document.getElementById('diet-warnings');
  if (!box) return;
  if (!warnings || !warnings.length) {
    box.innerHTML = '<p class="diet-empty">目前沒有特別需要避開的食物。如果有新的診斷，記得更新病歷。</p>';
    return;
  }
  box.innerHTML = warnings.map(function(w) {
    var avoid = (w.avoid || []).map(function(f) { return '<span class="diet-chip-bad">' + chatEscape(f) + '</span>'; }).join('');
    return ''
      + '<div class="diet-warn">'
      +   '<div class="diet-warn-head">' + chatEscape(w.disease || '') + '</div>'
      +   '<div class="diet-warn-avoid">' + avoid + '</div>'
      +   (w.reason ? '<div class="diet-warn-reason">' + chatEscape(w.reason) + '</div>' : '')
      + '</div>';
  }).join('');
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function renderDietSuggestions(s) {
  var list = document.getElementById('diet-suggest-list');
  if (!list) return;
  var foods = (s && s[_dietSelectedMeal]) || [];
  if (!foods.length) {
    list.innerHTML = '<p class="diet-empty">尚無建議</p>';
    return;
  }
  list.innerHTML = foods.map(function(f) {
    return '<span class="diet-chip-good">' + chatEscape(f) + '</span>';
  }).join('');
}

function dietSwitchMeal(m) {
  _dietSelectedMeal = m;
  document.querySelectorAll('#diet-meal-tabs .diet-meal-tab').forEach(function(b) {
    b.classList.toggle('active', b.getAttribute('data-meal') === m);
  });
  if (_dietGuide) renderDietSuggestions(_dietGuide.meal_suggestions || {});
}

var _dietLogMeal = 'breakfast';

function dietPickLogMeal(m) {
  _dietLogMeal = m;
  document.querySelectorAll('#diet-log-meal-pick .diet-log-meal').forEach(function(b) {
    b.classList.toggle('active', b.getAttribute('data-log-meal') === m);
  });
}

async function dietSubmitLog() {
  var pid = getStablePatientId();
  if (!pid) { showToast('請先登入', 'warning'); return; }
  var foods = (document.getElementById('diet-log-foods').value || '').trim();
  if (!foods) { showToast('請填吃了什麼', 'warning'); return; }
  var note = (document.getElementById('diet-log-note').value || '').trim();
  var statusEl = document.getElementById('diet-log-status');
  statusEl.textContent = '送出中…';
  statusEl.className = 'diet-log-status';
  try {
    var res = await fetch(API + '/diet/records', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-User-Id': pid },
      body: JSON.stringify({ patient_id: pid, meal_type: _dietLogMeal, foods: foods, note: note }),
    });
    if (!res.ok) {
      var err = await res.json().catch(function() { return {}; });
      throw new Error(err.detail || '送出失敗');
    }
    document.getElementById('diet-log-foods').value = '';
    document.getElementById('diet-log-note').value = '';
    statusEl.textContent = '已記錄 ' + DIET_MEAL_LABEL[_dietLogMeal];
    statusEl.className = 'diet-log-status diet-log-status-ok';
    showToast('飲食打卡完成', 'success');
    fetchDietTodayRecords();
    fetchDietWeekly();
  } catch (e) {
    statusEl.textContent = '送出失敗：' + (e.message || '');
    statusEl.className = 'diet-log-status diet-log-status-error';
  }
}

function fetchDietTodayRecords() {
  var pid = getStablePatientId();
  if (!pid) return;
  var box = document.getElementById('diet-today-list');
  if (!box) return;
  var today = new Date();
  var d = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
  var tz = today.getTimezoneOffset(); // 分鐘，UTC 西側為正
  var url = API + '/diet/records/' + encodeURIComponent(pid) + '?date=' + d + '&tz_offset=' + tz;
  box.innerHTML = '<p class="diet-empty">載入中…</p>';
  fetch(url)
    .then(function(r) {
      if (!r.ok) {
        return r.text().then(function(body) {
          var snippet = (body || '').replace(/\s+/g, ' ').slice(0, 120);
          throw new Error('HTTP ' + r.status + (snippet ? '：' + snippet : ''));
        });
      }
      return r.text().then(function(text) {
        try { return JSON.parse(text); }
        catch (e) {
          throw new Error('回應非 JSON：' + (text || '').slice(0, 120));
        }
      });
    })
    .then(function(data) {
      var rows = (data && data.records) || [];
      if (data && data.error) {
        box.innerHTML = '<p class="diet-empty">讀取失敗：' + chatEscape(data.error) +
          ' <button class="diet-retry-btn" type="button" onclick="fetchDietTodayRecords()">重試</button></p>';
        return;
      }
      if (!rows.length) {
        box.innerHTML = '<p class="diet-empty">今天還沒有紀錄。</p>';
        return;
      }
      box.innerHTML = rows.map(function(r) {
        var t = new Date(r.eaten_at).toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' });
        return ''
          + '<div class="diet-record">'
          +   '<span class="diet-record-meal">' + (DIET_MEAL_LABEL[r.meal_type] || r.meal_type) + '</span>'
          +   '<div class="diet-record-body">'
          +     '<div class="diet-record-foods">' + chatEscape(r.foods || '') + '</div>'
          +     (r.note ? '<div class="diet-record-note">' + chatEscape(r.note) + '</div>' : '')
          +   '</div>'
          +   '<span class="diet-record-time">' + t + '</span>'
          + '</div>';
      }).join('');
    })
    .catch(function(e) {
      console.error('[diet] fetch today records failed:', e);
      var msg = (e && e.message) ? e.message : '網路錯誤';
      box.innerHTML = '<p class="diet-empty">讀取失敗：' + chatEscape(msg) +
        ' <button class="diet-retry-btn" type="button" onclick="fetchDietTodayRecords()">重試</button></p>';
    });
}

// ─── 飲食週報 ────────────────────────────────────────────────
var _dietWeeklyData     = null;   // { weeks: [...] } 快取 4 週
var _dietWeeklyWeekIdx  = 0;      // 0 = 本週、1 = 上週、…
var _dietWeeklyChartType = 'line'; // 'line' | 'stack' | 'multi'
var _dietWeeklyMealColors = {
  breakfast: '#f4b942',
  lunch:     '#5b9fe8',
  dinner:    '#7d6dc7',
  snack:     '#4caf90',
};
// 折線圖 4 條線的設定（key 對應 by_day.intake_pct.* 與 completeness）
var _dietWeeklyLineSeries = [
  { key: 'completeness', label: '完整度', color: '#4caf90', desc: '早午晚點打卡加權' },
  { key: 'protein',      label: '蛋白質', color: '#e76f51', desc: '佔每日目標 %' },
  { key: 'water',        label: '水分',   color: '#5b9fe8', desc: '佔每日目標 %' },
  { key: 'fiber',        label: '纖維',   color: '#b07cd6', desc: '佔每日目標 %' },
];

function fetchDietWeekly() {
  var pid = getStablePatientId();
  if (!pid) return;
  var stats = document.getElementById('diet-weekly-stats');
  if (!stats) return;
  stats.innerHTML = '<div class="diet-empty">載入中…</div>';
  var tz = new Date().getTimezoneOffset();
  fetch(API + '/diet/weekly/' + encodeURIComponent(pid) + '?weeks=4&tz_offset=' + tz)
    .then(function(r) {
      if (!r.ok) {
        return r.text().then(function(body) {
          throw new Error('HTTP ' + r.status + '：' + (body || '').slice(0, 120));
        });
      }
      return r.json();
    })
    .then(function(data) {
      _dietWeeklyData = data || { weeks: [] };
      if (data && data.error) {
        stats.innerHTML = '<div class="diet-empty">讀取失敗：' + chatEscape(data.error) +
          ' <button class="diet-retry-btn" type="button" onclick="fetchDietWeekly()">重試</button></div>';
        return;
      }
      renderDietWeekly();
    })
    .catch(function(e) {
      console.error('[diet] weekly fetch failed:', e);
      stats.innerHTML = '<div class="diet-empty">讀取失敗：' + chatEscape((e && e.message) || '網路錯誤') +
        ' <button class="diet-retry-btn" type="button" onclick="fetchDietWeekly()">重試</button></div>';
    });
}

function dietWeeklySwitchWeek(idx) {
  _dietWeeklyWeekIdx = idx | 0;
  // 更新 tab active
  var tabs = document.querySelectorAll('#diet-weekly-week-tabs .diet-weekly-week-tab');
  tabs.forEach(function(t) {
    t.classList.toggle('active', String(idx) === t.getAttribute('data-week-idx'));
  });
  renderDietWeekly();
}

function dietWeeklySwitchChart(type) {
  if (type !== 'line' && type !== 'stack' && type !== 'multi') return;
  _dietWeeklyChartType = type;
  var tabs = document.querySelectorAll('#diet-weekly-chart-tabs .diet-weekly-chart-tab');
  tabs.forEach(function(t) {
    t.classList.toggle('active', type === t.getAttribute('data-chart-type'));
  });
  renderDietWeekly();
}

function renderDietWeekly() {
  if (!_dietWeeklyData || !_dietWeeklyData.weeks) return;
  var week = _dietWeeklyData.weeks[_dietWeeklyWeekIdx] || null;
  var stats = document.getElementById('diet-weekly-stats');
  var meta  = document.getElementById('diet-weekly-meta');
  var foods = document.getElementById('diet-weekly-top-foods');
  var canvas = document.getElementById('diet-weekly-canvas');
  if (!stats || !canvas) return;

  if (!week || !week.by_day || !week.by_day.length) {
    stats.innerHTML = '<div class="diet-empty">這 7 天還沒打卡。</div>';
    if (meta) meta.textContent = '';
    if (foods) foods.innerHTML = '';
    var c0 = canvas.getContext('2d');
    c0.clearRect(0, 0, canvas.width, canvas.height);
    return;
  }

  // 4 個指標卡：早 X/7、午 X/7、晚 X/7、點 X/7
  var t = week.totals || {};
  var hits = { breakfast: 0, lunch: 0, dinner: 0, snack: 0 };
  week.by_day.forEach(function(d) {
    if (d.breakfast) hits.breakfast++;
    if (d.lunch)     hits.lunch++;
    if (d.dinner)    hits.dinner++;
    if (d.snack)     hits.snack++;
  });
  stats.innerHTML =
    [['breakfast','早'],['lunch','午'],['dinner','晚'],['snack','點']].map(function(p) {
      return '<div class="diet-weekly-stat" style="border-color:' + _dietWeeklyMealColors[p[0]] + '">' +
        '<div class="diet-weekly-stat-meal" style="color:' + _dietWeeklyMealColors[p[0]] + '">' + p[1] + '</div>' +
        '<div class="diet-weekly-stat-frac">' + hits[p[0]] + '<span class="diet-weekly-stat-of">/7</span></div>' +
        '<div class="diet-weekly-stat-total">共 ' + (t[p[0]] || 0) + ' 餐</div>' +
      '</div>';
    }).join('');

  // 完整度說明
  var pct = Math.round((week.completeness_avg || 0) * 100);
  if (meta) {
    meta.textContent = '本週完整度：' + pct + '%（' + week.week_start + ' ~ ' + week.week_end + '）';
  }

  // top foods chips
  if (foods) {
    var tf = week.top_foods || [];
    if (tf.length) {
      foods.innerHTML = '<span class="diet-weekly-top-foods-label">常見食物</span>' +
        tf.slice(0, 6).map(function(p) {
          return '<span class="diet-weekly-food-chip">' + chatEscape(p[0]) + ' <em>×' + p[1] + '</em></span>';
        }).join('');
    } else {
      foods.innerHTML = '';
    }
  }

  // legend / hint：只有折線圖會顯示營養素圖例與估算註記
  _renderDietWeeklyLegend(_dietWeeklyChartType === 'line');

  // 繪製圖表
  if (_dietWeeklyChartType === 'stack') {
    drawDietWeeklyStack(week);
  } else if (_dietWeeklyChartType === 'multi') {
    drawDietWeeklyMulti(week);
  } else {
    drawDietWeeklyLine(week);
  }
}

function _renderDietWeeklyLegend(show) {
  var legend = document.getElementById('diet-weekly-chart-legend');
  var hint   = document.getElementById('diet-weekly-chart-hint');
  if (!legend) return;
  if (!show) {
    legend.innerHTML = '';
    legend.style.display = 'none';
    if (hint) { hint.textContent = ''; hint.style.display = 'none'; }
    return;
  }
  legend.style.display = '';
  legend.innerHTML = _dietWeeklyLineSeries.map(function(s) {
    return '<span class="diet-weekly-legend-item" title="' + chatEscape(s.desc) + '">'
      +   '<span class="diet-weekly-legend-dot" style="background:' + s.color + '"></span>'
      +   '<span class="diet-weekly-legend-label">' + chatEscape(s.label) + '</span>'
      + '</span>';
  }).join('');
  if (hint) {
    hint.textContent = '蛋白質／水分／纖維為食物關鍵字粗估，僅供趨勢參考。';
    hint.style.display = '';
  }
}

function _dietWeeklyCanvasSetup() {
  var canvas = document.getElementById('diet-weekly-canvas');
  if (!canvas) return null;
  var dpr = window.devicePixelRatio || 1;
  var rect = canvas.getBoundingClientRect();
  var ctx = canvas.getContext('2d');
  var w = canvas.width = Math.max(2, rect.width * dpr);
  var h = canvas.height = Math.max(2, rect.height * dpr);
  ctx.clearRect(0, 0, w, h);
  return { ctx: ctx, w: w, h: h, dpr: dpr };
}

function _dietWeeklyDayLabels(week) {
  // 顯示 月/日（mm/dd）
  return week.by_day.map(function(d) {
    var parts = d.date.split('-');
    return parts[1] + '/' + parts[2];
  });
}

function drawDietWeeklyLine(week) {
  // 折線：完整度 + 蛋白質/水分/纖維 攝取比例（皆 0~1，超過 100% 截到 1）
  var s = _dietWeeklyCanvasSetup();
  if (!s) return;
  var ctx = s.ctx, w = s.w, h = s.h, dpr = s.dpr;
  var pad = 22 * dpr;
  var padLeft = 32 * dpr;

  var days = week.by_day;
  if (!days.length) return;
  var targets = week.daily_targets || { protein_g: 60, water_ml: 2000, fiber_g: 25 };

  function clamp01(v) { return Math.max(0, Math.min(1, v || 0)); }
  function pctFor(d, key) {
    if (key === 'completeness') return clamp01(d.completeness);
    // 後端有給 intake_pct 直接用，舊資料 fallback 從 nutrients 算
    if (d.intake_pct && typeof d.intake_pct[key] === 'number') {
      return clamp01(d.intake_pct[key]);
    }
    var n = d.nutrients || {};
    if (key === 'protein') return clamp01((n.protein_g || 0) / (targets.protein_g || 60));
    if (key === 'water')   return clamp01((n.water_ml  || 0) / (targets.water_ml  || 2000));
    if (key === 'fiber')   return clamp01((n.fiber_g   || 0) / (targets.fiber_g   || 25));
    return 0;
  }

  // 格線：50% 虛線 + 100% 細實線
  ctx.strokeStyle = 'rgba(120,140,170,0.18)';
  ctx.lineWidth = 1 * dpr;
  ctx.setLineDash([4 * dpr, 4 * dpr]);
  var midY = h - pad - (h - 2 * pad) * 0.5;
  ctx.beginPath();
  ctx.moveTo(padLeft, midY); ctx.lineTo(w - pad, midY); ctx.stroke();
  ctx.setLineDash([]);

  var stepX = function(i) {
    return padLeft + (w - pad - padLeft) * (days.length === 1 ? 0.5 : i / (days.length - 1));
  };
  var yFrom = function(v) { return h - pad - (h - 2 * pad) * v; };

  // 完整度先畫底部漸層
  var compPts = days.map(function(d, i) {
    return { x: stepX(i), y: yFrom(clamp01(d.completeness)) };
  });
  var grad = ctx.createLinearGradient(0, pad, 0, h - pad);
  grad.addColorStop(0, 'rgba(76,175,144,0.22)');
  grad.addColorStop(1, 'rgba(76,175,144,0)');
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.moveTo(compPts[0].x, h - pad);
  compPts.forEach(function(p) { ctx.lineTo(p.x, p.y); });
  ctx.lineTo(compPts[compPts.length - 1].x, h - pad);
  ctx.closePath();
  ctx.fill();

  // 4 條線：完整度粗一點，營養素細一點
  _dietWeeklyLineSeries.forEach(function(series, idx) {
    var pts = days.map(function(d, i) {
      return { x: stepX(i), y: yFrom(pctFor(d, series.key)) };
    });
    ctx.strokeStyle = series.color;
    ctx.lineWidth = (idx === 0 ? 2.2 : 1.6) * dpr;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.beginPath();
    pts.forEach(function(p, i) { i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y); });
    ctx.stroke();

    ctx.fillStyle = series.color;
    var dotR = (idx === 0 ? 3 : 2.2) * dpr;
    pts.forEach(function(p) { ctx.beginPath(); ctx.arc(p.x, p.y, dotR, 0, 2 * Math.PI); ctx.fill(); });
  });

  // y 標籤
  ctx.fillStyle = 'rgba(120,140,170,0.7)';
  ctx.font = (10 * dpr) + 'px system-ui';
  ctx.textAlign = 'left';
  ctx.fillText('100%', 2 * dpr, pad + 4 * dpr);
  ctx.fillText('50%',  2 * dpr, midY + 4 * dpr);
  ctx.fillText('0%',   2 * dpr, h - pad + 4 * dpr);

  // x 標籤（日期）
  var labels = _dietWeeklyDayLabels(week);
  ctx.textAlign = 'center';
  compPts.forEach(function(p, i) {
    ctx.fillText(labels[i], p.x, h - pad + 14 * dpr);
  });
}

function drawDietWeeklyStack(week) {
  // 堆疊長條：每天每餐打卡 = 1 unit；y 軸 0~4
  var s = _dietWeeklyCanvasSetup();
  if (!s) return;
  var ctx = s.ctx, w = s.w, h = s.h, dpr = s.dpr;
  var pad = 22 * dpr;
  var padLeft = 32 * dpr;
  var days = week.by_day;
  var n = days.length;
  var slot = (w - pad - padLeft) / n;
  var barW = slot * 0.65;
  var meals = ['breakfast','lunch','dinner','snack'];
  var unitH = (h - 2 * pad) / 4;

  // y 軸格線
  ctx.strokeStyle = 'rgba(120,140,170,0.12)';
  ctx.lineWidth = 1 * dpr;
  for (var k = 1; k <= 4; k++) {
    var yy = h - pad - unitH * k;
    ctx.beginPath(); ctx.moveTo(padLeft, yy); ctx.lineTo(w - pad, yy); ctx.stroke();
  }

  days.forEach(function(d, i) {
    var x = padLeft + slot * (i + 0.5) - barW / 2;
    var stackY = h - pad;
    meals.forEach(function(m) {
      if (d[m]) {
        ctx.fillStyle = _dietWeeklyMealColors[m];
        ctx.fillRect(x, stackY - unitH + 1 * dpr, barW, unitH - 2 * dpr);
        stackY -= unitH;
      }
    });
  });

  // 標籤
  ctx.fillStyle = 'rgba(120,140,170,0.7)';
  ctx.font = (10 * dpr) + 'px system-ui';
  ctx.textAlign = 'left';
  ctx.fillText('4', 2 * dpr, pad + 4 * dpr);
  ctx.fillText('2', 2 * dpr, h - pad - unitH * 2 + 4 * dpr);
  ctx.fillText('0', 2 * dpr, h - pad + 4 * dpr);

  var labels = _dietWeeklyDayLabels(week);
  ctx.textAlign = 'center';
  days.forEach(function(_, i) {
    var cx = padLeft + slot * (i + 0.5);
    ctx.fillText(labels[i], cx, h - pad + 14 * dpr);
  });
}

function drawDietWeeklyMulti(week) {
  // 4 條折線：早午晚點分別累積打卡（0/1 per day）
  var s = _dietWeeklyCanvasSetup();
  if (!s) return;
  var ctx = s.ctx, w = s.w, h = s.h, dpr = s.dpr;
  var pad = 22 * dpr;
  var padLeft = 32 * dpr;
  var days = week.by_day;
  var n = days.length;
  var meals = ['breakfast','lunch','dinner','snack'];

  // y 軸：每條線在獨立帶（4 帶）— 讓 4 條線不重疊
  // 改採累積線：每條線是「截至這天的總次數 / 7」 0~1
  var bandH = (h - 2 * pad);
  var stepX = (w - pad - padLeft) / Math.max(1, n - 1);

  // 格線
  ctx.strokeStyle = 'rgba(120,140,170,0.12)';
  ctx.lineWidth = 1 * dpr;
  ctx.setLineDash([3 * dpr, 3 * dpr]);
  ctx.beginPath();
  ctx.moveTo(padLeft, h - pad - bandH * 0.5); ctx.lineTo(w - pad, h - pad - bandH * 0.5);
  ctx.stroke();
  ctx.setLineDash([]);

  meals.forEach(function(m) {
    var cum = 0;
    var pts = days.map(function(d, i) {
      if (d[m]) cum++;
      return {
        x: padLeft + stepX * i,
        y: h - pad - bandH * (cum / 7),
      };
    });
    ctx.strokeStyle = _dietWeeklyMealColors[m];
    ctx.lineWidth = 2 * dpr;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    pts.forEach(function(p, i) { i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y); });
    ctx.stroke();
    ctx.fillStyle = _dietWeeklyMealColors[m];
    pts.forEach(function(p) { ctx.beginPath(); ctx.arc(p.x, p.y, 2.5 * dpr, 0, 2 * Math.PI); ctx.fill(); });
  });

  // y 標籤
  ctx.fillStyle = 'rgba(120,140,170,0.7)';
  ctx.font = (10 * dpr) + 'px system-ui';
  ctx.textAlign = 'left';
  ctx.fillText('7', 2 * dpr, pad + 4 * dpr);
  ctx.fillText('0', 2 * dpr, h - pad + 4 * dpr);

  // 圖例
  ctx.font = (9 * dpr) + 'px system-ui';
  var legendX = padLeft;
  var legendY = pad - 4 * dpr;
  [['breakfast','早'],['lunch','午'],['dinner','晚'],['snack','點']].forEach(function(p) {
    ctx.fillStyle = _dietWeeklyMealColors[p[0]];
    ctx.fillRect(legendX, legendY - 6 * dpr, 8 * dpr, 8 * dpr);
    ctx.fillStyle = 'rgba(120,140,170,0.9)';
    ctx.fillText(p[1], legendX + 11 * dpr, legendY + 1 * dpr);
    legendX += 28 * dpr;
  });

  var labels = _dietWeeklyDayLabels(week);
  ctx.fillStyle = 'rgba(120,140,170,0.7)';
  ctx.font = (10 * dpr) + 'px system-ui';
  ctx.textAlign = 'center';
  days.forEach(function(_, i) {
    var x = padLeft + stepX * i;
    ctx.fillText(labels[i], x, h - pad + 14 * dpr);
  });
}


// ─── 藥物搜尋（藥物百科） ─────────────────────────────────
// 走 backend /drug-search 端點：先查 drug_reference 快取，沒命中才呼叫 LLM。
// 同時支援文字搜尋、拍照辨識、從個人用藥清單一鍵查詢。
// 顯眼的免責聲明：所有 AI 整理的內容都不取代醫師判斷。

function drugSearch() {
  // 若是從個人用藥清單跳過來，預填查詢字串
  var prefill = window._drugSearchPrefill || "";
  window._drugSearchPrefill = "";
  return (
    '<div class="card">' +
      '<h2><i data-lucide="search" style="width:20px;height:20px;vertical-align:middle"></i> 藥物百科查詢</h2>' +
      '<p style="margin-top:8px;color:var(--text-dim)">輸入藥名（中文 / 英文 / 商品名）查詢副作用、風險、用法與基礎衛教。</p>' +
      '<div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">' +
        '<input id="drug-search-input" type="text" placeholder="例如：普拿疼、Acetaminophen、Lipitor" value="' + escapeHtml(prefill) + '" ' +
          'onkeydown="if(event.key===\'Enter\')runDrugSearch()" ' +
          'style="flex:1;min-width:200px;padding:10px 12px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-card)" />' +
        '<button class="primary" onclick="runDrugSearch()">' +
          '<i data-lucide="search" style="width:14px;height:14px;vertical-align:middle"></i> 查詢' +
        '</button>' +
        '<button class="secondary" onclick="document.getElementById(\'drug-photo-input\').click()" title="拍藥盒、藥袋或藥單後自動查詢">' +
          '<i data-lucide="camera" style="width:14px;height:14px;vertical-align:middle"></i> 拍照查詢' +
        '</button>' +
        '<input type="file" id="drug-photo-input" accept="image/*" capture="environment" style="display:none" onchange="handleDrugPhoto(this)" />' +
      '</div>' +
      '<div style="margin-top:10px;padding:8px 12px;background:rgba(220,170,80,0.1);border-radius:var(--radius-sm);border:1px solid rgba(220,170,80,0.3);font-size:0.82rem;color:var(--text-dim)">' +
        '<i data-lucide="alert-triangle" style="width:14px;height:14px;vertical-align:middle"></i> ' +
        '此查詢結果由 AI 整理，<strong>僅供衛教參考</strong>。實際處方與劑量請以您的主治醫師與藥師說明為準。' +
      '</div>' +
    '</div>' +
    '<div class="card" id="drug-search-result-card" style="display:none">' +
      '<div id="drug-search-result"></div>' +
    '</div>' +
    '<div class="card">' +
      '<h3><i data-lucide="trending-up" style="width:18px;height:18px;vertical-align:middle"></i> 熱門查詢</h3>' +
      '<p style="margin-top:4px;color:var(--text-dim);font-size:0.9rem">最常被查詢的藥物（從快取統計）</p>' +
      '<div id="drug-trending" style="margin-top:8px"><p style="color:var(--text-muted)">載入中…</p></div>' +
    '</div>'
  );
}

function loadDrugSearchPage() {
  // 若有預填字串，自動執行一次查詢
  var input = document.getElementById('drug-search-input');
  if (input && input.value.trim()) {
    runDrugSearch();
  }
  // 載入熱門查詢列表
  fetch(API + "/drug-search/trending/list?limit=8")
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var el = document.getElementById('drug-trending');
      if (!el) return;
      var items = (data && data.items) || [];
      if (!items.length) {
        el.innerHTML = '<p style="color:var(--text-muted)">尚無熱門查詢。試著搜尋一個藥物吧！</p>';
        return;
      }
      var html = '<div style="display:flex;flex-wrap:wrap;gap:8px">';
      items.forEach(function(it) {
        var rawQuery = it.name_zh || it.name_en || '';
        var label = escapeHtml(it.name_zh || it.name_en || '未命名');
        // 用 data-q 屬性 + escapeHtml 安全傳遞查詢字串，避免靠 JS 字串轉義
        // （未轉義反斜線會造成 XSS 風險）。事件 handler 從 dataset.q 拿值。
        html += '<button class="secondary" type="button" style="padding:6px 12px;font-size:0.9rem" ' +
          'data-q="' + escapeHtml(rawQuery) + '" ' +
          'onclick="quickDrugSearch(this.dataset.q)">' + label +
          ' <span style="color:var(--text-muted);font-size:0.8em">(' + (it.query_count || 0) + ')</span>' +
          '</button>';
      });
      html += '</div>';
      el.innerHTML = html;
    })
    .catch(function() {
      var el = document.getElementById('drug-trending');
      if (el) el.innerHTML = '<p style="color:var(--text-muted)">熱門列表載入失敗</p>';
    });
}

function quickDrugSearch(name) {
  var input = document.getElementById('drug-search-input');
  if (input) input.value = name;
  runDrugSearch();
}

function runDrugSearch() {
  var input = document.getElementById('drug-search-input');
  var q = (input && input.value || '').trim();
  if (!q) {
    showToast('請輸入要查詢的藥名', 'warn');
    return;
  }
  var card = document.getElementById('drug-search-result-card');
  var box = document.getElementById('drug-search-result');
  if (card) card.style.display = '';
  if (box) box.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:20px"><i data-lucide="loader" style="width:18px;height:18px;vertical-align:middle"></i> 查詢中… 第一次查詢會稍久（AI 整理中）</p>';
  if (window.lucide && window.lucide.createIcons) { try { window.lucide.createIcons(); } catch(e) {} }

  fetch(API + "/drug-search/?q=" + encodeURIComponent(q))
    .then(function(r) { return r.json(); })
    .then(function(data) { renderDrugSearchResult(data); })
    .catch(function() {
      if (box) box.innerHTML = '<p style="color:var(--danger)">查詢失敗，請稍後再試</p>';
    });
}

function renderDrugSearchResult(data) {
  var box = document.getElementById('drug-search-result');
  if (!box) return;
  if (!data || data.matched === false) {
    box.innerHTML =
      '<div style="padding:16px;text-align:center">' +
        '<i data-lucide="search-x" style="width:32px;height:32px;color:var(--text-muted)"></i>' +
        '<p style="margin-top:8px;color:var(--text-dim)">' + escapeHtml((data && data.disclaimer) || '無法辨識此藥名，請確認拼字或嘗試英文藥名。') + '</p>' +
      '</div>';
    if (window.lucide && window.lucide.createIcons) { try { window.lucide.createIcons(); } catch(e) {} }
    return;
  }
  box.innerHTML = _renderDrugCard(data);
  if (window.lucide && window.lucide.createIcons) { try { window.lucide.createIcons(); } catch(e) {} }
}

function _renderDrugCard(d) {
  var nameZh = escapeHtml(d.name_zh || '');
  var nameEn = escapeHtml(d.name_en || '');
  var displayName = nameZh && nameEn ? nameZh + '（' + nameEn + '）' : (nameZh || nameEn || '未命名');
  var aliases = Array.isArray(d.aliases) ? d.aliases : [];
  var aliasHtml = aliases.length
    ? '<div style="margin-top:6px;color:var(--text-dim);font-size:0.88rem">別名 / 商品名：' +
        aliases.map(function(a) { return escapeHtml(a); }).join('、') + '</div>'
    : '';
  var cachedBadge = d.cached
    ? '<span style="font-size:0.75rem;padding:2px 8px;border-radius:8px;background:rgba(80,160,120,0.15);color:#3a8c5e;margin-left:8px">快取</span>'
    : '<span style="font-size:0.75rem;padding:2px 8px;border-radius:8px;background:rgba(100,140,200,0.15);color:#4a7bb6;margin-left:8px">AI 即時整理</span>';

  var se = d.side_effects || {};
  var common = Array.isArray(se.common) ? se.common : [];
  var serious = Array.isArray(se.serious) ? se.serious : [];

  var risks = d.risks || {};
  var contra = Array.isArray(risks.contraindications) ? risks.contraindications : [];
  var warns = Array.isArray(risks.warnings) ? risks.warnings : [];
  var inter = Array.isArray(risks.interactions) ? risks.interactions : [];

  function bulletList(items) {
    if (!items.length) return '<p style="color:var(--text-muted);font-style:italic">（無資料）</p>';
    return '<ul style="margin:6px 0 0 18px;padding:0;line-height:1.7">' +
      items.map(function(x) { return '<li>' + escapeHtml(x) + '</li>'; }).join('') +
      '</ul>';
  }

  return (
    '<header style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:8px">' +
      '<div>' +
        '<h2 style="margin:0">' + displayName + cachedBadge + '</h2>' +
        (d.category ? '<div style="margin-top:4px"><span class="med-card-tag">' + escapeHtml(d.category) + '</span></div>' : '') +
        aliasHtml +
      '</div>' +
    '</header>' +
    (d.indication
      ? '<section style="margin-top:14px"><h3 style="margin:0 0 4px"><i data-lucide="target" style="width:16px;height:16px;vertical-align:middle"></i> 適應症</h3>' +
        '<p style="margin:0;color:var(--text-main)">' + escapeHtml(d.indication) + '</p></section>'
      : '') +
    (d.usage
      ? '<section style="margin-top:14px"><h3 style="margin:0 0 4px"><i data-lucide="clock" style="width:16px;height:16px;vertical-align:middle"></i> 用法用量</h3>' +
        '<p style="margin:0;color:var(--text-main);white-space:pre-wrap">' + escapeHtml(d.usage) + '</p></section>'
      : '') +
    '<section style="margin-top:14px"><h3 style="margin:0 0 4px"><i data-lucide="alert-circle" style="width:16px;height:16px;vertical-align:middle"></i> 副作用</h3>' +
      '<div style="margin-top:6px"><strong style="color:var(--text-main);font-size:0.9rem">常見（多數人會慢慢適應）</strong>' +
        bulletList(common) +
      '</div>' +
      '<div style="margin-top:10px;padding:10px 12px;background:rgba(220,80,80,0.08);border-radius:var(--radius-sm);border:1px solid rgba(220,80,80,0.25)">' +
        '<strong style="color:#c43d3d;font-size:0.9rem"><i data-lucide="alert-octagon" style="width:14px;height:14px;vertical-align:middle"></i> 嚴重（出現請立刻就醫）</strong>' +
        bulletList(serious) +
      '</div>' +
    '</section>' +
    '<section style="margin-top:14px"><h3 style="margin:0 0 4px"><i data-lucide="shield-alert" style="width:16px;height:16px;vertical-align:middle"></i> 風險與警語</h3>' +
      (contra.length ? '<div style="margin-top:6px"><strong style="font-size:0.9rem">禁忌</strong>' + bulletList(contra) + '</div>' : '') +
      (warns.length ? '<div style="margin-top:6px"><strong style="font-size:0.9rem">警語</strong>' + bulletList(warns) + '</div>' : '') +
      (inter.length ? '<div style="margin-top:6px"><strong style="font-size:0.9rem">交互作用</strong>' + bulletList(inter) + '</div>' : '') +
      (!contra.length && !warns.length && !inter.length ? '<p style="color:var(--text-muted);font-style:italic">（無特別記載）</p>' : '') +
    '</section>' +
    (d.education
      ? '<section style="margin-top:14px"><h3 style="margin:0 0 4px"><i data-lucide="book-heart" style="width:16px;height:16px;vertical-align:middle"></i> 基礎衛教</h3>' +
        '<p style="margin:0;color:var(--text-main);white-space:pre-wrap;line-height:1.7">' + escapeHtml(d.education) + '</p></section>'
      : '') +
    '<footer style="margin-top:16px;padding:10px 12px;background:rgba(220,170,80,0.08);border-radius:var(--radius-sm);border:1px solid rgba(220,170,80,0.25);font-size:0.82rem;color:var(--text-dim)">' +
      '<i data-lucide="info" style="width:14px;height:14px;vertical-align:middle"></i> ' +
      escapeHtml(d.disclaimer || '此資訊由 AI 整理，僅供衛教參考，個別用藥請以醫師處方與藥師說明為準。') +
    '</footer>'
  );
}

function handleDrugPhoto(input) {
  var file = input && input.files && input.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function(ev) {
    var dataUrl = ev.target.result || '';
    var commaIdx = dataUrl.indexOf(',');
    if (commaIdx === -1) {
      showToast('照片讀取失敗', 'error');
      return;
    }
    var b64 = dataUrl.substring(commaIdx + 1);
    var mediaType = (file.type || 'image/jpeg');
    var card = document.getElementById('drug-search-result-card');
    var box = document.getElementById('drug-search-result');
    if (card) card.style.display = '';
    if (box) box.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:20px">辨識中… 拍藥盒/藥袋會逐筆查詢，可能需要 10~30 秒</p>';

    fetch(API + "/drug-search/from-photo", {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_base64: b64, media_type: mediaType })
    })
      .then(function(r) { return r.json(); })
      .then(function(data) { renderDrugPhotoResults(data); })
      .catch(function() {
        if (box) box.innerHTML = '<p style="color:var(--danger)">辨識失敗，請改用文字搜尋</p>';
      });
  };
  reader.readAsDataURL(file);
  // 重置以便連拍
  input.value = '';
}

function renderDrugPhotoResults(data) {
  var box = document.getElementById('drug-search-result');
  if (!box) return;
  var results = (data && data.results) || [];
  if (!results.length) {
    box.innerHTML =
      '<div style="text-align:center;padding:20px">' +
        '<p style="color:var(--text-muted);margin:0">沒有辨識到藥名。</p>' +
        '<p style="color:var(--text-dim);margin:8px 0 0;font-size:0.88rem">' +
          '小提醒：藥盒請對準正面（含商品名／學名的那一面）、避免反光與模糊；藥袋請拍清楚藥名那一行。' +
          '若仍無法辨識，請改用文字搜尋輸入藥名。' +
        '</p>' +
      '</div>';
    return;
  }
  var html = '<h3 style="margin:0 0 8px">辨識結果（' + results.length + ' 筆）</h3>';
  results.forEach(function(r, i) {
    // 優先顯示後端實際命中的查詢字（matched_query）— OCR 把藥盒中文辨成亂碼時，
    // matched_query 會是後端從亂碼裡撈出來的乾淨英文藥名。沒命中才退回 recognized_name。
    var shownName = r.matched_query || r.recognized_name || '';
    var hadGarble = r.matched_query && r.recognized_name && r.matched_query !== r.recognized_name;
    html += '<div style="margin-top:12px;padding:12px;border:1px solid var(--border-glass);border-radius:var(--radius-sm)">' +
      '<div style="font-size:0.85rem;color:var(--text-dim);margin-bottom:8px">' +
        '辨識藥名：<strong>' + escapeHtml(shownName) + '</strong>' +
        (r.recognized_dosage ? '・' + escapeHtml(r.recognized_dosage) : '') +
        (r.recognized_frequency ? '・' + escapeHtml(r.recognized_frequency) : '') +
        (hadGarble
          ? '<span style="margin-left:6px;font-size:0.78rem;color:var(--text-muted)">（已自動清理讀錯的字）</span>'
          : '') +
      '</div>';
    if (r.info && r.info.matched) {
      html += _renderDrugCard(r.info);
    } else {
      html += '<p style="color:var(--text-muted);font-style:italic">無法查到此藥的衛教資訊。</p>';
    }
    html += '</div>';
  });
  box.innerHTML = html;
  if (window.lucide && window.lucide.createIcons) { try { window.lucide.createIcons(); } catch(e) {} }
}

// 從別處（個人用藥清單）跳過來查詢
function openDrugSearchFor(name) {
  window._drugSearchPrefill = name || '';
  if (typeof navigateTo === 'function') {
    navigateTo('drugSearch', null);
  } else {
    showPage('drugSearch');
  }
}


// ─── 疾病百科（Disease Lookup）─────────────────────────────
// 對話式 UI：搜尋一次拿到結構化的疾病卡片（資訊 / 症狀 / 用藥 / 風險 / 未來發展 / 自我照護），
// 之後可以在同一個對話框繼續追問，後端會以已查到的疾病為脈絡回答。
// 每則機器訊息結尾都會顯示「免責聲明 + 文獻來源 (PubMed)」。

var _disease = {
  current: null,        // 目前的疾病物件（從 GET /diseases/?q= 拿到的）
  history: [],          // 對話歷史 [{role:'user'|'assistant', content}]
  pendingMsg: false,
};

function diseaseSearch() {
  var prefill = window._diseaseSearchPrefill || '';
  window._diseaseSearchPrefill = '';
  return ''
    + '<div class="card">'
    +   '<h2><i data-lucide="stethoscope" style="width:20px;height:20px;vertical-align:middle"></i> 疾病百科查詢</h2>'
    +   '<p style="margin-top:8px;color:var(--text-dim)">輸入疾病名稱（中文 / 英文）查詢資訊、用藥、風險與未來發展。第一次查詢由 AI 整理，第二次直接從快取回。</p>'
    +   '<div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">'
    +     '<input id="disease-search-input" type="text" placeholder="例如：第二型糖尿病、Hypertension、痛風" value="' + escapeHtml(prefill) + '" '
    +       'onkeydown="if(event.key===\'Enter\')runDiseaseSearch()" '
    +       'style="flex:1;min-width:200px;padding:10px 12px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-card)" />'
    +     '<button class="primary" onclick="runDiseaseSearch()">'
    +       '<i data-lucide="search" style="width:14px;height:14px;vertical-align:middle"></i> 查詢'
    +     '</button>'
    +   '</div>'
    +   '<div style="margin-top:10px;padding:8px 12px;background:rgba(220,170,80,0.1);border-radius:var(--radius-sm);border:1px solid rgba(220,170,80,0.3);font-size:0.82rem;color:var(--text-dim)">'
    +     '<i data-lucide="alert-triangle" style="width:14px;height:14px;vertical-align:middle"></i> '
    +     '此查詢結果由 AI 整理，<strong>僅供衛教參考</strong>。實際診斷與治療請以您的主治醫師為準。'
    +   '</div>'
    + '</div>'

    + '<div class="card" id="disease-result-card" style="display:none">'
    +   '<div id="disease-result"></div>'
    + '</div>'

    + '<div class="card" id="disease-chat-card" style="display:none">'
    +   '<h3><i data-lucide="message-circle" style="width:18px;height:18px;vertical-align:middle"></i> 繼續追問這個疾病</h3>'
    +   '<p style="margin-top:4px;color:var(--text-dim);font-size:0.9rem">針對上方查詢的疾病，可以追問細節（例如：「有什麼飲食要避免？」「我這個年紀該多久回診？」）</p>'
    +   '<div id="disease-chat-stream" style="margin-top:12px;display:flex;flex-direction:column;gap:10px;max-height:400px;overflow-y:auto;padding:8px"></div>'
    +   '<form id="disease-chat-form" style="display:flex;gap:8px;margin-top:12px" onsubmit="event.preventDefault();diseaseChatSend()">'
    +     '<input id="disease-chat-input" type="text" autocomplete="off" placeholder="輸入追問的問題…" '
    +       'style="flex:1;min-width:200px;padding:10px 12px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-card)" />'
    +     '<button type="submit" class="primary">'
    +       '<i data-lucide="send" style="width:14px;height:14px;vertical-align:middle"></i> 送出'
    +     '</button>'
    +   '</form>'
    + '</div>'

    + '<div class="card">'
    +   '<h3><i data-lucide="trending-up" style="width:18px;height:18px;vertical-align:middle"></i> 熱門查詢</h3>'
    +   '<p style="margin-top:4px;color:var(--text-dim);font-size:0.9rem">最常被查詢的疾病</p>'
    +   '<div id="disease-trending" style="margin-top:8px"><p style="color:var(--text-muted)">載入中…</p></div>'
    + '</div>';
}

function loadDiseaseSearchPage() {
  var input = document.getElementById('disease-search-input');
  if (input && input.value.trim()) {
    runDiseaseSearch();
  }
  fetch(API + '/diseases/trending/list?limit=8')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var el = document.getElementById('disease-trending');
      if (!el) return;
      var items = (data && data.items) || [];
      if (!items.length) {
        el.innerHTML = '<p style="color:var(--text-muted)">尚無熱門查詢，試著搜尋一個疾病吧！</p>';
        return;
      }
      var html = '<div style="display:flex;flex-wrap:wrap;gap:8px">';
      items.forEach(function(it) {
        var rawQuery = it.name_zh || it.name_en || '';
        var label = escapeHtml(it.name_zh || it.name_en || '未命名');
        html += '<button class="secondary" type="button" style="padding:6px 12px;font-size:0.9rem" '
          + 'data-q="' + escapeHtml(rawQuery) + '" '
          + 'onclick="quickDiseaseSearch(this.dataset.q)">' + label
          + ' <span style="color:var(--text-muted);font-size:0.8em">(' + (it.query_count || 0) + ')</span>'
          + '</button>';
      });
      html += '</div>';
      el.innerHTML = html;
    })
    .catch(function() {
      var el = document.getElementById('disease-trending');
      if (el) el.innerHTML = '<p style="color:var(--text-muted)">熱門列表載入失敗</p>';
    });
}

function quickDiseaseSearch(name) {
  var input = document.getElementById('disease-search-input');
  if (input) input.value = name;
  runDiseaseSearch();
}

function runDiseaseSearch() {
  var input = document.getElementById('disease-search-input');
  var q = (input && input.value || '').trim();
  if (!q) {
    showToast('請輸入要查詢的疾病名稱', 'warn');
    return;
  }
  var card = document.getElementById('disease-result-card');
  var box = document.getElementById('disease-result');
  if (card) card.style.display = '';
  if (box) box.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:20px"><i data-lucide="loader" style="width:18px;height:18px;vertical-align:middle"></i> 查詢中… 第一次查詢會稍久（AI 整理 + 找文獻中）</p>';
  if (window.lucide && window.lucide.createIcons) { try { window.lucide.createIcons(); } catch(e) {} }

  fetch(API + '/diseases/?q=' + encodeURIComponent(q))
    .then(function(r) { return r.json(); })
    .then(function(data) { renderDiseaseResult(data); })
    .catch(function() {
      if (box) box.innerHTML = '<p style="color:var(--danger)">查詢失敗，請稍後再試</p>';
    });
}

function _diseaseListBlock(title, icon, items, color) {
  if (!items || !items.length) return '';
  var html = '<div style="margin-top:14px">'
    + '<h4 style="display:flex;align-items:center;gap:6px;margin:0 0 6px 0;color:' + (color || 'var(--text)') + '">'
    + '<i data-lucide="' + icon + '" style="width:16px;height:16px"></i> ' + escapeHtml(title)
    + '</h4>'
    + '<ul style="margin:0;padding-left:18px;line-height:1.7;color:var(--text-dim)">';
  items.forEach(function(it) {
    if (typeof it === 'string') {
      html += '<li>' + escapeHtml(it) + '</li>';
    } else if (it && typeof it === 'object') {
      var line = escapeHtml(it.name || '');
      if (it.drug_class) line += ' <span style="color:var(--text-muted);font-size:0.9em">(' + escapeHtml(it.drug_class) + ')</span>';
      if (it.purpose) line += ' — ' + escapeHtml(it.purpose);
      html += '<li>' + line + '</li>';
    }
  });
  html += '</ul></div>';
  return html;
}

function _diseaseRefBlock(refs) {
  // 文獻來源 — 一律顯示這個 block；沒抓到就顯示「目前無近期 review，AI 回覆已附免責聲明」
  var html = '<div style="margin-top:18px;padding-top:12px;border-top:1px dashed var(--border-glass)">'
    + '<h4 style="display:flex;align-items:center;gap:6px;margin:0 0 8px 0;color:var(--text-dim);font-size:0.95rem">'
    + '<i data-lucide="book-open" style="width:16px;height:16px"></i> 文獻來源（PubMed 近 5 年 review）'
    + '</h4>';
  if (!refs || !refs.length) {
    html += '<p style="color:var(--text-muted);font-size:0.85rem;margin:0">目前 PubMed 沒抓到近期 review。本次回覆內容由 AI 從訓練資料整理，建議與您的醫師討論。</p>';
  } else {
    html += '<ol style="margin:0;padding-left:20px;color:var(--text-dim);font-size:0.88rem;line-height:1.6">';
    refs.forEach(function(r) {
      var line = '';
      if (r.authors) line += escapeHtml(r.authors) + '. ';
      line += '<strong>' + escapeHtml(r.title || '(no title)') + '</strong>';
      if (r.journal) line += '. <em>' + escapeHtml(r.journal) + '</em>';
      if (r.year) line += ', ' + escapeHtml(r.year);
      if (r.url) line += '. <a href="' + r.url + '" target="_blank" rel="noopener" style="color:var(--accent)">PubMed</a>';
      html += '<li style="margin-bottom:4px">' + line + '</li>';
    });
    html += '</ol>';
  }
  html += '</div>';
  return html;
}

function _diseaseDisclaimerBlock(text) {
  return '<div style="margin-top:12px;padding:8px 12px;background:rgba(220,170,80,0.1);border-radius:var(--radius-sm);border:1px solid rgba(220,170,80,0.3);font-size:0.82rem;color:var(--text-dim)">'
    + '<i data-lucide="alert-triangle" style="width:14px;height:14px;vertical-align:middle"></i> '
    + '<strong>免責聲明：</strong>' + escapeHtml(text || '此資訊由 AI 整理，僅供衛教參考，不能取代醫師診斷與個別處方。')
    + '</div>';
}

function renderDiseaseResult(data) {
  var box = document.getElementById('disease-result');
  if (!box) return;

  if (!data || data.matched === false) {
    box.innerHTML =
      '<div style="padding:16px;text-align:center">'
      + '<i data-lucide="search-x" style="width:32px;height:32px;color:var(--text-muted)"></i>'
      + '<p style="margin-top:8px;color:var(--text-dim)">' + escapeHtml((data && data.disclaimer) || '無法辨識此疾病名稱，請確認拼字或嘗試英文。') + '</p>'
      + _diseaseRefBlock([])
      + _diseaseDisclaimerBlock((data && data.disclaimer) || '此資訊由 AI 整理，僅供衛教參考。')
      + '</div>';
    var chatCard = document.getElementById('disease-chat-card');
    if (chatCard) chatCard.style.display = 'none';
    if (window.lucide && window.lucide.createIcons) { try { window.lucide.createIcons(); } catch(e) {} }
    return;
  }

  _disease.current = data;
  _disease.history = [];

  var name = data.name_zh || data.name_en || '未命名';
  var subtitle = '';
  if (data.name_zh && data.name_en) subtitle = data.name_en;
  if (data.icd10_code) subtitle += (subtitle ? ' · ' : '') + 'ICD-10: ' + data.icd10_code;
  if (data.icd10_category) subtitle += (subtitle ? ' · ' : '') + escapeHtml(data.icd10_category);

  var html = ''
    + '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">'
    +   '<div>'
    +     '<h3 style="margin:0">' + escapeHtml(name) + '</h3>'
    +     (subtitle ? '<p style="margin:4px 0 0;color:var(--text-muted);font-size:0.9rem">' + subtitle + '</p>' : '')
    +   '</div>'
    +   '<span style="font-size:0.8rem;color:var(--text-muted)">' + (data.cached ? '快取命中' : 'AI 即時整理') + ' · 查詢 ' + (data.query_count || 1) + ' 次</span>'
    + '</div>';

  if (data.overview) {
    html += '<div style="margin-top:14px"><h4 style="margin:0 0 6px 0">📖 是什麼病</h4>'
      + '<p style="margin:0;line-height:1.7;color:var(--text-dim)">' + escapeHtml(data.overview) + '</p></div>';
  }

  html += _diseaseListBlock('病因 / 風險因子', 'alert-circle', data.causes);

  if (data.symptoms) {
    html += _diseaseListBlock('常見症狀', 'activity', data.symptoms.common);
    html += _diseaseListBlock('警訊症狀（要立刻就醫）', 'alert-octagon', data.symptoms.warning, 'var(--danger)');
  }

  html += _diseaseListBlock('常用藥物（一般類別）', 'pill', data.common_medications);
  html += _diseaseListBlock('治療方式', 'heart-pulse', data.treatments);
  html += _diseaseListBlock('長期風險與併發症', 'shield-alert', data.complications);

  if (data.prognosis) {
    html += '<div style="margin-top:14px"><h4 style="margin:0 0 6px 0">🌱 未來發展與預後</h4>'
      + '<p style="margin:0;line-height:1.7;color:var(--text-dim)">' + escapeHtml(data.prognosis) + '</p></div>';
  }

  html += _diseaseListBlock('自我照護建議', 'leaf', data.self_care);
  html += _diseaseListBlock('立刻就醫的訊號', 'siren', data.red_flags, 'var(--danger)');

  // 永遠在最後加：文獻來源 + 免責聲明
  html += _diseaseRefBlock(data.references || []);
  html += _diseaseDisclaimerBlock(data.disclaimer);

  box.innerHTML = html;

  // 顯示對話追問區，並重置串流
  var chatCard = document.getElementById('disease-chat-card');
  var stream = document.getElementById('disease-chat-stream');
  if (chatCard) chatCard.style.display = '';
  if (stream) {
    stream.innerHTML = ''
      + '<div style="background:var(--bg-card);padding:10px 12px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);color:var(--text-dim);font-size:0.92rem">'
      + '👋 我整理好「<strong>' + escapeHtml(name) + '</strong>」的資訊了，有什麼想再問的嗎？例如「我該多久回診一次？」「有什麼食物要避開？」'
      + '</div>';
  }

  if (window.lucide && window.lucide.createIcons) { try { window.lucide.createIcons(); } catch(e) {} }
}

function _diseaseChatBubble(role, contentHtml) {
  var align = role === 'user' ? 'flex-end' : 'flex-start';
  var bg = role === 'user' ? 'var(--accent)' : 'var(--bg-card)';
  var color = role === 'user' ? '#fff' : 'var(--text)';
  return '<div style="display:flex;justify-content:' + align + '">'
    + '<div style="max-width:88%;padding:10px 14px;border-radius:14px;background:' + bg + ';color:' + color + ';line-height:1.65;border:1px solid var(--border-glass);font-size:0.95rem">'
    + contentHtml
    + '</div></div>';
}

function diseaseChatSend() {
  if (_disease.pendingMsg) return;
  var input = document.getElementById('disease-chat-input');
  var msg = (input && input.value || '').trim();
  if (!msg) return;
  if (!_disease.current || !_disease.current.id) {
    showToast('請先搜尋一個疾病再追問', 'warn');
    return;
  }
  var stream = document.getElementById('disease-chat-stream');
  if (!stream) return;

  // 顯示使用者訊息
  stream.insertAdjacentHTML('beforeend', _diseaseChatBubble('user', escapeHtml(msg).replace(/\n/g, '<br>')));
  stream.insertAdjacentHTML(
    'beforeend',
    '<div id="disease-chat-thinking" style="display:flex;justify-content:flex-start"><div style="padding:10px 14px;border-radius:14px;background:var(--bg-card);color:var(--text-muted);border:1px solid var(--border-glass);font-size:0.95rem">疾病助手思考中…</div></div>'
  );
  stream.scrollTop = stream.scrollHeight;
  if (input) input.value = '';

  _disease.pendingMsg = true;
  fetch(API + '/diseases/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      disease_id: _disease.current.id,
      message: msg,
      history: _disease.history.slice(-12),
    }),
  })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var thinking = document.getElementById('disease-chat-thinking');
      if (thinking) thinking.remove();
      var reply = (data && data.reply) || '抱歉，疾病助手暫時忙線中，請稍後再試。';
      var refs = (data && data.references) || [];
      var disclaimer = (data && data.disclaimer) || '此回覆由 AI 整理，僅供衛教參考；實際診療請依您的主治醫師為準。';

      var bubbleHtml = '<div style="white-space:pre-wrap">' + escapeHtml(reply) + '</div>'
        + _diseaseRefBlock(refs)
        + _diseaseDisclaimerBlock(disclaimer);
      stream.insertAdjacentHTML('beforeend', _diseaseChatBubble('assistant', bubbleHtml));

      _disease.history.push({ role: 'user', content: msg });
      _disease.history.push({ role: 'assistant', content: reply });

      if (window.lucide && window.lucide.createIcons) { try { window.lucide.createIcons(); } catch(e) {} }
      stream.scrollTop = stream.scrollHeight;
    })
    .catch(function() {
      var thinking = document.getElementById('disease-chat-thinking');
      if (thinking) thinking.remove();
      stream.insertAdjacentHTML(
        'beforeend',
        _diseaseChatBubble('assistant', '<span style="color:var(--danger)">追問失敗，請稍後再試。</span>'
          + _diseaseRefBlock([])
          + _diseaseDisclaimerBlock('此回覆由 AI 整理，僅供衛教參考；實際診療請依您的主治醫師為準。'))
      );
    })
    .then(function() { _disease.pendingMsg = false; });
}

// 從外部頁面（症狀分析）呼叫：預填疾病名稱並導向疾病百科
function navigateToDiseaseSearch(name) {
  window._diseaseSearchPrefill = name || '';
  if (typeof navigateTo === 'function') {
    navigateTo('diseaseSearch');
  } else {
    showPage('diseaseSearch');
  }
}

// ─── 提醒通知（Reminders） ─────────────────────────────────

var _remindersList = [];
var _remindersInbox = [];
var _remindersPid = null;
var _pushVapidPublicKey = null;
var _pushSubscribed = false;
var _remindersInboxTimer = null;

function reminders() {
  _remindersPid = getStablePatientId();
  var permState = (typeof Notification !== 'undefined') ? Notification.permission : 'unsupported';
  var permLabel = ({ granted: '已允許', denied: '已封鎖', default: '尚未授權', unsupported: '此瀏覽器不支援' })[permState] || permState;
  var permColor = permState === 'granted' ? '#2ecc71' : (permState === 'denied' ? '#e74c3c' : '#f39c12');
  return ''
    + '<div class="card">'
    + '  <h2><i data-lucide="bell-ring" style="width:20px;height:20px;vertical-align:middle"></i> 提醒通知</h2>'
    + '  <p style="margin-top:8px;color:var(--text-dim)">設定吃藥、回診、檢查等提醒，到時間會以站內通知或手機推播提醒你。</p>'
    + '</div>'
    + '<div class="card">'
    + '  <h3><i data-lucide="shield-check" style="width:18px;height:18px;vertical-align:middle"></i> 推播設定</h3>'
    + '  <div style="margin-top:8px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">'
    + '    <span>通知權限：<strong style="color:' + permColor + '">' + permLabel + '</strong></span>'
    + '    <span id="reminders-push-state" style="color:var(--text-dim);font-size:0.9rem">推播訂閱：載入中…</span>'
    + '  </div>'
    + '  <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">'
    + '    <button class="primary" onclick="reminderEnablePush()"><i data-lucide="bell-plus" style="width:14px;height:14px;vertical-align:middle"></i> 啟用手機推播</button>'
    + '    <button class="secondary" onclick="reminderDisablePush()"><i data-lucide="bell-off" style="width:14px;height:14px;vertical-align:middle"></i> 取消推播</button>'
    + '    <button class="secondary" onclick="reminderTestDispatch()"><i data-lucide="send" style="width:14px;height:14px;vertical-align:middle"></i> 觸發目前到期提醒</button>'
    + '  </div>'
    + '  <p style="margin-top:8px;color:var(--text-muted);font-size:0.8rem">站內通知中心永遠都會收到提醒；手機推播需要瀏覽器授權與後端 VAPID 設定。</p>'
    + '</div>'
    + '<div class="card">'
    + '  <h3><i data-lucide="plus-circle" style="width:18px;height:18px;vertical-align:middle"></i> 新增提醒</h3>'
    + '  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px">'
    + '    <label style="font-size:0.85rem;color:var(--text-dim)">類型'
    + '      <select id="rem-type" style="width:100%;padding:8px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);margin-top:4px" onchange="reminderToggleSource()">'
    + '        <option value="medication">吃藥提醒</option>'
    + '        <option value="appointment">回診/預約</option>'
    + '        <option value="lab">檢查/檢驗</option>'
    + '        <option value="custom" selected>自訂提醒</option>'
    + '      </select>'
    + '    </label>'
    + '    <label style="font-size:0.85rem;color:var(--text-dim)">重複頻率'
    + '      <select id="rem-freq" style="width:100%;padding:8px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);margin-top:4px" onchange="reminderToggleWeekly()">'
    + '        <option value="once" selected>單次</option>'
    + '        <option value="daily">每天</option>'
    + '        <option value="weekly">每週</option>'
    + '        <option value="monthly">每月</option>'
    + '      </select>'
    + '    </label>'
    + '  </div>'
    + '  <label style="font-size:0.85rem;color:var(--text-dim);display:block;margin-top:8px">標題（必填）'
    + '    <input id="rem-title" type="text" placeholder="例如：早餐後吃血壓藥" style="width:100%;padding:8px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);margin-top:4px" />'
    + '  </label>'
    + '  <label style="font-size:0.85rem;color:var(--text-dim);display:block;margin-top:8px">說明（可選）'
    + '    <textarea id="rem-body" rows="2" placeholder="例如：白色 5mg，一日一顆" style="width:100%;padding:8px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);margin-top:4px"></textarea>'
    + '  </label>'
    + '  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px">'
    + '    <label style="font-size:0.85rem;color:var(--text-dim)">首次觸發時間'
    + '      <input id="rem-when" type="datetime-local" style="width:100%;padding:8px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);margin-top:4px" />'
    + '    </label>'
    + '    <label id="rem-source-wrap" style="font-size:0.85rem;color:var(--text-dim);display:none">關聯藥物（可選）'
    + '      <select id="rem-source" style="width:100%;padding:8px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);margin-top:4px"><option value="">— 不關聯 —</option></select>'
    + '    </label>'
    + '  </div>'
    + '  <div id="rem-weekly-wrap" style="display:none;margin-top:8px">'
    + '    <div style="font-size:0.85rem;color:var(--text-dim);margin-bottom:4px">每週重複的星期</div>'
    + '    <div style="display:flex;gap:6px;flex-wrap:wrap">'
    + ['一','二','三','四','五','六','日'].map(function(label, idx) {
        return '<label style="display:inline-flex;align-items:center;gap:4px;padding:4px 8px;border:1px solid var(--border-glass);border-radius:var(--radius-sm);cursor:pointer">'
          + '<input type="checkbox" class="rem-dow" value="' + idx + '" /> ' + label + '</label>';
      }).join('')
    + '    </div>'
    + '  </div>'
    + '  <div style="margin-top:12px">'
    + '    <button class="primary" onclick="reminderSubmitNew()"><i data-lucide="save" style="width:14px;height:14px;vertical-align:middle"></i> 建立提醒</button>'
    + '  </div>'
    + '</div>'
    + '<div class="card">'
    + '  <div style="display:flex;justify-content:space-between;align-items:center">'
    + '    <h3><i data-lucide="inbox" style="width:18px;height:18px;vertical-align:middle"></i> 站內通知</h3>'
    + '    <button class="secondary" onclick="reminderMarkAllRead()" style="padding:4px 12px;font-size:0.85rem">全部標為已讀</button>'
    + '  </div>'
    + '  <div id="rem-inbox-list" style="margin-top:12px"><p style="color:var(--text-muted)">載入中…</p></div>'
    + '</div>'
    + '<div class="card">'
    + '  <div style="display:flex;justify-content:space-between;align-items:center">'
    + '    <h3><i data-lucide="list-checks" style="width:18px;height:18px;vertical-align:middle"></i> 我的提醒</h3>'
    + '    <button class="secondary" onclick="loadRemindersPage()" style="padding:4px 12px;font-size:0.85rem">重新整理</button>'
    + '  </div>'
    + '  <div id="rem-list" style="margin-top:12px"><p style="color:var(--text-muted)">載入中…</p></div>'
    + '</div>';
}

function reminderToggleSource() {
  var t = document.getElementById('rem-type').value;
  var wrap = document.getElementById('rem-source-wrap');
  var sel = document.getElementById('rem-source');
  if (!wrap || !sel) return;
  function _setOptions(opts) {
    _remClear(sel);
    opts.forEach(function(o) {
      var opt = document.createElement('option');
      opt.value = String(o.value || '');
      opt.textContent = String(o.label || '');
      sel.appendChild(opt);
    });
  }
  if (t === 'medication') {
    wrap.style.display = '';
    _setOptions([{ value: '', label: '— 不關聯 —' }]);
    fetch(API + '/medications/?patient_id=' + _remindersPid)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var meds = (data.medications || []).filter(function(m) { return m.active !== 0; });
        var opts = [{ value: '', label: '— 不關聯 —' }].concat(meds.map(function(m) {
          var label = String(m.name || '') + (m.dosage ? ' · ' + String(m.dosage) : '');
          return { value: m.id, label: label };
        }));
        _setOptions(opts);
      })
      .catch(function() { _setOptions([{ value: '', label: '（無法載入藥物清單）' }]); });
  } else {
    wrap.style.display = 'none';
    _setOptions([{ value: '', label: '— 不關聯 —' }]);
  }
}

function reminderToggleWeekly() {
  var f = document.getElementById('rem-freq').value;
  var wrap = document.getElementById('rem-weekly-wrap');
  if (wrap) wrap.style.display = (f === 'weekly') ? '' : 'none';
}

function loadRemindersPage() {
  _remindersPid = getStablePatientId();
  // 預設首次觸發時間 = 30 分鐘後
  var when = document.getElementById('rem-when');
  if (when && !when.value) {
    var d = new Date(Date.now() + 30 * 60 * 1000);
    var pad = function(n) { return ('0' + n).slice(-2); };
    when.value = d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
      + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }
  _remindersBindDelegated();
  reminderRefreshList();
  reminderRefreshInbox();
  reminderRefreshPushState();
  if (_remindersInboxTimer) clearInterval(_remindersInboxTimer);
  _remindersInboxTimer = setInterval(reminderRefreshInbox, 30000);
}

window.addEventListener('beforeunload', function() {
  if (_remindersInboxTimer) clearInterval(_remindersInboxTimer);
});

function reminderRefreshList() {
  fetch(API + '/reminders/?patient_id=' + encodeURIComponent(_remindersPid))
    .then(function(r) { return r.json(); })
    .then(function(data) {
      _remindersList = data.reminders || [];
      reminderRenderList();
    })
    .catch(function() {
      var el = document.getElementById('rem-list');
      if (el) {
        _remClear(el);
        el.appendChild(_remH('p', { style: 'color:var(--text-muted)' }, '無法載入提醒清單。'));
      }
    });
}

// 小工具：DOM 建構（避免 innerHTML 與 user-controlled 資料混合）
function _remH(tag, props, children) {
  var el = document.createElement(tag);
  if (props) {
    for (var k in props) {
      if (k === 'style') el.style.cssText = props[k];
      else if (k === 'class') el.className = props[k];
      else if (k.indexOf('data-') === 0) el.setAttribute(k, String(props[k]));
      else el[k] = props[k];
    }
  }
  if (children) {
    (Array.isArray(children) ? children : [children]).forEach(function(c) {
      if (c == null || c === false) return;
      el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
  }
  return el;
}

function _remClear(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
}

function _remindersBindDelegated() {
  var listEl = document.getElementById('rem-list');
  if (listEl && !listEl.dataset.bound) {
    listEl.dataset.bound = '1';
    listEl.addEventListener('click', function(e) {
      var btn = e.target.closest && e.target.closest('[data-action]');
      if (!btn || !listEl.contains(btn)) return;
      var id = btn.getAttribute('data-id');
      var action = btn.getAttribute('data-action');
      if (action === 'toggle') reminderToggleActive(id, btn.getAttribute('data-active') !== '1');
      else if (action === 'delete') reminderDelete(id);
    });
  }
  var inboxEl = document.getElementById('rem-inbox-list');
  if (inboxEl && !inboxEl.dataset.bound) {
    inboxEl.dataset.bound = '1';
    inboxEl.addEventListener('click', function(e) {
      var btn = e.target.closest && e.target.closest('[data-action]');
      if (!btn || !inboxEl.contains(btn)) return;
      if (btn.getAttribute('data-action') === 'mark-read') {
        reminderMarkRead(btn.getAttribute('data-id'));
      }
    });
  }
}

function reminderRenderList() {
  var el = document.getElementById('rem-list');
  if (!el) return;
  _remClear(el);
  if (!_remindersList.length) {
    el.appendChild(_remH('p', { style: 'color:var(--text-muted)' }, '還沒有提醒，先在上面建立第一筆吧。'));
    return;
  }
  var typeLabel = { medication: '吃藥', appointment: '回診', lab: '檢查', custom: '自訂' };
  var freqLabel = { once: '單次', daily: '每天', weekly: '每週', monthly: '每月' };
  _remindersList.forEach(function(r) {
    var next = r.next_fire_at ? new Date(r.next_fire_at).toLocaleString() : '—';
    var active = (r.active === true || r.active === 1);
    var typeText = typeLabel[r.reminder_type] || String(r.reminder_type || '');
    var freqText = freqLabel[r.frequency] || String(r.frequency || '');

    var titleEl = _remH('div', { style: 'font-weight:600' }, String(r.title || ''));
    var metaEl = _remH('div', { style: 'font-size:0.85rem;color:var(--text-dim);margin-top:2px' },
      typeText + ' · ' + freqText + ' · 下次：' + next + (active ? '' : ' · 已停用'));
    var leftChildren = [titleEl, metaEl];
    if (r.body) {
      leftChildren.push(_remH('div', { style: 'font-size:0.85rem;color:var(--text-dim);margin-top:4px' }, String(r.body)));
    }
    var left = _remH('div', { style: 'flex:1;min-width:0' }, leftChildren);

    var toggleBtn = _remH('button', {
      'class': 'secondary',
      style: 'padding:4px 8px;font-size:0.8rem',
      'data-action': 'toggle',
      'data-id': String(r.id || ''),
      'data-active': active ? '1' : '0',
    }, active ? '停用' : '啟用');
    var delBtn = _remH('button', {
      'class': 'secondary',
      style: 'padding:4px 8px;font-size:0.8rem;color:#c0392b',
      'data-action': 'delete',
      'data-id': String(r.id || ''),
    }, '刪除');
    var actions = _remH('div', { style: 'display:flex;flex-direction:column;gap:4px' }, [toggleBtn, delBtn]);

    var card = _remH('div', {
      style: 'padding:10px;border:1px solid var(--border-glass);border-radius:var(--radius-sm);margin-bottom:8px;display:flex;justify-content:space-between;align-items:flex-start;gap:8px',
    }, [left, actions]);
    el.appendChild(card);
  });
}

function reminderRefreshInbox() {
  fetch(API + '/reminders/inbox/list?patient_id=' + encodeURIComponent(_remindersPid) + '&limit=20')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      _remindersInbox = data.items || [];
      reminderRenderInbox(data.unread || 0);
      reminderUpdateNavBadge(data.unread || 0);
    })
    .catch(function() {
      var el = document.getElementById('rem-inbox-list');
      if (el) {
        _remClear(el);
        el.appendChild(_remH('p', { style: 'color:var(--text-muted)' }, '無法載入通知。'));
      }
    });
}

function reminderRenderInbox(unread) {
  var el = document.getElementById('rem-inbox-list');
  if (!el) return;
  _remClear(el);
  if (!_remindersInbox.length) {
    el.appendChild(_remH('p', { style: 'color:var(--text-muted)' }, '目前沒有通知。'));
    return;
  }
  var unreadNum = Number(unread || 0);
  var totalNum = Number(_remindersInbox.length);
  var summary = _remH('div', { style: 'margin-bottom:8px;font-size:0.85rem;color:var(--text-dim)' }, [
    '未讀 ',
    _remH('strong', null, String(unreadNum)),
    ' 則 / 共 ' + totalNum + ' 則',
  ]);
  el.appendChild(summary);

  _remindersInbox.forEach(function(n) {
    var isRead = (n.read === true || n.read === 1);
    var when = n.created_at ? new Date(n.created_at).toLocaleString() : '';
    var headerLeft = _remH('div', { style: 'font-weight:' + (isRead ? '500' : '600') }, String(n.title || ''));
    var headerRight = _remH('div', { style: 'font-size:0.75rem;color:var(--text-muted);white-space:nowrap' }, when);
    var header = _remH('div', { style: 'display:flex;justify-content:space-between;gap:8px' }, [headerLeft, headerRight]);
    var children = [header];
    if (n.body) {
      children.push(_remH('div', { style: 'font-size:0.85rem;color:var(--text-dim);margin-top:4px' }, String(n.body)));
    }
    if (!isRead) {
      children.push(_remH('button', {
        'class': 'secondary',
        style: 'margin-top:6px;padding:2px 8px;font-size:0.75rem',
        'data-action': 'mark-read',
        'data-id': String(n.id || ''),
      }, '標為已讀'));
    }
    var card = _remH('div', {
      style: 'padding:10px;border:1px solid var(--border-glass);border-radius:var(--radius-sm);margin-bottom:6px;background:' + (isRead ? 'transparent' : 'rgba(100,140,200,0.06)'),
    }, children);
    el.appendChild(card);
  });
}

function reminderUpdateNavBadge(unread) {
  var badge = document.getElementById('reminders-nav-badge');
  if (!badge) return;
  var n = Number(unread || 0);
  if (n > 0) {
    badge.style.display = '';
    badge.textContent = n > 99 ? '99+' : String(n);
  } else {
    badge.style.display = 'none';
  }
}

function reminderMarkRead(id) {
  fetch(API + '/reminders/inbox/' + encodeURIComponent(id), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ read: true }),
  }).then(reminderRefreshInbox);
}

function reminderMarkAllRead() {
  fetch(API + '/reminders/inbox/read-all?patient_id=' + encodeURIComponent(_remindersPid), { method: 'POST' })
    .then(reminderRefreshInbox);
}

function reminderToggleActive(id, active) {
  fetch(API + '/reminders/' + encodeURIComponent(id), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ active: !!active }),
  }).then(reminderRefreshList);
}

function reminderDelete(id) {
  if (!confirm('確定要刪除這筆提醒嗎？')) return;
  fetch(API + '/reminders/' + encodeURIComponent(id), { method: 'DELETE' })
    .then(reminderRefreshList);
}

function reminderSubmitNew() {
  var type = document.getElementById('rem-type').value;
  var freq = document.getElementById('rem-freq').value;
  var title = (document.getElementById('rem-title').value || '').trim();
  var bodyText = (document.getElementById('rem-body').value || '').trim();
  var whenStr = document.getElementById('rem-when').value;
  if (!title) { alert('請填寫提醒標題'); return; }
  if (!whenStr) { alert('請選擇首次觸發時間'); return; }
  var whenIso = new Date(whenStr).toISOString();
  var dow = [];
  if (freq === 'weekly') {
    document.querySelectorAll('.rem-dow:checked').forEach(function(cb) { dow.push(parseInt(cb.value, 10)); });
    if (!dow.length) { alert('每週重複請至少勾一個星期'); return; }
  }
  var sourceId = (type === 'medication') ? (document.getElementById('rem-source').value || null) : null;
  var payload = {
    patient_id: _remindersPid,
    reminder_type: type,
    title: title,
    body: bodyText || null,
    source_id: sourceId,
    frequency: freq,
    days_of_week: dow.length ? dow : null,
    scheduled_at: whenIso,
    active: true,
  };
  fetch(API + '/reminders/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
    .then(function(r) { if (!r.ok) throw new Error('http ' + r.status); return r.json(); })
    .then(function() {
      document.getElementById('rem-title').value = '';
      document.getElementById('rem-body').value = '';
      reminderRefreshList();
    })
    .catch(function(e) { alert('建立失敗：' + e.message); });
}

function reminderTestDispatch() {
  fetch(API + '/reminders/dispatch?patient_id=' + encodeURIComponent(_remindersPid), { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      alert('已派發：' + (data.dispatched || 0) + ' 則（push 成功 ' + (data.push_ok || 0) + ' / 失敗 ' + (data.push_fail || 0) + '）');
      reminderRefreshInbox();
      reminderRefreshList();
    })
    .catch(function() { alert('派發失敗'); });
}

// ─── Push subscription ────────────────────────────────────

function reminderRefreshPushState() {
  var el = document.getElementById('reminders-push-state');
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    if (el) el.textContent = '推播訂閱：此瀏覽器不支援 Web Push';
    return;
  }
  navigator.serviceWorker.ready.then(function(reg) {
    return reg.pushManager.getSubscription();
  }).then(function(sub) {
    _pushSubscribed = !!sub;
    if (el) el.textContent = '推播訂閱：' + (_pushSubscribed ? '已啟用' : '未啟用');
  });
}

function _urlBase64ToUint8Array(base64String) {
  var padding = '='.repeat((4 - base64String.length % 4) % 4);
  var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  var raw = atob(base64);
  var out = new Uint8Array(raw.length);
  for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

function reminderEnablePush() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    alert('此瀏覽器不支援 Web Push');
    return;
  }
  Notification.requestPermission().then(function(perm) {
    if (perm !== 'granted') { alert('需要允許通知才能啟用推播'); return; }
    fetch(API + '/reminders/push/config')
      .then(function(r) { return r.json(); })
      .then(function(cfg) {
        if (!cfg.vapid_public_key) {
          alert('伺服器尚未設定 VAPID 公鑰；站內通知仍可正常使用。');
          return;
        }
        _pushVapidPublicKey = cfg.vapid_public_key;
        return navigator.serviceWorker.ready.then(function(reg) {
          return reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: _urlBase64ToUint8Array(cfg.vapid_public_key),
          });
        }).then(function(sub) {
          var json = sub.toJSON();
          return fetch(API + '/reminders/push/subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              patient_id: _remindersPid,
              endpoint: json.endpoint,
              p256dh: json.keys.p256dh,
              auth: json.keys.auth,
              user_agent: navigator.userAgent.slice(0, 200),
            }),
          });
        }).then(function() {
          _pushSubscribed = true;
          reminderRefreshPushState();
          alert('已啟用手機推播。');
        });
      })
      .catch(function(e) { alert('啟用推播失敗：' + (e && e.message || e)); });
  });
}

function reminderDisablePush() {
  if (!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.ready.then(function(reg) {
    return reg.pushManager.getSubscription();
  }).then(function(sub) {
    if (!sub) { alert('目前未啟用推播'); return; }
    var endpoint = sub.endpoint;
    return sub.unsubscribe().then(function() {
      return fetch(API + '/reminders/push/subscribe?endpoint=' + encodeURIComponent(endpoint), { method: 'DELETE' });
    });
  }).then(function() {
    _pushSubscribed = false;
    reminderRefreshPushState();
    alert('已取消推播。');
  });
}

// 在 SW 收到推播點擊時，把使用者帶到提醒頁
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.addEventListener('message', function(e) {
    if (e.data && e.data.type === 'mdpiece-notification-click') {
      if (typeof navigateTo === 'function') navigateTo('reminders');
    }
  });
}

// 全域：登入後或 app 啟動時，背景同步未讀數
function reminderBackgroundSync() {
  try {
    var pid = (typeof getStablePatientId === 'function') ? getStablePatientId() : null;
    if (!pid) return;
    // 同步前先觸發伺服器派發（命中本帳號的到期 reminder）
    fetch(API + '/reminders/dispatch?patient_id=' + encodeURIComponent(pid), { method: 'POST' })
      .catch(function() {})
      .finally(function() {
        fetch(API + '/reminders/inbox/list?patient_id=' + encodeURIComponent(pid) + '&unread_only=true&limit=1')
          .then(function(r) { return r.json(); })
          .then(function(data) { reminderUpdateNavBadge(data.unread || 0); })
          .catch(function() {});
      });
  } catch {}
}

setTimeout(reminderBackgroundSync, 4000);
setInterval(reminderBackgroundSync, 5 * 60 * 1000);

// ─── Service Worker ───────────────────────────────────────

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}

showPage("home");

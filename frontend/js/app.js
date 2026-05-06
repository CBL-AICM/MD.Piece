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

function escHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>');
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
  return `
    <div class="card memo-hero">
      <h2 style="display:flex;align-items:center;gap:8px">
        <i data-lucide="sticky-note" style="width:22px;height:22px"></i> Memo
      </h2>
      <p style="margin-top:6px;color:var(--text-dim)">
        隨手拍下症狀、藥袋、傷口；或寫下下次門診要跟醫師說的話。所有 memo 都存在這台裝置上。
      </p>
    </div>

    <div class="card memo-quick">
      <button class="memo-quick-btn memo-quick-photo" onclick="memoStartPhoto()">
        <i data-lucide="camera" style="width:24px;height:24px"></i>
        <div>
          <strong>拍張照片</strong>
          <small>症狀、藥袋、傷口、皮疹…</small>
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
  // 開啟系統相機 / 檔案選擇器
  var input = document.getElementById("memo-photo-input");
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
  memos.unshift({
    id: "m_" + Date.now() + "_" + Math.random().toString(36).slice(2, 6),
    type: _memoStagedPhoto ? "photo" : "text",
    photo: _memoStagedPhoto || null,
    text: text,
    forDoctor: !!forDoctor,
    createdAt: new Date().toISOString()
  });
  memoSaveAll(memos);
  memoCancelCompose();
  memoRenderList();
  showToast("已儲存", "success");
}

function memoDelete(id) {
  if (!confirm("確定要刪除這則 memo？")) return;
  var memos = memoLoad().filter(function(m) { return m.id !== id; });
  memoSaveAll(memos);
  memoRenderList();
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
          '<button class="memo-del" onclick="memoDelete(\'' + m.id + '\')" title="刪除">' +
            '<i data-lucide="trash-2" style="width:14px;height:14px"></i>' +
          '</button>' +
        '</div>' +
        '<div class="memo-item-body">' + bodyHtml + '</div>' +
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

function previsit() {
  return ''
    + '<section class="pv-page">'
    + '  <header class="pv-header">'
    + '    <div>'
    + '      <p class="pv-eyebrow">// previsit &gt; pre_consultation_report</p>'
    + '      <h2 class="pv-title"><i data-lucide="clipboard-check"></i> 診前報告</h2>'
    + '      <p class="pv-sub">看診前 30 秒讀完：AI 幫你整理近 30 天的症狀、情緒、用藥與就診紀錄，並列出這次門診最該問的三件事。</p>'
    + '    </div>'
    + '    <div class="pv-actions-top">'
    + '      <button class="pv-btn pv-btn-ghost" onclick="previsitReload()" title="重新生成">'
    + '        <i data-lucide="refresh-cw"></i> 重新生成'
    + '      </button>'
    + '      <button class="pv-btn pv-btn-ghost" onclick="previsitDownload(\'pdf\')" title="下載 PDF（會開啟列印視窗，請選擇「另存為 PDF」）">'
    + '        <i data-lucide="file-down"></i> 下載 PDF'
    + '      </button>'
    + '      <button class="pv-btn pv-btn-ghost" onclick="previsitDownload(\'doc\')" title="下載 Word（.doc）">'
    + '        <i data-lucide="file-text"></i> 下載 Word'
    + '      </button>'
    + '      <button class="pv-btn pv-btn-primary" onclick="previsitCopy()" title="複製為純文字帶去診間">'
    + '        <i data-lucide="clipboard-copy"></i> 複製給醫師'
    + '      </button>'
    + '    </div>'
    + '  </header>'
    + ''
    + '  <section class="pv-section pv-checklist">'
    + '    <h3 class="pv-section-title"><i data-lucide="list-checks"></i> 這次最該問醫師的三件事</h3>'
    + '    <ol id="pv-checklist-list" class="pv-checklist-list">'
    + '      <li class="pv-loading"><i data-lucide="loader" class="pv-spin"></i> AI 整理中…</li>'
    + '    </ol>'
    + '    <p class="pv-source" id="pv-checklist-source"></p>'
    + '  </section>'
    + ''
    + '  <section class="pv-section pv-report">'
    + '    <h3 class="pv-section-title"><i data-lucide="file-text"></i> 30 天健康摘要</h3>'
    + '    <div class="pv-stats" id="pv-stats"></div>'
    + '    <div id="pv-report-body" class="pv-report-body">'
    + '      <p class="pv-loading"><i data-lucide="loader" class="pv-spin"></i> AI 撰寫中…</p>'
    + '    </div>'
    + '    <p class="pv-source" id="pv-report-source"></p>'
    + '  </section>'
    + ''
    + '  <p class="pv-disclaimer"><i data-lucide="info"></i> 本報告由 AI 整理你輸入的紀錄，僅供與醫師溝通參考，不取代醫師診斷。</p>'
    + '</section>'
    + pushHubBlock();
}

// ─── 診前報告 (Pre-consultation Report) ──────────────────────

var _previsitData = { checklist: null, report: null };

function loadPrevisitPage() {
  if (typeof lucide !== 'undefined') lucide.createIcons();
  var pid = (typeof getStablePatientId === 'function') ? getStablePatientId() : null;
  if (!pid) return;

  _previsitData = { checklist: null, report: null };

  fetch(API + '/reports/' + encodeURIComponent(pid) + '/checklist')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      _previsitData.checklist = data;
      previsitRenderChecklist(data);
    })
    .catch(function() {
      previsitRenderChecklistError();
    });

  fetch(API + '/reports/' + encodeURIComponent(pid) + '/monthly')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      _previsitData.report = data;
      previsitRenderReport(data);
    })
    .catch(function() {
      previsitRenderReportError();
    });

  // 載入「推送給醫師」區塊（醫師清單 + 推送歷史）
  if (typeof loadPushHubBlock === 'function') loadPushHubBlock();
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
  var srcLabel = src === 'ai' ? 'AI 生成'
    : src === 'default' ? '預設提示（紀錄不足）'
    : src === 'no_data' ? '紀錄不足'
    : src;
  return when ? (srcLabel + ' · ' + when) : srcLabel;
}

function previsitReload() {
  var listEl = document.getElementById('pv-checklist-list');
  var bodyEl = document.getElementById('pv-report-body');
  if (listEl) listEl.innerHTML = '<li class="pv-loading"><i data-lucide="loader" class="pv-spin"></i> AI 整理中…</li>';
  if (bodyEl) bodyEl.innerHTML = '<p class="pv-loading"><i data-lucide="loader" class="pv-spin"></i> AI 撰寫中…</p>';
  if (typeof lucide !== 'undefined') lucide.createIcons();
  loadPrevisitPage();
}

function previsitCopy() {
  var d = _previsitData || {};
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
  lines.push('▍30 天健康摘要');
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

// 下載 PDF / Word：先抓 patient-summary（300–500 字白話摘要），
// 再用 HTML 包成可列印的版面 → PDF 走 window.print()，Word 走 .doc Blob
function previsitDownload(format) {
  var pid = (typeof getStablePatientId === 'function') ? getStablePatientId() : null;
  if (!pid) {
    if (typeof showToast === 'function') showToast('找不到使用者，請先登入', 'warning');
    return;
  }
  if (typeof showToast === 'function') showToast('AI 撰寫中，請稍候…', 'info');

  fetch(API + '/reports/' + encodeURIComponent(pid) + '/patient-summary')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var summary = (data && data.summary) || '（暫無摘要）';
      var counts = (data && data.raw_data) || {};
      var checklist = (_previsitData && _previsitData.checklist && _previsitData.checklist.checklist) || [];
      var html = previsitBuildPrintableHTML(summary, counts, checklist);
      if (format === 'doc') {
        previsitDownloadDoc(html);
      } else {
        previsitOpenPrint(html);
      }
    })
    .catch(function() {
      if (typeof showToast === 'function') showToast('產生報告失敗，請稍後再試', 'error');
    });
}

function previsitBuildPrintableHTML(summary, counts, checklist) {
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
    + '<title>MD.Piece 診前報告 ' + dateStr + '</title>'
    + '<style>'
    + '  @page { size: A4; margin: 18mm 16mm; }'
    + '  body { font-family: "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif; color: #222; line-height: 1.75; font-size: 14px; }'
    + '  h1 { font-size: 22px; margin: 0 0 4px; }'
    + '  .meta { color: #666; font-size: 12px; margin-bottom: 18px; }'
    + '  h2 { font-size: 15px; margin: 22px 0 8px; padding-bottom: 4px; border-bottom: 1px solid #ddd; color: #2a5d8f; }'
    + '  p { margin: 0 0 10px; }'
    + '  ol { padding-left: 22px; margin: 0; }'
    + '  ol li { margin-bottom: 6px; }'
    + '  table.stats { width: 100%; border-collapse: collapse; margin: 6px 0 4px; }'
    + '  table.stats td { width: 25%; text-align: center; padding: 8px 4px; border: 1px solid #e2e2e2; background: #f7f9fc; }'
    + '  table.stats td strong { display: block; font-size: 18px; color: #2a5d8f; }'
    + '  table.stats td span { font-size: 11px; color: #666; }'
    + '  .footer { margin-top: 28px; padding-top: 10px; border-top: 1px dashed #ccc; font-size: 11px; color: #888; }'
    + '</style></head><body>'
    + '<h1>診前報告</h1>'
    + '<div class="meta">產出日期：' + dateStr + ' · 由 MD.Piece 整理過去 30 天的紀錄</div>'
    + '<h2>近 30 天紀錄概覽</h2>'
    + statsHtml
    + '<h2>給醫師的話（患者整理）</h2>'
    + paragraphs
    + '<h2>這次想請醫師確認的事</h2>'
    + checklistHtml
    + '<div class="footer">本報告由 AI 整理患者自行輸入的紀錄，僅供醫病溝通參考，不取代醫師診斷。</div>'
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

function previsitDownloadDoc(html) {
  // Word 可以直接讀 HTML，副檔名用 .doc + application/msword
  var blob = new Blob(['﻿', html], { type: 'application/msword' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = 'MD.Piece-診前報告-' + new Date().toISOString().slice(0, 10) + '.doc';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
  if (typeof showToast === 'function') showToast('已開始下載 Word 檔', 'success');
}

function labs() {
  return `
    <div class="card labs-hero">
      <h2 style="display:flex;align-items:center;gap:8px">
        <i data-lucide="trending-up" style="width:22px;height:22px"></i> 報告數值
      </h2>
      <p style="margin-top:6px;color:var(--text-dim)">
        輸入任何檢驗項目（血液、肝腎、免疫、罕見值都可以），AI 會告訴你正常範圍、是否異常、生活建議。<strong>結果僅供參考，不取代醫師判讀。</strong>
      </p>
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
  pieces: 'your-pieces', account: 'account',
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
    home, symptoms, doctors, records, medications, education,
    vitals, emotions, memo, previsit, story, labs, pieces, account, settings, diet
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
    if (page === "previsit") loadPrevisitPage();
    if (page === "emotions") loadEmotionsPage();
    if (page === "diet") loadDietPage();
    if (page === "account") loadAccountPage();
    if (page === "settings") loadSettingsPage();
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

function selectAuthRole(role) {
  _authRole = role;
  document.querySelectorAll('.auth-role-btn[data-role]').forEach(b => {
    b.classList.toggle('selected', b.dataset.role === role);
  });
  const field = document.getElementById('reg-doctor-key-field');
  if (field) field.hidden = role !== 'doctor';
}

function selectLoginRole(role) {
  _loginRole = role;
  document.querySelectorAll('.auth-role-btn[data-login-role]').forEach(b => {
    b.classList.toggle('selected', b.dataset.loginRole === role);
  });
  const field = document.getElementById('login-doctor-key-field');
  if (field) field.hidden = role !== 'doctor';
  document.getElementById('login-error').hidden = true;
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
  const doctor_key = document.getElementById('login-doctor-key').value.trim();
  if (!username || !password) return;
  if (_loginRole === 'doctor' && !doctor_key) {
    showAuthError('login', '請輸入醫師通行碼');
    return;
  }
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
      body: JSON.stringify({
        username, password,
        doctor_key: _loginRole === 'doctor' ? doctor_key : null,
      })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const detail = err.detail || '登入失敗';
      if (detail.indexOf('醫師') >= 0 && detail.indexOf('通行碼') >= 0) {
        if (_loginRole !== 'doctor') selectLoginRole('doctor');
        showAuthError('login', '此帳號為醫師身份，請輸入醫師通行碼');
        const keyInput = document.getElementById('login-doctor-key');
        if (keyInput) { keyInput.focus(); keyInput.select(); }
        btn.disabled = false;
        btn.innerHTML = original;
        if (typeof lucide !== 'undefined') lucide.createIcons();
        return;
      }
      throw new Error(detail);
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

  const doctor_key = document.getElementById('reg-doctor-key').value.trim();
  if (_authRole === 'doctor' && !doctor_key) {
    showAuthError('register', '請輸入醫師通行碼');
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
    role: _authRole,
    avatar_url: _regAvatarDataUrl || null,
    doctor_key: _authRole === 'doctor' ? doctor_key : null,
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
  if (user.role === 'doctor') {
    try { localStorage.setItem('mdp.doctorUser', JSON.stringify(user)); } catch {}
    try { localStorage.removeItem('mdpiece_user'); } catch {}
    window.location.assign('/doctor/');
    return;
  }
  setCurrentUser(user);
  const overlay = document.getElementById('register-overlay');
  overlay.classList.remove('show');
  setTimeout(() => {
    overlay.style.display = 'none';
    document.getElementById('app-wrapper').classList.add('show');
    showPage('home');
    if (typeof lucide !== 'undefined') lucide.createIcons();
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
  return ''
    + '<button type="button" class="' + cls + '" onclick="openNextVisitEditor()" title="' + _T('home.visit.editTitle') + '">'
    +   '<i data-lucide="calendar-check-2" style="width:14px;height:14px"></i>'
    +   '<span>' + _T('home.visit.label') + ' ' + pretty + '</span>'
    +   '<span class="home-visit-countdown">' + label + '</span>'
    + '</button>'
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
            <i data-lucide="smile" style="width:16px;height:16px;color:var(--rose, #e8889c)"></i>
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
        ${homeCard('records','id-card',_T('home.card.records.title'),_T('home.card.records.desc'),'purple')}
        ${homeCard('doctors','stethoscope',_T('home.card.doctors.title'),_T('home.card.doctors.desc'),'rose')}
        ${homeCard('medications','pill',_T('home.card.medications.title'),_T('home.card.medications.desc'),'amber')}
        ${homeCard('education','book-heart',_T('home.card.education.title'),_T('home.card.education.desc'),'teal')}
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

  fetch(API + '/medications/?patient_id=' + pid)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var el = document.getElementById('home-med-summary');
      if (!el) return;
      var meds = (data.medications || []).filter(function(m) { return m.active !== 0; });
      if (!meds.length) {
        el.innerHTML = '<p class="home-ov-empty">' + _T('home.med.empty') + '</p>';
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

      <section class="term-section">
        <header class="ts-head">
          <span class="ts-prompt">$ status</span>
          <span class="ts-tag">period_summary</span>
        </header>
        <div class="ts-body">
          <div class="ts-stat-grid">
            <div class="ts-stat">
              <span class="ts-stat-label">// ${_T('sym.stat.days')}</span>
              <span class="ts-stat-num">${periodDays}</span>
              <span class="ts-stat-unit">days</span>
            </div>
            <div class="ts-stat">
              <span class="ts-stat-label">// ${_T('sym.stat.logged')}</span>
              <span class="ts-stat-num">${totalCount}</span>
              <span class="ts-stat-unit">${_T('sym.stat.times')}</span>
            </div>
            <div class="ts-stat">
              <span class="ts-stat-label">// ${_T('sym.stat.top')}</span>
              <span class="ts-stat-num sm">${topCat ? _symField(topCat, 'zh') : '—'}</span>
              <span class="ts-stat-unit">${topCat ? topCount + ' ' + _T('sym.stat.times') : _T('sym.stat.empty')}</span>
            </div>
            <div class="ts-stat">
              <span class="ts-stat-label">// ${_T('sym.stat.nextVisit')}</span>
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
          <span class="ts-prompt">$ ./record-symptom</span>
          <span class="ts-tag">choose_category</span>
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
                <span class="scc-del" onclick="event.stopPropagation(); removeCustomSymptomCatAndRefresh('${c.id}')" title="${_T('sym.card.custom.delTitle')}">×</span>
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
          <span class="ts-prompt">$ ./log-entry</span>
          <span class="ts-tag" id="logform-cat-tag">—</span>
        </header>
        <div class="ts-body" id="logform-body"></div>
      </section>

      <section class="term-section">
        <header class="ts-head">
          <span class="ts-prompt">$ tail -f today.log</span>
          <span class="ts-tag">${_Tf('sym.today.tag', { n: todayEntries.length })}</span>
        </header>
        <div class="ts-body">
          ${todayEntries.length === 0 ? `
            <p class="sym-empty">${_T('sym.today.empty')}</p>
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
          <span class="ts-prompt">$ summary --period last_${periodDays}_days</span>
          <span class="ts-tag">accumulated</span>
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
  const latestAcross = getVitalEntries().sort((a,b) => new Date(b.recordedAt) - new Date(a.recordedAt))[0];
  const lastUpdate = latestAcross ? new Date(latestAcross.recordedAt) : null;
  const lastUpdateStr = lastUpdate ? `${(lastUpdate.getMonth()+1)}/${lastUpdate.getDate()} ${lastUpdate.toTimeString().slice(0,5)}` : '—';

  return `
    <div class="sym-page">

      <section class="term-section">
        <header class="ts-head">
          <span class="ts-prompt">$ status</span>
          <span class="ts-tag">vitals_overview</span>
        </header>
        <div class="ts-body">
          <div class="ts-stat-grid">
            <div class="ts-stat">
              <span class="ts-stat-label">// 追蹤中</span>
              <span class="ts-stat-num">${trackedMetrics.length}</span>
              <span class="ts-stat-unit">項指標</span>
            </div>
            <div class="ts-stat">
              <span class="ts-stat-label">// 總紀錄</span>
              <span class="ts-stat-num">${totalEntries}</span>
              <span class="ts-stat-unit">筆</span>
            </div>
            <div class="ts-stat">
              <span class="ts-stat-label">// 自訂指標</span>
              <span class="ts-stat-num">${getCustomMetrics().length}</span>
              <span class="ts-stat-unit">項</span>
            </div>
            <div class="ts-stat">
              <span class="ts-stat-label">// 上次更新</span>
              <span class="ts-stat-num sm">${lastUpdateStr}</span>
              <span class="ts-stat-unit">${lastUpdate ? '已記錄' : '尚無紀錄'}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="term-section">
        <header class="ts-head">
          <span class="ts-prompt">$ ./track --setup</span>
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
                  ${m.custom ? `<button class="vt-cm-del" onclick="deleteCustomMetricAndRefresh(event,'${m.id}')" title="刪除自訂">×</button>` : ''}
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
          <span class="ts-prompt">$ ./record</span>
          <span class="ts-tag" id="vt-logform-tag">—</span>
        </header>
        <div class="ts-body" id="vt-logform-body"></div>
      </section>

      <section class="term-section">
        <header class="ts-head">
          <span class="ts-prompt">$ snapshot</span>
          <span class="ts-tag">latest_per_metric</span>
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
          <span class="ts-prompt">$ tail -n 30 vitals.log</span>
          <span class="ts-tag">history</span>
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
  if (!name) { alert('請輸入指標名稱'); return; }
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
  if (!v1) { alert('請輸入數值'); return; }
  const entry = {
    id: 'vt-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8),
    metricId,
    value: parseFloat(v1),
    recordedAt: new Date().toISOString()
  };
  if (m.dual) {
    const v2 = document.getElementById('vt-val2').value;
    if (!v2) { alert('請完整輸入收縮 / 舒張壓'); return; }
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
          <textarea id="bi-allergies" rows="2" placeholder="${_T('rec.placeholder.allergies')}">${v('allergies')}</textarea>
        </label>
        <label class="bi-field">
          <span>${_T('rec.field.conditions')}</span>
          <textarea id="bi-conditions" rows="2" placeholder="${_T('rec.placeholder.conditions')}">${v('conditions')}</textarea>
        </label>
        <label class="bi-field">
          <span>${_T('rec.field.currentDisease')}</span>
          <textarea id="bi-current-disease" rows="2" placeholder="${_T('rec.placeholder.currentDisease')}">${v('current_disease')}</textarea>
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
  fetch(API + "/medications/?patient_id=" + _medsPatientId)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      _medsList = (data.medications || []).filter(function(m) { return m.active !== 0; });
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
    el.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:20px">' + _T('meds.list.empty') + '</p>';
    return;
  }

  var buckets = _bucketMeds(_medsList);
  var html = '<div class="med-slots">';

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
        '<button class="med-card-mini" onclick="logMedTaken(\'' + med.id + '\',false)" title="' + _T('meds.card.skipTitle') + '">✗</button>' +
        '<button class="med-card-mini" onclick="showEffectForm(\'' + med.id + '\',\'' + safeName + '\')" title="' + _T('meds.card.effectTitle') + '">★</button>' +
      '</div>' +
    '</button>'
  );
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
    var dataUrl = prepared.dataUrl;
    var mediaType = prepared.mediaType;
    var base64Data = dataUrl.split(",")[1];

    document.getElementById("med-photo-preview").innerHTML =
      '<img src="' + dataUrl + '" style="max-width:100%;max-height:240px;border-radius:var(--radius-sm);border:1px solid var(--border-glass)" />' +
      '<div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px">' +
      '已壓縮為 ' + (Math.round(base64Data.length * 0.75 / 1024)) + ' KB，' +
      '若辨識仍失敗，可改用手動填寫。</div>';
    document.getElementById("med-recognize-result").innerHTML =
      '<div style="text-align:center;padding:16px;color:var(--text-muted)">' +
      '<div class="loading-spinner"></div>' +
      '<p style="margin-top:8px">AI 正在辨識藥袋／藥單...</p>' +
      '<p style="margin-top:4px;font-size:0.75rem;opacity:0.7">第一次辨識較慢，最多約 30 秒</p>' +
      '</div>';

    fetch(API + "/medications/recognize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ patient_id: _medsPatientId, image_base64: base64Data, media_type: mediaType })
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

        // 沒辨識出任何藥；把每個 vision provider 的失敗訊息一併秀出，方便排查
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

  // 確保 lucide icon 出現
  if (typeof lucide !== 'undefined') setTimeout(function() { lucide.createIcons(); }, 30);
}

// ── 精選文章（GitHub 審稿過的 Markdown 文章）──────────────
var _eduArticles = {};            // slug -> card / full article
var _eduArticleByIcd10Dim = {};   // "I10:disease_awareness" -> slug

function loadFeaturedArticles() {
  var el = document.getElementById("edu-featured-list");
  // 抓全部文章建索引（給書本章節對照用），再過濾出 featured 顯示在卡片區
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

      if (!el) return;
      var featured = arts.filter(function(a) { return a.featured; }).slice(0, 6);
      if (!featured.length) {
        el.innerHTML = '<div style="color:var(--text-dim);font-size:.85rem">尚無精選文章。</div>';
        return;
      }
      el.innerHTML = featured.map(function(a) {
        var tagHtml = (a.tags || []).slice(0, 3).map(function(t) {
          return '<span style="display:inline-block;padding:2px 8px;border-radius:10px;background:var(--bg-soft);font-size:.72rem;color:var(--text-dim);margin-right:4px">' + escapeHtml(t) + '</span>';
        }).join("");
        return '<button class="article-card" onclick="eduOpenArticle(\'' + escapeHtml(a.slug) + '\')" ' +
               'style="text-align:left;padding:12px;border-radius:10px;border:1px solid var(--border);background:var(--bg-card);cursor:pointer;display:flex;flex-direction:column;gap:6px">' +
               '<div style="font-weight:600;line-height:1.4">' + escapeHtml(a.title) + '</div>' +
               (a.summary ? '<div style="font-size:.82rem;color:var(--text-dim);line-height:1.5">' + escapeHtml(a.summary) + '</div>' : '') +
               (tagHtml ? '<div style="margin-top:4px">' + tagHtml + '</div>' : '') +
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
  var sources = (article.sources || []).map(function(s) {
    return '<li style="margin-bottom:6px;line-height:1.5;font-size:.85rem">' + escapeHtml(s) + '</li>';
  }).join("");
  var tags = (article.tags || []).map(function(t) {
    return '<span style="display:inline-block;padding:3px 9px;border-radius:10px;background:var(--bg-soft);font-size:.75rem;color:var(--text-dim);margin:2px">' + escapeHtml(t) + '</span>';
  }).join("");
  var leftHtml =
    '<div class="nb-heading"><i data-lucide="bookmark" style="width:20px;height:20px"></i> 文章資訊</div>' +
    (article.summary ? '<div class="nb-subtle" style="line-height:1.6">' + escapeHtml(article.summary) + '</div>' : '') +
    (tags ? '<div style="margin-top:12px">' + tags + '</div>' : '') +
    (sources ? '<div style="margin-top:18px">' +
       '<div style="font-size:.85rem;font-weight:600;margin-bottom:8px;color:var(--text-dim)">參考來源</div>' +
       '<ol style="padding-left:20px;color:var(--text-dim)">' + sources + '</ol>' +
       '</div>' : '') +
    (article.reviewed_at ? '<div style="margin-top:16px;font-size:.75rem;color:var(--text-dim)">最後審稿：' + escapeHtml(article.reviewed_at) + '</div>' : '');

  var rightInner = (body == null)
    ? '<div class="nb-empty" style="padding:30px">內容載入中…</div>'
    : '<div style="line-height:1.85">' + markdownToHtml(body) + '</div>';

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
    '<div style="font-size:.94rem;line-height:1.85">' + markdownToHtml(article.body || "") + '</div>' +
    sourcesBlock +
    reviewedBlock;

  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function eduFallbackContent(book, label) {
  return '' +
    '<h3>' + escapeHtml(book.title) + '：' + escapeHtml(label) + '</h3>' +
    '<p>這一頁正在編寫中——之後會由 AI 根據最新文獻自動填上溫暖、易懂的內容。</p>' +
    '<p>在那之前，你可以：</p>' +
    '<ul>' +
      '<li>回到書架挑另一本書，先看看其他主題。</li>' +
      '<li>把你想知道的細節寫進「醫療 Chat」，由 AI 直接回答。</li>' +
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
      if (typeof showToast === 'function') showToast('複製失敗，請手動選取', 'error');
      console.log(text);
    });
  } else {
    console.log(text);
    if (typeof showToast === 'function') showToast('已輸出到 console', 'success');
  }
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
  var ac   = (user && user.avatar_color) ? user.avatar_color : '#C97F4B';

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
    alert('請輸入檢驗項目與數值');
    return;
  }

  const resultEl = document.getElementById('lab-result');
  resultEl.style.display = 'block';
  resultEl.innerHTML = '<p class="labs-loading"><i data-lucide="loader" class="labs-spin"></i> AI 解讀中…</p>';
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


// ─── 診前報告 / 推送給醫師 ─────────────────────────────────
// 患者把近期紀錄推送給醫師端：使用既有 /doctor-notes/ 表，
// tags = ["patient_push", <category>]，doctor_id 留空（任一醫師可看）

var PUSH_CATS = [
  { key: 'symptoms', label: '症狀記錄', icon: 'scan-search', desc: '近 7 天的症狀分析與打卡' },
  { key: 'medications', label: '用藥情況', icon: 'pill', desc: '使用中的藥物 + 服藥率' },
  { key: 'emotions', label: '情緒電力', icon: 'battery-charging', desc: '近 7 天每日情緒電量' },
  { key: 'vitals', label: '生理紀錄', icon: 'activity', desc: '近期血壓、血糖、體重等' },
  { key: 'labs', label: '檢驗報告', icon: 'trending-up', desc: '近期檢驗值與 AI 解讀' },
];

function getMyDoctor() {
  try { return JSON.parse(localStorage.getItem('mdpiece_my_doctor')) || null; }
  catch { return null; }
}
function setMyDoctor(d) {
  if (d) localStorage.setItem('mdpiece_my_doctor', JSON.stringify(d));
  else localStorage.removeItem('mdpiece_my_doctor');
}

// 推送給醫師區塊 — 注入在 main 的 previsit() 頁面尾巴
function pushHubBlock() {
  return (
    '<section class="previsit-wrap" style="margin-top:24px">' +
      '<header class="previsit-head">' +
        '<h2><i data-lucide="send" style="width:22px;height:22px"></i> 推送給醫師</h2>' +
        '<p>把近一週的紀錄推給主治醫師，他在醫師端就能看到你特別想他注意的事情。</p>' +
      '</header>' +
      '<div class="previsit-doctor-row" id="previsit-doctor-row">載入醫師清單中…</div>' +
      '<div class="previsit-grid">' +
        PUSH_CATS.map(function(c) {
          return '<div class="previsit-card" id="push-card-' + c.key + '">' +
            '<div class="previsit-card-head">' +
              '<i data-lucide="' + c.icon + '" style="width:20px;height:20px"></i>' +
              '<div>' +
                '<h3>' + c.label + '</h3>' +
                '<p>' + c.desc + '</p>' +
              '</div>' +
            '</div>' +
            '<button class="previsit-push-btn" onclick="pushCategoryToDoctor(\'' + c.key + '\')">' +
              '<i data-lucide="send" style="width:14px;height:14px"></i> 推送給醫師' +
            '</button>' +
            '<div class="previsit-status" id="push-status-' + c.key + '"></div>' +
          '</div>';
        }).join('') +
      '</div>' +
      '<div class="previsit-message">' +
        '<h3><i data-lucide="message-square" style="width:18px;height:18px"></i> 想跟醫師說的話</h3>' +
        '<textarea id="push-custom-text" rows="3" placeholder="例如：這週副作用比較明顯，希望可以調整劑量…"></textarea>' +
        '<button class="previsit-push-btn" onclick="pushCustomMessageToDoctor()">' +
          '<i data-lucide="send" style="width:14px;height:14px"></i> 送出留言' +
        '</button>' +
        '<div class="previsit-status" id="push-status-message"></div>' +
      '</div>' +
      '<div class="previsit-disclaimer">' +
        '⚠ 推送的資料會出現在醫師端「患者推送」面板，僅供您的主治醫師臨床參考；' +
        'MD.Piece 為 AI 輔助工具，不可作為診斷或醫療依據。' +
      '</div>' +
    '</section>'
  );
}

function _pushSetStatus(key, text, type) {
  var el = document.getElementById('push-status-' + key);
  if (!el) return;
  el.textContent = text;
  el.className = 'previsit-status ' + (type ? 'previsit-status-' + type : '');
}

async function pushCategoryToDoctor(cat) {
  var pid = getStablePatientId();
  if (!pid) { showToast('請先登入', 'warning'); return; }
  _pushSetStatus(cat, '收集資料中…', 'loading');
  try {
    var summary = await _buildCategorySummary(cat, pid);
    if (!summary) {
      _pushSetStatus(cat, '近 7 天沒有資料可推送', 'warning');
      return;
    }
    var myDr = getMyDoctor();
    var tags = ['patient_push', cat];
    if (myDr && myDr.id) tags.push('dr_' + myDr.id);
    await fetch(API + '/doctor-notes/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-User-Id': pid },
      body: JSON.stringify({
        patient_id: pid,
        doctor_id: myDr ? myDr.id : null,
        content: summary,
        tags: tags,
      }),
    }).then(function(r) {
      if (!r.ok) throw new Error('推送失敗');
    });
    _pushSetStatus(cat, '✓ 已推送，剛剛 ' + new Date().toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' }), 'ok');
    showToast('已推送 ' + (PUSH_CATS.find(function(c) { return c.key === cat; }) || {}).label + ' 給醫師', 'success');
  } catch (e) {
    _pushSetStatus(cat, '推送失敗：' + (e.message || ''), 'error');
  }
}

async function pushCustomMessageToDoctor() {
  var pid = getStablePatientId();
  if (!pid) { showToast('請先登入', 'warning'); return; }
  var ta = document.getElementById('push-custom-text');
  var text = (ta && ta.value || '').trim();
  if (!text) { showToast('請先寫下想說的話', 'warning'); return; }
  _pushSetStatus('message', '送出中…', 'loading');
  try {
    var myDr2 = getMyDoctor();
    var tags2 = ['patient_push', 'message'];
    if (myDr2 && myDr2.id) tags2.push('dr_' + myDr2.id);
    await fetch(API + '/doctor-notes/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-User-Id': pid },
      body: JSON.stringify({
        patient_id: pid,
        doctor_id: myDr2 ? myDr2.id : null,
        content: text,
        tags: tags2,
      }),
    }).then(function(r) { if (!r.ok) throw new Error('送出失敗'); });
    if (ta) ta.value = '';
    _pushSetStatus('message', '✓ 已送出', 'ok');
    showToast('留言已送給醫師', 'success');
  } catch (e) {
    _pushSetStatus('message', '送出失敗：' + (e.message || ''), 'error');
  }
}

async function _buildCategorySummary(cat, pid) {
  var pidQ = encodeURIComponent(pid);
  if (cat === 'symptoms') {
    var res = await fetch(API + '/symptoms/history/' + pidQ).then(function(r) { return r.ok ? r.json() : null; }).catch(function() { return null; });
    var hist = res && res.history || [];
    var since = Date.now() - 7 * 86400000;
    var recent = hist.filter(function(x) { return new Date(x.created_at).getTime() >= since; });
    if (!recent.length) return '';
    var lines = ['【近 7 天症狀紀錄】共 ' + recent.length + ' 筆'];
    recent.slice(0, 8).forEach(function(s) {
      var d = (s.created_at || '').slice(0, 10);
      var arr = Array.isArray(s.symptoms) ? s.symptoms.join('、') : (s.symptoms || '');
      var ai = (s.ai_response && (s.ai_response.summary || s.ai_response.assessment)) || '';
      lines.push('• ' + d + '：' + arr + (ai ? '（' + ai.slice(0, 60) + '）' : ''));
    });
    return lines.join('\n');
  }
  if (cat === 'medications') {
    var meds = await fetch(API + '/medications/?patient_id=' + pidQ).then(function(r) { return r.ok ? r.json() : null; }).catch(function() { return null; });
    var stats = await fetch(API + '/medications/stats?patient_id=' + pidQ + '&days=7').then(function(r) { return r.ok ? r.json() : null; }).catch(function() { return null; });
    var active = ((meds && meds.medications) || []).filter(function(m) { return m.active !== 0; });
    if (!active.length && !stats) return '';
    var rate = stats && stats.summary && stats.summary.adherence_rate;
    var lines = ['【近 7 天用藥情況】使用中藥物 ' + active.length + ' 種' + (rate != null ? '，服藥率 ' + rate + '%' : '')];
    active.slice(0, 10).forEach(function(m) {
      lines.push('• ' + m.name + (m.dosage ? '（' + m.dosage + '）' : '') + (m.frequency ? ' · ' + m.frequency : ''));
    });
    return lines.join('\n');
  }
  if (cat === 'emotions') {
    var em = await fetch(API + '/emotions/trend?patient_id=' + pidQ + '&days=7').then(function(r) { return r.ok ? r.json() : null; }).catch(function() { return null; });
    if (!em || !em.trend || !em.trend.length) return '';
    var avg = em.average_score;
    var avgPct = (avg != null) ? _moodPercent(avg) : null;
    var lines = ['【近 7 天情緒電量】平均 ' + (avgPct != null ? avgPct + '%' : '—') + '，共 ' + em.total_records + ' 筆'];
    em.trend.slice(-7).forEach(function(t) {
      lines.push('• ' + t.date + '：' + t.score + ' 分');
    });
    return lines.join('\n');
  }
  if (cat === 'vitals') {
    // vitals 端點不一定存在；用 localStorage 後備
    try {
      var raw = localStorage.getItem('mdpiece_vitals_v1');
      var arr = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(arr) || !arr.length) return '';
      var since = Date.now() - 7 * 86400000;
      var recent = arr.filter(function(v) { return v.ts && new Date(v.ts).getTime() >= since; });
      if (!recent.length) return '';
      var lines = ['【近 7 天生理紀錄】共 ' + recent.length + ' 筆'];
      recent.slice(0, 12).forEach(function(v) {
        var d = (v.ts || '').slice(0, 10);
        lines.push('• ' + d + '：' + (v.metric || '指標') + ' ' + (v.value || '') + (v.unit || ''));
      });
      return lines.join('\n');
    } catch { return ''; }
  }
  if (cat === 'labs') {
    var labs = await fetch(API + '/labs/?patient_id=' + pidQ).then(function(r) { return r.ok ? r.json() : null; }).catch(function() { return null; });
    var arr = (labs && (labs.labs || labs.items)) || [];
    if (!arr.length) return '';
    var lines = ['【檢驗報告】共 ' + arr.length + ' 筆'];
    arr.slice(0, 10).forEach(function(l) {
      lines.push('• ' + (l.test_name || l.name || '檢驗') + '：' + (l.value || '') + ' ' + (l.unit || ''));
    });
    return lines.join('\n');
  }
  return '';
}


async function loadPushHubBlock() {
  // 1. 醫師清單 + 當前綁定
  var row = document.getElementById('previsit-doctor-row');
  if (!row) return;
  try {
    var res = await fetch(API + '/auth/users');
    var users = res.ok ? (await res.json()).users || [] : [];
    var doctors = users.filter(function(u) { return u.role === 'doctor'; });
    var current = getMyDoctor();
    if (!doctors.length) {
      row.innerHTML = '<p class="previsit-doctor-empty">系統中尚無醫師帳號，您仍可推送，所有醫師都會看得到。</p>';
    } else {
      var options = '<option value="">— 推送給所有醫師（公開）—</option>' +
        doctors.map(function(d) {
          var sel = current && current.id === d.id ? ' selected' : '';
          return '<option value="' + d.id + '"' + sel + '>' +
            escapeHtml(d.nickname || d.username) + '</option>';
        }).join('');
      row.innerHTML =
        '<label class="previsit-doctor-label">' +
          '<i data-lucide="stethoscope" style="width:16px;height:16px"></i>' +
          '<span>主治醫師</span>' +
        '</label>' +
        '<select id="previsit-doctor-select" onchange="onMyDoctorChange(this)">' + options + '</select>' +
        (current ? '<span class="previsit-doctor-bound">已綁定：' + escapeHtml(current.nickname || current.username) + '</span>' : '');
      if (typeof lucide !== 'undefined') lucide.createIcons();
    }
  } catch (e) {
    row.innerHTML = '<p class="previsit-doctor-empty">無法載入醫師清單（' + escapeHtml(e.message || '') + '）</p>';
  }
  // 2. 推送歷史
  loadPushHistory();
}

function onMyDoctorChange(sel) {
  var id = sel.value;
  if (!id) { setMyDoctor(null); showToast('已取消綁定', 'success'); return; }
  // 查 user 物件
  var name = sel.options[sel.selectedIndex].textContent;
  setMyDoctor({ id: id, nickname: name });
  showToast('已綁定主治醫師：' + name, 'success');
  var bound = document.querySelector('.previsit-doctor-bound');
  if (bound) bound.textContent = '已綁定：' + name;
  else {
    var row = document.getElementById('previsit-doctor-row');
    if (row) {
      var span = document.createElement('span');
      span.className = 'previsit-doctor-bound';
      span.textContent = '已綁定：' + name;
      row.appendChild(span);
    }
  }
}

async function loadPushHistory() {
  var pid = getStablePatientId();
  if (!pid) return;
  // 從 doctor_notes 抓含 patient_push 的紀錄
  try {
    var res = await fetch(API + '/doctor-notes/?patient_id=' + encodeURIComponent(pid));
    var notes = res.ok ? (await res.json()).notes || [] : [];
    var pushes = notes.filter(function(n) {
      return Array.isArray(n.tags) && n.tags.indexOf('patient_push') >= 0;
    });
    var box = document.getElementById('push-history-list');
    if (!box) {
      // 動態插入容器
      var wrap = document.querySelector('.previsit-wrap');
      if (!wrap) return;
      var div = document.createElement('div');
      div.className = 'previsit-history';
      div.innerHTML =
        '<h3><i data-lucide="history" style="width:16px;height:16px"></i> 我推送過什麼</h3>' +
        '<div id="push-history-list"></div>';
      wrap.appendChild(div);
      box = document.getElementById('push-history-list');
      if (typeof lucide !== 'undefined') lucide.createIcons();
    }
    if (!pushes.length) {
      box.innerHTML = '<p class="previsit-empty">尚未推送過任何紀錄</p>';
      return;
    }
    var labels = { symptoms: '症狀', medications: '用藥', emotions: '情緒', vitals: '生理', labs: '檢驗', message: '留言' };
    box.innerHTML = pushes.slice(0, 20).map(function(n) {
      var cat = (n.tags || []).find(function(t) { return t !== 'patient_push' && t.indexOf('dr_') !== 0; }) || 'message';
      var when = (n.created_at || '').slice(0, 16).replace('T', ' ');
      var preview = (n.content || '').slice(0, 80);
      return '<div class="push-history-row">' +
        '<span class="push-history-cat">' + (labels[cat] || cat) + '</span>' +
        '<span class="push-history-when">' + when + '</span>' +
        '<span class="push-history-preview">' + escapeHtml(preview) + (n.content && n.content.length > 80 ? '…' : '') + '</span>' +
      '</div>';
    }).join('');
  } catch (e) {
    /* ignore */
  }
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
  renderMoodCalendar();
  renderMoodLine();
  renderMoodTable();
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

function renderBasicNutrients() {
  var box = document.getElementById('diet-basic-nutrients');
  if (!box) return;
  box.innerHTML = DIET_BASIC_NUTRIENTS.map(function(n) {
    return ''
      + '<div class="diet-nutrient">'
      +   '<div class="diet-nutrient-head">'
      +     '<i data-lucide="' + n.icon + '" style="width:16px;height:16px"></i>'
      +     '<strong>' + escHtml(n.name) + '</strong>'
      +     '<span class="diet-nutrient-daily">' + escHtml(n.daily) + '</span>'
      +   '</div>'
      +   '<div class="diet-nutrient-role">' + escHtml(n.role) + '</div>'
      +   '<div class="diet-nutrient-sources"><span class="diet-nutrient-label">食物來源</span>' + escHtml(n.sources) + '</div>'
      +   '<div class="diet-nutrient-tip">' + escHtml(n.tip) + '</div>'
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
    +     '<p class="diet-pick-sub">選擇障礙嗎？讓 AI 依你的病史挑一道。</p>'
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
      + escHtml(d)
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
    return '<span class="diet-pick-chip">' + escHtml(c) + '</span>';
  }).join('');
  var mealLabelMap = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '點心' };
  var mealBadge = (_dietPickMealType === 'any' && g.meal_type)
    ? '<span class="diet-pick-meal-badge">幫你抽了個 ' + mealLabelMap[g.meal_type] + '</span>'
    : '';
  box.className = 'diet-pick-result diet-pick-show';
  box.innerHTML = ''
    + mealBadge
    + '<div class="diet-pick-name">' + escHtml(g.name) + '</div>'
    + (g.cuisine || g.where_to_get || g.price_tier || g.price_twd
        ? '<div class="diet-pick-meta">'
          + (g.cuisine ? '<span>' + escHtml(g.cuisine) + '</span>' : '')
          + (g.where_to_get ? '<span class="diet-pick-where"><i data-lucide="map-pin" style="width:12px;height:12px"></i> ' + escHtml(g.where_to_get) + '</span>' : '')
          + ((g.price_tier || g.price_twd)
              ? '<span class="diet-pick-price-tag">' + escHtml(g.price_tier || '') + (g.price_twd ? ' · 約 NT$' + g.price_twd : '') + '</span>'
              : '')
          + ((g.calorie_kcal || g.calorie_tier)
              ? '<span class="diet-pick-cal-tag">' + (g.calorie_kcal ? g.calorie_kcal + ' kcal' : escHtml(g.calorie_tier || '')) + '</span>'
              : '')
        + '</div>'
        : '')
    + (components ? '<div class="diet-pick-chips">' + components + '</div>' : '')
    + (g.reason ? '<div class="diet-pick-reason">' + escHtml(g.reason) + '</div>' : '')
    + (g.fallback ? '<div class="diet-pick-fallback">（AI 暫時不在線，先給你一個常見選擇）</div>' : '');
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
    +   '<span class="diet-drink-name">' + escHtml(g.name) + '</span>'
    +   '<button class="diet-drink-reroll" onclick="dietPickDrink(true)" title="換一杯"><i data-lucide="refresh-cw" style="width:14px;height:14px"></i></button>'
    + '</div>'
    + '<div class="diet-drink-meta">'
    +   (g.where_to_get ? '<span>' + escHtml(g.where_to_get) + '</span>' : '')
    +   (g.price_tier ? '<span class="diet-pick-price-tag">' + escHtml(g.price_tier) + (g.price_twd ? ' · NT$' + g.price_twd : '') + '</span>' : '')
    +   (g.calorie_kcal != null ? '<span class="diet-pick-cal-tag">' + g.calorie_kcal + ' kcal</span>' : '')
    +   '<span class="diet-drink-caf' + (g.caffeine_mg > 100 ? ' high' : '') + '">' + caf + '</span>'
    +   (g.sugar_level && g.sugar_level !== '不適用' ? '<span class="diet-drink-sugar">' + escHtml(g.sugar_level) + '</span>' : '')
    + '</div>'
    + (g.reason ? '<div class="diet-drink-reason">' + escHtml(g.reason) + '</div>' : '');
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function fetchCaffeineGuide() {
  var card = document.getElementById('diet-caffeine-card');
  var body = document.getElementById('diet-caffeine-body');
  if (!card || !body) return;
  fetch(API + '/diet/caffeine-guide')
    .then(function(r) { return r.json(); })
    .then(function(g) {
      var sources = (g.common_sources || []).map(function(s) {
        return '<tr><td>' + escHtml(s.item) + '</td><td>' + s.mg + ' mg</td></tr>';
      }).join('');
      var warns = (g.warnings || []).map(function(w) {
        return ''
          + '<div class="diet-caf-warn">'
          +   '<div class="diet-caf-warn-head"><strong>' + escHtml(w.group) + '</strong>'
          +     '<span class="diet-caf-warn-limit">' + escHtml(w.limit) + '</span></div>'
          +   '<div class="diet-caf-warn-note">' + escHtml(w.note) + '</div>'
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
    tipsEl.innerHTML = (tips || []).map(function(x) { return '<li>' + escHtml(x) + '</li>'; }).join('');
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
    var avoid = (w.avoid || []).map(function(f) { return '<span class="diet-chip-bad">' + escHtml(f) + '</span>'; }).join('');
    return ''
      + '<div class="diet-warn">'
      +   '<div class="diet-warn-head">' + escHtml(w.disease || '') + '</div>'
      +   '<div class="diet-warn-avoid">' + avoid + '</div>'
      +   (w.reason ? '<div class="diet-warn-reason">' + escHtml(w.reason) + '</div>' : '')
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
    return '<span class="diet-chip-good">' + escHtml(f) + '</span>';
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
  } catch (e) {
    statusEl.textContent = '送出失敗：' + (e.message || '');
    statusEl.className = 'diet-log-status diet-log-status-error';
  }
}

function fetchDietTodayRecords() {
  var pid = getStablePatientId();
  if (!pid) return;
  var today = new Date();
  var d = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
  var tz = today.getTimezoneOffset(); // 分鐘，UTC 西側為正
  fetch(API + '/diet/records/' + encodeURIComponent(pid) + '?date=' + d + '&tz_offset=' + tz)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var box = document.getElementById('diet-today-list');
      if (!box) return;
      var rows = (data && data.records) || [];
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
          +     '<div class="diet-record-foods">' + escHtml(r.foods || '') + '</div>'
          +     (r.note ? '<div class="diet-record-note">' + escHtml(r.note) + '</div>' : '')
          +   '</div>'
          +   '<span class="diet-record-time">' + t + '</span>'
          + '</div>';
      }).join('');
    })
    .catch(function() {
      var box = document.getElementById('diet-today-list');
      if (box) box.innerHTML = '<p class="diet-empty">讀取失敗</p>';
    });
}


// ─── Service Worker ───────────────────────────────────────

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}

showPage("home");

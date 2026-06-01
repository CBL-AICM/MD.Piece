/* ═══════════════════════════════════════════════════════════════
   MD.Piece — 衛教醫典閱讀器・漸進增強（standalone）

   觀察 #app 內衛教文章閱讀器的渲染（renderArticleSpread 產生的
   .edu-article-body），加上：章節書籤、閱讀進度、首字下沉、詞彙彈窗。
   全程不改 app.js；任何錯誤都 try/catch 吞掉，絕不弄壞頁面。
   還原：移除 index.html 的 <script> 與 css/edu-codex.css 即可。
   ═══════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  // 小型醫學詞彙表（首次出現才標註，避免雜亂）。資料不足時就少標。
  var GLOSS = {
    "抗體": "免疫系統製造、用來辨識並中和外來物質（抗原）的蛋白質。",
    "抗原": "能引發免疫反應的物質，通常是病原體或外來分子的一部分。",
    "自體免疫": "免疫系統誤把自己的正常組織當成外來敵人加以攻擊。",
    "發炎": "身體對傷害或感染的防禦反應，常見紅、腫、熱、痛。",
    "緩解": "疾病症狀明顯減輕或暫時消失的狀態（不等於痊癒）。",
    "預後": "醫師對疾病未來發展與恢復情況的預估。",
    "副作用": "藥物在治療目標之外、額外產生的非預期反應。"
  };

  function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }

  // ── 閱讀進度條 ──
  function ensureBar() {
    var bar = document.getElementById("codex-progress");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "codex-progress";
      bar.innerHTML = "<i></i>";
      document.body.appendChild(bar);
    }
    return bar;
  }
  function updateProgress() {
    try {
      var body = document.querySelector('body[data-page="education"] .edu-article-body');
      var bar = document.getElementById("codex-progress");
      if (!body || !bar) { if (bar) bar.classList.remove("show"); return; }
      var rect = body.getBoundingClientRect();
      var total = rect.height - window.innerHeight;
      var scrolled = Math.min(Math.max(-rect.top, 0), Math.max(total, 1));
      var pct = total > 4 ? (scrolled / total * 100) : (rect.top < 0 ? 100 : 0);
      bar.classList.add("show");
      bar.firstChild.style.width = Math.max(0, Math.min(100, pct)).toFixed(1) + "%";
    } catch (e) {}
  }

  // ── 首字下沉 ──
  function dropCap(body) {
    try {
      var walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, null);
      var n;
      while ((n = walker.nextNode())) {
        var p = n.parentNode; if (!p) continue;
        var pn = p.nodeName.toLowerCase();
        if (pn === "h2" || pn === "h3" || pn === "h4") continue;
        var t = n.nodeValue; var idx = t.search(/\S/);
        if (idx < 0) continue;
        var frag = document.createDocumentFragment();
        if (idx > 0) frag.appendChild(document.createTextNode(t.slice(0, idx)));
        var span = document.createElement("span");
        span.className = "codex-dropcap";
        span.textContent = t.charAt(idx);
        frag.appendChild(span);
        frag.appendChild(document.createTextNode(t.slice(idx + 1)));
        p.replaceChild(frag, n);
        return;
      }
    } catch (e) {}
  }

  // ── 章節書籤（注入左頁）──
  function buildChapters(nb, body) {
    try {
      var heads = body.querySelectorAll("h2, h3, h4");
      if (!heads.length) return;
      var items = [];
      for (var i = 0; i < heads.length; i++) {
        var h = heads[i];
        if (!h.id) h.id = "codex-ch-" + i;
        h.classList.add("codex-chapter");
        items.push({ id: h.id, text: h.textContent || "", tag: h.tagName.toLowerCase() });
      }
      var left = nb.querySelector(".nb-page.left");
      if (!left || left.querySelector(".codex-toc")) return;
      var nav = document.createElement("nav");
      nav.className = "codex-toc";
      nav.innerHTML = '<div class="codex-toc-title">◆ 章節書籤</div>' +
        items.map(function (it) {
          return '<button type="button" class="codex-bm codex-bm-' + it.tag + '" data-target="' + it.id + '">' + esc(it.text) + "</button>";
        }).join("");
      left.appendChild(nav);
      nav.addEventListener("click", function (e) {
        var b = e.target.closest(".codex-bm"); if (!b) return;
        var el = document.getElementById(b.getAttribute("data-target"));
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    } catch (e) {}
  }

  // ── 詞彙標註（只標首次出現，安全走訪 text node）──
  function applyGlossary(body) {
    try {
      var terms = Object.keys(GLOSS); if (!terms.length) return;
      var used = {};
      var walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, null);
      var nodes = [], n;
      while ((n = walker.nextNode())) nodes.push(n);
      nodes.forEach(function (node) {
        var p = node.parentNode; if (!p) return;
        var pn = p.nodeName.toLowerCase();
        if (pn === "h2" || pn === "h3" || pn === "h4" || pn === "a" || pn === "button") return;
        if (p.classList && (p.classList.contains("codex-term") || p.classList.contains("codex-dropcap"))) return;
        var text = node.nodeValue, hit = null, at = -1;
        for (var i = 0; i < terms.length; i++) {
          if (used[terms[i]]) continue;
          var k = text.indexOf(terms[i]);
          if (k >= 0 && (at < 0 || k < at)) { at = k; hit = terms[i]; }
        }
        if (!hit) return;
        var frag = document.createDocumentFragment();
        frag.appendChild(document.createTextNode(text.slice(0, at)));
        var span = document.createElement("span");
        span.className = "codex-term";
        span.setAttribute("tabindex", "0");
        span.setAttribute("role", "button");
        span.setAttribute("data-def", GLOSS[hit]);
        span.textContent = hit;
        frag.appendChild(span);
        frag.appendChild(document.createTextNode(text.slice(at + hit.length)));
        p.replaceChild(frag, node);
        used[hit] = 1;
      });
    } catch (e) {}
  }

  // ── 詞彙彈窗 ──
  var _pop = null;
  function hideGloss() { if (_pop) { _pop.remove(); _pop = null; } }
  function showGloss(term) {
    hideGloss();
    _pop = document.createElement("div");
    _pop.className = "codex-gloss-pop";
    _pop.innerHTML = '<div class="codex-gloss-term">' + esc(term.textContent) + "</div>" +
                     '<div class="codex-gloss-def">' + esc(term.getAttribute("data-def")) + "</div>";
    document.body.appendChild(_pop);
    var r = term.getBoundingClientRect();
    _pop.style.top = (window.scrollY + r.bottom + 8) + "px";
    var maxLeft = window.scrollX + window.innerWidth - _pop.offsetWidth - 12;
    _pop.style.left = Math.max(12, Math.min(window.scrollX + r.left, maxLeft)) + "px";
  }

  // ── 主流程 ──
  function enhance(nb) {
    try {
      var body = nb.querySelector(".edu-article-body");
      if (!body || body.getAttribute("data-codex")) return;
      body.setAttribute("data-codex", "1");
      document.body.classList.add("codex-reading");
      buildChapters(nb, body);
      dropCap(body);
      applyGlossary(body);
      ensureBar();
      ensureLaunchBtn();
      updateProgress();
      // 點開書本 → 自動彈開翻頁書本閱讀器
      if (!body.getAttribute("data-auto")) {
        body.setAttribute("data-auto", "1");
        setTimeout(function () { openReader(); }, 80);
      }
    } catch (e) {}
  }

  // ════════════════════════════════════════════════════════════
  //  翻頁書本閱讀器（古董書 · 真正分頁）
  // ════════════════════════════════════════════════════════════
  var _reader = null;
  var _R = { page: 0, pages: 1, step: 0, gap: 0, flow: null, stage: null, fallback: false, chapters: [] };

  // ── 古典銅版風醫學插圖（純 inline SVG，單色墨線 + 排線陰影）──
  var CODEX_PLATES = [
    // 解剖心臟
    '<svg viewBox="0 0 240 300" fill="none" stroke="#2a1d12" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M120 66 C118 46 132 34 150 38 C170 42 174 62 164 78"/>' +
      '<path d="M104 64 C96 46 80 42 70 52"/><path d="M134 56 C150 46 150 34 138 30"/>' +
      '<path d="M120 252 C58 200 38 150 60 108 C74 86 102 86 120 110 C138 86 166 86 180 108 C202 150 182 200 120 252 Z" stroke-width="2.8"/>' +
      '<path d="M118 112 C110 152 106 192 116 232"/><path d="M118 150 C100 160 84 168 74 160"/><path d="M122 176 C142 184 158 180 170 166"/>' +
      '<g stroke-width="1" opacity=".5"><path d="M150 128 L172 150"/><path d="M146 146 L174 170"/><path d="M150 168 L170 188"/><path d="M152 188 L164 202"/></g>' +
    '</svg>',
    // 藥草
    '<svg viewBox="0 0 240 300" fill="none" stroke="#2a1d12" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M120 286 C120 224 118 162 122 96"/>' +
      '<circle cx="121" cy="84" r="11"/><path d="M121 73 V58 M132 84 H148 M110 84 H94 M129 76 L141 64 M113 76 L101 64"/>' +
      '<path d="M122 132 C150 122 168 132 176 152 C156 158 134 152 122 140"/><path d="M120 132 C92 122 74 132 66 152 C86 158 108 152 120 140"/>' +
      '<path d="M122 178 C148 168 166 178 174 198 C154 204 134 198 122 186"/><path d="M120 178 C94 168 76 178 68 198 C88 204 108 198 120 186"/>' +
      '<path d="M120 286 C110 294 104 296 96 298 M120 286 C130 294 138 296 146 298 M120 288 V298"/>' +
      '<g stroke-width="1" opacity=".5"><path d="M140 140 l16 8 M134 146 l14 5 M86 140 l-16 8 M92 146 l-14 5"/></g>' +
    '</svg>',
    // 研缽與藥瓶
    '<svg viewBox="0 0 240 300" fill="none" stroke="#2a1d12" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M150 70 L198 30" stroke-width="6"/><circle cx="150" cy="74" r="9"/>' +
      '<path d="M58 168 H182 C176 224 152 252 120 252 C88 252 64 224 58 168 Z"/>' +
      '<path d="M50 168 H190" stroke-width="3"/><ellipse cx="120" cy="168" rx="62" ry="12"/>' +
      '<g stroke-width="1" opacity=".45"><path d="M150 188 l18 16 M140 212 l24 14 M118 226 l20 12"/></g>' +
      '<path d="M36 250 q-8 -34 8 -40 q16 6 8 40 Z" transform="translate(150 -6)"/>' +
    '</svg>',
    // 顱骨
    '<svg viewBox="0 0 240 300" fill="none" stroke="#2a1d12" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M62 132 C60 80 94 50 120 50 C146 50 180 80 178 132 C178 152 170 162 166 176 L158 200 C156 210 148 214 138 214 L102 214 C92 214 84 210 82 200 L74 176 C70 162 62 152 62 132 Z"/>' +
      '<path d="M98 214 C98 238 110 248 120 248 C130 248 142 238 142 214"/>' +
      '<ellipse cx="98" cy="140" rx="16" ry="18"/><ellipse cx="142" cy="140" rx="16" ry="18"/>' +
      '<path d="M120 156 L112 184 C116 188 124 188 128 184 Z"/>' +
      '<path d="M104 214 V232 M114 214 V234 M126 214 V234 M136 214 V232 M100 224 H140"/>' +
      '<path d="M120 50 C116 72 124 72 120 94" stroke-width="1.3" opacity=".6"/>' +
      '<g stroke-width="1" opacity=".4"><path d="M150 108 l16 10 M150 120 l18 8 M74 108 l-16 10 M74 120 l-18 8"/></g>' +
    '</svg>'
  ];
  var PLATE_LABELS = ["圖 · 心之府", "圖 · 本草", "圖 · 製劑", "圖 · 顱骨"];
  function hashStr(s) { var h = 0; s = s || ""; for (var i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) | 0; } return Math.abs(h); }

  // 手機版書籤貼紙的醫療圖示：依文章標題穩定挑選一個（同一篇始終同一圖示，
  // 不同文章視覺有變化）。三個圖示分屬「整體照護 / 用藥 / 就診」三個語意。
  var _STICKER_ICONS = ["heart", "pill", "stethoscope"];
  function pickStickerIcon(title) { return _STICKER_ICONS[hashStr(title) % _STICKER_ICONS.length]; }

  function decoratePlates(flow, title) {
    if (!flow) return;
    var base = hashStr(title);
    // 卷首插圖頁（插圖 + 章名），仿古董書扉頁
    var fi = base % CODEX_PLATES.length;
    var frontis = document.createElement("figure");
    frontis.className = "codex-frontis";
    frontis.innerHTML =
      '<div class="codex-plate-art">' + CODEX_PLATES[fi] + "</div>" +
      '<figcaption class="codex-frontis-cap">' +
        '<div class="codex-frontis-eyebrow">醫 典 圖 譜</div>' +
        '<div class="codex-frontis-rule"></div>' +
        '<div class="codex-frontis-title">' + esc(title) + "</div>" +
      "</figcaption>";
    flow.insertBefore(frontis, flow.firstChild);
    // 每章前插一張整頁插圖
    var heads = flow.querySelectorAll("h2");
    for (var i = 0; i < heads.length; i++) {
      var pi = (base + i + 1) % CODEX_PLATES.length;
      var fig = document.createElement("figure");
      fig.className = "codex-plate";
      fig.innerHTML = '<div class="codex-plate-art">' + CODEX_PLATES[pi] + "</div>" +
        '<figcaption>' + esc(PLATE_LABELS[pi]) + "</figcaption>";
      heads[i].parentNode.insertBefore(fig, heads[i]);
    }
  }

  function ensureLaunchBtn() {
    var b = document.getElementById("codex-open-btn");
    if (!b) {
      b = document.createElement("button");
      b.id = "codex-open-btn";
      b.type = "button";
      b.innerHTML = "📖 翻頁閱讀";
      b.addEventListener("click", openReader);
      document.body.appendChild(b);
    }
    b.classList.add("show");
  }
  function hideLaunchBtn() {
    var b = document.getElementById("codex-open-btn");
    if (b) b.classList.remove("show");
  }

  function openReader() {
    try {
      if (_reader) return;
      var src = document.querySelector('body[data-page="education"] .edu-article-body');
      if (!src) return;
      var titleEl = document.querySelector("#edu-breadcrumb .crumb.current");
      var title = titleEl ? (titleEl.textContent || "").trim() : "衛教文章";

      _reader = document.createElement("div");
      _reader.className = "codex-reader";
      _reader.setAttribute("role", "dialog");
      _reader.setAttribute("aria-modal", "true");
      _reader.setAttribute("aria-label", "翻頁閱讀");
      _reader.innerHTML =
        '<div class="codex-reader-bar">' +
          '<button type="button" class="codex-rbtn" data-act="close" aria-label="關閉">✕</button>' +
          '<div class="codex-reader-title">' + esc(title) + "</div>" +
          '<button type="button" class="codex-rbtn" data-act="toc" aria-label="章節">☰</button>' +
        "</div>" +
        '<div class="codex-book">' +
          '<div class="codex-reader-stage">' +
            '<div class="codex-spine"></div>' +
            // 手機版書籤貼紙（桌機由 CSS 隱藏）— 依文章標題雜湊穩定挑選圖示
            '<div class="codex-bookmark-sticker" aria-hidden="true">' +
              '<i data-lucide="' + pickStickerIcon(title) + '"></i>' +
            "</div>" +
            '<div class="codex-reader-flow edu-article-body"></div>' +
            '<button type="button" class="codex-edge prev" aria-label="上一頁"></button>' +
            '<button type="button" class="codex-edge next" aria-label="下一頁"></button>' +
            '<div class="codex-folio"><span class="cur">1</span></div>' +
          "</div>" +
        "</div>" +
        '<div class="codex-pagebar"><i></i></div>' +
        '<div class="codex-dots" aria-hidden="true"></div>' +  // 手機版圓點 indicator
        '<div class="codex-reader-foot">' +
          '<button type="button" class="codex-fbtn" data-act="prev">‹ 前頁</button>' +
          '<div class="codex-pageno"><span class="cur">1</span> / <span class="tot">1</span></div>' +
          '<button type="button" class="codex-fbtn" data-act="next">後頁 ›</button>' +
        "</div>" +
        '<aside class="codex-toc-drawer" hidden></aside>';
      document.body.appendChild(_reader);

      _R.flow = _reader.querySelector(".codex-reader-flow");
      _R.stage = _reader.querySelector(".codex-reader-stage");
      _R.flow.innerHTML = src.innerHTML; // 複製已增強內容（dropcap / glossary / 章節 id）
      try { decoratePlates(_R.flow, title); } catch (e) {}
      _R.page = 0;

      document.body.classList.add("codex-reader-open");
      _reader.addEventListener("click", onReaderClick);
      bindSwipe(_R.stage);
      window.addEventListener("keydown", onReaderKey);
      window.addEventListener("resize", relayoutSoon);

      // 彈開動畫後量測（字型/圖片載入會影響高度，延後再量一次）
      requestAnimationFrame(function () { layout(); goTo(0, true); });
      setTimeout(function () { if (_reader) { layout(); goTo(_R.page, true); } }, 300);
      if (typeof lucide !== "undefined") { try { lucide.createIcons(); } catch (e) {} }
    } catch (e) { closeReader(); }
  }

  function closeReader() {
    try {
      window.removeEventListener("keydown", onReaderKey);
      window.removeEventListener("resize", relayoutSoon);
      if (_reader) { _reader.remove(); _reader = null; }
      document.body.classList.remove("codex-reader-open");
      _R = { page: 0, pages: 1, step: 0, gap: 0, flow: null, stage: null, fallback: false, chapters: [] };
    } catch (e) {}
  }

  function layout() {
    try {
      var flow = _R.flow, stage = _R.stage;
      if (!flow || !stage) return;
      var W = stage.clientWidth, H = stage.clientHeight;
      if (W < 40 || H < 40) return;
      var gap = Math.max(28, Math.round(W * 0.12));
      _R.gap = gap;
      flow.style.transition = "none";
      flow.style.transform = "translateX(0)";
      flow.style.overflow = "";
      flow.style.width = W + "px";
      flow.style.height = H + "px";
      flow.style.columnGap = gap + "px";
      flow.style.columnFill = "auto";
      var cs = window.getComputedStyle(flow);
      var padL = parseFloat(cs.paddingLeft) || 0;
      var padR = parseFloat(cs.paddingRight) || 0;
      var Cw = W - padL - padR;
      flow.style.columnWidth = Cw + "px";
      // 量測
      var content = flow.scrollWidth - padL;
      var step = Cw + gap;
      var pages = Math.max(1, Math.round((content + gap) / step));
      // 備援：columns 沒生效（內容仍垂直溢位）→ 改垂直捲動，仍維持書頁外觀
      if (pages <= 1 && flow.scrollHeight > H + 6) {
        flow.style.columnWidth = "";
        flow.style.columnGap = "";
        flow.style.overflowY = "auto";
        flow.style.overflowX = "hidden";
        _R.fallback = true; _R.pages = 1; _R.step = step;
        buildDrawer(); updateFoot(); return;
      }
      _R.fallback = false; _R.step = step; _R.pages = pages;
      // 各章節落在哪頁（transform 為 0 時量）
      _R.chapters = [];
      var heads = flow.querySelectorAll("h2, h3");
      var fLeft = flow.getBoundingClientRect().left;
      for (var i = 0; i < heads.length; i++) {
        var x = heads[i].getBoundingClientRect().left - fLeft;
        var pg = Math.max(0, Math.min(pages - 1, Math.round(x / step)));
        _R.chapters.push({ text: heads[i].textContent || "", page: pg });
      }
      buildDrawer();
      if (_R.page > pages - 1) _R.page = pages - 1;
      requestAnimationFrame(function () {
        if (_R.flow) _R.flow.style.transition = "transform .45s cubic-bezier(.4,0,.2,1)";
      });
      updateFoot();
    } catch (e) {}
  }

  function goTo(p, instant) {
    try {
      if (!_reader || _R.fallback) { updateFoot(); return; }
      var flow = _R.flow; if (!flow) return;
      p = Math.max(0, Math.min(p, _R.pages - 1));
      _R.page = p;
      if (instant) flow.style.transition = "none";
      flow.style.transform = "translateX(" + (-(p * _R.step)) + "px)";
      if (instant) requestAnimationFrame(function () { if (_R.flow) _R.flow.style.transition = "transform .45s cubic-bezier(.4,0,.2,1)"; });
      _reader.classList.remove("turning"); void _reader.offsetWidth; _reader.classList.add("turning");
      updateFoot();
    } catch (e) {}
  }
  function next() { goTo(_R.page + 1); }
  function prev() { goTo(_R.page - 1); }

  function updateFoot() {
    if (!_reader) return;
    var n = _R.fallback ? 1 : (_R.page + 1);
    _reader.querySelectorAll(".codex-pageno .cur, .codex-folio .cur").forEach(function (el) { el.textContent = n; });
    var tot = _reader.querySelector(".codex-pageno .tot"); if (tot) tot.textContent = _R.pages;
    var bar = _reader.querySelector(".codex-pagebar i");
    if (bar) bar.style.width = (_R.pages > 1 ? (_R.page / (_R.pages - 1) * 100) : 100) + "%";
    refreshDots();
  }

  // 手機版圓點 indicator：≤8 頁直接一頁一點，>8 頁壓縮成 8 點（每點對應 N 頁），
  // 避免在頁數多的衛教文上點數爆量；桌機 CSS 完全隱藏這個容器。
  function refreshDots() {
    var box = _reader && _reader.querySelector(".codex-dots");
    if (!box) return;
    var total = Math.max(1, _R.pages || 1);
    if (total <= 1) { box.innerHTML = ""; return; }
    var maxDots = 8;
    var nDots = Math.min(total, maxDots);
    var perDot = total / nDots;
    var activeDot = Math.min(nDots - 1, Math.floor(_R.page / perDot));
    var html = "";
    for (var i = 0; i < nDots; i++) {
      html += '<span class="codex-dot' + (i === activeDot ? " active" : "") + '"></span>';
    }
    box.innerHTML = html;
  }

  function buildDrawer() {
    var d = _reader && _reader.querySelector(".codex-toc-drawer");
    if (!d) return;
    if (!_R.chapters.length) { d.innerHTML = '<div class="codex-toc-title">本篇無章節</div>'; return; }
    d.innerHTML = '<div class="codex-toc-title">◆ 章節</div>' + _R.chapters.map(function (c) {
      return '<button type="button" class="codex-bm" data-jump="' + c.page + '">' + esc(c.text) + "</button>";
    }).join("");
  }

  function onReaderClick(e) {
    var t = e.target;
    var hit = t.closest ? t.closest("[data-act], [data-jump], .codex-edge") : null;
    if (!hit) return;
    if (hit.classList.contains("codex-edge")) { hit.classList.contains("next") ? next() : prev(); return; }
    if (hit.hasAttribute("data-jump")) {
      goTo(parseInt(hit.getAttribute("data-jump"), 10) || 0);
      var dr = _reader.querySelector(".codex-toc-drawer"); if (dr) dr.hidden = true;
      return;
    }
    var act = hit.getAttribute("data-act");
    if (act === "close") closeReader();
    else if (act === "next") next();
    else if (act === "prev") prev();
    else if (act === "toc") { var d = _reader.querySelector(".codex-toc-drawer"); if (d) d.hidden = !d.hidden; }
  }
  function onReaderKey(e) {
    if (!_reader) return;
    if (e.key === "ArrowRight") next();
    else if (e.key === "ArrowLeft") prev();
    else if (e.key === "Escape") closeReader();
  }
  function bindSwipe(stage) {
    var x0 = null, y0 = null, t0 = 0;
    stage.addEventListener("touchstart", function (e) {
      var t = e.touches[0]; x0 = t.clientX; y0 = t.clientY; t0 = Date.now();
    }, { passive: true });
    stage.addEventListener("touchend", function (e) {
      if (x0 == null) return;
      var t = e.changedTouches[0];
      var dx = t.clientX - x0, dy = t.clientY - y0, dt = Date.now() - t0;
      x0 = null;
      if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy) * 1.4 && dt < 900) { dx < 0 ? next() : prev(); }
    }, { passive: true });
  }
  var _relT;
  function relayoutSoon() { clearTimeout(_relT); _relT = setTimeout(function () { layout(); goTo(_R.page, true); }, 200); }

  function scan() {
    try {
      var nb = document.getElementById("edu-notebook");
      if (nb && nb.querySelector(".edu-article-body")) enhance(nb);
      if (!document.querySelector('body[data-page="education"] .edu-article-body')) {
        document.body.classList.remove("codex-reading");
        hideGloss();
        hideLaunchBtn();
        closeReader();
      }
    } catch (e) {}
  }

  function init() {
    try {
      var app = document.getElementById("app") || document.body;
      var obs = new MutationObserver(function () { scan(); });
      obs.observe(app, { childList: true, subtree: true });
      window.addEventListener("scroll", updateProgress, { passive: true });
      window.addEventListener("resize", updateProgress);
      document.addEventListener("click", function (e) {
        var t = e.target.closest ? e.target.closest(".codex-term") : null;
        if (t) { e.stopPropagation(); showGloss(t); }
        else if (!(e.target.closest && e.target.closest(".codex-gloss-pop"))) hideGloss();
      });
      document.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && e.target && e.target.classList && e.target.classList.contains("codex-term")) showGloss(e.target);
        if (e.key === "Escape") hideGloss();
      });
      scan();
    } catch (e) {}
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

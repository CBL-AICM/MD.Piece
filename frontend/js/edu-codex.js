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
            '<div class="codex-reader-flow edu-article-body"></div>' +
            '<button type="button" class="codex-edge prev" aria-label="上一頁"></button>' +
            '<button type="button" class="codex-edge next" aria-label="下一頁"></button>' +
            '<div class="codex-folio"><span class="cur">1</span></div>' +
          "</div>" +
        "</div>" +
        '<div class="codex-pagebar"><i></i></div>' +
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

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
      updateProgress();
    } catch (e) {}
  }

  function scan() {
    try {
      var nb = document.getElementById("edu-notebook");
      if (nb && nb.querySelector(".edu-article-body")) enhance(nb);
      if (!document.querySelector('body[data-page="education"] .edu-article-body')) {
        document.body.classList.remove("codex-reading");
        hideGloss();
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

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
  // i18n helper: edu-codex 隨 index.html 載入 i18n.js，渲染期 window.MDPiece_i18n 必在。
  function T(k) { return (window.MDPiece_i18n && window.MDPiece_i18n.t) ? window.MDPiece_i18n.t(k) : k; }

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
      nav.innerHTML = '<div class="codex-toc-title">' + esc(T("codex.toc.bookmarks")) + '</div>' +
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

  // ── 雕刻線畫醫學插圖（純 inline SVG）── 與文章疾病／章節主題相關，不放不相關圖。
  var S0 = '<svg viewBox="0 0 240 300" fill="none" stroke="#2a1d12" stroke-linecap="round" stroke-linejoin="round" stroke-width="5">';
  var PLATE_SVG = {
    // 器官／概念
    heart: S0 + '<path d="M120 252 C58 200 38 150 60 108 C74 86 102 86 120 110 C138 86 166 86 180 108 C202 150 182 200 120 252 Z"/><path d="M120 66 C118 46 132 34 150 38 C170 42 174 62 164 80"/><path d="M104 66 C96 48 80 44 70 54"/><path d="M118 112 C110 152 106 192 116 232"/><path d="M118 150 C100 160 84 168 74 160"/><path d="M122 176 C142 184 158 180 170 166"/></svg>',
    lungs: S0 + '<path d="M120 60 V120"/><path d="M120 78 C108 86 98 92 94 104"/><path d="M120 78 C132 86 142 92 146 104"/><path d="M104 104 C84 110 70 142 70 190 C70 226 86 244 102 238 C113 234 112 208 112 180 V120"/><path d="M136 104 C156 110 170 142 170 190 C170 226 154 244 138 238 C127 234 128 208 128 180 V120"/></svg>',
    kidney: S0 + '<path d="M104 84 C70 86 52 120 52 158 C52 206 78 234 106 230 C124 227 122 208 113 192 C104 176 104 134 114 116 C122 102 122 82 104 84 Z"/><path d="M98 158 h-22 M98 158 l-12 -12 M98 158 l-12 12" stroke-width="3"/></svg>',
    brain: S0 + '<path d="M88 92 C72 80 50 90 50 112 C36 116 36 140 52 146 C46 164 62 178 78 170 C84 190 116 190 116 166 V100 C116 84 96 80 88 92 Z"/><path d="M152 92 C168 80 190 90 190 112 C204 116 204 140 188 146 C194 164 178 178 162 170 C156 190 124 190 124 166 V100 C124 84 144 80 152 92 Z"/><path d="M120 98 V210"/><path d="M120 210 C110 224 108 238 120 250 C132 238 130 224 120 210"/></svg>',
    glucose: S0 + '<path d="M120 72 C150 122 176 152 176 186 C176 220 150 242 120 242 C90 242 64 220 64 186 C64 152 90 122 120 72 Z"/><g stroke-width="3"><rect x="150" y="92" width="22" height="22" rx="3" transform="rotate(20 161 103)"/><rect x="58" y="116" width="20" height="20" rx="3" transform="rotate(-14 68 126)"/></g></svg>',
    joint: S0 + '<path d="M150 62 c14 -10 30 6 20 20 c12 4 10 24 -6 24 l-40 40"/><path d="M118 150 l-40 40 c-14 -2 -18 16 -6 24 c-10 14 6 30 20 20"/><circle cx="120" cy="150" r="22"/></svg>',
    stomach: S0 + '<path d="M108 64 V96 C108 104 100 108 92 112 C66 124 56 160 70 196 C84 232 130 246 158 222 C178 204 178 178 166 172"/><path d="M108 96 C130 96 150 110 156 134"/></svg>',
    liver: S0 + '<path d="M52 116 C100 96 168 96 196 112 C200 150 184 196 150 206 C140 209 132 200 128 190 C124 200 116 206 104 204 C72 198 50 160 52 116 Z"/><path d="M120 122 V196" stroke-width="2.5"/></svg>',
    eye: S0 + '<path d="M40 150 C80 104 160 104 200 150 C160 196 80 196 40 150 Z"/><circle cx="120" cy="150" r="30"/><circle cx="120" cy="150" r="11" fill="#2a1d12" stroke="none"/></svg>',
    cell: S0 + '<circle cx="120" cy="150" r="78"/><circle cx="120" cy="150" r="34"/><circle cx="110" cy="142" r="7" fill="#2a1d12" stroke="none"/><g stroke-width="2.5"><circle cx="82" cy="112" r="6"/><circle cx="166" cy="172" r="6"/></g></svg>',
    bp: S0 + '<rect x="62" y="120" width="116" height="64" rx="12"/><path d="M178 140 h20 a10 10 0 0 1 10 10 v8 a10 10 0 0 1 -10 10 h-20"/><path d="M86 152 h18 l10 -18 l14 36 l9 -18 h20" stroke-width="4"/><path d="M120 184 V210 M96 210 h48"/></svg>',
    // 章節主題
    pill: S0 + '<rect x="58" y="118" width="118" height="56" rx="28" transform="rotate(-32 117 146)"/><path d="M96 96 L138 178" transform="rotate(-32 117 146)"/><circle cx="156" cy="198" r="32"/><path d="M134 198 H178"/></svg>',
    symptom: S0 + '<circle cx="112" cy="138" r="56"/><path d="M152 178 L196 222"/><path d="M82 138 h16 l10 -22 l16 44 l10 -22 h16"/></svg>',
    life: S0 + '<circle cx="120" cy="92" r="24"/><g stroke-width="3"><path d="M120 54 V44 M80 92 H70 M170 92 h-10 M92 64 l-8 -8 M148 64 l8 -8"/></g><path d="M120 176 V250 M120 200 C150 192 176 200 184 226 C156 234 130 226 120 212 M120 212 C92 204 66 212 58 238 C86 246 110 238 120 224"/></svg>',
    alert: S0 + '<path d="M120 70 L198 214 H42 Z" stroke-width="6"/><path d="M120 122 V168" stroke-width="8"/><circle cx="120" cy="190" r="5" fill="#2a1d12" stroke="none"/></svg>',
    track: S0 + '<rect x="58" y="74" width="124" height="158" rx="10"/><rect x="96" y="60" width="48" height="28" rx="7"/><path d="M82 184 l24 -28 l22 18 l30 -46" stroke-width="4"/></svg>',
    urgent: S0 + '<circle cx="120" cy="150" r="80"/><path d="M120 112 V188 M82 150 H158" stroke-width="10"/></svg>',
    // 通用（僅扉頁退而求其次用，非誤導性）
    steth: S0 + '<path d="M80 52 C68 92 86 116 118 130"/><path d="M160 52 C172 92 154 116 122 130"/><circle cx="80" cy="48" r="8"/><circle cx="160" cy="48" r="8"/><path d="M120 130 V204"/><circle cx="120" cy="232" r="28"/><circle cx="120" cy="232" r="14"/></svg>'
  };

  // 文章疾病 → 器官／概念圖（關鍵字比對，越具體放越前面）
  var DISEASE_PLATES = [
    { k: ["高血壓", "血壓"], svg: "bp", label: "codex.plate.bp" },
    { k: ["糖尿", "血糖", "胰島", "代謝症候"], svg: "glucose", label: "codex.plate.glucose" },
    { k: ["腎", "洗腎", "透析", "尿蛋白"], svg: "kidney", label: "codex.plate.kidney" },
    { k: ["肺", "氣喘", "哮喘", "copd", "阻塞性", "呼吸", "肺炎", "支氣管"], svg: "lungs", label: "codex.plate.lungs" },
    { k: ["腦", "中風", "失智", "阿茲海默", "帕金森", "癲癇", "頭痛", "偏頭痛", "多發性硬化"], svg: "brain", label: "codex.plate.brain" },
    { k: ["關節", "退化性", "類風濕", "痛風", "骨質疏鬆", "脊椎", "五十肩", "骨"], svg: "joint", label: "codex.plate.joint" },
    { k: ["肝", "肝炎", "脂肪肝", "肝硬化"], svg: "liver", label: "codex.plate.liver" },
    { k: ["胃", "腸", "消化", "潰瘍", "腸躁", "胃食道", "便秘"], svg: "stomach", label: "codex.plate.stomach" },
    { k: ["眼", "視網膜", "青光眼", "白內障", "乾眼", "黃斑", "乾燥症"], svg: "eye", label: "codex.plate.eye" },
    { k: ["免疫", "紅斑性狼瘡", "sle", "狼瘡", "過敏", "癌", "腫瘤", "白血病", "淋巴", "血液"], svg: "cell", label: "codex.plate.cell" },
    { k: ["心", "心臟", "心血管", "冠心", "心衰", "心肌", "高血脂", "膽固醇", "動脈"], svg: "heart", label: "codex.plate.heart" }
  ];
  // 章節主題 → 主題圖（用藥／症狀／生活／風險／追蹤／緊急）
  var DIMENSION_PLATES = [
    { k: ["用藥", "藥物", "服藥", "藥"], svg: "pill", label: "codex.plate.pill" },
    { k: ["症狀", "徵兆", "辨認", "警訊"], svg: "symptom", label: "codex.plate.symptom" },
    { k: ["生活", "飲食", "運動", "作息", "自我照護", "保健"], svg: "life", label: "codex.plate.life" },
    { k: ["併發", "風險", "長期", "惡化", "預後"], svg: "alert", label: "codex.plate.alert" },
    { k: ["追蹤", "監測", "回診", "檢查", "記錄"], svg: "track", label: "codex.plate.track" },
    { k: ["緊急", "立即", "送醫", "危險", "急性"], svg: "urgent", label: "codex.plate.urgent" }
  ];
  function matchPlate(text, list) {
    var s = String(text || "").toLowerCase();
    for (var i = 0; i < list.length; i++) {
      for (var j = 0; j < list[i].k.length; j++) {
        if (s.indexOf(String(list[i].k[j]).toLowerCase()) !== -1) return list[i];
      }
    }
    return null;
  }
  function hashStr(s) { var h = 0; s = s || ""; for (var i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) | 0; } return Math.abs(h); }

  // 手機版書籤貼紙的醫療圖示：依文章標題穩定挑選一個（同一篇始終同一圖示，
  // 不同文章視覺有變化）。三個圖示分屬「整體照護 / 用藥 / 就診」三個語意。
  var _STICKER_ICONS = ["heart", "pill", "stethoscope"];
  function pickStickerIcon(title) { return _STICKER_ICONS[hashStr(title) % _STICKER_ICONS.length]; }

  function decoratePlates(flow, title) {
    if (!flow) return;
    // 文章層級疾病：用「標題＋所有章名」比對（標題常是通用字，疾病名多在章名裡，
    // 如「認識高血壓」），比只看標題穩。用於扉頁與章節無主題對應時的退路。
    var diseaseText = String(title || "");
    var hs = flow.querySelectorAll("h2, h3");
    for (var q = 0; q < hs.length; q++) diseaseText += " " + (hs[q].textContent || "");
    var disease = matchPlate(diseaseText, DISEASE_PLATES);
    // 卷首插圖頁：有疾病對應就放疾病器官圖；否則用通用聽診器（非誤導性）。
    var coverSvg = disease ? PLATE_SVG[disease.svg] : PLATE_SVG.steth;
    var frontis = document.createElement("figure");
    frontis.className = "codex-frontis";
    frontis.innerHTML =
      '<div class="codex-plate-art">' + coverSvg + "</div>" +
      '<figcaption class="codex-frontis-cap">' +
        '<div class="codex-frontis-eyebrow">' + esc(T("codex.frontis.eyebrow")) + '</div>' +
        '<div class="codex-frontis-rule"></div>' +
        '<div class="codex-frontis-title">' + esc(title) + "</div>" +
      "</figcaption>";
    flow.insertBefore(frontis, flow.firstChild);
    // 每章：先比對章名主題（用藥／症狀／生活…），否則退回文章疾病圖；
    // 兩者皆無對應 → 不放圖（規則：不要不相關圖片）。
    var heads = flow.querySelectorAll("h2");
    for (var i = 0; i < heads.length; i++) {
      var plate = matchPlate(heads[i].textContent || "", DIMENSION_PLATES) || disease;
      if (!plate) continue;
      var fig = document.createElement("figure");
      fig.className = "codex-plate";
      fig.innerHTML = '<div class="codex-plate-art">' + PLATE_SVG[plate.svg] + "</div>" +
        '<figcaption>' + esc(T(plate.label)) + "</figcaption>";
      heads[i].parentNode.insertBefore(fig, heads[i]);
    }
  }

  function ensureLaunchBtn() {
    var b = document.getElementById("codex-open-btn");
    if (!b) {
      b = document.createElement("button");
      b.id = "codex-open-btn";
      b.type = "button";
      b.textContent = "📖 " + T("codex.open");
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
      var title = titleEl ? (titleEl.textContent || "").trim() : T("codex.fallbackTitle");

      _reader = document.createElement("div");
      _reader.className = "codex-reader";
      _reader.setAttribute("role", "dialog");
      _reader.setAttribute("aria-modal", "true");
      _reader.setAttribute("aria-label", T("codex.aria.reader"));
      _reader.innerHTML =
        '<div class="codex-reader-bar">' +
          '<button type="button" class="codex-rbtn" data-act="close" aria-label="' + esc(T("codex.aria.close")) + '">✕</button>' +
          '<div class="codex-reader-title">' + esc(title) + "</div>" +
          '<button type="button" class="codex-rbtn" data-act="toc" aria-label="' + esc(T("codex.aria.toc")) + '">☰</button>' +
        "</div>" +
        '<div class="codex-book">' +
          '<div class="codex-reader-stage">' +
            '<div class="codex-spine"></div>' +
            // 手機版書籤貼紙（桌機由 CSS 隱藏）— 依文章標題雜湊穩定挑選圖示
            '<div class="codex-bookmark-sticker" aria-hidden="true">' +
              '<i data-lucide="' + pickStickerIcon(title) + '"></i>' +
            "</div>" +
            '<div class="codex-reader-flow edu-article-body"></div>' +
            '<button type="button" class="codex-edge prev" aria-label="' + esc(T("codex.aria.prev")) + '"></button>' +
            '<button type="button" class="codex-edge next" aria-label="' + esc(T("codex.aria.next")) + '"></button>' +
            '<div class="codex-folio"><span class="cur">1</span></div>' +
          "</div>" +
        "</div>" +
        '<div class="codex-pagebar"><i></i></div>' +
        '<div class="codex-dots" aria-hidden="true"></div>' +  // 手機版圓點 indicator
        '<div class="codex-reader-foot">' +
          '<button type="button" class="codex-fbtn" data-act="prev">' + esc(T("codex.foot.prev")) + '</button>' +
          '<div class="codex-pageno"><span class="cur">1</span> / <span class="tot">1</span></div>' +
          '<button type="button" class="codex-fbtn" data-act="next">' + esc(T("codex.foot.next")) + '</button>' +
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

  // 對開模式把整頁插圖推到偶數欄（左頁）：先量好所有插圖原始欄位，再依序補空白欄。
  // 因每個 spacer 恰占一欄，插圖最終欄＝原始欄＋其前已插入的 spacer 數（可純算）。
  function _balancePlatesLeft(flow, step) {
    try {
      if (flow.querySelector(".codex-col-spacer")) return;   // 已平衡過，避免重複插入
      var flowLeft = flow.getBoundingClientRect().left;       // 此時 transform 為 translateX(0)
      var plates = [].slice.call(flow.querySelectorAll(".codex-frontis, .codex-plate"));
      var cols = plates.map(function (pl) {
        return Math.round((pl.getBoundingClientRect().left - flowLeft) / step);
      });
      var inserted = 0;
      for (var i = 0; i < plates.length; i++) {
        if ((cols[i] + inserted) % 2 === 1) {                 // 落在右頁（奇數欄）→ 補一欄推到左頁
          var sp = document.createElement("div");
          sp.className = "codex-col-spacer";
          plates[i].parentNode.insertBefore(sp, plates[i]);
          inserted++;
        }
      }
    } catch (e) {}
  }

  function layout() {
    try {
      var flow = _R.flow, stage = _R.stage;
      if (!flow || !stage) return;
      var W = stage.clientWidth, H = stage.clientHeight;
      if (W < 40 || H < 40) return;
      // 桌機（≥768px）＝對開兩頁：每欄＝半頁、一次顯示兩欄；手機＝單頁。
      var twoUp = !!(window.matchMedia && window.matchMedia("(min-width: 768px)").matches);
      _R.twoUp = twoUp;
      _R.colsPerView = twoUp ? 2 : 1;
      // 對開時 gap 當作中央書脊寬；單頁時為頁間留白
      var gap = twoUp ? Math.max(30, Math.round(W * 0.05)) : Math.max(28, Math.round(W * 0.12));
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
      var colW = twoUp ? Math.floor((Cw - gap) / 2) : Cw;
      flow.style.columnWidth = colW + "px";
      var step = colW + gap;
      // 對開模式：把每張整頁插圖推到「左頁」（偶數欄），對齊圖 2 的左插圖／右文字。
      // 先一次量好所有插圖的原始欄位，再依序插空白欄（每欄恰補 1），不重複量測。
      if (twoUp) _balancePlatesLeft(flow, step);
      // 量測（step ＝ 一欄寬＋gap）
      var content = flow.scrollWidth - padL;
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
      var cpv = _R.colsPerView || 1;
      p = Math.floor(p / cpv) * cpv;                                 // 對齊到對開起始欄
      var maxStart = Math.max(0, Math.ceil(_R.pages / cpv) * cpv - cpv);
      p = Math.max(0, Math.min(p, maxStart));
      _R.page = p;
      if (instant) flow.style.transition = "none";
      flow.style.transform = "translateX(" + (-(p * _R.step)) + "px)";
      if (instant) requestAnimationFrame(function () { if (_R.flow) _R.flow.style.transition = "transform .45s cubic-bezier(.4,0,.2,1)"; });
      _reader.classList.remove("turning"); void _reader.offsetWidth; _reader.classList.add("turning");
      updateFoot();
    } catch (e) {}
  }
  // 翻頁葉（3D）：對開模式才生效，在書脊處長出一張紙旋轉，做出翻頁動畫。
  // prefers-reduced-motion 直接略過。
  function turnLeaf(dir) {
    try {
      if (!_R.twoUp || !_R.stage) return;
      if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      var leaf = document.createElement("div");
      leaf.className = "codex-leaf " + (dir > 0 ? "turn-next" : "turn-prev");
      _R.stage.appendChild(leaf);
      var kill = function () { if (leaf.parentNode) leaf.parentNode.removeChild(leaf); };
      leaf.addEventListener("animationend", kill);
      setTimeout(kill, 800);
    } catch (e) {}
  }
  function next() { var c = _R.colsPerView || 1; if (_R.page + c <= _R.pages - 1) turnLeaf(1); goTo(_R.page + c); }
  function prev() { var c = _R.colsPerView || 1; if (_R.page - c >= 0) turnLeaf(-1); goTo(_R.page - c); }

  function updateFoot() {
    if (!_reader) return;
    var n = _R.fallback ? 1 : (_R.page + 1);
    _reader.querySelectorAll(".codex-folio .cur").forEach(function (el) { el.textContent = n; });
    // 對開模式頁碼顯示成「左–右」（如 3–4）
    var label = "" + n;
    if (_R.twoUp && !_R.fallback) {
      var right = Math.min(_R.pages, _R.page + 2);
      if (right > n) label = n + "–" + right;
    }
    _reader.querySelectorAll(".codex-pageno .cur").forEach(function (el) { el.textContent = label; });
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
    if (!_R.chapters.length) { d.innerHTML = '<div class="codex-toc-title">' + esc(T("codex.toc.empty")) + '</div>'; return; }
    d.innerHTML = '<div class="codex-toc-title">' + esc(T("codex.toc.title")) + '</div>' + _R.chapters.map(function (c) {
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

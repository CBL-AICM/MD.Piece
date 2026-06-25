/* MD.Piece 研究後台 — 獨立研究者頁面（登入 + 患者人數統計 + 兌換管理）。
   與病患 PWA 分開；共用同一套後端 API。需 doctor 角色帳號。 */
(function () {
  'use strict';

  var API = location.hostname === 'localhost' ? 'http://localhost:8000' : '';
  var TOK_KEY = 'mdpiece_admin_token';

  // ── helpers ───────────────────────────────────────────────
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function getTok() { try { return localStorage.getItem(TOK_KEY); } catch (e) { return null; } }
  function setTok(t) { try { t ? localStorage.setItem(TOK_KEY, t) : localStorage.removeItem(TOK_KEY); } catch (e) {} }
  function role(tok) {
    try {
      var p = JSON.parse(atob(tok.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
      return p.role;
    } catch (e) { return null; }
  }
  function api(path, opts) {
    opts = opts || {};
    var headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
    var tok = getTok();
    if (tok) headers['Authorization'] = 'Bearer ' + tok;
    return fetch(API + path, Object.assign({}, opts, { headers: headers })).then(function (r) {
      if (r.status === 401) { setTok(null); renderLogin(T('admin.err.sessionExpired')); throw new Error('401'); }
      return r;
    });
  }
  function icons() { if (window.lucide && lucide.createIcons) try { lucide.createIcons(); } catch (e) {} }
  var app = function () { return document.getElementById('app'); };

  // ── i18n（共用 window.MDPiece_i18n，跟病患 App 同一份語言偏好）──
  function T(k) { return (window.MDPiece_i18n && window.MDPiece_i18n.t) ? window.MDPiece_i18n.t(k) : k; }
  function Tf(k, v) { return (window.MDPiece_i18n && window.MDPiece_i18n.tf) ? window.MDPiece_i18n.tf(k, v) : T(k); }
  var _rerender = null;
  function wireLang() {
    var b = document.getElementById('ad-lang');
    if (b) b.onclick = function () { if (window.toggleLang) window.toggleLang(); };
  }
  function langBtn() {
    return '<button class="ad-tab" id="ad-lang" title="' + esc(T('lang.toggleTitle')) + '">'
      + esc(T('lang.label')) + '</button>';
  }
  window.addEventListener('mdpiece-lang-change', function () { try { if (_rerender) _rerender(); } catch (e) {} });

  // ── login ─────────────────────────────────────────────────
  function renderLogin(errMsg) {
    _rerender = function () { renderLogin(errMsg); };
    app().innerHTML =
      '<div class="ad-login"><div class="ad-login-card">'
      + '<div class="ad-brand">MD.Piece ' + esc(T('admin.console')) + '<small>RESEARCH CONSOLE</small></div>'
      + '<div class="ad-field"><label>' + esc(T('admin.login.username')) + '</label><input class="ad-input" id="ad-u" autocomplete="username" /></div>'
      + '<div class="ad-field"><label>' + esc(T('auth.label.password')) + '</label><input class="ad-input" id="ad-p" type="password" autocomplete="current-password" /></div>'
      + '<div class="ad-err" id="ad-err">' + esc(errMsg || '') + '</div>'
      + '<button class="ad-btn" id="ad-login"><i data-lucide="log-in"></i> ' + esc(T('auth.submit.login')) + '</button>'
      + '<p class="ad-meta" style="text-align:center;margin-top:14px">' + esc(T('admin.login.note')) + '</p>'
      + '<div style="text-align:center;margin-top:10px">' + langBtn() + '</div>'
      + '</div></div>';
    icons();
    wireLang();
    var u = document.getElementById('ad-u'), p = document.getElementById('ad-p');
    var btn = document.getElementById('ad-login');
    function submit() {
      var err = document.getElementById('ad-err');
      if (!u.value.trim() || !p.value) { err.textContent = T('admin.err.needCreds'); return; }
      btn.disabled = true; err.textContent = '';
      fetch(API + '/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: u.value.trim(), password: p.value }),
      }).then(function (r) {
        return r.json().then(function (j) { return { ok: r.ok, j: j }; });
      }).then(function (res) {
        if (!res.ok) { err.textContent = res.j.detail || T('admin.err.loginFail'); btn.disabled = false; return; }
        if (res.j.role !== 'doctor') { err.textContent = T('admin.err.notResearcher'); btn.disabled = false; return; }
        setTok(res.j.access_token);
        renderDashboard('participants');
      }).catch(function () { err.textContent = T('admin.err.network'); btn.disabled = false; });
    }
    btn.onclick = submit;
    p.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(); });
    u.focus();
  }

  // ── dashboard shell ───────────────────────────────────────
  function renderDashboard(tab) {
    _rerender = function () { renderDashboard(tab); };
    app().innerHTML =
      '<div class="ad-wrap">'
      + '<div class="ad-head"><h1>' + esc(T('admin.console')) + '</h1>'
      + '<span class="who" id="ad-who"></span>'
      + langBtn()
      + '<button class="ad-tab" id="ad-logout"><i data-lucide="log-out" style="width:14px;height:14px"></i> ' + esc(T('logout.label')) + '</button></div>'
      + '<div class="ad-tabs">'
      + '<button class="ad-tab" data-tab="participants">' + esc(T('admin.tab.participants')) + '</button>'
      + '<button class="ad-tab" data-tab="rewards">' + esc(T('admin.tab.rewards')) + '</button>'
      + '</div><div id="ad-body"><div class="ad-empty">' + esc(T('admin.loading')) + '</div></div></div>';
    document.getElementById('ad-logout').onclick = function () { setTok(null); renderLogin(); };
    wireLang();
    var who = role(getTok()); document.getElementById('ad-who').textContent = who ? T('admin.role.researcher') : '';
    Array.prototype.forEach.call(document.querySelectorAll('.ad-tab[data-tab]'), function (b) {
      b.onclick = function () { renderDashboard(b.getAttribute('data-tab')); };
    });
    icons();
    setActiveTab(tab);
    if (tab === 'rewards') loadRedemptions();
    else loadParticipants();
  }
  function setActiveTab(tab) {
    Array.prototype.forEach.call(document.querySelectorAll('.ad-tab[data-tab]'), function (b) {
      b.classList.toggle('active', b.getAttribute('data-tab') === tab);
    });
  }

  // ── 患者人數統計 tab ───────────────────────────────────────
  // 接 /admin-stats/patients：彙總卡（總人數 / 性別 / 年齡 / 疾病 / 活躍天數分布）
  // ＋患者清單。已於後端排除 sim3200_ 模擬帳號（從統計排除、不刪資料）。
  function loadParticipants() {
    var body = document.getElementById('ad-body');
    body.innerHTML = '<div id="ad-pt"><div class="ad-empty">' + esc(T('admin.loading')) + '</div></div>';
    api('/admin-stats/patients').then(function (r) {
      if (!r.ok) throw new Error('pt'); return r.json();
    }).then(renderParticipants).catch(function (e) {
      if (String(e.message) !== '401') document.getElementById('ad-pt').innerHTML = '<div class="ad-empty">' + esc(T('admin.err.participantsLoad')) + '</div>';
    });
  }
  // 患者清單可達上千列 → 前端搜尋 + 分頁，避免一次塞滿 DOM。
  var _ptAll = [];
  var _ptQuery = '';
  var _ptPage = 0;
  var PT_PAGE_SIZE = 50;

  function _genderLabel(g) {
    return g === 'male' ? T('admin.gender.male') : (g === 'female' ? T('admin.gender.female') : g);
  }

  // 把一個分布物件（{key:count}）畫成一張統計卡，數量多到少排序。
  function _distCard(title, dist) {
    var keys = Object.keys(dist || {});
    if (!keys.length) return '';
    keys.sort(function (a, b) { return dist[b] - dist[a]; });
    var rows = keys.map(function (k) {
      var label = (k === 'male' || k === 'female') ? _genderLabel(k) : k;
      return '<div class="ad-dist-row"><span class="ad-dist-k">' + esc(label) + '</span>'
        + '<span class="ad-dist-v">' + dist[k] + '</span></div>';
    }).join('');
    return '<div class="ad-card ad-stat-card"><h3>' + esc(title) + '</h3>' + rows + '</div>';
  }

  function _summaryHtml(data) {
    var s = data.summary || {};
    var headline = '<div class="ad-card ad-stat-headline">'
      + '<div class="ad-stat-big">' + (s.total || 0) + '</div>'
      + '<div class="ad-stat-cap">' + esc(T('admin.stat.totalPatients')) + '</div>'
      + '<div class="ad-sub">' + esc(Tf('admin.stat.withRecords', { n: s.with_records || 0 })) + '</div>'
      + '</div>';
    var cards = [
      _distCard(T('admin.stat.byGender'), s.by_gender),
      _distCard(T('admin.stat.byAge'), s.by_age_band),
      _distCard(T('admin.stat.byAdherence'), s.by_adherence_band),
      _distCard(T('admin.stat.byDisease'), s.by_disease),
    ].join('');
    return '<div class="ad-stat-grid">' + headline + cards + '</div>';
  }

  function renderParticipants(data) {
    var box = document.getElementById('ad-pt');
    _ptAll = data.patients || [];
    _ptQuery = '';
    _ptPage = 0;
    var summary = _summaryHtml(data);
    if (!_ptAll.length) {
      box.innerHTML = summary + '<div class="ad-empty">' + esc(T('admin.participants.empty')) + '</div>';
      return;
    }
    box.innerHTML = summary
      + '<p class="ad-meta">' + esc(Tf('admin.participants.summary', { n: _ptAll.length })) + ' ' + esc(data.note || '') + '</p>'
      + '<div class="ad-field" style="margin-bottom:10px"><input class="ad-input" id="ad-pt-search" placeholder="' + esc(T('admin.pt.search')) + '" /></div>'
      + '<div id="ad-pt-list"></div>';
    var s = document.getElementById('ad-pt-search');
    if (s) s.oninput = function () { _ptQuery = (s.value || '').trim().toLowerCase(); _ptPage = 0; _ptRenderList(); };
    _ptRenderList();
  }

  function _ptFiltered() {
    if (!_ptQuery) return _ptAll;
    return _ptAll.filter(function (p) {
      return ((p.nickname || '') + ' ' + (p.username || '') + ' ' + (p.patient_id || '') + ' ' + (p.disease || ''))
        .toLowerCase().indexOf(_ptQuery) !== -1;
    });
  }

  function _ptRenderList() {
    var box = document.getElementById('ad-pt-list');
    if (!box) return;
    var list = _ptFiltered();
    var pages = Math.max(1, Math.ceil(list.length / PT_PAGE_SIZE));
    if (_ptPage >= pages) _ptPage = pages - 1;
    var slice = list.slice(_ptPage * PT_PAGE_SIZE, (_ptPage + 1) * PT_PAGE_SIZE);
    if (!list.length) { box.innerHTML = '<div class="ad-empty">' + esc(T('admin.pt.noMatch')) + '</div>'; return; }
    var head = '<tr><th class="l">' + esc(T('admin.col.user')) + '</th>'
      + '<th>' + esc(T('admin.col.gender')) + '</th><th>' + esc(T('admin.col.age')) + '</th>'
      + '<th class="l">' + esc(T('admin.col.disease')) + '</th>'
      + '<th>' + esc(T('admin.col.adherenceDays')) + '</th><th class="l">' + esc(T('admin.col.registered')) + '</th></tr>';
    var rows = slice.map(function (p) {
      var uidShort = (p.patient_id || '').slice(0, 8);
      var name = p.nickname || p.username || '';
      var who = name
        ? '<b>' + esc(name) + '</b><div class="ad-sub">' + esc(uidShort) + '</div>'
        : '<span class="ad-sub">' + esc(uidShort) + '</span>';
      var reg = (p.registered_at || '').slice(0, 10);
      return '<tr class="ad-row" data-pid="' + esc(p.patient_id) + '">'
        + '<td class="l">' + who + '</td>'
        + '<td>' + (p.gender ? esc(_genderLabel(p.gender)) : '—') + '</td>'
        + '<td>' + (p.age != null ? p.age : '—') + '</td>'
        + '<td class="l">' + (p.disease ? esc(p.disease) : '<span class="ad-sub">—</span>') + '</td>'
        + '<td>' + (p.adherence_days != null ? p.adherence_days : '—') + '</td>'
        + '<td class="l ad-sub">' + esc(reg) + '</td></tr>';
    }).join('');
    var pager = pages > 1
      ? '<div style="display:flex;align-items:center;justify-content:center;gap:12px;margin-top:10px">'
        + '<button class="ad-btn secondary" id="ad-pt-prev"' + (_ptPage <= 0 ? ' disabled' : '') + '>‹</button>'
        + '<span class="ad-sub">' + esc(Tf('admin.pt.page', { page: _ptPage + 1, pages: pages })) + '</span>'
        + '<button class="ad-btn secondary" id="ad-pt-next"' + (_ptPage >= pages - 1 ? ' disabled' : '') + '>›</button>'
        + '</div>'
      : '';
    box.innerHTML = '<p class="ad-sub" style="margin:0 2px 6px">' + esc(Tf('admin.pt.shown', { shown: slice.length, total: list.length })) + '</p>'
      + '<div class="ad-card" style="padding:6px 10px"><table class="ad-tbl">' + head + rows + '</table></div>' + pager;
    Array.prototype.forEach.call(box.querySelectorAll('.ad-row'), function (tr) {
      tr.onclick = function () { openParticipant(tr.getAttribute('data-pid')); };
    });
    var prev = document.getElementById('ad-pt-prev'); if (prev) prev.onclick = function () { if (_ptPage > 0) { _ptPage--; _ptRenderList(); } };
    var next = document.getElementById('ad-pt-next'); if (next) next.onclick = function () { _ptPage++; _ptRenderList(); };
  }

  // ── per-participant drawer：個別患者的每日紀錄活躍度 ──────────
  function openParticipant(pid) {
    var bg = document.createElement('div'); bg.className = 'ad-drawer-bg';
    var dr = document.createElement('div'); dr.className = 'ad-drawer';
    dr.innerHTML = '<div class="ad-empty">' + esc(T('admin.loading')) + '</div>';
    function close() { bg.remove(); dr.remove(); }
    bg.onclick = close;
    document.body.appendChild(bg); document.body.appendChild(dr);
    api('/admin-stats/patients/' + encodeURIComponent(pid)).then(function (r) {
      if (!r.ok) throw new Error('sm'); return r.json();
    }).then(function (data) { renderParticipant(dr, data, close); })
      .catch(function (e) { if (String(e.message) !== '401') dr.innerHTML = '<div class="ad-empty">' + esc(T('admin.err.load')) + '</div>'; });
  }

  function _dailyCard(adh) {
    var daily = (adh && adh.daily) || [];
    var an = (adh && adh.analysis) || {};
    var summary = '<p class="ad-meta">' + esc(Tf('admin.daily.summary', {
        first: (an.first_date || '—'), last: (an.last_date || '—'),
        span: (an.span_days || 0), active: (adh.active_days || 0), streak: (an.longest_streak || 0),
      }))
      + (an.coverage != null ? esc(Tf('admin.daily.coverage', { pct: Math.round(an.coverage * 100) })) : '') + '</p>';
    var title = '<h3 style="font-size:.95rem;margin:16px 0 4px;color:var(--navy,#1a1730)">' + esc(T('admin.daily.title')) + '</h3>';
    if (!daily.length) return title + '<p class="ad-meta">' + esc(T('admin.daily.empty')) + '</p>';
    var head = '<tr><th class="l">' + esc(T('admin.col.date')) + '</th><th>' + esc(T('admin.col.symptoms')) + '</th><th>' + esc(T('admin.col.vitals')) + '</th><th>' + esc(T('admin.col.sleep')) + '</th><th>' + esc(T('admin.col.total')) + '</th></tr>';
    var rows = daily.map(function (d) {
      return '<tr><td class="l ad-sub">' + esc(d.date) + '</td>'
        + '<td>' + (d.symptoms || '·') + '</td><td>' + (d.vitals || '·') + '</td>'
        + '<td>' + (d.sleep || '·') + '</td><td class="ad-r">' + (d.total || 0) + '</td></tr>';
    }).join('');
    return title + summary
      + '<div class="ad-card" style="padding:6px 10px"><table class="ad-tbl">' + head + rows + '</table></div>';
  }

  function renderParticipant(dr, data, close) {
    var adh = data.adherence || {};
    dr.innerHTML =
      '<div class="ad-drawer-head"><h2>' + esc(T('admin.drawer.title')) + '</h2><button class="ad-x" id="ad-dx"><i data-lucide="x"></i></button></div>'
      + '<p class="ad-meta">' + esc(Tf('admin.drawer.activity', {
          id: (data.patient_id || '').slice(0, 12),
          active: (adh.active_days || 0),
          sym: (((adh.by_source || {}).symptoms || {}).days || 0),
          vit: (((adh.by_source || {}).vitals || {}).days || 0),
          slp: (((adh.by_source || {}).sleep || {}).days || 0),
        })) + '</p>'
      + _dailyCard(adh);
    document.getElementById('ad-dx').onclick = close;
    icons();
  }

  // ── rewards / redemptions tab ─────────────────────────────
  // 院方在此檢視病患的兌換申請，並核發（fulfilled）或退回退點（cancelled）。
  function rwStatus(st) {
    st = st || 'requested';
    var cls = st === 'fulfilled' ? 'ok' : (st === 'cancelled' ? 'none' : 'part');
    return '<span class="ad-pill ' + cls + '">' + esc(T('admin.rw.st.' + st)) + '</span>';
  }
  function loadRedemptions() {
    var body = document.getElementById('ad-body');
    body.innerHTML = '<div id="ad-rw"><div class="ad-empty">' + esc(T('admin.loading')) + '</div></div>';
    api('/rewards/admin/redemptions').then(function (r) {
      if (!r.ok) throw new Error('rw'); return r.json();
    }).then(renderRedemptions).catch(function (e) {
      if (String(e.message) !== '401') document.getElementById('ad-rw').innerHTML = '<div class="ad-empty">' + esc(T('admin.rw.err')) + '</div>';
    });
  }
  function renderRedemptions(data) {
    var box = document.getElementById('ad-rw');
    var rs = data.redemptions || [];
    if (!rs.length) { box.innerHTML = '<div class="ad-empty">' + esc(T('admin.rw.empty')) + '</div>'; return; }
    var c = data.counts || {};
    var head = '<tr><th class="l">' + esc(T('admin.rw.col.patient')) + '</th><th class="l">' + esc(T('admin.rw.col.reward')) + '</th>'
      + '<th>' + esc(T('admin.rw.col.cost')) + '</th><th>' + esc(T('admin.rw.col.status')) + '</th>'
      + '<th class="l">' + esc(T('admin.rw.col.time')) + '</th><th></th></tr>';
    var rows = rs.map(function (r) {
      var pending = (r.status || 'requested') === 'requested';
      var act = pending
        ? '<button class="ad-btn" data-act="fulfill" data-id="' + esc(r.id) + '">' + esc(T('admin.rw.fulfill')) + '</button>'
          + ' <button class="ad-btn secondary" data-act="cancel" data-id="' + esc(r.id) + '">' + esc(T('admin.rw.cancel')) + '</button>'
        : '<span class="ad-sub">—</span>';
      return '<tr><td class="l"><span class="ad-sub">' + esc((r.patient_id || '').slice(0, 8)) + '</span></td>'
        + '<td class="l">' + esc(r.reward_name || r.reward_id || '—') + '</td>'
        + '<td>' + (r.cost != null ? r.cost : '—') + '</td>'
        + '<td>' + rwStatus(r.status) + '</td>'
        + '<td class="l ad-sub">' + esc((r.created_at || '').slice(0, 10)) + '</td>'
        + '<td>' + act + '</td></tr>';
    }).join('');
    box.innerHTML = '<p class="ad-meta">' + esc(Tf('admin.rw.summary', { req: c.requested || 0, ful: c.fulfilled || 0, can: c.cancelled || 0 })) + '</p>'
      + '<div class="ad-card" style="padding:6px 10px"><table class="ad-tbl">' + head + rows + '</table></div>';
    Array.prototype.forEach.call(box.querySelectorAll('button[data-act]'), function (b) {
      b.onclick = function () { rwAction(b.getAttribute('data-act'), b.getAttribute('data-id'), b); };
    });
  }
  function rwAction(act, id, btn) {
    btn.disabled = true;
    api('/rewards/admin/redemptions/' + encodeURIComponent(id) + '/' + act, { method: 'POST' }).then(function (r) {
      if (!r.ok) throw new Error('act'); return r.json();
    }).then(function () { loadRedemptions(); }).catch(function (e) {
      if (String(e.message) !== '401') {
        btn.disabled = false;
        var box = document.getElementById('ad-rw');
        if (box) { var n = document.createElement('div'); n.className = 'ad-empty'; n.textContent = T('admin.rw.actErr'); box.insertBefore(n, box.firstChild); }
      }
    });
  }

  // ── boot ──────────────────────────────────────────────────
  function boot() {
    try { document.title = 'MD.Piece ' + T('admin.console'); } catch (e) {}
    var tok = getTok();
    if (tok && role(tok) === 'doctor') renderDashboard('participants');
    else { if (tok) setTok(null); renderLogin(); }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();

/* MD.Piece 研究後台 — 獨立研究者頁面（登入 + 研究問卷分析 + 患者管理）。
   與病患 PWA 分開；共用同一套後端 API。需 doctor 角色帳號。 */
(function () {
  'use strict';

  var API = location.hostname === 'localhost' ? 'http://localhost:8000' : '';
  var STUDY = 'mdpiece_feasibility_v2';
  var TOK_KEY = 'mdpiece_admin_token';
  var TPS = [
    { id: 'D0', label: 'D0' }, { id: 'D14', label: 'D14' },
    { id: 'D28', label: 'D28' }, { id: 'FU48', label: 'FU48' },
  ];

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
  function tpName(t) { return t === 'FU48' ? T('admin.tp.fu48') : t; }
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
        renderDashboard('analysis');
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
      + '<button class="ad-tab" data-tab="analysis">' + esc(T('admin.tab.analysis')) + '</button>'
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
    if (tab === 'participants') loadParticipants();
    else if (tab === 'rewards') loadRedemptions();
    else loadAnalysis();
  }
  function setActiveTab(tab) {
    Array.prototype.forEach.call(document.querySelectorAll('.ad-tab[data-tab]'), function (b) {
      b.classList.toggle('active', b.getAttribute('data-tab') === tab);
    });
  }

  // ── analysis tab ──────────────────────────────────────────
  function descCell(d) {
    if (!d || !d.n) return '—';
    return '<span class="ad-r">' + d.mean + (d.sd != null ? '±' + d.sd : '') + '</span>'
      + '<div class="ad-sub">n=' + d.n + ' · ' + esc(T('admin.stat.median')) + ' ' + d.median + '</div>';
  }
  function loadAnalysis() {
    var body = document.getElementById('ad-body');
    body.innerHTML =
      '<div class="ad-actions">'
      + '<button class="ad-btn" id="ad-exp-long"><i data-lucide="download"></i> ' + esc(T('admin.export.long')) + '</button>'
      + '<button class="ad-btn secondary" id="ad-exp-wide"><i data-lucide="download"></i> ' + esc(T('admin.export.wide')) + '</button>'
      + '</div><div id="ad-an"><div class="ad-empty">' + esc(T('admin.loading')) + '</div></div>';
    document.getElementById('ad-exp-long').onclick = function () { exportCsv('long'); };
    document.getElementById('ad-exp-wide').onclick = function () { exportCsv('wide'); };
    icons();
    api('/surveys/study/' + STUDY + '/analysis').then(function (r) {
      if (!r.ok) throw new Error('an'); return r.json();
    }).then(renderAnalysis).catch(function (e) {
      if (String(e.message) !== '401') document.getElementById('ad-an').innerHTML = '<div class="ad-empty">' + esc(T('admin.err.analysisLoad')) + '</div>';
    });
  }
  function renderAnalysis(data) {
    var box = document.getElementById('ad-an');
    if (!data.parts || !data.parts.length || !data.respondents) {
      box.innerHTML = '<div class="ad-empty">' + esc(T('admin.analysis.empty')) + '</div>';
      return;
    }
    var cards = data.parts.map(function (p) {
      var inner = '';
      if (p.by_timepoint) {
        var tps = p.timepoints || Object.keys(p.by_timepoint);
        inner += '<table class="ad-tbl"><tr><th class="l">' + esc(T('admin.col.timepoint')) + '</th>' + tps.map(function (t) { return '<th>' + esc(tpName(t)) + '</th>'; }).join('') + '</tr>'
          + '<tr><td class="l">' + esc(T('admin.col.value')) + '</td>' + tps.map(function (t) { return '<td>' + descCell(p.by_timepoint[t]) + '</td>'; }).join('') + '</tr></table>';
      }
      if (p.paired_D0_D28) {
        inner += '<p class="ad-meta">' + esc(T('admin.analysis.paired')) + '<span class="ad-r">' + p.paired_D0_D28.r + '</span>'
          + esc(Tf('admin.analysis.pairedTail', { dir: p.paired_D0_D28.direction, n: p.paired_D0_D28.n_pairs })) + '</p>';
      }
      if (p.subscales) {
        var tps2 = p.timepoints || [];
        Object.keys(p.subscales).forEach(function (name) {
          var byt = p.subscales[name];
          inner += '<table class="ad-tbl"><tr><th class="l">' + esc(name) + '</th>' + tps2.map(function (t) { return '<th>' + esc(tpName(t)) + '</th>'; }).join('') + '</tr><tr><td class="l">' + esc(T('admin.col.mean')) + '</td>'
            + tps2.map(function (t) {
              var d = byt[t] || {};
              return '<td>' + descCell(d) + (d.pct_acceptable != null ? '<div class="ad-sub">' + esc(Tf('admin.analysis.acceptable', { pct: d.pct_acceptable })) + '</div>' : '') + '</td>';
            }).join('') + '</tr></table>';
        });
      }
      if (p.top_score_rate) {
        inner += '<p class="ad-meta">collaboRATE top-score' + esc(T('admin.colon')) + Object.keys(p.top_score_rate).map(function (t) {
          var x = p.top_score_rate[t]; return esc(tpName(t)) + ' ' + (x.rate != null ? Math.round(x.rate * 100) + '%' : '—') + esc(Tf('admin.nPar', { n: x.n }));
        }).join(T('admin.semi')) + '</p>';
      }
      if (p.nps) {
        inner += '<p class="ad-meta">' + Object.keys(p.nps).map(function (t) {
          var x = p.nps[t]; return esc(tpName(t)) + ' NPS <span class="ad-r">' + x.nps + '</span>' + esc(Tf('admin.analysis.npsTail', { pro: x.promoters, pas: x.passives, det: x.detractors }));
        }).join(T('admin.semi')) + '</p>';
      }
      if (p.cronbach_alpha) {
        var ca = p.cronbach_alpha;
        inner += ca.subscales
          ? '<p class="ad-meta">Cronbach α' + esc(T('admin.colon')) + Object.keys(ca.subscales).map(function (k) { return esc(k) + ' ' + ca.subscales[k].alpha; }).join(T('admin.semi')) + '</p>'
          : '<p class="ad-meta">Cronbach α = <span class="ad-r">' + ca.alpha + '</span>' + esc(Tf('admin.analysis.cronbachTail', { k: ca.k, scope: ca.scope || '' })) + '</p>';
      }
      if (p.background) {
        inner += Object.keys(p.background).map(function (iid) {
          var b = p.background[iid];
          var cc = Object.keys(b.counts || {}).map(function (o) { return esc(o) + '×' + b.counts[o]; }).join(T('admin.comma'));
          return '<p class="ad-meta">' + esc(b.text) + esc(T('admin.colon')) + (cc || '—') + '</p>';
        }).join('');
      }
      return '<div class="ad-card"><h3>' + esc(p.part) + '. ' + esc(p.title)
        + ' <span class="meta">' + esc(Tf('admin.analysis.cardMeta', { method: p.method, n: p.respondents })) + '</span></h3>' + inner + '</div>';
    }).join('');
    box.innerHTML = '<p class="ad-meta">' + esc(Tf('admin.analysis.respondents', { n: data.respondents })) + esc(data.note || '') + '</p>' + cards;
  }

  function exportCsv(fmt) {
    api('/surveys/study/' + STUDY + '/export?format=' + fmt).then(function (r) {
      if (!r.ok) throw new Error('exp'); return r.text();
    }).then(function (text) {
      var blob = new Blob([text], { type: 'text/csv;charset=utf-8' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a'); a.href = url; a.download = STUDY + '_' + fmt + '.csv';
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    }).catch(function (e) { if (String(e.message) !== '401') alert(T('admin.err.exportFail')); });
  }

  // ── participants tab ──────────────────────────────────────
  function pill(done, total) {
    if (!total) return '<span class="ad-sub">—</span>';
    var cls = done >= total ? 'ok' : (done > 0 ? 'part' : 'none');
    return '<span class="ad-pill ' + cls + '">' + done + '/' + total + '</span>';
  }
  function loadParticipants() {
    var body = document.getElementById('ad-body');
    body.innerHTML = '<div id="ad-pt"><div class="ad-empty">' + esc(T('admin.loading')) + '</div></div>';
    api('/surveys/study/' + STUDY + '/participants').then(function (r) {
      if (!r.ok) throw new Error('pt'); return r.json();
    }).then(renderParticipants).catch(function (e) {
      if (String(e.message) !== '401') document.getElementById('ad-pt').innerHTML = '<div class="ad-empty">' + esc(T('admin.err.participantsLoad')) + '</div>';
    });
  }
  function renderParticipants(data) {
    var box = document.getElementById('ad-pt');
    var ps = data.participants || [];
    if (!ps.length) {
      box.innerHTML = '<div class="ad-empty">' + esc(T('admin.participants.empty')) + '</div>';
      return;
    }
    var head = '<tr><th class="l">' + esc(T('admin.col.code')) + '</th><th class="l">' + esc(T('admin.col.user')) + '</th>'
      + TPS.map(function (t) { return '<th>' + esc(tpName(t.id)) + '</th>'; }).join('')
      + '<th>' + esc(T('admin.col.adherenceDays')) + '</th><th class="l">' + esc(T('admin.col.lastActivity')) + '</th></tr>';
    var rows = ps.map(function (p) {
      var tpc = TPS.map(function (t) {
        var c = (p.completion || {})[t.id];
        return '<td>' + (c ? pill(c.done, c.total) : '<span class="ad-sub">—</span>') + '</td>';
      }).join('');
      var uidShort = (p.patient_id || '').slice(0, 8);
      var last = (p.last_activity || '').slice(0, 10);
      return '<tr class="ad-row" data-pid="' + esc(p.patient_id) + '">'
        + '<td class="l"><b>' + esc(p.participant_code || '—') + '</b></td>'
        + '<td class="l"><span class="ad-sub">' + esc(uidShort) + '</span></td>'
        + tpc + '<td>' + (p.adherence_days != null ? p.adherence_days : '—') + '</td>'
        + '<td class="l ad-sub">' + esc(last) + '</td></tr>';
    }).join('');
    box.innerHTML = '<p class="ad-meta">' + esc(Tf('admin.participants.summary', { n: ps.length })) + '</p>'
      + '<div class="ad-card" style="padding:6px 10px"><table class="ad-tbl">' + head + rows + '</table></div>';
    Array.prototype.forEach.call(box.querySelectorAll('.ad-row'), function (tr) {
      tr.onclick = function () { openParticipant(tr.getAttribute('data-pid')); };
    });
  }

  // ── per-participant drawer ────────────────────────────────
  function openParticipant(pid) {
    var bg = document.createElement('div'); bg.className = 'ad-drawer-bg';
    var dr = document.createElement('div'); dr.className = 'ad-drawer';
    dr.innerHTML = '<div class="ad-empty">' + esc(T('admin.loading')) + '</div>';
    function close() { bg.remove(); dr.remove(); }
    bg.onclick = close;
    document.body.appendChild(bg); document.body.appendChild(dr);
    api('/surveys/study/' + STUDY + '/participants/' + encodeURIComponent(pid) + '/summary').then(function (r) {
      if (!r.ok) throw new Error('sm'); return r.json();
    }).then(function (data) { renderParticipant(dr, data, close); })
      .catch(function (e) { if (String(e.message) !== '401') dr.innerHTML = '<div class="ad-empty">' + esc(T('admin.err.load')) + '</div>'; });
  }
  function scoreText(sc) {
    if (!sc) return '—';
    if (sc.method === 'mean') return sc.mean != null ? (T('admin.score.mean') + ' ' + sc.mean) : T('admin.score.none');
    if (sc.method === 'sum') return sc.total != null ? (T('admin.score.total') + ' ' + sc.total) : T('admin.score.none');
    if (sc.method === 'top_score') return Tf('admin.score.topMean', { top: (sc.top_score != null ? sc.top_score : '—'), mean: (sc.mean != null ? sc.mean : '—') });
    if (sc.method === 'subscales') {
      var s = sc.subscales || {};
      return Object.keys(s).map(function (k) { return k + ' ' + (s[k].mean != null ? s[k].mean : '—'); }).join(T('admin.comma'));
    }
    return T('admin.score.filled');
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
    // 以所有出現過的時點為欄
    var allTps = [];
    (data.parts || []).forEach(function (p) { (p.timepoints || []).forEach(function (t) { if (allTps.indexOf(t) < 0) allTps.push(t); }); });
    var order = ['D0', 'D14', 'D28', 'FU48'];
    allTps.sort(function (a, b) { return order.indexOf(a) - order.indexOf(b); });
    var head = '<tr><th class="l">' + esc(T('admin.col.part')) + '</th>' + allTps.map(function (t) { return '<th>' + esc(tpName(t)) + '</th>'; }).join('') + '</tr>';
    // 重建每列以對齊欄位
    var rows = (data.parts || []).map(function (p) {
      var cells = allTps.map(function (tp) {
        if ((p.timepoints || []).indexOf(tp) < 0) return '<td class="ad-sub">·</td>';
        var st = (p.by_timepoint || {})[tp] || {};
        return '<td>' + (st.completed ? scoreText(st.scores) : '<span class="ad-sub">' + esc(T('admin.status.unfilled')) + '</span>') + '</td>';
      }).join('');
      return '<tr><td class="l"><b>' + esc(p.part) + '</b> ' + esc(p.title) + '</td>' + cells + '</tr>';
    }).join('');
    var ehl = data.eheals_m07
      ? '<p class="ad-meta">' + esc(Tf('admin.eheals', { score: data.eheals_m07.total_score, level: (data.eheals_m07.literacy_level || '') })) + '</p>' : '';
    dr.innerHTML =
      '<div class="ad-drawer-head"><h2>' + esc(T('admin.drawer.title')) + '</h2><button class="ad-x" id="ad-dx"><i data-lucide="x"></i></button></div>'
      + '<p class="ad-meta">' + esc(Tf('admin.drawer.activity', {
          id: (data.patient_id || '').slice(0, 12),
          active: (adh.active_days || 0),
          sym: (((adh.by_source || {}).symptoms || {}).days || 0),
          vit: (((adh.by_source || {}).vitals || {}).days || 0),
          slp: (((adh.by_source || {}).sleep || {}).days || 0),
        })) + '</p>'
      + ehl
      + '<div class="ad-card" style="padding:6px 10px"><table class="ad-tbl">' + head + rows + '</table></div>'
      + '<p class="ad-meta">' + esc(T('admin.drawer.note')) + '</p>'
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
    if (tok && role(tok) === 'doctor') renderDashboard('analysis');
    else { if (tok) setTok(null); renderLogin(); }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();

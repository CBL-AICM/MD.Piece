/* MD.Piece 研究後台 — 獨立研究者頁面（登入 + 研究問卷分析 + 患者管理）。
   與病患 PWA 分開；共用同一套後端 API。需 doctor 角色帳號。 */
(function () {
  'use strict';

  var API = location.hostname === 'localhost' ? 'http://localhost:8000' : '';
  var STUDY = 'mdpiece_feasibility_v2';
  var TOK_KEY = 'mdpiece_admin_token';
  var TPS = [
    { id: 'D0', label: 'D0' }, { id: 'D14', label: 'D14' },
    { id: 'D28', label: 'D28' }, { id: 'FU48', label: '回診48h' },
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
      if (r.status === 401) { setTok(null); renderLogin('登入已過期，請重新登入'); throw new Error('401'); }
      return r;
    });
  }
  function icons() { if (window.lucide && lucide.createIcons) try { lucide.createIcons(); } catch (e) {} }
  var app = function () { return document.getElementById('app'); };

  // ── login ─────────────────────────────────────────────────
  function renderLogin(errMsg) {
    app().innerHTML =
      '<div class="ad-login"><div class="ad-login-card">'
      + '<div class="ad-brand">MD.Piece 研究後台<small>RESEARCH CONSOLE</small></div>'
      + '<div class="ad-field"><label>研究者帳號</label><input class="ad-input" id="ad-u" autocomplete="username" /></div>'
      + '<div class="ad-field"><label>密碼</label><input class="ad-input" id="ad-p" type="password" autocomplete="current-password" /></div>'
      + '<div class="ad-err" id="ad-err">' + esc(errMsg || '') + '</div>'
      + '<button class="ad-btn" id="ad-login"><i data-lucide="log-in"></i> 登入</button>'
      + '<p class="ad-meta" style="text-align:center;margin-top:14px">僅限研究者帳號。此頁不收集病患資料、僅供研究分析。</p>'
      + '</div></div>';
    icons();
    var u = document.getElementById('ad-u'), p = document.getElementById('ad-p');
    var btn = document.getElementById('ad-login');
    function submit() {
      var err = document.getElementById('ad-err');
      if (!u.value.trim() || !p.value) { err.textContent = '請輸入帳號與密碼'; return; }
      btn.disabled = true; err.textContent = '';
      fetch(API + '/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: u.value.trim(), password: p.value }),
      }).then(function (r) {
        return r.json().then(function (j) { return { ok: r.ok, j: j }; });
      }).then(function (res) {
        if (!res.ok) { err.textContent = res.j.detail || '登入失敗'; btn.disabled = false; return; }
        if (res.j.role !== 'doctor') { err.textContent = '此頁僅限研究者帳號'; btn.disabled = false; return; }
        setTok(res.j.access_token);
        renderDashboard('analysis');
      }).catch(function () { err.textContent = '連線失敗，稍後再試'; btn.disabled = false; });
    }
    btn.onclick = submit;
    p.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(); });
    u.focus();
  }

  // ── dashboard shell ───────────────────────────────────────
  function renderDashboard(tab) {
    app().innerHTML =
      '<div class="ad-wrap">'
      + '<div class="ad-head"><h1>研究後台</h1>'
      + '<span class="who" id="ad-who"></span>'
      + '<button class="ad-tab" id="ad-logout"><i data-lucide="log-out" style="width:14px;height:14px"></i> 登出</button></div>'
      + '<div class="ad-tabs">'
      + '<button class="ad-tab" data-tab="analysis">研究問卷分析</button>'
      + '<button class="ad-tab" data-tab="participants">患者管理</button>'
      + '</div><div id="ad-body"><div class="ad-empty">載入中…</div></div></div>';
    document.getElementById('ad-logout').onclick = function () { setTok(null); renderLogin(); };
    var who = role(getTok()); document.getElementById('ad-who').textContent = who ? '身分：研究者' : '';
    Array.prototype.forEach.call(document.querySelectorAll('.ad-tab[data-tab]'), function (b) {
      b.onclick = function () { renderDashboard(b.getAttribute('data-tab')); };
    });
    icons();
    setActiveTab(tab);
    if (tab === 'participants') loadParticipants(); else loadAnalysis();
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
      + '<div class="ad-sub">n=' + d.n + ' · 中位 ' + d.median + '</div>';
  }
  function loadAnalysis() {
    var body = document.getElementById('ad-body');
    body.innerHTML =
      '<div class="ad-actions">'
      + '<button class="ad-btn" id="ad-exp-long"><i data-lucide="download"></i> 匯出 long CSV</button>'
      + '<button class="ad-btn secondary" id="ad-exp-wide"><i data-lucide="download"></i> 匯出 wide CSV</button>'
      + '</div><div id="ad-an"><div class="ad-empty">載入中…</div></div>';
    document.getElementById('ad-exp-long').onclick = function () { exportCsv('long'); };
    document.getElementById('ad-exp-wide').onclick = function () { exportCsv('wide'); };
    icons();
    api('/surveys/study/' + STUDY + '/analysis').then(function (r) {
      if (!r.ok) throw new Error('an'); return r.json();
    }).then(renderAnalysis).catch(function (e) {
      if (String(e.message) !== '401') document.getElementById('ad-an').innerHTML = '<div class="ad-empty">分析載入失敗</div>';
    });
  }
  function renderAnalysis(data) {
    var box = document.getElementById('ad-an');
    if (!data.parts || !data.parts.length || !data.respondents) {
      box.innerHTML = '<div class="ad-empty">目前尚無作答資料。受試者在病患 App 完成填答後，這裡會顯示彙整。</div>';
      return;
    }
    var cards = data.parts.map(function (p) {
      var inner = '';
      if (p.by_timepoint) {
        var tps = p.timepoints || Object.keys(p.by_timepoint);
        inner += '<table class="ad-tbl"><tr><th class="l">時點</th>' + tps.map(function (t) { return '<th>' + esc(t) + '</th>'; }).join('') + '</tr>'
          + '<tr><td class="l">數值</td>' + tps.map(function (t) { return '<td>' + descCell(p.by_timepoint[t]) + '</td>'; }).join('') + '</tr></table>';
      }
      if (p.paired_D0_D28) {
        inner += '<p class="ad-meta">配對 D0→D28 效應量 r = <span class="ad-r">' + p.paired_D0_D28.r + '</span>（' + esc(p.paired_D0_D28.direction) + '，n=' + p.paired_D0_D28.n_pairs + '）</p>';
      }
      if (p.subscales) {
        var tps2 = p.timepoints || [];
        Object.keys(p.subscales).forEach(function (name) {
          var byt = p.subscales[name];
          inner += '<table class="ad-tbl"><tr><th class="l">' + esc(name) + '</th>' + tps2.map(function (t) { return '<th>' + esc(t) + '</th>'; }).join('') + '</tr><tr><td class="l">平均</td>'
            + tps2.map(function (t) {
              var d = byt[t] || {};
              return '<td>' + descCell(d) + (d.pct_acceptable != null ? '<div class="ad-sub">≥可接受 ' + d.pct_acceptable + '%</div>' : '') + '</td>';
            }).join('') + '</tr></table>';
        });
      }
      if (p.top_score_rate) {
        inner += '<p class="ad-meta">collaboRATE top-score：' + Object.keys(p.top_score_rate).map(function (t) {
          var x = p.top_score_rate[t]; return esc(t) + ' ' + (x.rate != null ? Math.round(x.rate * 100) + '%' : '—') + '（n=' + x.n + '）';
        }).join('；') + '</p>';
      }
      if (p.nps) {
        inner += '<p class="ad-meta">' + Object.keys(p.nps).map(function (t) {
          var x = p.nps[t]; return esc(t) + ' NPS <span class="ad-r">' + x.nps + '</span>（推薦 ' + x.promoters + '／中立 ' + x.passives + '／貶低 ' + x.detractors + '）';
        }).join('；') + '</p>';
      }
      if (p.cronbach_alpha) {
        var ca = p.cronbach_alpha;
        inner += ca.subscales
          ? '<p class="ad-meta">Cronbach α：' + Object.keys(ca.subscales).map(function (k) { return esc(k) + ' ' + ca.subscales[k].alpha; }).join('；') + '</p>'
          : '<p class="ad-meta">Cronbach α = <span class="ad-r">' + ca.alpha + '</span>（k=' + ca.k + '，' + esc(ca.scope || '') + '）</p>';
      }
      if (p.background) {
        inner += Object.keys(p.background).map(function (iid) {
          var b = p.background[iid];
          var cc = Object.keys(b.counts || {}).map(function (o) { return esc(o) + '×' + b.counts[o]; }).join('、');
          return '<p class="ad-meta">' + esc(b.text) + '：' + (cc || '—') + '</p>';
        }).join('');
      }
      return '<div class="ad-card"><h3>' + esc(p.part) + '. ' + esc(p.title)
        + ' <span class="meta">（' + esc(p.method) + '，n=' + p.respondents + '）</span></h3>' + inner + '</div>';
    }).join('');
    box.innerHTML = '<p class="ad-meta">受試者 ' + data.respondents + ' 人。' + esc(data.note || '') + '</p>' + cards;
  }

  function exportCsv(fmt) {
    api('/surveys/study/' + STUDY + '/export?format=' + fmt).then(function (r) {
      if (!r.ok) throw new Error('exp'); return r.text();
    }).then(function (text) {
      var blob = new Blob([text], { type: 'text/csv;charset=utf-8' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a'); a.href = url; a.download = STUDY + '_' + fmt + '.csv';
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    }).catch(function (e) { if (String(e.message) !== '401') alert('匯出失敗'); });
  }

  // ── participants tab ──────────────────────────────────────
  function pill(done, total) {
    if (!total) return '<span class="ad-sub">—</span>';
    var cls = done >= total ? 'ok' : (done > 0 ? 'part' : 'none');
    return '<span class="ad-pill ' + cls + '">' + done + '/' + total + '</span>';
  }
  function loadParticipants() {
    var body = document.getElementById('ad-body');
    body.innerHTML = '<div id="ad-pt"><div class="ad-empty">載入中…</div></div>';
    api('/surveys/study/' + STUDY + '/participants').then(function (r) {
      if (!r.ok) throw new Error('pt'); return r.json();
    }).then(renderParticipants).catch(function (e) {
      if (String(e.message) !== '401') document.getElementById('ad-pt').innerHTML = '<div class="ad-empty">受試者列表載入失敗</div>';
    });
  }
  function renderParticipants(data) {
    var box = document.getElementById('ad-pt');
    var ps = data.participants || [];
    if (!ps.length) {
      box.innerHTML = '<div class="ad-empty">目前尚無受試者作答。</div>';
      return;
    }
    var head = '<tr><th class="l">代號</th><th class="l">使用者</th>'
      + TPS.map(function (t) { return '<th>' + esc(t.label) + '</th>'; }).join('')
      + '<th>依從(天)</th><th class="l">最後活動</th></tr>';
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
    box.innerHTML = '<p class="ad-meta">共 ' + ps.length + ' 位受試者。數字＝該時點已完成份數／適用份數；點列查看個人跨時點彙整。</p>'
      + '<div class="ad-card" style="padding:6px 10px"><table class="ad-tbl">' + head + rows + '</table></div>';
    Array.prototype.forEach.call(box.querySelectorAll('.ad-row'), function (tr) {
      tr.onclick = function () { openParticipant(tr.getAttribute('data-pid')); };
    });
  }

  // ── per-participant drawer ────────────────────────────────
  function openParticipant(pid) {
    var bg = document.createElement('div'); bg.className = 'ad-drawer-bg';
    var dr = document.createElement('div'); dr.className = 'ad-drawer';
    dr.innerHTML = '<div class="ad-empty">載入中…</div>';
    function close() { bg.remove(); dr.remove(); }
    bg.onclick = close;
    document.body.appendChild(bg); document.body.appendChild(dr);
    api('/surveys/study/' + STUDY + '/participants/' + encodeURIComponent(pid) + '/summary').then(function (r) {
      if (!r.ok) throw new Error('sm'); return r.json();
    }).then(function (data) { renderParticipant(dr, data, close); })
      .catch(function (e) { if (String(e.message) !== '401') dr.innerHTML = '<div class="ad-empty">載入失敗</div>'; });
  }
  function scoreText(sc) {
    if (!sc) return '—';
    if (sc.method === 'mean') return sc.mean != null ? ('平均 ' + sc.mean) : '不計分';
    if (sc.method === 'sum') return sc.total != null ? ('總分 ' + sc.total) : '不計分';
    if (sc.method === 'top_score') return 'top ' + (sc.top_score != null ? sc.top_score : '—') + '／平均 ' + (sc.mean != null ? sc.mean : '—');
    if (sc.method === 'subscales') {
      var s = sc.subscales || {};
      return Object.keys(s).map(function (k) { return k + ' ' + (s[k].mean != null ? s[k].mean : '—'); }).join('，');
    }
    return '已填';
  }
  function renderParticipant(dr, data, close) {
    var adh = data.adherence || {};
    // 以所有出現過的時點為欄
    var allTps = [];
    (data.parts || []).forEach(function (p) { (p.timepoints || []).forEach(function (t) { if (allTps.indexOf(t) < 0) allTps.push(t); }); });
    var order = ['D0', 'D14', 'D28', 'FU48'];
    allTps.sort(function (a, b) { return order.indexOf(a) - order.indexOf(b); });
    var head = '<tr><th class="l">部分</th>' + allTps.map(function (t) { return '<th>' + esc(t) + '</th>'; }).join('') + '</tr>';
    // 重建每列以對齊欄位
    var rows = (data.parts || []).map(function (p) {
      var cells = allTps.map(function (tp) {
        if ((p.timepoints || []).indexOf(tp) < 0) return '<td class="ad-sub">·</td>';
        var st = (p.by_timepoint || {})[tp] || {};
        return '<td>' + (st.completed ? scoreText(st.scores) : '<span class="ad-sub">未填</span>') + '</td>';
      }).join('');
      return '<tr><td class="l"><b>' + esc(p.part) + '</b> ' + esc(p.title) + '</td>' + cells + '</tr>';
    }).join('');
    var ehl = data.eheals_m07
      ? '<p class="ad-meta">M07 eHEALS 總分 ' + esc(data.eheals_m07.total_score) + '（' + esc(data.eheals_m07.literacy_level || '') + '）</p>' : '';
    dr.innerHTML =
      '<div class="ad-drawer-head"><h2>受試者彙整</h2><button class="ad-x" id="ad-dx"><i data-lucide="x"></i></button></div>'
      + '<p class="ad-meta">使用者 ' + esc((data.patient_id || '').slice(0, 12)) + '… · 日常紀錄活動 <b>' + (adh.active_days || 0) + '</b> 天'
      + '（症狀 ' + (((adh.by_source || {}).symptoms || {}).days || 0) + '／生理值 ' + (((adh.by_source || {}).vitals || {}).days || 0) + '／睡眠 ' + (((adh.by_source || {}).sleep || {}).days || 0) + '）</p>'
      + ehl
      + '<div class="ad-card" style="padding:6px 10px"><table class="ad-tbl">' + head + rows + '</table></div>'
      + '<p class="ad-meta">數值為各量表計分結果；「·」表該時點不適用、「未填」表尚未作答。</p>';
    document.getElementById('ad-dx').onclick = close;
    icons();
  }

  // ── boot ──────────────────────────────────────────────────
  function boot() {
    var tok = getTok();
    if (tok && role(tok) === 'doctor') renderDashboard('analysis');
    else { if (tok) setTok(null); renderLogin(); }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();

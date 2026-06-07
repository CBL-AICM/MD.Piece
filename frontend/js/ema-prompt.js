/*
 * ema-prompt.js — EMA 待作答問卷的 App 內通道（codebook v3 / EMA 觸發引擎前端）
 *
 * 流程：開 App / 點 Web Push 深連結 → GET /ema/pending → 彈底部問卷 sheet →
 *   作答 → POST /surveys/{key}/responses → POST /ema/deliveries/{id}/complete。
 * 後端：backend/routers/ema.py（pending / complete）、surveys 引擎（題目與計分）。
 *
 * 設計：自足、解耦（沿用 app.js 同樣的 API base 與 token key，不依賴其內部函式，
 *   避免動到 app.js 上萬行）。只在已登入時運作。
 *
 * 注意：EMA 推送用的 survey 建議是「無 timepoints」的短微問卷；若 survey 設了
 *   timepoints，submit 會要求 timepoint（後端會明確 400，規則 12）。
 */
(function () {
  'use strict';

  var API = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '';
  var TOKEN_KEY = 'mdpiece_access_token';
  var POLL_MS = 60000;
  var showing = false;

  function token() { try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; } }
  function authed() { return !!token(); }
  function H() { return { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token() }; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>]/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]; }); }

  // ── 一次性注入樣式 ──
  function injectCss() {
    if (document.getElementById('ema-css')) return;
    var s = document.createElement('style'); s.id = 'ema-css';
    s.textContent =
      '.ema-scrim{position:fixed;inset:0;background:rgba(15,27,39,.45);z-index:9998;opacity:0;transition:.3s}' +
      '.ema-scrim.on{opacity:1}' +
      '.ema-sheet{position:fixed;left:0;right:0;bottom:0;max-width:520px;margin:0 auto;background:#fff;z-index:9999;' +
      'border-radius:22px 22px 0 0;padding:8px 18px 22px;transform:translateY(105%);transition:transform .38s cubic-bezier(.2,.9,.3,1.1);' +
      'max-height:86vh;overflow-y:auto;box-shadow:0 -10px 40px -10px rgba(31,61,88,.4);font-family:inherit}' +
      '.ema-sheet.on{transform:translateY(0)}' +
      '.ema-grab{width:40px;height:5px;border-radius:9px;background:rgba(31,61,88,.15);margin:8px auto 12px}' +
      '.ema-chip{display:inline-block;font-size:12px;font-weight:700;color:#2F8378;background:#E4F0EE;padding:5px 11px;border-radius:99px;margin-bottom:10px}' +
      '.ema-sheet h3{font-size:18px;font-weight:800;margin:2px 0 3px;color:#1F3D58}' +
      '.ema-sub{font-size:13px;color:#5A7388;margin:0 0 16px}' +
      '.ema-q{margin-bottom:18px}.ema-qt{font-size:15px;font-weight:600;margin-bottom:9px;color:#1F3D58;line-height:1.45}' +
      '.ema-lk{display:flex;gap:6px;flex-wrap:wrap}' +
      '.ema-lk button{flex:1;min-width:34px;min-height:42px;border:1.5px solid rgba(31,61,88,.12);background:#fff;border-radius:11px;font:inherit;font-size:15px;font-weight:700;color:#5A7388;cursor:pointer}' +
      '.ema-lk button.sel{background:#4A90C2;border-color:#4A90C2;color:#fff}' +
      '.ema-opt{display:block;width:100%;text-align:left;border:1.5px solid rgba(31,61,88,.12);background:#fff;border-radius:11px;padding:11px 13px;margin-bottom:7px;font:inherit;font-size:14px;cursor:pointer}' +
      '.ema-opt.sel{background:#EAF2F9;border-color:#4A90C2;color:#1F3D58;font-weight:600}' +
      '.ema-ends{display:flex;justify-content:space-between;font-size:11px;color:#8FA4B5;margin-top:3px}' +
      '.ema-ta{width:100%;min-height:64px;border:1.5px solid rgba(31,61,88,.12);border-radius:11px;padding:10px;font:inherit;font-size:14px}' +
      '.ema-submit{width:100%;min-height:46px;border:0;border-radius:13px;background:#4A90C2;color:#fff;font:inherit;font-size:15px;font-weight:700;cursor:pointer;margin-top:4px}' +
      '.ema-submit:disabled{opacity:.4;cursor:not-allowed}' +
      '.ema-skip{width:100%;background:none;border:0;color:#8FA4B5;font:inherit;font-size:13px;text-decoration:underline;cursor:pointer;margin-top:10px}';
    document.head.appendChild(s);
  }

  function api(path, opts) {
    return fetch(API + path, Object.assign({ headers: H() }, opts || {}))
      .then(function (r) { if (!r.ok) throw new Error('http ' + r.status); return r.json(); });
  }

  // ── 渲染一份 EMA 問卷 ──
  function render(delivery, survey, patientId) {
    injectCss();
    if (showing) return; showing = true;
    var answers = {};
    var scrim = document.createElement('div'); scrim.className = 'ema-scrim';
    var sheet = document.createElement('div'); sheet.className = 'ema-sheet';
    var items = survey.items || [];
    // 研究問卷的量尺放在 scoring.scale（非逐題）；render 時以此 fallback，避免渲染錯範圍。
    var sc = (survey.scoring && survey.scoring.scale) || {};

    function close(complete) {
      sheet.classList.remove('on'); scrim.classList.remove('on');
      setTimeout(function () { scrim.remove(); sheet.remove(); showing = false; if (complete) setTimeout(poll, 800); }, 350);
    }
    function refresh() { btn.disabled = items.some(function (it) { return it.type !== 'text' && answers[it.id] == null; }); }

    var html = '<div class="ema-grab"></div><div class="ema-chip">◷ 簡短問卷</div>' +
      '<h3>' + esc(survey.title) + '</h3><p class="ema-sub">' + esc(survey.description || '') + '</p><div id="ema-qs"></div>';
    sheet.innerHTML = html;
    var qs = sheet.querySelector('#ema-qs');

    items.forEach(function (it) {
      var q = document.createElement('div'); q.className = 'ema-q';
      var inner = '<div class="ema-qt">' + esc(it.text) + '</div>';
      if (it.type === 'likert') {
        var lo = (it.min != null ? it.min : (sc.min != null ? sc.min : 1));
        var hi = (it.max != null ? it.max : (sc.max != null ? sc.max : 7));
        var loL = it.lo || sc.min_label || '';
        var hiL = it.hi || sc.max_label || '';
        inner += '<div class="ema-lk">';
        for (var v = lo; v <= hi; v++) inner += '<button data-v="' + v + '">' + v + '</button>';
        inner += '</div>';
        if (loL || hiL) inner += '<div class="ema-ends"><span>' + esc(loL) + '</span><span>' + esc(hiL) + '</span></div>';
      } else if (it.type === 'single' || it.type === 'multi') {
        (it.options || []).forEach(function (o) { inner += '<button class="ema-opt" data-o="' + esc(o) + '">' + esc(o) + '</button>'; });
      } else if (it.type === 'text') {
        inner += '<textarea class="ema-ta" data-text></textarea>';
      }
      q.innerHTML = inner; qs.appendChild(q);

      q.querySelectorAll('.ema-lk button').forEach(function (b) {
        b.onclick = function () {
          q.querySelectorAll('.ema-lk button').forEach(function (x) { x.classList.remove('sel'); });
          b.classList.add('sel'); answers[it.id] = parseInt(b.getAttribute('data-v'), 10); refresh();
        };
      });
      q.querySelectorAll('.ema-opt').forEach(function (b) {
        b.onclick = function () {
          if (it.type === 'single') {
            q.querySelectorAll('.ema-opt').forEach(function (x) { x.classList.remove('sel'); });
            b.classList.add('sel'); answers[it.id] = b.getAttribute('data-o');
          } else {
            b.classList.toggle('sel'); answers[it.id] = [].map.call(q.querySelectorAll('.ema-opt.sel'), function (x) { return x.getAttribute('data-o'); });
          }
          refresh();
        };
      });
      var ta = q.querySelector('[data-text]');
      if (ta) ta.oninput = function () { var v = ta.value.trim(); if (v) answers[it.id] = v; else delete answers[it.id]; };
    });

    var btn = document.createElement('button'); btn.className = 'ema-submit'; btn.textContent = '送出'; btn.disabled = true;
    var skip = document.createElement('button'); skip.className = 'ema-skip'; skip.textContent = '稍後再說';
    sheet.appendChild(btn); sheet.appendChild(skip);
    skip.onclick = function () { close(false); };
    btn.onclick = function () {
      btn.disabled = true; btn.textContent = '送出中…';
      var body = { patient_id: patientId, answers: answers };
      var tps = (survey.scoring && survey.scoring.timepoints) || [];
      if (tps.length) body.timepoint = tps[tps.length - 1];   // 有 timepoints 才帶（EMA 建議用無 timepoints 的微問卷）
      api('/surveys/' + encodeURIComponent(survey.key) + '/responses', { method: 'POST', body: JSON.stringify(body) })
        .then(function (resp) {
          return api('/ema/deliveries/' + encodeURIComponent(delivery.id) + '/complete',
            { method: 'POST', body: JSON.stringify({ response_id: resp.id }) });
        })
        .then(function () { close(true); })
        .catch(function () { btn.disabled = false; btn.textContent = '送出失敗，再試一次'; });
    };

    document.body.appendChild(scrim); document.body.appendChild(sheet);
    scrim.onclick = function () { close(false); };
    requestAnimationFrame(function () { scrim.classList.add('on'); sheet.classList.add('on'); });
  }

  // ── 拉待作答並彈出第一筆 ──
  function poll() {
    if (!authed() || showing) return;
    api('/ema/pending').then(function (data) {
      var first = (data.pending || [])[0];
      if (!first) return;
      api('/surveys/' + encodeURIComponent(first.survey_key)).then(function (survey) {
        render(first, survey, data.patient_id);
      }).catch(function () {});
    }).catch(function () {});
  }

  function start() {
    // 深連結（Web Push 點開）：/?ema_delivery=<id> → 立即拉一次
    poll();
    setInterval(poll, POLL_MS);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
  window.EMAPrompt = { poll: poll };
})();

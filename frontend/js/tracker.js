/*
 * tracker.js — MD.Piece 前端埋點層（codebook v3「使用行為 / 遺失與錯誤事件」TEL 來源）
 *
 * 定位：把使用者操作 / 技術錯誤打成事件，批次送 POST /events（後端 service_role 代寫）。
 *   後端 backend/routers/events.py 再純程式碼聚合成 codebook 衍生變項。
 *
 * 設計：
 *   - 自足、解耦：沿用 app.js 同樣的 API base 與 token key，但不依賴其內部函式。
 *   - 只在「已登入」時送（有 token 才送；身份由後端從 token 決定，前端不帶 user_id）。
 *   - 離線佇列：放 localStorage，連線/下次載入時補送（occurred_at 帶事件真實時間）。
 *   - 隱私：metadata 嚴禁放姓名 / 原始作答 / 自由文字；只放型別、計數、識別碼。
 *
 * 用法：
 *   <script src="/js/tracker.js"></script>   // 在 app.js 之前載入
 *   Tracker.track('feature', 'use', { target: 'previsit_summary' });
 *   Tracker.screen('risk_dashboard');        // 畫面瀏覽捷徑
 *   Session start/end 與 error/crash 已自動掛載，無需手動呼叫。
 */
(function () {
  'use strict';

  var API = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '';
  var TOKEN_KEY = 'mdpiece_access_token';
  var QUEUE_KEY = 'mdpiece_event_queue';
  var SESSION_KEY = 'mdpiece_session_id';
  var BATCH_MAX = 50;
  var FLUSH_MS = 15000;

  var ALLOWED = ['session', 'screen', 'feature', 'reminder', 'error', 'crash', 'api', 'data', 'edit', 'push'];

  function token() { try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; } }
  function nowISO() { return new Date().toISOString(); }

  function loadQueue() {
    try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]'); } catch (e) { return []; }
  }
  function saveQueue(q) {
    try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q.slice(-500))); } catch (e) {}
  }

  function sessionId() {
    var sid;
    try { sid = sessionStorage.getItem(SESSION_KEY); } catch (e) {}
    if (!sid) {
      sid = (Date.now().toString(36) + Math.random().toString(36).slice(2, 8));
      try { sessionStorage.setItem(SESSION_KEY, sid); } catch (e) {}
    }
    return sid;
  }

  /** 推一個事件進佇列（不立即送）。 */
  function track(event_type, event_name, opts) {
    if (ALLOWED.indexOf(event_type) === -1) return;
    opts = opts || {};
    var ev = {
      event_type: event_type,
      event_name: event_name || null,
      target: opts.target || null,
      value: (typeof opts.value === 'number') ? opts.value : null,
      metadata: opts.metadata || null,
      occurred_at: nowISO(),
      session_id: sessionId()
    };
    var q = loadQueue();
    q.push(ev);
    saveQueue(q);
    if (q.length >= BATCH_MAX) flush();
  }

  /** 把佇列批次送後端；失敗 / 離線就留著下次再送（規則 12：不靜默丟失）。 */
  function flush() {
    var t = token();
    if (!t) return;                       // 未登入不送
    if (navigator && navigator.onLine === false) return;
    var q = loadQueue();
    if (!q.length) return;
    var batch = q.slice(0, 200);
    fetch(API + '/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + t },
      body: JSON.stringify({ events: batch }),
      keepalive: true
    }).then(function (res) {
      if (!res.ok) throw new Error('http ' + res.status);
      saveQueue(loadQueue().slice(batch.length));   // 成功才移除已送部分
    }).catch(function () { /* 留在佇列，下次補送 */ });
  }

  // ── 自動掛載：session 生命週期 ──────────────────────
  var sessionStart = Date.now();
  track('session', 'start');

  function endSession() {
    track('session', 'end', { value: Math.round((Date.now() - sessionStart) / 1000) });
    flush();
  }
  window.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') endSession();
    else { sessionStart = Date.now(); track('session', 'start'); }
  });
  window.addEventListener('beforeunload', endSession);
  window.addEventListener('online', flush);

  // ── 自動掛載：全域錯誤 / crash ──────────────────────
  window.addEventListener('error', function (e) {
    track('error', 'runtime_error', { target: (e && e.filename) || null,
      metadata: { msg: e && e.message ? String(e.message).slice(0, 200) : null } });
  });
  window.addEventListener('unhandledrejection', function (e) {
    track('crash', 'app_crash', { metadata: {
      reason: e && e.reason ? String(e.reason).slice(0, 200) : null } });
  });

  // 週期性 flush
  setInterval(flush, FLUSH_MS);

  // ── 對外 API ─────────────────────────────────────
  window.Tracker = {
    track: track,
    flush: flush,
    screen: function (name) { track('screen', 'view', { target: name }); },
    feature: function (name, opts) { track('feature', 'use', Object.assign({ target: name }, opts || {})); },
    apiFailure: function (target, status) { track('api', 'failure', { target: target, value: status }); }
  };
})();

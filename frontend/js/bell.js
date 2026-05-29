/**
 * 鈴聲提醒播放器（前景）
 *
 * 為什麼用 Web Audio API 合成而不是 mp3：
 *  - 不必上傳 / 維護音檔資產，部署更乾淨
 *  - 不受 PWA 快取版本影響
 *  - 預設 5 種音色可立即提供，自訂上傳鈴聲走 <audio> 播放外部 URL
 *
 * iOS Safari 必須在第一次使用者互動後才能播放音訊，本檔提供 unlockAudio()，
 * app.js 在 init 期收第一個 click/touch 時呼叫一次即可。
 */

(function () {
  "use strict";

  var _ctx = null;
  var _unlocked = false;
  var _cachedPrefs = {};  // { kind: { bell_sound, volume, enabled } }
  var _cachedPatientId = null;
  var _customAudioCache = {};  // url -> HTMLAudioElement

  // ─── AudioContext lifecycle ───────────────────────────

  function _getCtx() {
    if (_ctx) return _ctx;
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    try { _ctx = new AC(); } catch (e) { return null; }
    return _ctx;
  }

  function unlockAudio() {
    if (_unlocked) return;
    var ctx = _getCtx();
    if (!ctx) return;
    // iOS：在使用者手勢中 resume + 播一個 0 振幅的 buffer
    if (ctx.state === "suspended") {
      try { ctx.resume(); } catch (e) {}
    }
    try {
      var src = ctx.createBufferSource();
      src.buffer = ctx.createBuffer(1, 1, 22050);
      src.connect(ctx.destination);
      src.start(0);
    } catch (e) {}
    _unlocked = true;
  }

  // ─── 合成預設鈴聲 ───────────────────────────────────────
  // 每個 preset 是一組 (frequency Hz, startDelaySec, durationSec) 的音符序列。

  var PRESETS = {
    gentle: {  // 溫和的三連音（C5 → E5 → G5）— 服藥提醒預設
      notes: [
        { f: 523.25, t: 0.00, d: 0.35 },
        { f: 659.25, t: 0.18, d: 0.40 },
        { f: 783.99, t: 0.40, d: 0.55 },
      ],
      type: "sine",
      gain: 0.25,
    },
    chime: {  // 風鈴感（A5 高八度 → A6）— 回診/檢查預設
      notes: [
        { f: 880.00, t: 0.00, d: 0.65 },
        { f: 1318.51, t: 0.10, d: 0.65 },
      ],
      type: "triangle",
      gain: 0.20,
    },
    soft: {  // 單一柔和音 — 預設
      notes: [
        { f: 440.00, t: 0.00, d: 0.50 },
      ],
      type: "sine",
      gain: 0.22,
    },
    alert: {  // 雙短促音 — 量測提醒預設
      notes: [
        { f: 880.00, t: 0.00, d: 0.18 },
        { f: 880.00, t: 0.25, d: 0.18 },
      ],
      type: "square",
      gain: 0.18,
    },
    urgent: {  // 三短促音 + 高頻 — 醫師要件測 / urgent priority
      notes: [
        { f: 988.00, t: 0.00, d: 0.15 },
        { f: 988.00, t: 0.22, d: 0.15 },
        { f: 988.00, t: 0.44, d: 0.15 },
        { f: 1318.51, t: 0.70, d: 0.30 },
      ],
      type: "square",
      gain: 0.22,
    },
  };

  function _playPreset(presetId, volume01) {
    var preset = PRESETS[presetId] || PRESETS.gentle;
    var ctx = _getCtx();
    if (!ctx) return Promise.resolve();
    if (ctx.state === "suspended") { try { ctx.resume(); } catch (e) {} }

    var master = ctx.createGain();
    master.gain.value = Math.max(0, Math.min(1, volume01)) * (preset.gain || 0.2);
    master.connect(ctx.destination);

    var now = ctx.currentTime;
    var endTime = now;
    preset.notes.forEach(function (n) {
      var osc = ctx.createOscillator();
      var g = ctx.createGain();
      osc.type = preset.type;
      osc.frequency.value = n.f;
      // 簡易 ADSR envelope，避免「啪」一聲
      g.gain.setValueAtTime(0, now + n.t);
      g.gain.linearRampToValueAtTime(1, now + n.t + 0.02);
      g.gain.linearRampToValueAtTime(0.7, now + n.t + n.d * 0.4);
      g.gain.linearRampToValueAtTime(0, now + n.t + n.d);
      osc.connect(g);
      g.connect(master);
      osc.start(now + n.t);
      osc.stop(now + n.t + n.d + 0.05);
      endTime = Math.max(endTime, now + n.t + n.d);
    });

    return new Promise(function (resolve) {
      setTimeout(resolve, Math.max(0, (endTime - now) * 1000 + 50));
    });
  }

  function _playCustomUrl(url, volume01) {
    if (!url) return Promise.resolve();
    var audio = _customAudioCache[url];
    if (!audio) {
      audio = new Audio(url);
      audio.preload = "auto";
      _customAudioCache[url] = audio;
    }
    audio.volume = Math.max(0, Math.min(1, volume01));
    try {
      audio.currentTime = 0;
      var p = audio.play();
      if (p && p.then) return p.catch(function () {});
    } catch (e) {}
    return Promise.resolve();
  }

  // ─── 公開 API ─────────────────────────────────────────

  /**
   * 播放某種提醒類型對應的鈴聲。
   * kind: medication | appointment | lab | measurement | doctor_request | custom
   * overrides: { soundId, volume (0-100) } — 用於預覽
   */
  function playBell(kind, overrides) {
    overrides = overrides || {};
    var pref = _cachedPrefs[kind] || _cachedPrefs.custom || {};
    if (overrides.soundId === undefined && pref.enabled === false) {
      return Promise.resolve();
    }
    var soundId = overrides.soundId || pref.bell_sound || _defaultSoundForKind(kind);
    var volume = (overrides.volume != null ? overrides.volume : (pref.volume != null ? pref.volume : 70)) / 100;
    if (soundId && soundId.indexOf("http") === 0) {
      return _playCustomUrl(soundId, volume);
    }
    return _playPreset(soundId, volume);
  }

  function _defaultSoundForKind(kind) {
    switch (kind) {
      case "medication": return "gentle";
      case "appointment": return "chime";
      case "lab": return "chime";
      case "measurement": return "alert";
      case "doctor_request": return "urgent";
      default: return "soft";
    }
  }

  function listPresets() {
    return Object.keys(PRESETS).map(function (id) {
      return {
        id: id,
        label: { gentle: "溫和", chime: "風鈴", soft: "柔和", alert: "提示", urgent: "急促" }[id] || id,
      };
    });
  }

  // ─── 偏好同步 ────────────────────────────────────────

  function loadPrefs(patientId, apiBase) {
    if (!patientId) return Promise.resolve({});
    _cachedPatientId = patientId;
    var base = apiBase || "";
    return (self.apiFetch || fetch)(base + "/reminders/bell-prefs?patient_id=" + encodeURIComponent(patientId))
      .then(function (r) { return r.ok ? r.json() : { prefs: [] }; })
      .then(function (data) {
        _cachedPrefs = {};
        (data.prefs || []).forEach(function (p) {
          _cachedPrefs[p.kind] = {
            bell_sound: p.bell_sound,
            volume: p.volume,
            enabled: p.enabled !== false && p.enabled !== 0,
          };
        });
        return _cachedPrefs;
      })
      .catch(function () { return _cachedPrefs; });
  }

  function getPref(kind) {
    return _cachedPrefs[kind] || {
      bell_sound: _defaultSoundForKind(kind),
      volume: 70,
      enabled: true,
    };
  }

  function savePref(kind, pref, apiBase) {
    if (!_cachedPatientId) return Promise.reject(new Error("no patient"));
    var base = apiBase || "";
    var payload = {
      patient_id: _cachedPatientId,
      kind: kind,
      bell_sound: pref.bell_sound || _defaultSoundForKind(kind),
      volume: pref.volume != null ? pref.volume : 70,
      enabled: pref.enabled !== false,
    };
    _cachedPrefs[kind] = {
      bell_sound: payload.bell_sound,
      volume: payload.volume,
      enabled: payload.enabled,
    };
    return (self.apiFetch || fetch)(base + "/reminders/bell-prefs", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(function (r) { return r.ok ? r.json() : Promise.reject(); });
  }

  // ─── SW → 前景訊息 ──────────────────────────────────

  function handleSWMessage(event) {
    var data = event && event.data;
    if (!data || data.type !== "mdpiece-play-bell") return;
    var kind = data.reminder_type || "custom";
    var overrides = {};
    if (data.bell_sound) overrides.soundId = data.bell_sound;
    if (data.bell_volume != null) overrides.volume = data.bell_volume;
    playBell(kind, overrides);
  }

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.addEventListener("message", handleSWMessage);
  }

  // 第一次互動時自動 unlock
  var _onceUnlock = function () {
    unlockAudio();
    document.removeEventListener("click", _onceUnlock, true);
    document.removeEventListener("touchstart", _onceUnlock, true);
  };
  document.addEventListener("click", _onceUnlock, true);
  document.addEventListener("touchstart", _onceUnlock, true);

  window.MDBell = {
    play: playBell,
    preview: function (soundId, volume) {
      unlockAudio();
      return playBell("custom", { soundId: soundId, volume: volume });
    },
    unlock: unlockAudio,
    listPresets: listPresets,
    loadPrefs: loadPrefs,
    getPref: getPref,
    savePref: savePref,
    defaultSoundForKind: _defaultSoundForKind,
  };
})();

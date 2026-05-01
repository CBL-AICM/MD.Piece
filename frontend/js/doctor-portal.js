// 醫師端獨立入口：列病患、選病患、看用藥摘要 + 症狀趨勢 + 長期疼痛
const API = window.location.origin.includes("8000") || window.location.origin.includes("8765")
  ? window.location.origin
  : "http://127.0.0.1:8000";

let _patients = [];
let _selectedId = null;
let _rangeDays = 30;

function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function init() {
  loadPatients();
}

function loadPatients() {
  fetch(API + "/patients/")
    .then(r => r.json())
    .then(d => {
      _patients = d.patients || [];
      renderPatientList(_patients);
    })
    .catch(() => {
      document.getElementById("dp-patient-list").innerHTML =
        '<div class="dp-loading" style="color:#E85B7A">載入失敗，後端未啟動？</div>';
    });
}

function renderPatientList(list) {
  const el = document.getElementById("dp-patient-list");
  if (!list.length) {
    el.innerHTML = '<div class="dp-loading">尚無病患資料</div>';
    return;
  }
  el.innerHTML = list.map(p => `
    <div class="dp-pt ${p.id === _selectedId ? "active" : ""}" onclick="selectPatient('${p.id}')">
      <div class="name">${escapeHtml(p.name || "—")}</div>
      <div class="meta">
        ${p.age != null ? p.age + " 歲" : ""}
        ${p.gender ? " · " + (p.gender === "male" ? "男" : p.gender === "female" ? "女" : p.gender) : ""}
        ${p.phone ? " · " + escapeHtml(p.phone) : ""}
      </div>
    </div>
  `).join("");
}

function filterPatients(q) {
  const k = (q || "").trim().toLowerCase();
  if (!k) { renderPatientList(_patients); return; }
  renderPatientList(_patients.filter(p => (p.name || "").toLowerCase().includes(k)));
}

function selectPatient(id) {
  _selectedId = id;
  renderPatientList(_patients);
  loadDashboard();
}

function setRange(d) {
  _rangeDays = parseInt(d) || 30;
  loadDashboard();
}

function loadDashboard() {
  if (!_selectedId) return;
  const p = _patients.find(x => x.id === _selectedId) || {};
  const days = _rangeDays;

  const html = `
    <div class="dp-header">
      <div>
        <h2>${escapeHtml(p.name || "—")}</h2>
        <div style="color:var(--text-dim,#A8A39C);font-size:0.85rem;margin-top:2px">
          ${p.age != null ? p.age + " 歲" : ""}
          ${p.gender ? " · " + (p.gender === "male" ? "男" : "女") : ""}
          ${p.phone ? " · " + escapeHtml(p.phone) : ""}
          · ID: <code>${p.id}</code>
        </div>
      </div>
      <div class="dp-range">
        <label style="font-size:0.85rem;color:var(--text-dim,#A8A39C);margin-right:6px">統計區間</label>
        <select onchange="setRange(this.value)">
          ${[30, 90, 180, 365].map(n => `<option value="${n}" ${n === days ? "selected" : ""}>${n} 天</option>`).join("")}
        </select>
      </div>
    </div>

    <div class="dp-card" id="dp-meds">
      <h3><i data-lucide="pill" style="width:16px;height:16px"></i> 用藥摘要</h3>
      <div class="dp-loading">載入中...</div>
    </div>

    <div class="dp-card" id="dp-symptoms">
      <h3><i data-lucide="activity" style="width:16px;height:16px"></i> 症狀趨勢（回診間累計）</h3>
      <div class="dp-loading">載入中...</div>
    </div>

    <div class="dp-card" id="dp-pain">
      <h3><i data-lucide="alert-triangle" style="width:16px;height:16px"></i> 長期疼痛統計</h3>
      <div class="dp-loading">載入中...</div>
    </div>
  `;
  document.getElementById("dp-content").innerHTML = html;
  if (window.lucide) lucide.createIcons();

  loadMedSummary(_selectedId, days);
  loadSymptomTrend(_selectedId, days);
}

// ── 用藥摘要 ─────────────────────────────────────────────
function loadMedSummary(pid, days) {
  fetch(`${API}/medications/doctor-summary?patient_id=${pid}&days=${days}`)
    .then(r => r.json())
    .then(j => renderMedSummary(j))
    .catch(() => {
      document.getElementById("dp-meds").innerHTML =
        '<h3><i data-lucide="pill" style="width:16px;height:16px"></i> 用藥摘要</h3><div style="color:#E85B7A">載入失敗</div>';
      if (window.lucide) lucide.createIcons();
    });
}

function renderMedSummary(j) {
  const ov = j.overall || {};
  const per = j.per_medication || [];
  const alerts = j.missed_alerts || [];

  const stat = (n, l) => `<div class="dp-stat"><div class="dp-stat-num">${n}</div><div class="dp-stat-lbl">${l}</div></div>`;

  const stats = `
    <div class="dp-stats">
      ${stat(ov.adherence_rate + "%", "整體服藥率")}
      ${stat(ov.active_medications || 0, "用藥中")}
      ${stat(ov.total_log_records || 0, "區間打卡")}
      ${stat((j.period && j.period.days) + "天", "統計區間")}
    </div>`;

  const perRows = per.length
    ? per.map(p => {
        const rate = p.adherence_rate;
        const color = rate >= 80 ? "#55B88A" : rate >= 50 ? "#E89B5B" : "#E85B7A";
        const last = p.last_taken_at ? p.last_taken_at.slice(0, 16).replace("T", " ") : "—";
        const eff = p.avg_effectiveness != null ? `${p.avg_effectiveness} / 5` : "—";
        const sides = (p.side_effects && p.side_effects.length) ? p.side_effects.join("、") : "—";
        return `
          <div class="dp-row">
            <div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap">
              <strong>${escapeHtml(p.name || "")}${p.dosage ? ` <span style="color:var(--text-dim,#A8A39C);font-weight:400">${escapeHtml(p.dosage)}</span>` : ""}</strong>
              <span style="color:${color};font-weight:600">${rate}%</span>
            </div>
            <div style="font-size:0.8rem;color:var(--text-dim,#A8A39C)">最近：${last} · 平均療效：${eff} · 副作用：${escapeHtml(sides)}</div>
          </div>`;
      }).join("")
    : '<div style="color:var(--text-dim,#A8A39C);padding:8px">無有效藥物</div>';

  const alertHtml = alerts.length
    ? `<div style="margin-top:10px;padding:8px 10px;background:rgba(232,91,122,0.08);border:1px solid #E85B7A;border-radius:6px">
        <strong style="color:#E85B7A">⚠ 服藥警示</strong>
        <ul style="margin:4px 0 0 18px;font-size:0.85rem">
          ${alerts.map(a => `<li>${escapeHtml(a.name)} — ${escapeHtml(a.reason)}</li>`).join("")}
        </ul>
      </div>`
    : "";

  const summary = j.summary
    ? `<details open style="margin-top:10px"><summary style="cursor:pointer;color:var(--accent,#00D4AA)">AI 回診重點摘要</summary>
        <div class="dp-summary-md" style="margin-top:6px">${escapeHtml(j.summary)}</div>
      </details>`
    : '<div style="margin-top:8px;color:var(--text-dim,#A8A39C);font-size:0.85rem">（AI 摘要服務未啟用，僅顯示結構化資料）</div>';

  document.getElementById("dp-meds").innerHTML = `
    <h3><i data-lucide="pill" style="width:16px;height:16px"></i> 用藥摘要</h3>
    ${stats}
    <div style="font-weight:600;margin:10px 0 6px">各藥物服藥情況</div>
    <div style="display:grid;gap:4px">${perRows}</div>
    ${alertHtml}
    ${summary}
  `;
  if (window.lucide) lucide.createIcons();
}

// ── 症狀趨勢 + 長期疼痛 ────────────────────────────────
function loadSymptomTrend(pid, days) {
  fetch(`${API}/symptoms/trend?patient_id=${pid}&days=${days}`)
    .then(r => r.json())
    .then(d => {
      renderSymptomTrend(d);
      renderPainSummary(d);
    })
    .catch(() => {
      document.getElementById("dp-symptoms").innerHTML =
        '<h3><i data-lucide="activity" style="width:16px;height:16px"></i> 症狀趨勢</h3><div style="color:#E85B7A">載入失敗</div>';
      document.getElementById("dp-pain").innerHTML = "";
      if (window.lucide) lucide.createIcons();
    });
}

function renderSymptomTrend(d) {
  const by = d.by_symptom || [];
  const days = (d.period && d.period.days) || 30;

  let topHtml = "";
  if (!by.length) {
    topHtml = '<div style="color:var(--text-dim,#A8A39C);padding:8px">區間內無症狀紀錄</div>';
  } else {
    const stat = (n, l) => `<div class="dp-stat"><div class="dp-stat-num">${n}</div><div class="dp-stat-lbl">${l}</div></div>`;
    topHtml = `
      <div class="dp-stats">
        ${stat(d.total_entries, "總紀錄")}
        ${stat(by.length, "症狀類型")}
        ${stat(days + "天", "區間")}
      </div>
      <div style="display:grid;gap:4px;margin-top:10px">
        ${by.map(s => {
          const c = s.per_week >= 3 ? "#E85B7A" : s.per_week >= 1 ? "#E89B5B" : "#00D4AA";
          return `
            <div class="dp-row" style="display:grid;grid-template-columns:1.3fr 1fr 1fr;gap:8px;align-items:center">
              <div><strong>${escapeHtml(s.label)}</strong> × ${s.total} <span style="color:var(--text-dim,#A8A39C);font-size:0.75rem">（${s.active_days} 天）</span></div>
              <div><span style="color:${c};font-weight:600">${s.per_week}</span><span style="color:var(--text-dim,#A8A39C)"> 次/週</span></div>
              <div style="color:var(--text-dim,#A8A39C)">平均 ${s.avg_severity != null ? s.avg_severity : "—"} / 5</div>
            </div>`;
        }).join("")}
      </div>
    `;
  }

  document.getElementById("dp-symptoms").innerHTML = `
    <h3><i data-lucide="activity" style="width:16px;height:16px"></i> 症狀趨勢（回診間累計）</h3>
    ${topHtml}
    <div class="dp-canvas-wrap"><canvas id="dp-sym-canvas"></canvas></div>
  `;
  if (window.lucide) lucide.createIcons();
  drawTrendChart("dp-sym-canvas", d);
}

function renderPainSummary(d) {
  const ps = d.pain_summary || {};
  const items = ps.items || [];
  if (!items.length) {
    document.getElementById("dp-pain").innerHTML = `
      <h3><i data-lucide="alert-triangle" style="width:16px;height:16px"></i> 長期疼痛統計</h3>
      <div style="color:var(--text-dim,#A8A39C);padding:8px">區間內無疼痛類紀錄</div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }
  const rows = items.map(p => {
    const c = p.per_week >= 3 ? "#E85B7A" : p.per_week >= 1 ? "#E89B5B" : "#00D4AA";
    const first = p.first_recorded_at ? p.first_recorded_at.slice(0, 10) : "—";
    const last = p.last_recorded_at ? p.last_recorded_at.slice(0, 10) : "—";
    return `
      <div class="dp-row" style="display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr;gap:8px;align-items:center;font-size:0.85rem">
        <div><strong>${escapeHtml(p.label)}</strong>
          <div style="color:var(--text-dim,#A8A39C);font-size:0.72rem">${first} → ${last}</div>
        </div>
        <div><span style="color:${c};font-weight:600">${p.per_week}</span><span style="color:var(--text-dim,#A8A39C)"> 次/週</span></div>
        <div>共 ${p.total} 次<span style="color:var(--text-dim,#A8A39C)">（${p.active_days} 天）</span></div>
        <div>平均 ${p.avg_severity != null ? p.avg_severity : "—"} / 5</div>
      </div>`;
  }).join("");
  document.getElementById("dp-pain").innerHTML = `
    <h3><i data-lucide="alert-triangle" style="width:16px;height:16px"></i> 長期疼痛統計</h3>
    <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;margin-bottom:8px;font-size:0.88rem">
      <span style="color:var(--text-dim,#A8A39C)">總 <strong style="color:#E85B7A">${ps.total}</strong> 次・<strong>${ps.types}</strong> 類・約 <strong>${ps.per_week}</strong> 次/週・<strong>${ps.per_month}</strong> 次/月</span>
    </div>
    <div style="display:grid;gap:4px">${rows}</div>
  `;
  if (window.lucide) lucide.createIcons();
}

// ── 折線圖 ────────────────────────────────────────────
function drawTrendChart(canvasId, d) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const dates = d.dates || [];
  const series = (d.series || []).slice(0, 6);
  const ctx = canvas.getContext("2d");
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * 2; canvas.height = rect.height * 2;
  ctx.scale(2, 2);
  const w = rect.width, h = rect.height;
  const pad = { top: 18, right: 10, bottom: 32, left: 30 };
  const cw = w - pad.left - pad.right, ch = h - pad.top - pad.bottom;
  ctx.clearRect(0, 0, w, h);

  if (!dates.length || !series.length) {
    ctx.fillStyle = "#6E6860"; ctx.font = "12px 'Noto Sans TC'"; ctx.textAlign = "center";
    ctx.fillText("尚無症狀資料", w / 2, h / 2);
    return;
  }

  let maxCount = 1;
  series.forEach(s => s.counts.forEach(v => { if (v > maxCount) maxCount = v; }));

  ctx.strokeStyle = "rgba(255,255,255,0.08)"; ctx.lineWidth = 0.5;
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + (ch / 4) * i;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + cw, y); ctx.stroke();
  }
  ctx.fillStyle = "#6E6860"; ctx.font = "10px 'Noto Sans TC'"; ctx.textAlign = "right";
  for (let i = 0; i <= 4; i++) {
    const v = Math.round(maxCount - (maxCount / 4) * i);
    ctx.fillText(v, pad.left - 4, pad.top + (ch / 4) * i + 4);
  }

  ctx.textAlign = "center";
  [0, Math.floor(dates.length / 2), dates.length - 1].forEach(i => {
    const x = pad.left + (cw / Math.max(1, dates.length - 1)) * i;
    ctx.fillText(dates[i].slice(5), x, pad.top + ch + 16);
  });

  const colors = ["#00D4AA", "#5B9FE8", "#E89B5B", "#C977E8", "#E85B7A", "#7AE85B"];
  series.forEach((s, idx) => {
    const color = colors[idx % colors.length];
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 2; ctx.lineJoin = "round";
    ctx.beginPath();
    s.counts.forEach((v, i) => {
      const x = pad.left + (cw / Math.max(1, dates.length - 1)) * i;
      const y = pad.top + ch - (v / maxCount * ch);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });

  ctx.textAlign = "left"; ctx.font = "10px 'Noto Sans TC'";
  series.forEach((s, idx) => {
    const color = colors[idx % colors.length];
    const x = pad.left + 4 + idx * 80;
    if (x + 70 > pad.left + cw) return;
    ctx.fillStyle = color; ctx.fillRect(x, pad.top - 12, 8, 8);
    ctx.fillStyle = "#A8A39C";
    ctx.fillText(s.label + " (" + s.total + ")", x + 12, pad.top - 4);
  });
}

document.addEventListener("DOMContentLoaded", init);

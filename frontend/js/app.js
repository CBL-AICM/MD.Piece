const API = "http://localhost:8000";
const GITHUB_REPO = "human530/MD.Piece";

// ─── 路由 ──────────────────────────────────────────────────

function showPage(page) {
  const app = document.getElementById("app");
  const pages = { home, symptoms, doctors, patients, records, research, contributors };
  app.innerHTML = pages[page]?.() || "";
  // 頁面載入後的初始化
  if (page === "doctors") loadDoctors();
  if (page === "patients") loadPatients();
  if (page === "records") loadRecordsPage();
  if (page === "research") loadExperiments();
  if (page === "contributors") loadContributors();
}

// ─── 首頁 ──────────────────────────────────────────────────

function home() {
  return `
    <div class="card">
      <h2>歡迎使用 MD.Piece</h2>
      <p style="margin-top:8px">本平台提供醫病溝通、病歷管理與 AI 症狀分析服務</p>
    </div>
    <div class="card">
      <h3>功能總覽</h3>
      <p>• 症狀分析 - AI 智慧分析症狀，提供初步建議</p>
      <p>• 病歷管理 - 建立與查詢就診記錄</p>
      <p>• 醫師列表 - 管理醫師資料</p>
      <p>• 病患管理 - 管理病患資料</p>
      <p>• 自動研究 - AutoResearch 實驗管理（Colab GPU 訓練）</p>
    </div>`;
}

// ─── 症狀分析 ──────────────────────────────────────────────

function symptoms() {
  return `
    <div class="card">
      <h2>AI 症狀分析</h2>
      <p style="margin-bottom:12px;color:#666">輸入您的症狀，AI 將提供初步分析建議</p>
      <input id="symptom-input" placeholder="輸入症狀（以逗號分隔），例如：fever, headache, cough" />
      <div style="display:flex;gap:8px;margin-top:8px">
        <button class="primary" onclick="analyzeSymptoms()">AI 分析</button>
        <button class="secondary" onclick="quickAdvice()">快速查詢</button>
      </div>
      <div id="analysis-result"></div>
    </div>
    <div class="card">
      <h3>快速查詢</h3>
      <p style="color:#666;font-size:0.9rem">支援：fever、headache、chest pain、cough</p>
    </div>`;
}

async function analyzeSymptoms() {
  const input = document.getElementById("symptom-input").value;
  if (!input.trim()) return;
  const symptoms = input.split(",").map(s => s.trim()).filter(Boolean);
  const el = document.getElementById("analysis-result");
  el.innerHTML = '<div class="loading">分析中...</div>';

  try {
    const res = await fetch(`${API}/symptoms/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symptoms }),
    });
    const data = await res.json();

    const urgencyMap = {
      emergency: { label: "緊急", cls: "urgency-emergency" },
      high: { label: "高", cls: "urgency-high" },
      medium: { label: "中", cls: "urgency-medium" },
      low: { label: "低", cls: "urgency-low" },
    };
    const urg = urgencyMap[data.urgency] || urgencyMap.low;

    const conditions = (data.conditions || [])
      .map(c => `<li><strong>${c.name}</strong> — 可能性：${c.likelihood}</li>`)
      .join("");

    el.innerHTML = `
      <div class="ai-result-card">
        <div class="urgency-badge ${urg.cls}">緊急程度：${urg.label}</div>
        <h4>可能病因</h4>
        <ul>${conditions}</ul>
        <h4>建議科別</h4>
        <p>${data.recommended_department || "家醫科"}</p>
        <h4>建議</h4>
        <p>${data.advice || ""}</p>
        <div class="disclaimer">${data.disclaimer || "此分析僅供參考，不構成醫療診斷。如有不適請立即就醫。"}</div>
      </div>`;
  } catch (e) {
    el.innerHTML = '<div class="advice-box">分析失敗，請確認後端是否啟動。</div>';
  }
}

async function quickAdvice() {
  const input = document.getElementById("symptom-input").value.split(",")[0].trim();
  if (!input) return;
  const res = await fetch(`${API}/symptoms/advice?symptom=${encodeURIComponent(input)}`);
  const data = await res.json();
  document.getElementById("analysis-result").innerHTML =
    `<div class="advice-box"><strong>${data.symptom}</strong>：${data.advice}</div>`;
}

// ─── 醫師列表 ──────────────────────────────────────────────

function doctors() {
  return `
    <div class="card">
      <h2>新增醫師</h2>
      <input id="d-name" placeholder="醫師姓名" />
      <input id="d-specialty" placeholder="專科（例如：內科、外科）" />
      <input id="d-phone" placeholder="電話（選填）" />
      <button class="primary" onclick="addDoctor()">新增</button>
    </div>
    <div class="card">
      <h2>醫師列表</h2>
      <div id="doctor-list"><p>載入中...</p></div>
    </div>`;
}

async function loadDoctors() {
  const res = await fetch(`${API}/doctors/`);
  const data = await res.json();
  const el = document.getElementById("doctor-list");
  if (!data.doctors?.length) {
    el.innerHTML = "<p>尚無醫師資料</p>";
    return;
  }
  el.innerHTML = data.doctors.map(d => `
    <div class="record-card">
      <strong>${d.name}</strong> — ${d.specialty}
      ${d.phone ? `<span style="color:#666"> | ${d.phone}</span>` : ""}
      <button class="btn-delete" onclick="deleteDoctor('${d.id}')">刪除</button>
    </div>
  `).join("");
}

async function addDoctor() {
  const name = document.getElementById("d-name").value;
  const specialty = document.getElementById("d-specialty").value;
  const phone = document.getElementById("d-phone").value || undefined;
  if (!name || !specialty) return;
  await fetch(`${API}/doctors/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, specialty, phone }),
  });
  loadDoctors();
  document.getElementById("d-name").value = "";
  document.getElementById("d-specialty").value = "";
  document.getElementById("d-phone").value = "";
}

async function deleteDoctor(id) {
  if (!confirm("確定刪除此醫師？")) return;
  await fetch(`${API}/doctors/${id}`, { method: "DELETE" });
  loadDoctors();
}

// ─── 病患管理 ──────────────────────────────────────────────

function patients() {
  return `
    <div class="card">
      <h2>新增病患</h2>
      <input id="p-name" placeholder="姓名" />
      <input id="p-age" type="number" placeholder="年齡" />
      <select id="p-gender"><option value="">性別（選填）</option><option value="male">男</option><option value="female">女</option></select>
      <input id="p-phone" placeholder="電話（選填）" />
      <button class="primary" onclick="addPatient()">新增</button>
    </div>
    <div class="card">
      <h2>病患列表</h2>
      <div id="patient-list"><p>載入中...</p></div>
    </div>`;
}

async function loadPatients() {
  const res = await fetch(`${API}/patients/`);
  const data = await res.json();
  const el = document.getElementById("patient-list");
  if (!data.patients?.length) {
    el.innerHTML = "<p>尚無病患資料</p>";
    return;
  }
  el.innerHTML = data.patients.map(p => `
    <div class="record-card">
      <strong>${p.name}</strong> — ${p.age}歲
      ${p.gender ? ` | ${p.gender === "male" ? "男" : "女"}` : ""}
      ${p.phone ? ` | ${p.phone}` : ""}
      <button class="btn-delete" onclick="deletePatient('${p.id}')">刪除</button>
      <button class="btn-view" onclick="showPage('records');setTimeout(()=>{document.getElementById('r-patient').value='${p.id}';searchRecords()},100)">查看病歷</button>
    </div>
  `).join("");
}

async function addPatient() {
  const name = document.getElementById("p-name").value;
  const age = parseInt(document.getElementById("p-age").value);
  const gender = document.getElementById("p-gender").value || undefined;
  const phone = document.getElementById("p-phone").value || undefined;
  if (!name || !age) return;
  await fetch(`${API}/patients/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, age, gender, phone }),
  });
  loadPatients();
  document.getElementById("p-name").value = "";
  document.getElementById("p-age").value = "";
  document.getElementById("p-gender").value = "";
  document.getElementById("p-phone").value = "";
}

async function deletePatient(id) {
  if (!confirm("確定刪除此病患？相關病歷也會一併刪除。")) return;
  await fetch(`${API}/patients/${id}`, { method: "DELETE" });
  loadPatients();
}

// ─── 病歷管理 ──────────────────────────────────────────────

function records() {
  return `
    <div class="card">
      <h2>新增病歷</h2>
      <div class="form-grid">
        <select id="r-patient"><option value="">選擇病患</option></select>
        <select id="r-doctor"><option value="">選擇醫師（選填）</option></select>
        <input id="r-date" type="date" />
        <input id="r-symptoms" placeholder="症狀（逗號分隔）" />
        <textarea id="r-diagnosis" placeholder="診斷"></textarea>
        <textarea id="r-prescription" placeholder="處方"></textarea>
        <textarea id="r-notes" placeholder="備註"></textarea>
      </div>
      <button class="primary" onclick="addRecord()">建立病歷</button>
    </div>
    <div class="card">
      <h2>搜尋病歷</h2>
      <div class="filter-bar">
        <select id="filter-patient"><option value="">所有病患</option></select>
        <input id="filter-diagnosis" placeholder="搜尋診斷..." />
        <button class="primary" onclick="searchRecords()">搜尋</button>
      </div>
      <div id="record-list"><p>載入中...</p></div>
    </div>`;
}

async function loadRecordsPage() {
  // 載入病患和醫師 dropdown
  const [pRes, dRes] = await Promise.all([
    fetch(`${API}/patients/`).then(r => r.json()),
    fetch(`${API}/doctors/`).then(r => r.json()),
  ]);

  const patientOpts = (pRes.patients || []).map(p =>
    `<option value="${p.id}">${p.name} (${p.age}歲)</option>`
  ).join("");
  const doctorOpts = (dRes.doctors || []).map(d =>
    `<option value="${d.id}">${d.name} — ${d.specialty}</option>`
  ).join("");

  const rp = document.getElementById("r-patient");
  const rd = document.getElementById("r-doctor");
  const fp = document.getElementById("filter-patient");
  if (rp) rp.innerHTML = `<option value="">選擇病患</option>${patientOpts}`;
  if (rd) rd.innerHTML = `<option value="">選擇醫師（選填）</option>${doctorOpts}`;
  if (fp) fp.innerHTML = `<option value="">所有病患</option>${patientOpts}`;

  searchRecords();
}

async function addRecord() {
  const patient_id = document.getElementById("r-patient").value;
  if (!patient_id) { alert("請選擇病患"); return; }
  const doctor_id = document.getElementById("r-doctor").value || undefined;
  const dateVal = document.getElementById("r-date").value;
  const visit_date = dateVal ? new Date(dateVal).toISOString() : undefined;
  const symptomsStr = document.getElementById("r-symptoms").value;
  const symptoms = symptomsStr ? symptomsStr.split(",").map(s => s.trim()).filter(Boolean) : [];
  const diagnosis = document.getElementById("r-diagnosis").value || undefined;
  const prescription = document.getElementById("r-prescription").value || undefined;
  const notes = document.getElementById("r-notes").value || undefined;

  await fetch(`${API}/records/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patient_id, doctor_id, visit_date, symptoms, diagnosis, prescription, notes }),
  });
  searchRecords();
  // 清空表單
  ["r-symptoms", "r-diagnosis", "r-prescription", "r-notes"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = "";
  });
}

async function searchRecords() {
  const patientId = document.getElementById("filter-patient")?.value || "";
  const diagnosis = document.getElementById("filter-diagnosis")?.value || "";
  let url = `${API}/records/?`;
  if (patientId) url += `patient_id=${patientId}&`;
  if (diagnosis) url += `diagnosis=${encodeURIComponent(diagnosis)}&`;

  const res = await fetch(url);
  const data = await res.json();
  const el = document.getElementById("record-list");

  if (!data.records?.length) {
    el.innerHTML = "<p>尚無病歷資料</p>";
    return;
  }

  el.innerHTML = data.records.map(r => {
    const date = r.visit_date ? new Date(r.visit_date).toLocaleDateString("zh-TW") : "未記錄";
    const patientName = r.patients?.name || "未知";
    const doctorName = r.doctors?.name || "未指定";
    const symptoms = (r.symptoms || []).join(", ");
    return `
      <div class="record-card">
        <div class="record-header">
          <strong>${patientName}</strong> — ${date} — 醫師：${doctorName}
          <button class="btn-delete" onclick="deleteRecord('${r.id}')">刪除</button>
        </div>
        ${symptoms ? `<p><strong>症狀：</strong>${symptoms}</p>` : ""}
        ${r.diagnosis ? `<p><strong>診斷：</strong>${r.diagnosis}</p>` : ""}
        ${r.prescription ? `<p><strong>處方：</strong>${r.prescription}</p>` : ""}
        ${r.notes ? `<p><strong>備註：</strong>${r.notes}</p>` : ""}
      </div>`;
  }).join("");
}

async function deleteRecord(id) {
  if (!confirm("確定刪除此病歷？")) return;
  await fetch(`${API}/records/${id}`, { method: "DELETE" });
  searchRecords();
}

// ─── 自動研究 ─────────────────────────────────────────────

function research() {
  return `
    <div class="card">
      <h2>AutoResearch 實驗管理</h2>
      <p style="margin-top:8px;color:#666">
        基於 <a href="https://github.com/karpathy/autoresearch" target="_blank">karpathy/autoresearch</a> —
        AI Agent 自動修改模型、訓練、評估、保留最佳結果。
      </p>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
        <button class="primary" onclick="loadExperiments()">重新整理</button>
        <button class="secondary" onclick="checkGpuStatus()">檢查 GPU 狀態</button>
        <button class="secondary" onclick="document.getElementById('tsv-upload').click()">匯入 results.tsv</button>
        <input type="file" id="tsv-upload" accept=".tsv,.csv" style="display:none" onchange="uploadTsv(this)" />
      </div>
      <div id="gpu-status"></div>
    </div>
    <div class="card">
      <h3>val_bpb 趨勢</h3>
      <div id="bpb-chart" style="position:relative;height:200px;margin:12px 0">
        <canvas id="bpb-canvas" style="width:100%;height:100%"></canvas>
      </div>
      <div id="best-bpb" style="margin-top:8px"></div>
    </div>
    <div class="card">
      <h3>手動提交實驗結果</h3>
      <input id="exp-name" placeholder="實驗名稱（例如：baseline-run-1）" />
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
        <input id="exp-bpb" type="number" step="0.001" placeholder="val_bpb 分數" />
        <input id="exp-loss" type="number" step="0.001" placeholder="train_loss" />
        <input id="exp-steps" type="number" placeholder="訓練步數" />
        <input id="exp-duration" type="number" placeholder="訓練時間（秒）" />
      </div>
      <textarea id="exp-notes" placeholder="備註（模型設定、觀察等）"></textarea>
      <input id="exp-colab" placeholder="Colab 連結（選填）" />
      <div style="display:flex;gap:8px;align-items:center;margin-top:8px">
        <label style="font-size:0.9rem"><input type="checkbox" id="exp-kept" /> 保留此實驗</label>
        <button class="primary" onclick="submitExperiment()">提交結果</button>
      </div>
    </div>
    <div class="card">
      <h3>實驗結果</h3>
      <div id="experiment-list"><p>載入中...</p></div>
    </div>`;
}

async function loadExperiments() {
  try {
    var [listRes, statsRes] = await Promise.all([
      fetch(API + "/research/"),
      fetch(API + "/research/stats"),
    ]);
    var data = await listRes.json();
    var stats = await statsRes.json();

    // 畫圖表
    renderBpbChart(stats.chart_data || []);

    // 顯示最佳結果
    var bestEl = document.getElementById("best-bpb");
    if (bestEl && stats.best_bpb != null) {
      bestEl.innerHTML = '<div class="advice-box">' +
        '<strong>最佳 val_bpb：</strong>' + stats.best_bpb.toFixed(4) +
        ' (' + stats.best_experiment + ')' +
        ' — 共 ' + stats.total + ' 個實驗，' + stats.with_bpb + ' 個有 bpb 數據</div>';
    }

    // 顯示實驗列表
    var el = document.getElementById("experiment-list");
    if (!data.experiments?.length) {
      el.innerHTML = "<p>尚無實驗結果。請從 Colab 執行訓練後回傳，或匯入 results.tsv。</p>";
      return;
    }
    el.innerHTML = data.experiments.map(function(e) {
      var metrics = [];
      if (e.val_bpb != null) metrics.push("val_bpb: " + e.val_bpb);
      if (e.train_loss != null) metrics.push("loss: " + e.train_loss);
      if (e.steps != null) metrics.push(e.steps + " steps");
      if (e.duration_seconds != null) metrics.push(Math.round(e.duration_seconds) + "s");
      var keptBadge = e.kept === true
        ? '<span class="urgency-badge urgency-low" style="font-size:0.75rem;padding:2px 8px">kept</span>'
        : e.kept === false
        ? '<span class="urgency-badge urgency-high" style="font-size:0.75rem;padding:2px 8px">reverted</span>'
        : '';
      return '<div class="record-card">' +
        '<div class="record-header">' +
        '<strong>' + e.name + '</strong> ' + keptBadge + ' — ' + (e.submitted_at || "").slice(0, 10) +
        '<button class="btn-delete" onclick="deleteExperiment(\'' + e.id + '\')">刪除</button>' +
        '</div>' +
        (metrics.length ? '<p>' + metrics.join(' | ') + '</p>' : '') +
        (e.notes ? '<p style="color:#666">' + e.notes + '</p>' : '') +
        (e.colab_url ? '<p><a href="' + e.colab_url + '" target="_blank">Colab 連結</a></p>' : '') +
        '</div>';
    }).join("");
  } catch (e) {
    var el = document.getElementById("experiment-list");
    if (el) el.innerHTML = '<p style="color:#d32f2f">無法載入，請確認後端是否啟動。</p>';
  }
}

function renderBpbChart(chartData) {
  var canvas = document.getElementById("bpb-canvas");
  if (!canvas || !chartData.length) {
    var chartDiv = document.getElementById("bpb-chart");
    if (chartDiv) chartDiv.innerHTML = '<p style="color:#888;text-align:center;padding:40px 0">尚無 val_bpb 數據</p>';
    return;
  }
  var ctx = canvas.getContext("2d");
  var rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * (window.devicePixelRatio || 1);
  canvas.height = rect.height * (window.devicePixelRatio || 1);
  ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
  var W = rect.width, H = rect.height;
  var pad = { top: 10, right: 20, bottom: 30, left: 50 };

  var vals = chartData.map(function(d) { return d.val_bpb; });
  var minV = Math.min.apply(null, vals);
  var maxV = Math.max.apply(null, vals);
  var range = maxV - minV || 0.1;
  minV -= range * 0.1;
  maxV += range * 0.1;

  var plotW = W - pad.left - pad.right;
  var plotH = H - pad.top - pad.bottom;

  ctx.clearRect(0, 0, W, H);

  // Y axis
  ctx.strokeStyle = "#ddd";
  ctx.fillStyle = "#888";
  ctx.font = "11px sans-serif";
  ctx.textAlign = "right";
  for (var i = 0; i <= 4; i++) {
    var yVal = minV + (maxV - minV) * (1 - i / 4);
    var yPos = pad.top + plotH * (i / 4);
    ctx.beginPath();
    ctx.moveTo(pad.left, yPos);
    ctx.lineTo(W - pad.right, yPos);
    ctx.stroke();
    ctx.fillText(yVal.toFixed(3), pad.left - 5, yPos + 4);
  }

  // Plot line
  ctx.strokeStyle = "#1a73e8";
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (var j = 0; j < chartData.length; j++) {
    var x = pad.left + (plotW * j / Math.max(chartData.length - 1, 1));
    var y = pad.top + plotH * (1 - (chartData[j].val_bpb - minV) / (maxV - minV));
    if (j === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Dots
  for (var k = 0; k < chartData.length; k++) {
    var dx = pad.left + (plotW * k / Math.max(chartData.length - 1, 1));
    var dy = pad.top + plotH * (1 - (chartData[k].val_bpb - minV) / (maxV - minV));
    ctx.beginPath();
    ctx.arc(dx, dy, 4, 0, Math.PI * 2);
    ctx.fillStyle = chartData[k].kept ? "#43a047" : "#ef5350";
    ctx.fill();
    ctx.strokeStyle = "white";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }

  // X label
  ctx.fillStyle = "#888";
  ctx.font = "11px sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("Experiments", W / 2, H - 5);
}

async function submitExperiment() {
  var name = document.getElementById("exp-name").value;
  if (!name) { alert("請輸入實驗名稱"); return; }
  var body = {
    name: name,
    val_bpb: parseFloat(document.getElementById("exp-bpb").value) || undefined,
    train_loss: parseFloat(document.getElementById("exp-loss").value) || undefined,
    steps: parseInt(document.getElementById("exp-steps").value) || undefined,
    duration_seconds: parseFloat(document.getElementById("exp-duration").value) || undefined,
    notes: document.getElementById("exp-notes").value || undefined,
    colab_url: document.getElementById("exp-colab").value || undefined,
    kept: document.getElementById("exp-kept").checked,
  };
  await fetch(API + "/research/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  loadExperiments();
  ["exp-name", "exp-bpb", "exp-loss", "exp-steps", "exp-duration", "exp-notes", "exp-colab"].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.value = "";
  });
  document.getElementById("exp-kept").checked = false;
}

async function uploadTsv(input) {
  if (!input.files.length) return;
  var formData = new FormData();
  formData.append("file", input.files[0]);
  try {
    var res = await fetch(API + "/research/batch", { method: "POST", body: formData });
    var data = await res.json();
    alert("匯入成功：" + data.count + " 個實驗");
    loadExperiments();
  } catch (e) {
    alert("匯入失敗：" + e.message);
  }
  input.value = "";
}

async function deleteExperiment(id) {
  if (!confirm("確定刪除此實驗結果？")) return;
  await fetch(API + "/research/" + id, { method: "DELETE" });
  loadExperiments();
}

async function checkGpuStatus() {
  var el = document.getElementById("gpu-status");
  try {
    var res = await fetch(API + "/research/status/gpu");
    var data = await res.json();
    el.innerHTML = '<div class="advice-box" style="margin-top:8px">' +
      '<strong>GPU 狀態：</strong>' + (data.has_gpu ? '可用' : '不可用') +
      '<br>' + data.message + '</div>';
  } catch (e) {
    el.innerHTML = '<div class="advice-box" style="margin-top:8px;color:#d32f2f">無法檢查 GPU 狀態</div>';
  }
}

// ─── 貢獻者 ───────────────────────────────────────────────

function contributors() {
  return `
    <div class="card">
      <h2>GitHub 貢獻者</h2>
      <p style="margin-top:8px;color:#666">感謝所有為 MD.Piece 貢獻的開發者</p>
      <div id="contributors-list" style="margin-top:16px">載入中...</div>
    </div>`;
}

async function loadContributors() {
  const list = document.getElementById("contributors-list");
  try {
    const res = await fetch("https://api.github.com/repos/" + GITHUB_REPO + "/contributors");
    if (!res.ok) throw new Error("無法取得貢獻者資料");
    const data = await res.json();
    list.innerHTML = data.map(function(c) {
      return '<div class="contributor-card">' +
        '<img src="' + c.avatar_url + '" alt="' + c.login + '" class="contributor-avatar" />' +
        '<div class="contributor-info">' +
        '<a href="' + c.html_url + '" target="_blank" rel="noopener noreferrer" class="contributor-name">' + c.login + '</a>' +
        '<span class="contributor-commits">' + c.contributions + ' 次提交</span>' +
        '</div></div>';
    }).join("");
  } catch (e) {
    list.innerHTML = '<p style="color:#d32f2f">' + e.message + '</p>';
  }
}

// ─── Service Worker ───────────────────────────────────────

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}

showPage("home");

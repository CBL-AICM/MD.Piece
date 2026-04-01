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
  const symptoms = input.split(",").map(symptom_text => symptom_text.trim()).filter(Boolean);
  const analysis_result_element = document.getElementById("analysis-result");
  analysis_result_element.innerHTML = '<div class="loading">分析中...</div>';

  try {
    const api_response = await fetch(`${API}/symptoms/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symptoms }),
    });
    const response_data = await api_response.json();

    const urgencyMap = {
      emergency: { label: "緊急", cls: "urgency-emergency" },
      high: { label: "高", cls: "urgency-high" },
      medium: { label: "中", cls: "urgency-medium" },
      low: { label: "低", cls: "urgency-low" },
    };
    const urgency_info = urgencyMap[response_data.urgency] || urgencyMap.low;

    const conditions = (response_data.conditions || [])
      .map(condition_item => `<li><strong>${condition_item.name}</strong> — 可能性：${condition_item.likelihood}</li>`)
      .join("");

    analysis_result_element.innerHTML = `
      <div class="ai-result-card">
        <div class="urgency-badge ${urgency_info.cls}">緊急程度：${urgency_info.label}</div>
        <h4>可能病因</h4>
        <ul>${conditions}</ul>
        <h4>建議科別</h4>
        <p>${response_data.recommended_department || "家醫科"}</p>
        <h4>建議</h4>
        <p>${response_data.advice || ""}</p>
        <div class="disclaimer">${response_data.disclaimer || "此分析僅供參考，不構成醫療診斷。如有不適請立即就醫。"}</div>
      </div>`;
  } catch (fetch_error) {
    analysis_result_element.innerHTML = '<div class="advice-box">分析失敗，請確認後端是否啟動。</div>';
  }
}

async function quickAdvice() {
  const input = document.getElementById("symptom-input").value.split(",")[0].trim();
  if (!input) return;
  const api_response = await fetch(`${API}/symptoms/advice?symptom=${encodeURIComponent(input)}`);
  const response_data = await api_response.json();
  document.getElementById("analysis-result").innerHTML =
    `<div class="advice-box"><strong>${response_data.symptom}</strong>：${response_data.advice}</div>`;
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
  const api_response = await fetch(`${API}/doctors/`);
  const response_data = await api_response.json();
  const doctor_list_element = document.getElementById("doctor-list");
  if (!response_data.doctors?.length) {
    doctor_list_element.innerHTML = "<p>尚無醫師資料</p>";
    return;
  }
  doctor_list_element.innerHTML = response_data.doctors.map(doctor_entry => `
    <div class="record-card">
      <strong>${doctor_entry.name}</strong> — ${doctor_entry.specialty}
      ${doctor_entry.phone ? `<span style="color:#666"> | ${doctor_entry.phone}</span>` : ""}
      <button class="btn-delete" onclick="deleteDoctor('${doctor_entry.id}')">刪除</button>
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

async function deleteDoctor(doctor_id) {
  if (!confirm("確定刪除此醫師？")) return;
  await fetch(`${API}/doctors/${doctor_id}`, { method: "DELETE" });
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
  const api_response = await fetch(`${API}/patients/`);
  const response_data = await api_response.json();
  const patient_list_element = document.getElementById("patient-list");
  if (!response_data.patients?.length) {
    patient_list_element.innerHTML = "<p>尚無病患資料</p>";
    return;
  }
  patient_list_element.innerHTML = response_data.patients.map(patient_entry => `
    <div class="record-card">
      <strong>${patient_entry.name}</strong> — ${patient_entry.age}歲
      ${patient_entry.gender ? ` | ${patient_entry.gender === "male" ? "男" : "女"}` : ""}
      ${patient_entry.phone ? ` | ${patient_entry.phone}` : ""}
      <button class="btn-delete" onclick="deletePatient('${patient_entry.id}')">刪除</button>
      <button class="btn-view" onclick="showPage('records');setTimeout(()=>{document.getElementById('r-patient').value='${patient_entry.id}';searchRecords()},100)">查看病歷</button>
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

async function deletePatient(patient_id) {
  if (!confirm("確定刪除此病患？相關病歷也會一併刪除。")) return;
  await fetch(`${API}/patients/${patient_id}`, { method: "DELETE" });
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
  const [patients_response, doctors_response] = await Promise.all([
    fetch(`${API}/patients/`).then(patients_fetch_response => patients_fetch_response.json()),
    fetch(`${API}/doctors/`).then(doctors_fetch_response => doctors_fetch_response.json()),
  ]);

  const patientOpts = (patients_response.patients || []).map(patient_entry =>
    `<option value="${patient_entry.id}">${patient_entry.name} (${patient_entry.age}歲)</option>`
  ).join("");
  const doctorOpts = (doctors_response.doctors || []).map(doctor_entry =>
    `<option value="${doctor_entry.id}">${doctor_entry.name} — ${doctor_entry.specialty}</option>`
  ).join("");

  const record_patient_select = document.getElementById("r-patient");
  const record_doctor_select = document.getElementById("r-doctor");
  const filter_patient_select = document.getElementById("filter-patient");
  if (record_patient_select) record_patient_select.innerHTML = `<option value="">選擇病患</option>${patientOpts}`;
  if (record_doctor_select) record_doctor_select.innerHTML = `<option value="">選擇醫師（選填）</option>${doctorOpts}`;
  if (filter_patient_select) filter_patient_select.innerHTML = `<option value="">所有病患</option>${patientOpts}`;

  searchRecords();
}

async function addRecord() {
  const patient_id = document.getElementById("r-patient").value;
  if (!patient_id) { alert("請選擇病患"); return; }
  const doctor_id = document.getElementById("r-doctor").value || undefined;
  const dateVal = document.getElementById("r-date").value;
  const visit_date = dateVal ? new Date(dateVal).toISOString() : undefined;
  const symptomsStr = document.getElementById("r-symptoms").value;
  const symptoms = symptomsStr ? symptomsStr.split(",").map(symptom_text => symptom_text.trim()).filter(Boolean) : [];
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
    const form_field = document.getElementById(id);
    if (form_field) form_field.value = "";
  });
}

async function searchRecords() {
  const patientId = document.getElementById("filter-patient")?.value || "";
  const diagnosis = document.getElementById("filter-diagnosis")?.value || "";
  let url = `${API}/records/?`;
  if (patientId) url += `patient_id=${patientId}&`;
  if (diagnosis) url += `diagnosis=${encodeURIComponent(diagnosis)}&`;

  const api_response = await fetch(url);
  const response_data = await api_response.json();
  const record_list_element = document.getElementById("record-list");

  if (!response_data.records?.length) {
    record_list_element.innerHTML = "<p>尚無病歷資料</p>";
    return;
  }

  record_list_element.innerHTML = response_data.records.map(record_entry => {
    const date = record_entry.visit_date ? new Date(record_entry.visit_date).toLocaleDateString("zh-TW") : "未記錄";
    const patientName = record_entry.patients?.name || "未知";
    const doctorName = record_entry.doctors?.name || "未指定";
    const symptoms = (record_entry.symptoms || []).join(", ");
    return `
      <div class="record-card">
        <div class="record-header">
          <strong>${patientName}</strong> — ${date} — 醫師：${doctorName}
          <button class="btn-delete" onclick="deleteRecord('${record_entry.id}')">刪除</button>
        </div>
        ${symptoms ? `<p><strong>症狀：</strong>${symptoms}</p>` : ""}
        ${record_entry.diagnosis ? `<p><strong>診斷：</strong>${record_entry.diagnosis}</p>` : ""}
        ${record_entry.prescription ? `<p><strong>處方：</strong>${record_entry.prescription}</p>` : ""}
        ${record_entry.notes ? `<p><strong>備註：</strong>${record_entry.notes}</p>` : ""}
      </div>`;
  }).join("");
}

async function deleteRecord(record_id) {
  if (!confirm("確定刪除此病歷？")) return;
  await fetch(`${API}/records/${record_id}`, { method: "DELETE" });
  searchRecords();
}

// ─── Toast 通知 ──────────────────────────────────────────

function showToast(msg, type) {
  type = type || "info";
  var toast_container = document.getElementById("toast-container");
  if (!toast_container) {
    toast_container = document.createElement("div");
    toast_container.id = "toast-container";
    toast_container.style.cssText = "position:fixed;top:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px";
    document.body.appendChild(toast_container);
  }
  var colors = { success: "#43a047", error: "#d32f2f", info: "#1a73e8", warning: "#ef6c00" };
  var toast_element = document.createElement("div");
  toast_element.style.cssText = "padding:12px 20px;border-radius:8px;color:white;font-size:0.9rem;box-shadow:0 4px 12px rgba(0,0,0,0.2);transition:opacity 0.3s;max-width:360px;background:" + (colors[type] || colors.info);
  toast_element.textContent = msg;
  toast_container.appendChild(toast_element);
  setTimeout(function() { toast_element.style.opacity = "0"; setTimeout(function() { toast_element.remove(); }, 300); }, 3000);
}

// ─── 自動研究 ─────────────────────────────────────────────

var _researchChartData = []; // 供 tooltip 使用

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
        <button class="secondary" onclick="exportExperiments()">匯出 TSV</button>
        <input type="file" id="tsv-upload" accept=".tsv,.csv" style="display:none" onchange="uploadTsv(this)" />
      </div>
      <div id="gpu-status"></div>
    </div>
    <div class="card">
      <h3>統計總覽</h3>
      <div id="research-stats" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-top:12px"></div>
    </div>
    <div class="card">
      <h3>val_bpb 趨勢</h3>
      <div id="bpb-chart" style="position:relative;height:220px;margin:12px 0">
        <canvas id="bpb-canvas" style="width:100%;height:100%"></canvas>
        <div id="chart-tooltip" style="display:none;position:absolute;background:rgba(0,0,0,0.85);color:white;padding:8px 12px;border-radius:6px;font-size:0.8rem;pointer-events:none;white-space:pre-line;z-index:10"></div>
      </div>
      <div id="best-bpb" style="margin-top:8px"></div>
    </div>
    <div class="card">
      <h3>排行榜 (Top 5)</h3>
      <div id="leaderboard"></div>
    </div>
    <div class="card">
      <h3>篩選與搜尋</h3>
      <div class="filter-bar">
        <input id="exp-search" placeholder="搜尋名稱或備註..." style="flex:2" oninput="filterExperiments()" />
        <select id="exp-filter-kept" onchange="filterExperiments()" style="flex:1">
          <option value="">全部</option>
          <option value="true">Kept</option>
          <option value="false">Reverted</option>
        </select>
        <select id="exp-sort" onchange="filterExperiments()" style="flex:1">
          <option value="submitted_at">時間排序</option>
          <option value="val_bpb">val_bpb 排序</option>
          <option value="train_loss">loss 排序</option>
          <option value="duration_seconds">耗時排序</option>
        </select>
      </div>
      <div id="experiment-list"><p>載入中...</p></div>
    </div>
    <div class="card" id="submit-card">
      <h3 style="cursor:pointer" onclick="toggleSubmitForm()">手動提交實驗結果 <span id="submit-toggle" style="font-size:0.8rem;color:#888">展開</span></h3>
      <div id="submit-form" style="display:none">
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
    </div>`;
}

function toggleSubmitForm() {
  var form = document.getElementById("submit-form");
  var toggle = document.getElementById("submit-toggle");
  if (form.style.display === "none") {
    form.style.display = "block";
    toggle.textContent = "收起";
  } else {
    form.style.display = "none";
    toggle.textContent = "展開";
  }
}

var _allExperiments = [];

async function loadExperiments() {
  try {
    var [list_response, stats_response, leaderboard_response] = await Promise.all([
      fetch(API + "/research/"),
      fetch(API + "/research/stats"),
      fetch(API + "/research/leaderboard?top_n=5"),
    ]);
    var experiments_data = await list_response.json();
    var stats = await stats_response.json();
    var leaderboard_data = await leaderboard_response.json();

    _allExperiments = experiments_data.experiments || [];

    // 統計卡片
    renderStatsCards(stats);

    // 畫圖表
    renderBpbChart(stats.chart_data || []);

    // 顯示最佳結果
    var best_bpb_element = document.getElementById("best-bpb");
    if (best_bpb_element && stats.best_bpb != null) {
      best_bpb_element.innerHTML = '<div class="advice-box">' +
        '<strong>最佳 val_bpb：</strong>' + stats.best_bpb.toFixed(4) +
        ' (' + stats.best_experiment + ')' +
        ' — 共 ' + stats.total + ' 個實驗，' + stats.with_bpb + ' 個有 bpb 數據</div>';
    }

    // 排行榜
    renderLeaderboard(leaderboard_data.leaderboard || []);

    // 顯示實驗列表
    renderExperimentList(_allExperiments);
  } catch (load_error) {
    var experiment_list_element = document.getElementById("experiment-list");
    if (experiment_list_element) experiment_list_element.innerHTML = '<p style="color:#d32f2f">無法載入，請確認後端是否啟動。</p>';
  }
}

function renderStatsCards(stats) {
  var stats_element = document.getElementById("research-stats");
  if (!stats_element) return;
  var cards = [
    { label: "總實驗數", value: stats.total || 0, color: "#1a73e8" },
    { label: "保留 (Kept)", value: stats.kept_count || 0, color: "#43a047" },
    { label: "還原 (Reverted)", value: stats.reverted_count || 0, color: "#ef5350" },
    { label: "改善率", value: stats.improvement_rate != null ? stats.improvement_rate + "%" : "N/A", color: "#ef6c00" },
    { label: "最佳 val_bpb", value: stats.best_bpb != null ? stats.best_bpb.toFixed(4) : "N/A", color: "#7b1fa2" },
    { label: "總訓練時間", value: stats.total_duration_hours + "h", color: "#00838f" },
  ];
  stats_element.innerHTML = cards.map(function(stat_card) {
    return '<div style="text-align:center;padding:12px;background:#f8f9fa;border-radius:8px;border-left:3px solid ' + stat_card.color + '">' +
      '<div style="font-size:1.4rem;font-weight:700;color:' + stat_card.color + '">' + stat_card.value + '</div>' +
      '<div style="font-size:0.8rem;color:#666;margin-top:4px">' + stat_card.label + '</div></div>';
  }).join("");
}

function renderLeaderboard(ranking) {
  var leaderboard_element = document.getElementById("leaderboard");
  if (!leaderboard_element) return;
  if (!ranking.length) {
    leaderboard_element.innerHTML = '<p style="color:#888">尚無排行資料</p>';
    return;
  }
  var medals = ["#FFD700", "#C0C0C0", "#CD7F32"];
  leaderboard_element.innerHTML = '<table style="width:100%;border-collapse:collapse;font-size:0.9rem">' +
    '<tr style="border-bottom:2px solid #e0e0e0"><th style="text-align:left;padding:6px">#</th><th style="text-align:left;padding:6px">名稱</th><th style="text-align:right;padding:6px">val_bpb</th><th style="text-align:right;padding:6px">loss</th><th style="text-align:right;padding:6px">耗時</th></tr>' +
    ranking.map(function(ranking_entry) {
      var medal = ranking_entry.rank <= 3 ? '<span style="color:' + medals[ranking_entry.rank - 1] + ';font-weight:bold">' + ranking_entry.rank + '</span>' : ranking_entry.rank;
      var duration_display = ranking_entry.duration_seconds ? Math.round(ranking_entry.duration_seconds) + "s" : "-";
      return '<tr style="border-bottom:1px solid #f0f0f0">' +
        '<td style="padding:6px">' + medal + '</td>' +
        '<td style="padding:6px">' + ranking_entry.name + '</td>' +
        '<td style="text-align:right;padding:6px;font-weight:600;color:#1a73e8">' + (ranking_entry.val_bpb != null ? ranking_entry.val_bpb.toFixed(4) : "-") + '</td>' +
        '<td style="text-align:right;padding:6px">' + (ranking_entry.train_loss != null ? ranking_entry.train_loss.toFixed(4) : "-") + '</td>' +
        '<td style="text-align:right;padding:6px;color:#666">' + duration_display + '</td></tr>';
    }).join("") + '</table>';
}

function filterExperiments() {
  var search = (document.getElementById("exp-search").value || "").toLowerCase();
  var keptFilter = document.getElementById("exp-filter-kept").value;
  var sortBy = document.getElementById("exp-sort").value;

  var filtered = _allExperiments.slice();

  if (search) {
    filtered = filtered.filter(function(experiment_entry) {
      return (experiment_entry.name || "").toLowerCase().indexOf(search) !== -1 ||
             (experiment_entry.notes || "").toLowerCase().indexOf(search) !== -1;
    });
  }

  if (keptFilter === "true") {
    filtered = filtered.filter(function(experiment_entry) { return experiment_entry.kept === true; });
  } else if (keptFilter === "false") {
    filtered = filtered.filter(function(experiment_entry) { return experiment_entry.kept === false; });
  }

  if (sortBy === "val_bpb") {
    filtered.sort(function(exp_a, exp_b) { return (exp_a.val_bpb || Infinity) - (exp_b.val_bpb || Infinity); });
  } else if (sortBy === "train_loss") {
    filtered.sort(function(exp_a, exp_b) { return (exp_a.train_loss || Infinity) - (exp_b.train_loss || Infinity); });
  } else if (sortBy === "duration_seconds") {
    filtered.sort(function(exp_a, exp_b) { return (exp_b.duration_seconds || 0) - (exp_a.duration_seconds || 0); });
  }

  renderExperimentList(filtered);
}

function renderExperimentList(experiments) {
  var experiment_list_element = document.getElementById("experiment-list");
  if (!experiment_list_element) return;
  if (!experiments.length) {
    experiment_list_element.innerHTML = "<p>尚無實驗結果。請從 Colab 執行訓練後回傳，或匯入 results.tsv。</p>";
    return;
  }
  experiment_list_element.innerHTML = '<p style="color:#888;font-size:0.85rem;margin-bottom:8px">共 ' + experiments.length + ' 筆結果</p>' +
    experiments.map(function(experiment_entry) {
      var metrics = [];
      if (experiment_entry.val_bpb != null) metrics.push('<span style="font-weight:600;color:#1a73e8">bpb: ' + experiment_entry.val_bpb.toFixed(4) + '</span>');
      if (experiment_entry.train_loss != null) metrics.push("loss: " + experiment_entry.train_loss.toFixed(4));
      if (experiment_entry.steps != null) metrics.push(experiment_entry.steps + " steps");
      if (experiment_entry.duration_seconds != null) {
        var duration_seconds = experiment_entry.duration_seconds;
        metrics.push(duration_seconds >= 3600 ? (duration_seconds / 3600).toFixed(1) + "h" : duration_seconds >= 60 ? Math.round(duration_seconds / 60) + "m" : Math.round(duration_seconds) + "s");
      }
      var keptBadge = experiment_entry.kept === true
        ? '<span class="urgency-badge urgency-low" style="font-size:0.75rem;padding:2px 8px">kept</span>'
        : experiment_entry.kept === false
        ? '<span class="urgency-badge urgency-high" style="font-size:0.75rem;padding:2px 8px">reverted</span>'
        : '';
      return '<div class="record-card">' +
        '<div class="record-header">' +
        '<strong>' + experiment_entry.name + '</strong> ' + keptBadge + ' — ' + (experiment_entry.submitted_at || "").slice(0, 10) +
        '<button class="btn-delete" onclick="deleteExperiment(\'' + experiment_entry.id + '\')">刪除</button>' +
        '</div>' +
        (metrics.length ? '<p>' + metrics.join(' | ') + '</p>' : '') +
        (experiment_entry.notes ? '<p style="color:#666;font-size:0.9rem">' + experiment_entry.notes + '</p>' : '') +
        (experiment_entry.colab_url ? '<p><a href="' + experiment_entry.colab_url + '" target="_blank">Colab 連結</a></p>' : '') +
        '</div>';
    }).join("");
}

function renderBpbChart(chartData) {
  _researchChartData = chartData;
  var canvas = document.getElementById("bpb-canvas");
  if (!canvas || !chartData.length) {
    var chartDiv = document.getElementById("bpb-chart");
    if (chartDiv) chartDiv.innerHTML = '<p style="color:#888;text-align:center;padding:40px 0">尚無 val_bpb 數據</p>';
    return;
  }
  var ctx = canvas.getContext("2d");
  var rect = canvas.parentElement.getBoundingClientRect();
  var dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
  var W = rect.width, H = rect.height;
  var pad = { top: 15, right: 20, bottom: 30, left: 55 };

  var bpb_values = chartData.map(function(chart_point) { return chart_point.val_bpb; });
  var minV = Math.min.apply(null, bpb_values);
  var maxV = Math.max.apply(null, bpb_values);
  var range = maxV - minV || 0.1;
  minV -= range * 0.1;
  maxV += range * 0.1;

  var plotW = W - pad.left - pad.right;
  var plotH = H - pad.top - pad.bottom;

  ctx.clearRect(0, 0, W, H);

  // 背景漸層
  var gradient = ctx.createLinearGradient(0, pad.top, 0, H - pad.bottom);
  gradient.addColorStop(0, "rgba(26, 115, 232, 0.05)");
  gradient.addColorStop(1, "rgba(26, 115, 232, 0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(pad.left, pad.top, plotW, plotH);

  // Y axis grid
  ctx.strokeStyle = "#e8e8e8";
  ctx.fillStyle = "#888";
  ctx.font = "11px sans-serif";
  ctx.textAlign = "right";
  for (var i = 0; i <= 4; i++) {
    var yVal = minV + (maxV - minV) * (1 - i / 4);
    var yPos = pad.top + plotH * (i / 4);
    ctx.beginPath();
    ctx.setLineDash([4, 4]);
    ctx.moveTo(pad.left, yPos);
    ctx.lineTo(W - pad.right, yPos);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillText(yVal.toFixed(3), pad.left - 5, yPos + 4);
  }

  // 計算座標
  var points = [];
  for (var j = 0; j < chartData.length; j++) {
    points.push({
      x: pad.left + (plotW * j / Math.max(chartData.length - 1, 1)),
      y: pad.top + plotH * (1 - (chartData[j].val_bpb - minV) / (maxV - minV)),
    });
  }

  // 填充面積
  ctx.beginPath();
  ctx.moveTo(points[0].x, H - pad.bottom);
  for (var a = 0; a < points.length; a++) {
    ctx.lineTo(points[a].x, points[a].y);
  }
  ctx.lineTo(points[points.length - 1].x, H - pad.bottom);
  ctx.closePath();
  var areaGrad = ctx.createLinearGradient(0, pad.top, 0, H - pad.bottom);
  areaGrad.addColorStop(0, "rgba(26, 115, 232, 0.15)");
  areaGrad.addColorStop(1, "rgba(26, 115, 232, 0.02)");
  ctx.fillStyle = areaGrad;
  ctx.fill();

  // Plot line
  ctx.strokeStyle = "#1a73e8";
  ctx.lineWidth = 2.5;
  ctx.lineJoin = "round";
  ctx.beginPath();
  for (var l = 0; l < points.length; l++) {
    if (l === 0) ctx.moveTo(points[l].x, points[l].y);
    else ctx.lineTo(points[l].x, points[l].y);
  }
  ctx.stroke();

  // Best line
  var bestIdx = bpb_values.indexOf(Math.min.apply(null, bpb_values));
  ctx.strokeStyle = "rgba(67, 160, 71, 0.4)";
  ctx.lineWidth = 1;
  ctx.setLineDash([6, 4]);
  ctx.beginPath();
  ctx.moveTo(pad.left, points[bestIdx].y);
  ctx.lineTo(W - pad.right, points[bestIdx].y);
  ctx.stroke();
  ctx.setLineDash([]);

  // Dots
  for (var k = 0; k < points.length; k++) {
    ctx.beginPath();
    ctx.arc(points[k].x, points[k].y, 5, 0, Math.PI * 2);
    ctx.fillStyle = chartData[k].kept ? "#43a047" : chartData[k].kept === false ? "#ef5350" : "#999";
    ctx.fill();
    ctx.strokeStyle = "white";
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // X label
  ctx.fillStyle = "#888";
  ctx.font = "11px sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("Experiments (" + chartData.length + ")", W / 2, H - 5);

  // Tooltip 事件
  canvas.onmousemove = function(evt) {
    var canvas_rect = canvas.getBoundingClientRect();
    var mouse_x = evt.clientX - canvas_rect.left;
    var tooltip = document.getElementById("chart-tooltip");
    if (!tooltip) return;
    var hit_index = -1;
    for (var point_idx = 0; point_idx < points.length; point_idx++) {
      if (Math.abs(mouse_x - points[point_idx].x) < 15) { hit_index = point_idx; break; }
    }
    if (hit_index >= 0) {
      var hovered_data = chartData[hit_index];
      var tooltip_lines = [hovered_data.name];
      tooltip_lines.push("val_bpb: " + hovered_data.val_bpb.toFixed(4));
      if (hovered_data.train_loss != null) tooltip_lines.push("loss: " + hovered_data.train_loss.toFixed(4));
      if (hovered_data.steps) tooltip_lines.push("steps: " + hovered_data.steps);
      if (hovered_data.duration_seconds) tooltip_lines.push("duration: " + Math.round(hovered_data.duration_seconds) + "s");
      tooltip_lines.push(hovered_data.kept ? "kept" : hovered_data.kept === false ? "reverted" : "");
      tooltip.textContent = tooltip_lines.filter(Boolean).join("\n");
      tooltip.style.display = "block";
      tooltip.style.left = Math.min(points[hit_index].x + 10, W - 180) + "px";
      tooltip.style.top = (points[hit_index].y - 10) + "px";
    } else {
      tooltip.style.display = "none";
    }
  };
  canvas.onmouseleave = function() {
    var tooltip = document.getElementById("chart-tooltip");
    if (tooltip) tooltip.style.display = "none";
  };
}

async function submitExperiment() {
  var name = document.getElementById("exp-name").value;
  if (!name) { showToast("請輸入實驗名稱", "warning"); return; }
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
  try {
    var api_response = await fetch(API + "/research/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!api_response.ok) throw new Error("HTTP " + api_response.status);
    showToast("實驗已提交：" + name, "success");
    loadExperiments();
    ["exp-name", "exp-bpb", "exp-loss", "exp-steps", "exp-duration", "exp-notes", "exp-colab"].forEach(function(id) {
      var form_field = document.getElementById(id);
      if (form_field) form_field.value = "";
    });
    document.getElementById("exp-kept").checked = false;
  } catch (submit_error) {
    showToast("提交失敗：" + submit_error.message, "error");
  }
}

async function uploadTsv(input) {
  if (!input.files.length) return;
  var formData = new FormData();
  formData.append("file", input.files[0]);
  try {
    var api_response = await fetch(API + "/research/batch", { method: "POST", body: formData });
    var response_data = await api_response.json();
    showToast("匯入成功：" + response_data.count + " 個實驗" + (response_data.errors ? "，" + response_data.errors + " 個失敗" : ""), response_data.errors ? "warning" : "success");
    loadExperiments();
  } catch (upload_error) {
    showToast("匯入失敗：" + upload_error.message, "error");
  }
  input.value = "";
}

async function exportExperiments() {
  try {
    var api_response = await fetch(API + "/research/export");
    var response_data = await api_response.json();
    if (!response_data.tsv) { showToast("無資料可匯出", "warning"); return; }
    var tsv_blob = new Blob([response_data.tsv], { type: "text/tab-separated-values" });
    var download_url = URL.createObjectURL(tsv_blob);
    var download_link = document.createElement("a");
    download_link.href = download_url;
    download_link.download = "experiments_" + new Date().toISOString().slice(0, 10) + ".tsv";
    download_link.click();
    URL.revokeObjectURL(download_url);
    showToast("已匯出 " + response_data.count + " 筆實驗", "success");
  } catch (export_error) {
    showToast("匯出失敗：" + export_error.message, "error");
  }
}

async function deleteExperiment(experiment_id) {
  if (!confirm("確定刪除此實驗結果？")) return;
  try {
    await fetch(API + "/research/" + experiment_id, { method: "DELETE" });
    showToast("實驗已刪除", "success");
    loadExperiments();
  } catch (delete_error) {
    showToast("刪除失敗", "error");
  }
}

async function checkGpuStatus() {
  var gpu_status_element = document.getElementById("gpu-status");
  try {
    var api_response = await fetch(API + "/research/status/gpu");
    var response_data = await api_response.json();
    gpu_status_element.innerHTML = '<div class="advice-box" style="margin-top:8px">' +
      '<strong>GPU 狀態：</strong>' + (response_data.has_gpu ? '可用' : '不可用') +
      '<br>' + response_data.message + '</div>';
  } catch (fetch_error) {
    gpu_status_element.innerHTML = '<div class="advice-box" style="margin-top:8px;color:#d32f2f">無法檢查 GPU 狀態</div>';
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
  const contributors_list_element = document.getElementById("contributors-list");
  try {
    const api_response = await fetch("https://api.github.com/repos/" + GITHUB_REPO + "/contributors");
    if (!api_response.ok) throw new Error("無法取得貢獻者資料");
    const contributors_data = await api_response.json();
    contributors_list_element.innerHTML = contributors_data.map(function(contributor_entry) {
      return '<div class="contributor-card">' +
        '<img src="' + contributor_entry.avatar_url + '" alt="' + contributor_entry.login + '" class="contributor-avatar" />' +
        '<div class="contributor-info">' +
        '<a href="' + contributor_entry.html_url + '" target="_blank" rel="noopener noreferrer" class="contributor-name">' + contributor_entry.login + '</a>' +
        '<span class="contributor-commits">' + contributor_entry.contributions + ' 次提交</span>' +
        '</div></div>';
    }).join("");
  } catch (fetch_error) {
    contributors_list_element.innerHTML = '<p style="color:#d32f2f">' + fetch_error.message + '</p>';
  }
}

// ─── Service Worker ───────────────────────────────────────

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}

showPage("home");

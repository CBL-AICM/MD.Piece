const API = window.location.hostname === "localhost" ? "http://localhost:8000" : "";
const GITHUB_REPO = "CBL-AICM/MD.Piece";

// ─── 使用者狀態 ─────────────────────────────────────────────

function getCurrentUser() {
  try {
    return JSON.parse(localStorage.getItem('mdpiece_user'));
  } catch { return null; }
}

function setCurrentUser(user) {
  localStorage.setItem('mdpiece_user', JSON.stringify(user));
}

// ─── 路由 ──────────────────────────────────────────────────

function showPage(page) {
  const app = document.getElementById("app");
  const pages = { home, symptoms, doctors, patients, records, research, education, contributors };
  // Page transition
  app.style.opacity = '0';
  app.style.transform = 'translateY(12px)';
  setTimeout(() => {
    app.innerHTML = pages[page]?.() || "";
    // 頁面載入後的初始化
    if (page === "doctors") loadDoctors();
    if (page === "patients") loadPatients();
    if (page === "records") loadRecordsPage();
    if (page === "research") loadExperiments();
    if (page === "contributors") loadContributors();
    if (page === "education") loadEducationPage();
    // Render Lucide icons
    if (typeof lucide !== 'undefined') lucide.createIcons();
    // Fade in
    requestAnimationFrame(() => {
      app.style.transition = 'opacity .3s ease, transform .3s ease';
      app.style.opacity = '1';
      app.style.transform = 'translateY(0)';
    });
  }, 150);
}

// ─── 註冊頁面 ────────────────────────────────────────────────

function showRegister() {
  const app = document.getElementById("app");
  app.innerHTML = `
    <div class="register-container">
      <div class="register-card">
        <div class="register-header">
          <h2>歡迎加入 MD.Piece</h2>
          <p>告訴我們你是誰，開啟專屬體驗</p>
        </div>
        <div class="register-form">
          <label class="register-label">你的暱稱</label>
          <input id="reg-nickname" type="text" placeholder="輸入暱稱..." maxlength="20" autocomplete="off" />

          <label class="register-label" style="margin-top:18px">你的角色</label>
          <div class="role-select">
            <div class="role-card" id="role-doctor" onclick="selectRole('doctor')">
              <div class="role-icon role-icon-doctor"><i data-lucide="stethoscope"></i></div>
              <h4>醫師</h4>
              <p>管理患者、查看病歷</p>
            </div>
            <div class="role-card" id="role-patient" onclick="selectRole('patient')">
              <div class="role-icon role-icon-patient"><i data-lucide="heart-pulse"></i></div>
              <h4>患者</h4>
              <p>記錄症狀、追蹤健康</p>
            </div>
          </div>

          <button class="primary register-btn" id="reg-submit" onclick="submitRegister()" disabled>
            開始使用
          </button>
        </div>
      </div>
    </div>`;
  if (typeof lucide !== 'undefined') lucide.createIcons();
  document.getElementById('reg-nickname').addEventListener('input', validateRegForm);
}

let _selectedRole = null;

function selectRole(role) {
  _selectedRole = role;
  document.querySelectorAll('.role-card').forEach(c => c.classList.remove('selected'));
  document.getElementById(`role-${role}`).classList.add('selected');
  validateRegForm();
}

function validateRegForm() {
  const nickname = document.getElementById('reg-nickname')?.value.trim();
  const btn = document.getElementById('reg-submit');
  if (btn) btn.disabled = !(nickname && _selectedRole);
}

async function submitRegister() {
  const nickname = document.getElementById('reg-nickname').value.trim();
  if (!nickname || !_selectedRole) return;

  const btn = document.getElementById('reg-submit');
  btn.disabled = true;
  btn.textContent = '建立中...';

  const colors = ['#5B9FE8', '#9B80D4', '#D08A8A', '#55B88A', '#D9A54A'];
  const avatar_color = colors[Math.floor(Math.random() * colors.length)];

  try {
    const res = await fetch(`${API}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nickname, role: _selectedRole, avatar_color })
    });
    const user = await res.json();
    setCurrentUser(user);
    showPage('home');
    // Activate sidebar
    document.querySelectorAll('.nav-item').forEach((b, i) => {
      b.classList.toggle('active', i === 0);
    });
  } catch (e) {
    // Fallback: save locally if backend unavailable
    const user = { id: crypto.randomUUID(), nickname, role: _selectedRole, avatar_color };
    setCurrentUser(user);
    showPage('home');
  }
}

// ─── 首頁 ──────────────────────────────────────────────────

function home() {
  const user = getCurrentUser();
  const greeting = user
    ? `<h2 class="dash-title">${user.role === 'doctor' ? '🩺' : '💙'} ${user.nickname}，歡迎回來</h2>
       <p class="dash-subtitle">選擇你的下一步行動</p>`
    : `<h2 class="dash-title">任務總覽</h2>
       <p class="dash-subtitle">選擇你的下一步行動</p>`;
  return `
    <div class="dash-welcome">
      <div class="dash-welcome-text">
        ${greeting}
      </div>
      <div class="dash-stats">
        <div class="dash-stat">
          <span class="dash-stat-num">7</span>
          <span class="dash-stat-label">可用任務</span>
        </div>
        <div class="dash-stat-divider"></div>
        <div class="dash-stat">
          <span class="dash-stat-num">AI</span>
          <span class="dash-stat-label">分析引擎</span>
        </div>
        <div class="dash-stat-divider"></div>
        <div class="dash-stat">
          <span class="dash-stat-num">PWA</span>
          <span class="dash-stat-label">跨平台</span>
        </div>
      </div>
    </div>
    <div class="mission-grid">
      <div class="mission-card mission-blue" onclick="navigateTo('symptoms',null)">
        <div class="mission-icon"><i data-lucide="scan-search"></i></div>
        <h4>症狀分析</h4>
        <p>AI 助你釐清身體訊號</p>
        <span class="mission-tag tag-ready">可執行</span>
      </div>
      <div class="mission-card mission-purple" onclick="navigateTo('records',null)">
        <div class="mission-icon"><i data-lucide="clipboard-list"></i></div>
        <h4>病歷管理</h4>
        <p>守護每一次就診紀錄</p>
        <span class="mission-tag tag-ready">可執行</span>
      </div>
      <div class="mission-card mission-rose" onclick="navigateTo('doctors',null)">
        <div class="mission-icon"><i data-lucide="stethoscope"></i></div>
        <h4>醫師列表</h4>
        <p>管理你的醫療團隊</p>
        <span class="mission-tag tag-ready">可執行</span>
      </div>
      <div class="mission-card mission-mint" onclick="navigateTo('patients',null)">
        <div class="mission-icon"><i data-lucide="users"></i></div>
        <h4>病患管理</h4>
        <p>關懷每一位患者</p>
        <span class="mission-tag tag-ready">可執行</span>
      </div>
      <div class="mission-card mission-teal" onclick="navigateTo('education',null)">
        <div class="mission-icon"><i data-lucide="book-heart"></i></div>
        <h4>衛教專欄</h4>
        <p>溫暖易懂的健康知識</p>
        <span class="mission-tag tag-ready">可執行</span>
      </div>
      <div class="mission-card mission-gold" onclick="navigateTo('research',null)">
        <div class="mission-icon"><i data-lucide="flask-conical"></i></div>
        <h4>自動研究</h4>
        <p>探索醫學前沿</p>
        <span class="mission-tag tag-ready">可執行</span>
      </div>
      <div class="mission-card mission-purple" onclick="navigateTo('contributors',null)">
        <div class="mission-icon"><i data-lucide="heart-handshake"></i></div>
        <h4>貢獻者</h4>
        <p>共同打造的力量</p>
        <span class="mission-tag tag-community">社群</span>
      </div>
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

// ─── Toast 通知 ──────────────────────────────────────────

function showToast(msg, type) {
  type = type || "info";
  var existing = document.getElementById("toast-container");
  if (!existing) {
    existing = document.createElement("div");
    existing.id = "toast-container";
    existing.style.cssText = "position:fixed;top:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px";
    document.body.appendChild(existing);
  }
  var colors = { success: "#43a047", error: "#d32f2f", info: "#1a73e8", warning: "#ef6c00" };
  var toast = document.createElement("div");
  toast.style.cssText = "padding:12px 20px;border-radius:8px;color:white;font-size:0.9rem;box-shadow:0 4px 12px rgba(0,0,0,0.2);transition:opacity 0.3s;max-width:360px;background:" + (colors[type] || colors.info);
  toast.textContent = msg;
  existing.appendChild(toast);
  setTimeout(function() { toast.style.opacity = "0"; setTimeout(function() { toast.remove(); }, 300); }, 3000);
}

// ─── 衛教專欄 ─────────────────────────────────────────────

var _eduDiseases = [];
var _eduDimensions = [];

function education() {
  return `
    <div class="card">
      <h2>衛教專欄</h2>
      <p style="margin-top:8px;color:var(--text-dim)">
        選擇您的疾病，我們會用最溫暖、最易懂的方式，幫您了解疾病管理的每個面向。
      </p>
    </div>
    <div class="card">
      <h3>選擇疾病</h3>
      <div id="edu-disease-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-top:12px">
        <p style="color:var(--text-muted)">載入中...</p>
      </div>
    </div>
    <div id="edu-dimensions-section" style="display:none">
      <div class="card">
        <h3 id="edu-disease-title"></h3>
        <p style="margin-top:4px;color:var(--text-dim)">選擇您想了解的面向</p>
        <div id="edu-dim-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px;margin-top:12px"></div>
      </div>
    </div>
    <div id="edu-content-section" style="display:none">
      <div class="card">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <button class="secondary" onclick="eduBackToDimensions()" style="padding:4px 12px;font-size:0.85rem">← 返回</button>
          <h3 id="edu-content-title" style="flex:1"></h3>
        </div>
        <div id="edu-content-body" style="margin-top:16px;line-height:1.8"></div>
      </div>
    </div>
    <div id="edu-research-section" style="display:none">
      <div class="card">
        <h3><i data-lucide="search" style="width:20px;height:20px;vertical-align:middle"></i> 深度研究模式</h3>
        <p style="margin-top:8px;color:var(--text-dim)">
          使用 STORM 引擎搜尋醫學文獻，自動產出含引用來源的深度研究報告。
        </p>
        <div style="margin-top:12px">
          <input id="storm-topic" placeholder="輸入研究主題，例如：第二型糖尿病自我管理策略" style="width:100%" />
          <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
            <button class="primary" onclick="runStormResearch()">
              <i data-lucide="zap" style="width:14px;height:14px;vertical-align:middle"></i> STORM 文獻研究
            </button>
            <button class="secondary" onclick="runCoStormResearch()">
              <i data-lucide="users" style="width:14px;height:14px;vertical-align:middle"></i> Co-STORM 協作研究
            </button>
            <button class="secondary" onclick="checkStormStatus()">
              <i data-lucide="info" style="width:14px;height:14px;vertical-align:middle"></i> 檢查狀態
            </button>
          </div>
        </div>
        <div id="storm-status" style="margin-top:8px"></div>
      </div>
      <div id="storm-result-section" style="display:none">
        <div class="card">
          <div style="display:flex;align-items:center;gap:8px">
            <h3 id="storm-result-title"></h3>
          </div>
          <div id="storm-sources" style="margin-top:8px"></div>
          <div id="storm-result-body" style="margin-top:16px;line-height:1.8"></div>
        </div>
      </div>
    </div>`;
}

var _eduSelectedDisease = null;

function loadEducationPage() {
  fetch(API + "/education/diseases")
    .then(function(r) { return r.json(); })
    .then(function(data) {
      _eduDiseases = data.diseases || [];
      renderDiseaseGrid();
    })
    .catch(function() { showToast("載入疾病列表失敗", "error"); });
}

function renderDiseaseGrid() {
  var el = document.getElementById("edu-disease-grid");
  if (!_eduDiseases.length) { el.innerHTML = "<p>尚無支援的疾病</p>"; return; }

  var byCategory = {};
  _eduDiseases.forEach(function(d) {
    if (!byCategory[d.category]) byCategory[d.category] = [];
    byCategory[d.category].push(d);
  });

  var html = "";
  var catIcons = {
    "代謝疾病": "activity", "心血管疾病": "heart-pulse", "呼吸系統疾病": "wind",
    "消化系統疾病": "utensils", "肌肉骨骼疾病": "bone", "腎臟疾病": "droplets",
    "神經退化疾病": "brain", "精神疾病": "smile", "腫瘤追蹤": "shield-check", "未分類": "file-question"
  };

  Object.keys(byCategory).forEach(function(cat) {
    html += '<div style="grid-column:1/-1;margin-top:8px"><strong style="color:var(--text-dim);font-size:0.85rem">' + cat + '</strong></div>';
    byCategory[cat].forEach(function(d) {
      var icon = catIcons[cat] || "file-text";
      html += '<button class="edu-disease-btn" onclick="selectEduDisease(\'' + d.icd10 + '\',\'' + d.name + '\')">' +
        '<i data-lucide="' + icon + '" style="width:16px;height:16px"></i> ' +
        '<span>' + d.name + '</span>' +
        '<small style="color:var(--text-muted)">' + d.icd10 + '</small>' +
        '</button>';
    });
  });
  el.innerHTML = html;
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function selectEduDisease(icd10, name) {
  _eduSelectedDisease = { icd10: icd10, name: name };
  document.getElementById("edu-disease-title").textContent = name + "（" + icd10 + "）— 六大衛教維度";
  document.getElementById("edu-dimensions-section").style.display = "block";
  document.getElementById("edu-content-section").style.display = "none";
  document.getElementById("edu-research-section").style.display = "block";
  document.getElementById("storm-topic").value = name + " 衛教研究";

  var dims = [
    { key: "disease_awareness", label: "疾病管理", desc: "了解疾病、治療與費用", icon: "clipboard-check", color: "var(--accent)" },
    { key: "symptom_recognition", label: "症狀辨認", desc: "學會辨別身體訊號", icon: "search-check", color: "var(--purple)" },
    { key: "medication_knowledge", label: "用藥知識", desc: "藥物不可怕，是好朋友", icon: "pill", color: "var(--rose)" },
    { key: "self_management", label: "自我管理", desc: "飲食、運動、生活調整", icon: "salad", color: "var(--success)" },
    { key: "emergency_response", label: "緊急應變", desc: "什麼時候該去看醫生", icon: "siren", color: "var(--warning)" },
    { key: "complication_awareness", label: "併發症認知", desc: "了解風險，更有信心", icon: "shield-alert", color: "var(--danger)" },
  ];

  var html = "";
  dims.forEach(function(d) {
    html += '<button class="edu-dim-btn" onclick="loadEduContent(\'' + d.key + '\',\'' + d.label + '\')" style="border-left:3px solid ' + d.color + '">' +
      '<div style="display:flex;align-items:center;gap:8px">' +
      '<i data-lucide="' + d.icon + '" style="width:20px;height:20px;color:' + d.color + '"></i>' +
      '<div><strong>' + d.label + '</strong><br><small style="color:var(--text-dim)">' + d.desc + '</small></div>' +
      '</div></button>';
  });
  document.getElementById("edu-dim-grid").innerHTML = html;
  if (typeof lucide !== 'undefined') lucide.createIcons();

  document.getElementById("edu-dimensions-section").scrollIntoView({ behavior: "smooth" });
}

function loadEduContent(dimension, label) {
  document.getElementById("edu-content-section").style.display = "block";
  document.getElementById("edu-content-title").textContent =
    _eduSelectedDisease.name + " — " + label;
  document.getElementById("edu-content-body").innerHTML =
    '<div style="text-align:center;padding:40px;color:var(--text-muted)">' +
    '<div class="loading-spinner"></div>' +
    '<p style="margin-top:12px">正在為您準備溫暖的衛教內容...</p></div>';

  document.getElementById("edu-content-section").scrollIntoView({ behavior: "smooth" });

  fetch(API + "/education/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ icd10_code: _eduSelectedDisease.icd10, dimension: dimension })
  })
    .then(function(r) {
      if (!r.ok) throw new Error("API error");
      return r.json();
    })
    .then(function(data) {
      document.getElementById("edu-content-body").innerHTML = markdownToHtml(data.content);
    })
    .catch(function() {
      document.getElementById("edu-content-body").innerHTML =
        '<p style="color:var(--danger)">內容生成失敗，請稍後再試。</p>';
    });
}

function eduBackToDimensions() {
  document.getElementById("edu-content-section").style.display = "none";
  document.getElementById("edu-dimensions-section").scrollIntoView({ behavior: "smooth" });
}

// ── STORM / Co-STORM 深度研究 ─────────────────────────────

function runStormResearch() {
  var topic = document.getElementById("storm-topic").value.trim();
  if (!topic) { showToast("請輸入研究主題", "warning"); return; }

  var resultSection = document.getElementById("storm-result-section");
  resultSection.style.display = "block";
  document.getElementById("storm-result-title").textContent = "STORM 研究：" + topic;
  document.getElementById("storm-sources").innerHTML = "";
  document.getElementById("storm-result-body").innerHTML =
    '<div style="text-align:center;padding:60px;color:var(--text-muted)">' +
    '<div class="loading-spinner"></div>' +
    '<p style="margin-top:16px">STORM 正在搜尋文獻並生成研究報告...</p>' +
    '<p style="font-size:0.85rem;margin-top:4px">這可能需要數分鐘，請耐心等待</p></div>';
  resultSection.scrollIntoView({ behavior: "smooth" });

  var body = { topic: topic };
  if (_eduSelectedDisease) body.icd10_code = _eduSelectedDisease.icd10;

  fetch(API + "/education/research/storm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })
    .then(function(r) {
      if (!r.ok) throw new Error("API error");
      return r.json();
    })
    .then(function(data) {
      document.getElementById("storm-result-body").innerHTML = markdownToHtml(data.report || "無內容");
      if (data.sources && data.sources.length > 0) {
        document.getElementById("storm-sources").innerHTML =
          '<details style="margin-bottom:8px"><summary style="cursor:pointer;color:var(--accent);font-size:0.9rem">' +
          '引用來源（' + data.source_count + ' 篇）</summary>' +
          '<ul style="margin-top:8px;font-size:0.85rem;color:var(--text-dim)">' +
          data.sources.map(function(s) { return '<li style="margin-bottom:4px;word-break:break-all">' + s + '</li>'; }).join("") +
          '</ul></details>';
      }
      if (typeof lucide !== 'undefined') lucide.createIcons();
    })
    .catch(function(e) {
      document.getElementById("storm-result-body").innerHTML =
        '<p style="color:var(--danger)">研究生成失敗：' + e.message + '</p>';
    });
}

function runCoStormResearch() {
  var topic = document.getElementById("storm-topic").value.trim();
  if (!topic) { showToast("請輸入研究主題", "warning"); return; }

  var doctorInput = prompt("請輸入醫師觀點或問題（可留空讓 AI 自主研究）：");
  var doctorInputs = doctorInput ? [doctorInput] : [];

  var resultSection = document.getElementById("storm-result-section");
  resultSection.style.display = "block";
  document.getElementById("storm-result-title").textContent = "Co-STORM 協作研究：" + topic;
  document.getElementById("storm-sources").innerHTML = "";
  document.getElementById("storm-result-body").innerHTML =
    '<div style="text-align:center;padding:60px;color:var(--text-muted)">' +
    '<div class="loading-spinner"></div>' +
    '<p style="margin-top:16px">Co-STORM 正在進行多方協作研究...</p>' +
    '<p style="font-size:0.85rem;margin-top:4px">AI 專家群正在討論，這需要較長時間</p></div>';
  resultSection.scrollIntoView({ behavior: "smooth" });

  fetch(API + "/education/research/costorm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic: topic, doctor_inputs: doctorInputs })
  })
    .then(function(r) {
      if (!r.ok) throw new Error("API error");
      return r.json();
    })
    .then(function(data) {
      var html = markdownToHtml(data.report || "無內容");
      if (data.conversation && data.conversation.length > 0) {
        html += '<hr style="margin:24px 0;border-color:var(--border-glass)">';
        html += '<h4 style="color:var(--purple)">研究討論過程</h4>';
        data.conversation.forEach(function(turn) {
          var roleColor = turn.role === "doctor" ? "var(--accent)" : "var(--text-dim)";
          html += '<div style="margin:8px 0;padding:8px 12px;border-left:3px solid ' + roleColor + ';background:var(--bg-glass);border-radius:4px">' +
            '<strong style="color:' + roleColor + '">' + turn.role + '</strong>: ' + turn.utterance + '</div>';
        });
      }
      document.getElementById("storm-result-body").innerHTML = html;
      if (typeof lucide !== 'undefined') lucide.createIcons();
    })
    .catch(function(e) {
      document.getElementById("storm-result-body").innerHTML =
        '<p style="color:var(--danger)">協作研究失敗：' + e.message + '</p>';
    });
}

function checkStormStatus() {
  fetch(API + "/education/research/status")
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var html = '<div style="padding:8px 12px;background:var(--bg-glass);border-radius:var(--radius-sm);font-size:0.85rem;margin-top:8px">';
      html += '<div>STORM 引擎：' + (data.storm_available ? '<span style="color:var(--success)">可用</span>' : '<span style="color:var(--danger)">未安裝</span>') + '</div>';
      html += '<div>搜尋引擎：<strong>' + data.search_engine + '</strong></div>';
      html += '<div>Anthropic API：' + (data.anthropic_key_set ? '<span style="color:var(--success)">已設定</span>' : '<span style="color:var(--danger)">未設定</span>') + '</div>';
      html += '</div>';
      document.getElementById("storm-status").innerHTML = html;
    })
    .catch(function() { showToast("無法檢查 STORM 狀態", "error"); });
}

function markdownToHtml(md) {
  if (!md) return "";
  return md
    .replace(/^### (.+)$/gm, '<h4 style="margin-top:16px;margin-bottom:8px;color:var(--accent)">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 style="margin-top:20px;margin-bottom:8px">$1</h3>')
    .replace(/^# (.+)$/gm, '<h2 style="margin-top:24px;margin-bottom:12px">$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^- (.+)$/gm, '<li style="margin-left:20px;margin-bottom:4px">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li style="margin-left:20px;margin-bottom:4px"><strong>$1.</strong> $2</li>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
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
    var [listRes, statsRes, lbRes] = await Promise.all([
      fetch(API + "/research/"),
      fetch(API + "/research/stats"),
      fetch(API + "/research/leaderboard?top_n=5"),
    ]);
    var data = await listRes.json();
    var stats = await statsRes.json();
    var lb = await lbRes.json();

    _allExperiments = data.experiments || [];

    // 統計卡片
    renderStatsCards(stats);

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

    // 排行榜
    renderLeaderboard(lb.leaderboard || []);

    // 顯示實驗列表
    renderExperimentList(_allExperiments);
  } catch (e) {
    var el = document.getElementById("experiment-list");
    if (el) el.innerHTML = '<p style="color:#d32f2f">無法載入，請確認後端是否啟動。</p>';
  }
}

function renderStatsCards(stats) {
  var el = document.getElementById("research-stats");
  if (!el) return;
  var cards = [
    { label: "總實驗數", value: stats.total || 0, color: "#1a73e8" },
    { label: "保留 (Kept)", value: stats.kept_count || 0, color: "#43a047" },
    { label: "還原 (Reverted)", value: stats.reverted_count || 0, color: "#ef5350" },
    { label: "改善率", value: stats.improvement_rate != null ? stats.improvement_rate + "%" : "N/A", color: "#ef6c00" },
    { label: "最佳 val_bpb", value: stats.best_bpb != null ? stats.best_bpb.toFixed(4) : "N/A", color: "#7b1fa2" },
    { label: "總訓練時間", value: stats.total_duration_hours + "h", color: "#00838f" },
  ];
  el.innerHTML = cards.map(function(c) {
    return '<div style="text-align:center;padding:12px;background:#f8f9fa;border-radius:8px;border-left:3px solid ' + c.color + '">' +
      '<div style="font-size:1.4rem;font-weight:700;color:' + c.color + '">' + c.value + '</div>' +
      '<div style="font-size:0.8rem;color:#666;margin-top:4px">' + c.label + '</div></div>';
  }).join("");
}

function renderLeaderboard(ranking) {
  var el = document.getElementById("leaderboard");
  if (!el) return;
  if (!ranking.length) {
    el.innerHTML = '<p style="color:#888">尚無排行資料</p>';
    return;
  }
  var medals = ["#FFD700", "#C0C0C0", "#CD7F32"];
  el.innerHTML = '<table style="width:100%;border-collapse:collapse;font-size:0.9rem">' +
    '<tr style="border-bottom:2px solid #e0e0e0"><th style="text-align:left;padding:6px">#</th><th style="text-align:left;padding:6px">名稱</th><th style="text-align:right;padding:6px">val_bpb</th><th style="text-align:right;padding:6px">loss</th><th style="text-align:right;padding:6px">耗時</th></tr>' +
    ranking.map(function(r) {
      var medal = r.rank <= 3 ? '<span style="color:' + medals[r.rank - 1] + ';font-weight:bold">' + r.rank + '</span>' : r.rank;
      var dur = r.duration_seconds ? Math.round(r.duration_seconds) + "s" : "-";
      return '<tr style="border-bottom:1px solid #f0f0f0">' +
        '<td style="padding:6px">' + medal + '</td>' +
        '<td style="padding:6px">' + r.name + '</td>' +
        '<td style="text-align:right;padding:6px;font-weight:600;color:#1a73e8">' + (r.val_bpb != null ? r.val_bpb.toFixed(4) : "-") + '</td>' +
        '<td style="text-align:right;padding:6px">' + (r.train_loss != null ? r.train_loss.toFixed(4) : "-") + '</td>' +
        '<td style="text-align:right;padding:6px;color:#666">' + dur + '</td></tr>';
    }).join("") + '</table>';
}

function filterExperiments() {
  var search = (document.getElementById("exp-search").value || "").toLowerCase();
  var keptFilter = document.getElementById("exp-filter-kept").value;
  var sortBy = document.getElementById("exp-sort").value;

  var filtered = _allExperiments.slice();

  if (search) {
    filtered = filtered.filter(function(e) {
      return (e.name || "").toLowerCase().indexOf(search) !== -1 ||
             (e.notes || "").toLowerCase().indexOf(search) !== -1;
    });
  }

  if (keptFilter === "true") {
    filtered = filtered.filter(function(e) { return e.kept === true; });
  } else if (keptFilter === "false") {
    filtered = filtered.filter(function(e) { return e.kept === false; });
  }

  if (sortBy === "val_bpb") {
    filtered.sort(function(a, b) { return (a.val_bpb || Infinity) - (b.val_bpb || Infinity); });
  } else if (sortBy === "train_loss") {
    filtered.sort(function(a, b) { return (a.train_loss || Infinity) - (b.train_loss || Infinity); });
  } else if (sortBy === "duration_seconds") {
    filtered.sort(function(a, b) { return (b.duration_seconds || 0) - (a.duration_seconds || 0); });
  }

  renderExperimentList(filtered);
}

function renderExperimentList(experiments) {
  var el = document.getElementById("experiment-list");
  if (!el) return;
  if (!experiments.length) {
    el.innerHTML = "<p>尚無實驗結果。請從 Colab 執行訓練後回傳，或匯入 results.tsv。</p>";
    return;
  }
  el.innerHTML = '<p style="color:#888;font-size:0.85rem;margin-bottom:8px">共 ' + experiments.length + ' 筆結果</p>' +
    experiments.map(function(e) {
      var metrics = [];
      if (e.val_bpb != null) metrics.push('<span style="font-weight:600;color:#1a73e8">bpb: ' + e.val_bpb.toFixed(4) + '</span>');
      if (e.train_loss != null) metrics.push("loss: " + e.train_loss.toFixed(4));
      if (e.steps != null) metrics.push(e.steps + " steps");
      if (e.duration_seconds != null) {
        var d = e.duration_seconds;
        metrics.push(d >= 3600 ? (d / 3600).toFixed(1) + "h" : d >= 60 ? Math.round(d / 60) + "m" : Math.round(d) + "s");
      }
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
        (e.notes ? '<p style="color:#666;font-size:0.9rem">' + e.notes + '</p>' : '') +
        (e.colab_url ? '<p><a href="' + e.colab_url + '" target="_blank">Colab 連結</a></p>' : '') +
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

  var vals = chartData.map(function(d) { return d.val_bpb; });
  var minV = Math.min.apply(null, vals);
  var maxV = Math.max.apply(null, vals);
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
  var bestIdx = vals.indexOf(Math.min.apply(null, vals));
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
    var cRect = canvas.getBoundingClientRect();
    var mx = evt.clientX - cRect.left;
    var tooltip = document.getElementById("chart-tooltip");
    if (!tooltip) return;
    var hit = -1;
    for (var t = 0; t < points.length; t++) {
      if (Math.abs(mx - points[t].x) < 15) { hit = t; break; }
    }
    if (hit >= 0) {
      var d = chartData[hit];
      var lines = [d.name];
      lines.push("val_bpb: " + d.val_bpb.toFixed(4));
      if (d.train_loss != null) lines.push("loss: " + d.train_loss.toFixed(4));
      if (d.steps) lines.push("steps: " + d.steps);
      if (d.duration_seconds) lines.push("duration: " + Math.round(d.duration_seconds) + "s");
      lines.push(d.kept ? "kept" : d.kept === false ? "reverted" : "");
      tooltip.textContent = lines.filter(Boolean).join("\n");
      tooltip.style.display = "block";
      tooltip.style.left = Math.min(points[hit].x + 10, W - 180) + "px";
      tooltip.style.top = (points[hit].y - 10) + "px";
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
    var res = await fetch(API + "/research/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    showToast("實驗已提交：" + name, "success");
    loadExperiments();
    ["exp-name", "exp-bpb", "exp-loss", "exp-steps", "exp-duration", "exp-notes", "exp-colab"].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.value = "";
    });
    document.getElementById("exp-kept").checked = false;
  } catch (e) {
    showToast("提交失敗：" + e.message, "error");
  }
}

async function uploadTsv(input) {
  if (!input.files.length) return;
  var formData = new FormData();
  formData.append("file", input.files[0]);
  try {
    var res = await fetch(API + "/research/batch", { method: "POST", body: formData });
    var data = await res.json();
    showToast("匯入成功：" + data.count + " 個實驗" + (data.errors ? "，" + data.errors + " 個失敗" : ""), data.errors ? "warning" : "success");
    loadExperiments();
  } catch (e) {
    showToast("匯入失敗：" + e.message, "error");
  }
  input.value = "";
}

async function exportExperiments() {
  try {
    var res = await fetch(API + "/research/export");
    var data = await res.json();
    if (!data.tsv) { showToast("無資料可匯出", "warning"); return; }
    var blob = new Blob([data.tsv], { type: "text/tab-separated-values" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "experiments_" + new Date().toISOString().slice(0, 10) + ".tsv";
    a.click();
    URL.revokeObjectURL(url);
    showToast("已匯出 " + data.count + " 筆實驗", "success");
  } catch (e) {
    showToast("匯出失敗：" + e.message, "error");
  }
}

async function deleteExperiment(id) {
  if (!confirm("確定刪除此實驗結果？")) return;
  try {
    await fetch(API + "/research/" + id, { method: "DELETE" });
    showToast("實驗已刪除", "success");
    loadExperiments();
  } catch (e) {
    showToast("刪除失敗", "error");
  }
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

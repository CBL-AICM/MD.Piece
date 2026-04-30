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

// 取得或建立一個穩定 UUID（避免 demo 模式下 patient_id 不是 UUID 導致後端寫入失敗）
function getStablePatientId() {
  var user = getCurrentUser();
  if (user && user.id) return user.id;
  var demoId = localStorage.getItem('mdpiece_demo_pid');
  if (!demoId) {
    demoId = (crypto && crypto.randomUUID) ? crypto.randomUUID()
      : 'demo-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
    localStorage.setItem('mdpiece_demo_pid', demoId);
  }
  return demoId;
}

// ─── 路由 ──────────────────────────────────────────────────

function showPage(page) {
  const app = document.getElementById("app");
  const D = window.DailyFeatures || {};
  const pages = {
    home, symptoms, doctors, patients, records, medications, research, education, contributors,
    daily: D.dailyPage, labs: D.labsPage, knowledge: D.knowledgePage,
  };
  // Page transition
  app.style.opacity = '0';
  app.style.transform = 'translateY(12px)';
  setTimeout(() => {
    app.innerHTML = pages[page]?.() || "";
    // 頁面載入後的初始化
    if (page === "home") loadHomePage();
    if (page === "doctors") loadDoctors();
    if (page === "patients") loadPatients();
    if (page === "records") loadRecordsPage();
    if (page === "research") loadExperiments();
    if (page === "contributors") loadContributors();
    if (page === "education") loadEducationPage();
    if (page === "medications") loadMedicationsPage();
    if (page === "daily" && D.initDaily) D.initDaily();
    if (page === "labs" && D.initLabs) D.initLabs();
    if (page === "knowledge" && D.initKnowledge) D.initKnowledge();
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

// ─── 註冊頁面（ID Card 風格，覆蓋在星空上）──────────────

let _selectedRole = 'patient'; // 此網站為患者專用
const _avatarColors = ['#5B9FE8','#9B80D4','#D08A8A','#55B88A','#D9A54A','#E87B5B','#7BC8E8'];
let _avatarIdx = 0;

function showIdCardRegister() {
  const overlay = document.getElementById('register-overlay');
  overlay.style.display = 'flex';
  // Set today's date
  const now = new Date();
  document.getElementById('idcard-date').textContent =
    `${now.getFullYear()}.${String(now.getMonth()+1).padStart(2,'0')}.${String(now.getDate()).padStart(2,'0')}`;
  // Random starting color
  _avatarIdx = Math.floor(Math.random() * _avatarColors.length);
  applyAvatarColor();
  // Animate in
  requestAnimationFrame(() => overlay.classList.add('show'));
  if (typeof lucide !== 'undefined') lucide.createIcons();
  document.getElementById('idcard-name').addEventListener('input', validateIdCard);
}

function cycleAvatarColor() {
  _avatarIdx = (_avatarIdx + 1) % _avatarColors.length;
  applyAvatarColor();
}

function applyAvatarColor() {
  const el = document.getElementById('idcard-avatar');
  if (el) {
    el.style.background = _avatarColors[_avatarIdx] + '22';
    el.style.borderColor = _avatarColors[_avatarIdx];
    el.querySelector('svg').style.color = _avatarColors[_avatarIdx];
  }
}

function selectIdRole(role) {
  _selectedRole = role;
  document.querySelectorAll('.idcard-role-btn').forEach(b => b.classList.remove('selected'));
  document.getElementById(`idrole-${role}`).classList.add('selected');
  validateIdCard();
}

function validateIdCard() {
  const name = document.getElementById('idcard-name')?.value.trim();
  const btn = document.getElementById('idcard-submit');
  if (btn) btn.disabled = !name;
}

async function submitIdCard() {
  const nickname = document.getElementById('idcard-name').value.trim();
  const id_number = document.getElementById('idcard-idno')?.value.trim().toUpperCase() || '';
  if (!nickname || !_selectedRole) return;

  const btn = document.getElementById('idcard-submit');
  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader"></i> 發卡中…';
  if (typeof lucide !== 'undefined') lucide.createIcons();

  const avatar_color = _avatarColors[_avatarIdx];

  try {
    const res = await fetch(`${API}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nickname, role: _selectedRole, avatar_color, id_number })
    });
    const user = await res.json();
    user.id_number = id_number;
    setCurrentUser(user);
  } catch {
    const user = { id: crypto.randomUUID(), nickname, role: _selectedRole, avatar_color, id_number };
    setCurrentUser(user);
  }

  // Card flip-out animation, then enter app
  const overlay = document.getElementById('register-overlay');
  overlay.classList.add('card-done');
  setTimeout(() => {
    overlay.style.display = 'none';
    overlay.classList.remove('show','card-done');
    document.getElementById('app-wrapper').classList.add('show');
    showPage('home');
    if (typeof lucide !== 'undefined') lucide.createIcons();
  }, 700);
}

// ─── 首頁 ──────────────────────────────────────────────────

function getGreetingMessage() {
  var msgs = [
    '每一小步，都是照顧自己的開始',
    '健康是一塊一塊拼起來的拼圖',
    '慢慢來，我們陪你一起',
    '今天也要好好照顧自己喔',
    '記錄每個碎片，拼出完整的你',
    '你不是一個人，我們一直都在',
  ];
  return msgs[Math.floor(Math.random() * msgs.length)];
}

function getHealthTip() {
  var tips = [
    '深呼吸三次，讓肩膀放鬆下來，你做得很好。',
    '喝一杯溫水，給身體最簡單的關愛。',
    '今天有按時吃藥嗎？每一次準時都是對自己的守護。',
    '散步十分鐘，陽光是最好的維他命。',
    '寫下今天的感受，情緒也是健康的一塊拼圖。',
    '睡前放下手機，讓大腦也好好休息。',
    '跟身邊的人說說話，連結也是一種療癒。',
    '不用完美，只要每天進步一點點就好。',
  ];
  return tips[Math.floor(Math.random() * tips.length)];
}

function homeCard(page, icon, title, desc, color) {
  return `<div class="pzl-card pzl-${color}" onclick="navigateTo('${page}',null)">
    <div class="pzl-tab"></div>
    <div class="pzl-icon"><i data-lucide="${icon}"></i></div>
    <h4>${title}</h4>
    <p>${desc}</p></div>`;
}

function home() {
  const user = getCurrentUser();
  const hour = new Date().getHours();
  const greeting = hour < 12 ? '早安' : hour < 18 ? '午安' : '晚安';
  const today = new Date();
  const dateStr = today.getFullYear() + '/' + String(today.getMonth()+1).padStart(2,'0') + '/' + String(today.getDate()).padStart(2,'0');
  const dayStr = '星期' + ['日','一','二','三','四','五','六'][today.getDay()];
  const name = user ? user.nickname : '你';
  const ac = (user && user.avatar_color) ? user.avatar_color : '#5B9FE8';

  return `
    <div class="home-page">
      <svg class="home-deco home-deco-1" viewBox="0 0 48 48"><path d="M12 0h24v12c-4 0-6 3-6 6s2 6 6 6v12h-12c0-4-3-6-6-6s-6 2-6 6H0V24c4 0 6-3 6-6s-2-6-6-6V0h12z" fill="currentColor"/></svg>
      <svg class="home-deco home-deco-2" viewBox="0 0 48 48"><path d="M12 0h24v12c-4 0-6 3-6 6s2 6 6 6v12h-12c0-4-3-6-6-6s-6 2-6 6H0V24c4 0 6-3 6-6s-2-6-6-6V0h12z" fill="currentColor"/></svg>
      <svg class="home-deco home-deco-3" viewBox="0 0 48 48"><path d="M12 0h24v12c-4 0-6 3-6 6s2 6 6 6v12h-12c0-4-3-6-6-6s-6 2-6 6H0V24c4 0 6-3 6-6s-2-6-6-6V0h12z" fill="currentColor"/></svg>

      <!-- Hero: Logo + Greeting split -->
      <div class="home-hero">
        <div class="home-hero-left">
          <img src="icons/logo-core.jpg" alt="MD.Piece" class="home-logo" />
        </div>
        <div class="home-hero-right">
          <h2 class="home-title">${greeting}，${name}</h2>
          <p class="home-calm">${getGreetingMessage()}</p>
          <div class="home-date-row">
            <span class="home-datestr">${dateStr}</span>
            <span class="home-day">${dayStr}</span>
          </div>
        </div>
      </div>

      <!-- Quick Actions — spread wider -->
      <div class="home-quick">
        <button class="hq-btn hq-symptoms" onclick="navigateTo('symptoms',null)">
          <span class="hq-icon"><i data-lucide="scan-search"></i></span>
          <span>記錄症狀</span>
        </button>
        <button class="hq-btn hq-meds" onclick="navigateTo('medications',null)">
          <span class="hq-icon"><i data-lucide="pill"></i></span>
          <span>服藥打卡</span>
        </button>
        <button class="hq-btn hq-records" onclick="navigateTo('records',null)">
          <span class="hq-icon"><i data-lucide="clipboard-list"></i></span>
          <span>查看病歷</span>
        </button>
        <button class="hq-btn hq-edu" onclick="navigateTo('education',null)">
          <span class="hq-icon"><i data-lucide="book-heart"></i></span>
          <span>衛教知識</span>
        </button>
      </div>

      <!-- Three-column info row -->
      <div class="home-info-row">
        <div class="home-ov">
          <div class="home-ov-head">
            <i data-lucide="calendar-check" style="width:16px;height:16px;color:var(--accent)"></i>
            <span>今日服藥</span>
          </div>
          <div id="home-med-summary" class="home-ov-body">
            <p class="home-ov-placeholder">載入中...</p>
          </div>
        </div>
        <div class="home-ov">
          <div class="home-ov-head">
            <i data-lucide="sparkles" style="width:16px;height:16px;color:var(--purple)"></i>
            <span>健康小語</span>
          </div>
          <div class="home-ov-body">
            <p class="home-tip-text">${getHealthTip()}</p>
          </div>
        </div>
        <div class="home-ov">
          <div class="home-ov-head">
            <i data-lucide="activity" style="width:16px;height:16px;color:var(--teal)"></i>
            <span>平台狀態</span>
          </div>
          <div class="home-ov-body">
            <p class="home-ov-status"><span class="status-dot"></span> 系統正常運行</p>
            <p class="home-ov-ver">v2.0 · PWA 醫療輔助平台</p>
          </div>
        </div>
      </div>

      <!-- Feature grid label -->
      <div class="home-section-label">
        <svg viewBox="0 0 48 48" width="16" height="16"><path d="M12 0h24v12c-4 0-6 3-6 6s2 6 6 6v12h-12c0-4-3-6-6-6s-6 2-6 6H0V24c4 0 6-3 6-6s-2-6-6-6V0h12z" fill="currentColor" opacity="0.5"/></svg>
        功能拼圖
      </div>
      <div class="home-grid">
        ${homeCard('symptoms','scan-search','症狀分析','AI 助你釐清身體訊號','blue')}
        ${homeCard('records','clipboard-list','病歷管理','守護每一次就診紀錄','purple')}
        ${homeCard('doctors','stethoscope','醫師列表','管理你的醫療團隊','rose')}
        ${homeCard('patients','users','病患管理','關懷每一位患者','mint')}
        ${homeCard('medications','pill','藥物管理','拍藥袋、記服藥、追療效','amber')}
        ${homeCard('education','book-heart','衛教專欄','溫暖易懂的健康知識','teal')}
        ${homeCard('research','flask-conical','自動研究','探索醫學前沿','gold')}
        ${homeCard('contributors','heart-handshake','貢獻者','共同打造的力量','lavender')}
      </div>

      <!-- Footer tagline -->
      <div class="home-footer">
        <svg viewBox="0 0 48 48" width="20" height="20"><path d="M12 0h24v12c-4 0-6 3-6 6s2 6 6 6v12h-12c0-4-3-6-6-6s-6 2-6 6H0V24c4 0 6-3 6-6s-2-6-6-6V0h12z" fill="currentColor" opacity="0.12"/></svg>
        <p>將日常碎片拼起，醫起走出治療的迷霧</p>
        <p class="home-footer-credit">CBL-AICM Lab · Piece by Piece</p>
      </div>
    </div>`;
}

function loadHomePage() {
  var user = getCurrentUser();
  var pid = getStablePatientId();

  fetch(API + '/medications/?patient_id=' + pid)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var el = document.getElementById('home-med-summary');
      if (!el) return;
      var meds = (data.medications || []).filter(function(m) { return m.active !== 0; });
      if (!meds.length) {
        el.innerHTML = '<p class="home-ov-empty">尚無藥物紀錄，從藥物管理開始記錄吧</p>';
        return;
      }
      el.innerHTML =
        '<div class="home-med-count">' + meds.length + '</div>' +
        '<div class="home-med-label">種藥物追蹤中</div>' +
        '<button class="home-med-go" onclick="navigateTo(\'medications\',null)">前往服藥 →</button>';
    })
    .catch(function() {
      var el = document.getElementById('home-med-summary');
      if (el) el.innerHTML = '<p class="home-ov-empty">開始記錄你的第一顆藥物吧</p>';
    });
}

// ─── 症狀分析 ──────────────────────────────────────────────

function symptoms() {
  return `
    <div class="card">
      <h2>AI 症狀分析</h2>
      <p style="margin-bottom:12px;color:var(--text-dim)">輸入您的症狀，AI 將提供初步分析建議</p>
      <input id="symptom-input" placeholder="輸入症狀（以逗號分隔），例如：fever, headache, cough" />
      <div style="display:flex;gap:8px;margin-top:8px">
        <button class="primary" onclick="analyzeSymptoms()">AI 分析</button>
        <button class="secondary" onclick="quickAdvice()">快速查詢</button>
      </div>
      <div id="analysis-result"></div>
    </div>
    <div class="card">
      <h3>快速查詢</h3>
      <p style="color:var(--text-dim);font-size:0.9rem">支援：fever、headache、chest pain、cough</p>
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
      ${d.phone ? `<span style="color:var(--text-dim)"> | ${d.phone}</span>` : ""}
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
  var colors = { success: "#00D4AA", error: "#D94D4D", info: "#2B5CE6", warning: "#E8A84B" };
  var toast = document.createElement("div");
  toast.style.cssText = "padding:12px 20px;border-radius:8px;color:white;font-size:0.9rem;box-shadow:0 4px 12px rgba(0,0,0,0.2);transition:opacity 0.3s;max-width:360px;background:" + (colors[type] || colors.info);
  toast.textContent = msg;
  existing.appendChild(toast);
  setTimeout(function() { toast.style.opacity = "0"; setTimeout(function() { toast.remove(); }, 300); }, 3000);
}

// ─── 藥物管理 ─────────────────────────────────────────────

var _medsList = [];
var _medsPatientId = null;

function medications() {
  var user = getCurrentUser();
  _medsPatientId = getStablePatientId();
  return `
    <div class="card">
      <h2>藥物管理</h2>
      <p style="margin-top:8px;color:var(--text-dim)">拍攝藥袋即可自動辨識藥物，記錄服藥、追蹤療效。</p>
    </div>
    <div class="card">
      <h3><i data-lucide="camera" style="width:18px;height:18px;vertical-align:middle"></i> 藥袋辨識</h3>
      <p style="margin-top:4px;color:var(--text-dim);font-size:0.9rem">拍攝或上傳藥袋照片，AI 自動辨識藥物資訊</p>
      <div style="margin-top:10px;padding:10px 12px;background:rgba(100,140,200,0.08);border-radius:var(--radius-sm);border:1px solid rgba(100,140,200,0.2);font-size:0.85rem;color:var(--text-dim)">
        <strong style="color:var(--text-main);font-size:0.85rem">拍攝小提示</strong>
        <ul style="margin:6px 0 0 16px;padding:0;line-height:1.6">
          <li>將藥袋平放在桌面，避免皺摺遮蓋文字</li>
          <li>在光線充足處拍攝，避免反光與陰影</li>
          <li>確保<strong>藥名、劑量、用法</strong>等文字完整入鏡</li>
          <li>一次拍一包藥袋，避免多包重疊</li>
        </ul>
      </div>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
        <button class="primary" onclick="document.getElementById('med-camera').click()">
          <i data-lucide="camera" style="width:14px;height:14px;vertical-align:middle"></i> 拍攝藥袋
        </button>
        <button class="secondary" onclick="document.getElementById('med-upload').click()">
          <i data-lucide="upload" style="width:14px;height:14px;vertical-align:middle"></i> 上傳照片
        </button>
        <button class="secondary" onclick="renderManualMedForm('','直接填寫藥物資訊，按「加入我的藥物」即可寫入。')">
          <i data-lucide="pencil" style="width:14px;height:14px;vertical-align:middle"></i> 手動輸入
        </button>
        <input type="file" id="med-camera" accept="image/*" capture="environment" style="display:none" onchange="handleMedPhoto(this)" />
        <input type="file" id="med-upload" accept="image/*" style="display:none" onchange="handleMedPhoto(this)" />
      </div>
      <div id="med-photo-preview" style="margin-top:12px"></div>
      <div id="med-recognize-result" style="margin-top:12px"></div>
    </div>
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <h3>我的藥物</h3>
        <button class="secondary" onclick="loadMedicationsPage()" style="padding:4px 12px;font-size:0.85rem">重新整理</button>
      </div>
      <div id="med-list" style="margin-top:12px"><p style="color:var(--text-muted)">載入中...</p></div>
    </div>
    <div class="card">
      <h3><i data-lucide="bar-chart-3" style="width:18px;height:18px;vertical-align:middle"></i> 服藥統計</h3>
      <div id="med-stats" style="margin-top:12px"><p style="color:var(--text-muted)">載入中...</p></div>
      <div id="med-chart" style="position:relative;height:200px;margin-top:16px">
        <canvas id="adherence-canvas" style="width:100%;height:100%"></canvas>
      </div>
    </div>
    <div class="card">
      <h3><i data-lucide="file-text" style="width:18px;height:18px;vertical-align:middle"></i> 回診報告</h3>
      <p style="margin-top:4px;color:var(--text-dim);font-size:0.9rem">產出藥物管理報告供下次回診使用</p>
      <div style="display:flex;gap:8px;margin-top:8px">
        <select id="report-days" style="padding:6px 10px;border-radius:var(--radius-sm);border:1px solid var(--border-glass)">
          <option value="7">最近 7 天</option>
          <option value="14">最近 14 天</option>
          <option value="30" selected>最近 30 天</option>
          <option value="90">最近 90 天</option>
        </select>
        <button class="primary" onclick="generateMedReport()">產出報告</button>
      </div>
      <div id="med-report" style="margin-top:12px"></div>
    </div>`;
}

function loadMedicationsPage() {
  fetch(API + "/medications/?patient_id=" + _medsPatientId)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      _medsList = (data.medications || []).filter(function(m) { return m.active !== 0; });
      renderMedList();
    })
    .catch(function() { showToast("載入藥物列表失敗", "error"); });

  fetch(API + "/medications/stats?patient_id=" + _medsPatientId + "&days=30")
    .then(function(r) { return r.json(); })
    .then(function(data) { renderMedStats(data); })
    .catch(function() {});
}

function renderMedList() {
  var el = document.getElementById("med-list");
  if (!_medsList.length) {
    el.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:20px">尚無藥物紀錄，拍攝藥袋開始記錄吧！</p>';
    return;
  }
  var html = '<div style="display:grid;gap:10px">';
  _medsList.forEach(function(med) {
    var catColor = med.category ? 'var(--accent)' : 'var(--text-muted)';
    html += '<div class="med-item">' +
      '<div style="display:flex;justify-content:space-between;align-items:start">' +
      '<div>' +
      '<strong>' + med.name + '</strong>' +
      (med.dosage ? ' <span style="color:var(--text-dim);font-size:0.85rem">' + med.dosage + '</span>' : '') +
      (med.category ? '<br><span class="med-tag" style="border-color:' + catColor + ';color:' + catColor + '">' + med.category + '</span>' : '') +
      (med.frequency ? '<br><span style="font-size:0.85rem;color:var(--text-dim)">' + med.frequency + '</span>' : '') +
      '</div>' +
      '<div style="display:flex;gap:4px">' +
      '<button class="med-action-btn med-take" onclick="logMedTaken(\'' + med.id + '\',true)" title="已服藥">✓</button>' +
      '<button class="med-action-btn med-skip" onclick="logMedTaken(\'' + med.id + '\',false)" title="跳過">✗</button>' +
      '<button class="med-action-btn med-effect" onclick="showEffectForm(\'' + med.id + '\',\'' + med.name + '\')" title="記錄療效">★</button>' +
      '</div></div></div>';
  });
  html += '</div>';
  el.innerHTML = html;
}

function handleMedPhoto(input) {
  if (!input.files || !input.files[0]) return;
  var file = input.files[0];
  var reader = new FileReader();
  reader.onload = function(e) {
    var base64Full = e.target.result;
    var mediaType = file.type || "image/jpeg";
    var base64Data = base64Full.split(",")[1];

    document.getElementById("med-photo-preview").innerHTML =
      '<img src="' + base64Full + '" style="max-width:100%;max-height:200px;border-radius:var(--radius-sm);border:1px solid var(--border-glass)" />';
    document.getElementById("med-recognize-result").innerHTML =
      '<div style="text-align:center;padding:16px;color:var(--text-muted)">' +
      '<div class="loading-spinner"></div><p style="margin-top:8px">AI 正在辨識藥袋...</p></div>';

    fetch(API + "/medications/recognize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ patient_id: _medsPatientId, image_base64: base64Data, media_type: mediaType })
    })
      .then(function(r) {
        return r.text().then(function(t) {
          var parsed; try { parsed = JSON.parse(t); } catch (e) { parsed = { detail: t }; }
          return { ok: r.ok, status: r.status, data: parsed };
        });
      })
      .then(function(res) {
        if (!res.ok) {
          var msg = (res.data && (res.data.detail || res.data.message)) || ("HTTP " + res.status);
          renderManualMedForm("", "辨識失敗：" + msg + "。你可以改用手動填寫下方資料。");
          return;
        }
        var data = res.data || {};
        var parsed = data.parsed || [];

        if (parsed.length > 0) {
          // 辨識成功 → 一律走可編輯確認卡片，讓患者檢視標準欄位後才寫入
          renderRecognizedEditable(parsed, [], data.raw_text || "", []);
          return;
        }

        // 完全辨識不到
        renderManualMedForm(data.raw_text || "", "無法辨識藥物，你可以直接手動填寫下方資料，按「加入我的藥物」即可寫入。");
      })
      .catch(function(err) {
        renderManualMedForm("", "辨識服務連線失敗（" + (err && err.message || "網路錯誤") + "），你可以改用手動填寫下方資料。");
      });
  };
  reader.readAsDataURL(file);
  input.value = "";
}

function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// 辨識成功但寫入失敗 / 部分失敗 → 提供逐筆可編輯卡片
function renderRecognizedEditable(parsed, errors, rawText, alreadySaved) {
  var errMap = {};
  (errors || []).forEach(function(e) { errMap[e.name] = e.error; });
  var savedNames = {};
  (alreadySaved || []).forEach(function(m) { savedNames[m.name] = true; });

  var inputStyle = "padding:6px;border-radius:4px;border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)";
  var rows = parsed.map(function(m, i) {
    var isSaved = savedNames[m.name];
    var errMsg = errMap[m.name];
    var bgTint = isSaved ? "rgba(85,184,138,0.08)" : (errMsg ? "rgba(220,80,80,0.08)" : "var(--bg-glass)");
    var borderTint = isSaved ? "var(--success)" : (errMsg ? "var(--danger)" : "var(--border-glass)");
    return (
      '<div class="rec-med-card" data-idx="' + i + '" style="padding:10px;background:' + bgTint + ';border:1px solid ' + borderTint + ';border-radius:var(--radius-sm);display:grid;gap:6px">' +
        (isSaved ? '<div style="color:var(--success);font-size:0.8rem">已寫入 ✓</div>' :
         errMsg ? '<div style="color:var(--danger);font-size:0.8rem">寫入失敗：' + escapeHtml(errMsg) + '</div>' : '') +
        '<input class="rec-name" type="text" value="' + escapeHtml(m.name) + '" placeholder="藥名 *（必填）" style="' + inputStyle + '" />' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">' +
          '<input class="rec-dosage" type="text" value="' + escapeHtml(m.dosage) + '" placeholder="劑量（例：500mg）" style="' + inputStyle + '" />' +
          '<input class="rec-frequency" type="text" value="' + escapeHtml(m.frequency) + '" placeholder="頻率（例：一天三次）" style="' + inputStyle + '" />' +
        '</div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">' +
          '<input class="rec-usage" type="text" value="' + escapeHtml(m.usage) + '" placeholder="用法（飯前/飯後/睡前）" style="' + inputStyle + '" />' +
          '<input class="rec-duration" type="text" value="' + escapeHtml(m.duration) + '" placeholder="療程（例：7 天）" style="' + inputStyle + '" />' +
        '</div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">' +
          '<input class="rec-category" type="text" value="' + escapeHtml(m.category) + '" placeholder="分類" style="' + inputStyle + '" />' +
          '<input class="rec-purpose" type="text" value="' + escapeHtml(m.purpose) + '" placeholder="用途" style="' + inputStyle + '" />' +
        '</div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">' +
          '<input class="rec-hospital" type="text" value="' + escapeHtml(m.hospital) + '" placeholder="醫院/診所" style="' + inputStyle + '" />' +
          '<input class="rec-prescribed-date" type="text" value="' + escapeHtml(m.prescribed_date) + '" placeholder="開立日期（YYYY-MM-DD）" style="' + inputStyle + '" />' +
        '</div>' +
        '<textarea class="rec-instructions" rows="2" placeholder="備註 / 注意事項" style="' + inputStyle + ';resize:vertical">' + escapeHtml(m.instructions) + '</textarea>' +
        (isSaved ? '' : '<button class="primary" onclick="submitRecognizedOne(this)" style="padding:6px 10px;font-size:0.85rem">加入這筆到我的藥物</button>') +
      '</div>'
    );
  }).join("");

  var header = errors && errors.length
    ? '<p style="color:var(--warning);margin:0 0 8px">辨識成功但部分寫入失敗，請確認內容後重新送出。</p>'
    : '<p style="color:var(--text-dim);margin:0 0 8px">已辨識出以下藥物，請確認內容後一鍵加入我的藥物。</p>';

  var html =
    '<div style="padding:12px;background:rgba(160,140,220,0.06);border-radius:var(--radius-sm);border:1px solid var(--border-glass)">' +
      header +
      (rawText ? '<details style="margin-bottom:8px"><summary style="font-size:0.85rem;color:var(--text-muted);cursor:pointer">原始辨識文字</summary><pre style="font-size:0.8rem;white-space:pre-wrap;margin-top:4px;max-height:120px;overflow:auto">' + escapeHtml(rawText) + '</pre></details>' : '') +
      '<div id="rec-med-cards" style="display:grid;gap:10px">' + rows + '</div>' +
      '<div style="display:flex;gap:8px;margin-top:12px">' +
        '<button class="primary" onclick="submitAllRecognized()">全部加入我的藥物</button>' +
        '<button class="secondary" onclick="document.getElementById(\'med-recognize-result\').innerHTML=\'\'">取消</button>' +
      '</div>' +
    '</div>';
  document.getElementById("med-recognize-result").innerHTML = html;
}

function _collectRecCard(card) {
  var val = function(sel) { var el = card.querySelector(sel); return el ? (el.value || "").trim() : ""; };
  // 資料庫目前只有 dosage/frequency/category/purpose/instructions 欄位，
  // 新增的 usage/duration/hospital/prescribed_date 先合併到 frequency / instructions
  // 以保留資訊又不用改 schema
  var frequency = val(".rec-frequency");
  var usage = val(".rec-usage");
  var freqCombined = [frequency, usage].filter(Boolean).join("・");

  var instructions = val(".rec-instructions");
  var duration = val(".rec-duration");
  var hospital = val(".rec-hospital");
  var pdate = val(".rec-prescribed-date");
  var extra = [];
  if (duration) extra.push("療程：" + duration);
  if (hospital) extra.push("醫院：" + hospital);
  if (pdate) extra.push("開立日期：" + pdate);
  var instCombined = [instructions, extra.join("；")].filter(Boolean).join("\n");

  return {
    patient_id: _medsPatientId,
    name: val(".rec-name"),
    dosage: val(".rec-dosage") || null,
    frequency: freqCombined || null,
    category: val(".rec-category") || null,
    purpose: val(".rec-purpose") || null,
    instructions: instCombined || null,
  };
}

function submitRecognizedOne(btn) {
  var card = btn.closest(".rec-med-card");
  var body = _collectRecCard(card);
  if (!body.name) { showToast("藥物名稱不能空白", "warning"); return; }
  btn.disabled = true; btn.textContent = "加入中...";
  fetch(API + "/medications/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })
    .then(function(r) {
      return r.text().then(function(t) {
        var p; try { p = JSON.parse(t); } catch (e) { p = { detail: t }; }
        return { ok: r.ok, status: r.status, data: p };
      });
    })
    .then(function(res) {
      if (!res.ok) {
        var msg = (res.data && (res.data.detail || res.data.message)) || ("HTTP " + res.status);
        showToast("加入失敗：" + msg, "error");
        btn.disabled = false; btn.textContent = "重試加入";
        return;
      }
      card.style.background = "rgba(85,184,138,0.08)";
      card.style.borderColor = "var(--success)";
      btn.outerHTML = '<div style="color:var(--success);font-size:0.85rem;text-align:center">已寫入 ✓</div>';
      showToast("已加入「" + body.name + "」", "success");
      loadMedicationsPage();
    })
    .catch(function(err) {
      showToast("加入失敗：" + (err && err.message || "網路錯誤"), "error");
      btn.disabled = false; btn.textContent = "重試加入";
    });
}

function submitAllRecognized() {
  var cards = document.querySelectorAll("#rec-med-cards .rec-med-card");
  var pending = [];
  cards.forEach(function(c) {
    var hasSaveBtn = c.querySelector("button.primary");
    if (hasSaveBtn) pending.push(c);
  });
  if (!pending.length) { showToast("沒有需要加入的項目", "info"); return; }
  var okCount = 0, failCount = 0, done = 0;
  pending.forEach(function(card) {
    var btn = card.querySelector("button.primary");
    var body = _collectRecCard(card);
    if (!body.name) { failCount++; done++; if (done === pending.length) _afterBulkAdd(okCount, failCount); return; }
    btn.disabled = true; btn.textContent = "加入中...";
    fetch(API + "/medications/", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }).catch(function() { return { ok: r.ok, data: {} }; }); })
      .then(function(res) {
        if (res.ok) {
          okCount++;
          card.style.background = "rgba(85,184,138,0.08)";
          card.style.borderColor = "var(--success)";
          btn.outerHTML = '<div style="color:var(--success);font-size:0.85rem;text-align:center">已寫入 ✓</div>';
        } else {
          failCount++;
          btn.disabled = false; btn.textContent = "重試加入";
        }
      })
      .catch(function() { failCount++; btn.disabled = false; btn.textContent = "重試加入"; })
      .finally(function() {
        done++;
        if (done === pending.length) _afterBulkAdd(okCount, failCount);
      });
  });
}

function _afterBulkAdd(ok, fail) {
  if (ok && !fail) showToast("已加入 " + ok + " 種藥物 ✓", "success");
  else if (ok && fail) showToast("加入 " + ok + " 成功、" + fail + " 失敗", "warning");
  else showToast("加入失敗，請檢查欄位", "error");
  if (ok) loadMedicationsPage();
}

function renderManualMedForm(rawText, hint) {
  var html =
    '<div style="padding:12px;background:rgba(230,180,80,0.08);border-radius:var(--radius-sm);border:1px solid var(--warning)">' +
      '<p style="color:var(--warning);margin:0 0 8px">' + escapeHtml(hint) + '</p>' +
      (rawText ? '<details style="margin-bottom:8px"><summary style="font-size:0.85rem;color:var(--text-muted);cursor:pointer">原始辨識文字（可複製參考）</summary><pre style="font-size:0.8rem;white-space:pre-wrap;margin-top:4px;max-height:120px;overflow:auto">' + escapeHtml(rawText) + '</pre></details>' : '') +
      '<div style="display:grid;gap:8px">' +
        '<label style="font-size:0.85rem;color:var(--text-dim)">藥名 <span style="color:var(--danger)">*</span>' +
          '<input id="manual-med-name" type="text" placeholder="例：Panadol 普拿疼" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">劑量' +
            '<input id="manual-med-dosage" type="text" placeholder="例：500mg / 1顆" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">頻率' +
            '<input id="manual-med-frequency" type="text" placeholder="例：一天三次" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
        '</div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">用法' +
            '<input id="manual-med-usage" type="text" placeholder="飯前 / 飯後 / 睡前" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">療程' +
            '<input id="manual-med-duration" type="text" placeholder="例：7 天 / 長期" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
        '</div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">分類' +
            '<input id="manual-med-category" type="text" placeholder="例：止痛藥" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">用途' +
            '<input id="manual-med-purpose" type="text" placeholder="例：緩解頭痛" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
        '</div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">醫院 / 診所' +
            '<input id="manual-med-hospital" type="text" placeholder="例：台大醫院" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
          '<label style="font-size:0.85rem;color:var(--text-dim)">開立日期' +
            '<input id="manual-med-prescribed-date" type="text" placeholder="YYYY-MM-DD" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text)" /></label>' +
        '</div>' +
        '<label style="font-size:0.85rem;color:var(--text-dim)">備註 / 注意事項' +
          '<textarea id="manual-med-instructions" rows="2" placeholder="例：避免與葡萄柚汁併用" style="width:100%;padding:8px;margin-top:4px;border-radius:var(--radius-sm);border:1px solid var(--border-glass);background:var(--bg-glass);color:var(--text);resize:vertical"></textarea></label>' +
      '</div>' +
      '<div style="display:flex;gap:8px;margin-top:12px">' +
        '<button class="primary" onclick="submitManualMed()">加入我的藥物</button>' +
        '<button class="secondary" onclick="document.getElementById(\'med-recognize-result\').innerHTML=\'\'">取消</button>' +
      '</div>' +
    '</div>';
  document.getElementById("med-recognize-result").innerHTML = html;
}

function submitManualMed() {
  var g = function(id) { var el = document.getElementById(id); return el ? (el.value || "").trim() : ""; };
  var name = g("manual-med-name");
  if (!name) { showToast("請至少填寫藥物名稱", "warning"); return; }

  var frequency = g("manual-med-frequency");
  var usage = g("manual-med-usage");
  var freqCombined = [frequency, usage].filter(Boolean).join("・");

  var instructions = g("manual-med-instructions");
  var duration = g("manual-med-duration");
  var hospital = g("manual-med-hospital");
  var pdate = g("manual-med-prescribed-date");
  var extra = [];
  if (duration) extra.push("療程：" + duration);
  if (hospital) extra.push("醫院：" + hospital);
  if (pdate) extra.push("開立日期：" + pdate);
  var instCombined = [instructions, extra.join("；")].filter(Boolean).join("\n");

  var body = {
    patient_id: _medsPatientId,
    name: name,
    dosage: g("manual-med-dosage") || null,
    frequency: freqCombined || null,
    category: g("manual-med-category") || null,
    purpose: g("manual-med-purpose") || null,
    instructions: instCombined || null,
  };
  fetch(API + "/medications/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })
    .then(function(r) {
      return r.text().then(function(t) {
        var parsed; try { parsed = JSON.parse(t); } catch (e) { parsed = { detail: t }; }
        return { ok: r.ok, status: r.status, data: parsed };
      });
    })
    .then(function(res) {
      if (!res.ok) {
        var msg = (res.data && (res.data.detail || res.data.message)) || ("HTTP " + res.status);
        showToast("加入失敗：" + msg, "error");
        var box = document.getElementById("med-recognize-result");
        box.insertAdjacentHTML("beforeend",
          '<p style="color:var(--danger);margin-top:8px;font-size:0.85rem">伺服器回應：' + msg + '</p>');
        return;
      }
      showToast("已加入藥物 ✓", "success");
      document.getElementById("med-recognize-result").innerHTML =
        '<p style="color:var(--success)">已成功加入「' + name + '」到我的藥物。</p>';
      document.getElementById("med-photo-preview").innerHTML = "";
      loadMedicationsPage();
    })
    .catch(function(err) { showToast("加入失敗：" + (err && err.message || "網路錯誤"), "error"); });
}

function logMedTaken(medId, taken) {
  var skipReason = "";
  if (!taken) {
    skipReason = prompt("為什麼跳過這次服藥？（可留空）") || "";
  }
  fetch(API + "/medications/log", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patient_id: _medsPatientId, medication_id: medId, taken: taken, skip_reason: skipReason })
  })
    .then(function(r) { return r.json(); })
    .then(function() { showToast(taken ? "已記錄服藥 ✓" : "已記錄跳過", taken ? "success" : "info"); })
    .catch(function() { showToast("記錄失敗", "error"); });
}

function showEffectForm(medId, medName) {
  var eff = prompt(medName + " 療效如何？（1=沒效果 ~ 5=非常有效）", "3");
  if (!eff) return;
  var effNum = parseInt(eff);
  if (effNum < 1 || effNum > 5 || isNaN(effNum)) { showToast("請輸入 1-5 的數字", "warning"); return; }
  var sideEffects = prompt("有任何副作用嗎？（沒有就留空）") || "";
  var changes = prompt("症狀有什麼改善？（沒有就留空）") || "";

  fetch(API + "/medications/effects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      patient_id: _medsPatientId, medication_id: medId,
      effectiveness: effNum, side_effects: sideEffects, symptom_changes: changes
    })
  })
    .then(function(r) { return r.json(); })
    .then(function() { showToast("療效紀錄已儲存", "success"); })
    .catch(function() { showToast("紀錄失敗", "error"); });
}

function renderMedStats(data) {
  var el = document.getElementById("med-stats");
  var s = data.summary;
  el.innerHTML =
    '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px">' +
    '<div class="stat-box"><div class="stat-num">' + s.total_medications + '</div><div class="stat-label">藥物種類</div></div>' +
    '<div class="stat-box"><div class="stat-num">' + s.adherence_rate + '%</div><div class="stat-label">服藥率</div></div>' +
    '<div class="stat-box"><div class="stat-num">' + s.total_logs + '</div><div class="stat-label">服藥紀錄</div></div>' +
    '<div class="stat-box"><div class="stat-num">' + s.days + '天</div><div class="stat-label">統計期間</div></div>' +
    '</div>';

  // 畫服藥率折線圖
  if (data.adherence_trend && data.adherence_trend.length > 1) {
    drawAdherenceChart(data.adherence_trend);
  }
}

function drawAdherenceChart(trend) {
  var canvas = document.getElementById("adherence-canvas");
  if (!canvas) return;
  var ctx = canvas.getContext("2d");
  var rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * 2;
  canvas.height = rect.height * 2;
  ctx.scale(2, 2);
  var w = rect.width, h = rect.height;
  var pad = { top: 20, right: 10, bottom: 30, left: 40 };
  var cw = w - pad.left - pad.right;
  var ch = h - pad.top - pad.bottom;

  ctx.clearRect(0, 0, w, h);

  // 背景格線
  ctx.strokeStyle = "rgba(255,255,255,0.08)";
  ctx.lineWidth = 0.5;
  for (var i = 0; i <= 4; i++) {
    var y = pad.top + (ch / 4) * i;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + cw, y); ctx.stroke();
  }

  // Y 軸標籤
  ctx.fillStyle = "#6E6860";
  ctx.font = "10px 'Noto Sans TC'";
  ctx.textAlign = "right";
  for (var i = 0; i <= 4; i++) {
    ctx.fillText((100 - i * 25) + "%", pad.left - 4, pad.top + (ch / 4) * i + 4);
  }

  // 折線
  ctx.beginPath();
  ctx.strokeStyle = "#00D4AA";
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  trend.forEach(function(d, idx) {
    var x = pad.left + (cw / (trend.length - 1)) * idx;
    var y = pad.top + ch - (d.rate / 100 * ch);
    if (idx === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // 資料點
  trend.forEach(function(d, idx) {
    var x = pad.left + (cw / (trend.length - 1)) * idx;
    var y = pad.top + ch - (d.rate / 100 * ch);
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fillStyle = d.rate >= 80 ? "var(--success)" : d.rate >= 50 ? "var(--warning)" : "var(--danger)";
    ctx.fill();
  });

  // X 軸日期
  ctx.fillStyle = "#6E6860";
  ctx.font = "9px 'Noto Sans TC'";
  ctx.textAlign = "center";
  var step = Math.max(1, Math.floor(trend.length / 6));
  trend.forEach(function(d, idx) {
    if (idx % step === 0 || idx === trend.length - 1) {
      var x = pad.left + (cw / (trend.length - 1)) * idx;
      ctx.fillText(d.date.slice(5), x, h - 4);
    }
  });
}

function generateMedReport() {
  var days = document.getElementById("report-days").value;
  document.getElementById("med-report").innerHTML =
    '<div style="text-align:center;padding:30px;color:var(--text-muted)">' +
    '<div class="loading-spinner"></div><p style="margin-top:8px">正在產出回診報告...</p></div>';

  fetch(API + "/medications/report?patient_id=" + _medsPatientId + "&days=" + days)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      document.getElementById("med-report").innerHTML =
        '<div style="padding:16px;background:var(--bg-glass);border-radius:var(--radius-sm);border:1px solid var(--border-glass)">' +
        markdownToHtml(data.report) + '</div>';
    })
    .catch(function() {
      document.getElementById("med-report").innerHTML =
        '<p style="color:var(--danger)">報告生成失敗，請稍後再試。</p>';
    });
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
      <p style="margin-top:8px;color:var(--text-dim)">
        基於 <a href="https://github.com/karpathy/autoresearch" target="_blank" style="color:var(--accent)">karpathy/autoresearch</a> —
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
      <h3 style="cursor:pointer" onclick="toggleSubmitForm()">手動提交實驗結果 <span id="submit-toggle" style="font-size:0.8rem;color:var(--text-muted)">展開</span></h3>
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
    if (el) el.innerHTML = '<p style="color:var(--danger)">無法載入，請確認後端是否啟動。</p>';
  }
}

function renderStatsCards(stats) {
  var el = document.getElementById("research-stats");
  if (!el) return;
  var cards = [
    { label: "總實驗數", value: stats.total || 0, color: "var(--accent)" },
    { label: "保留 (Kept)", value: stats.kept_count || 0, color: "var(--success)" },
    { label: "還原 (Reverted)", value: stats.reverted_count || 0, color: "var(--danger)" },
    { label: "改善率", value: stats.improvement_rate != null ? stats.improvement_rate + "%" : "N/A", color: "var(--warning)" },
    { label: "最佳 val_bpb", value: stats.best_bpb != null ? stats.best_bpb.toFixed(4) : "N/A", color: "var(--purple)" },
    { label: "總訓練時間", value: stats.total_duration_hours + "h", color: "var(--teal)" },
  ];
  el.innerHTML = cards.map(function(c) {
    return '<div style="text-align:center;padding:12px;background:var(--bg-surface);border-radius:8px;border-left:3px solid ' + c.color + ';border:1px solid var(--border-glass)">' +
      '<div style="font-size:1.4rem;font-weight:700;color:' + c.color + '">' + c.value + '</div>' +
      '<div style="font-size:0.8rem;color:var(--text-muted);margin-top:4px">' + c.label + '</div></div>';
  }).join("");
}

function renderLeaderboard(ranking) {
  var el = document.getElementById("leaderboard");
  if (!el) return;
  if (!ranking.length) {
    el.innerHTML = '<p style="color:var(--text-muted)">尚無排行資料</p>';
    return;
  }
  var medals = ["#FFD700", "#C0C0C0", "#CD7F32"];
  el.innerHTML = '<table style="width:100%;border-collapse:collapse;font-size:0.9rem">' +
    '<tr style="border-bottom:2px solid var(--border-glass)"><th style="text-align:left;padding:6px;color:var(--text)">#</th><th style="text-align:left;padding:6px;color:var(--text)">名稱</th><th style="text-align:right;padding:6px;color:var(--text)">val_bpb</th><th style="text-align:right;padding:6px;color:var(--text)">loss</th><th style="text-align:right;padding:6px;color:var(--text)">耗時</th></tr>' +
    ranking.map(function(r) {
      var medal = r.rank <= 3 ? '<span style="color:' + medals[r.rank - 1] + ';font-weight:bold">' + r.rank + '</span>' : r.rank;
      var dur = r.duration_seconds ? Math.round(r.duration_seconds) + "s" : "-";
      return '<tr style="border-bottom:1px solid var(--border-glass)">' +
        '<td style="padding:6px;color:var(--text)">' + medal + '</td>' +
        '<td style="padding:6px;color:var(--text)">' + r.name + '</td>' +
        '<td style="text-align:right;padding:6px;font-weight:600;color:var(--accent)">' + (r.val_bpb != null ? r.val_bpb.toFixed(4) : "-") + '</td>' +
        '<td style="text-align:right;padding:6px;color:var(--text-dim)">' + (r.train_loss != null ? r.train_loss.toFixed(4) : "-") + '</td>' +
        '<td style="text-align:right;padding:6px;color:var(--text-muted)">' + dur + '</td></tr>';
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
  el.innerHTML = '<p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:8px">共 ' + experiments.length + ' 筆結果</p>' +
    experiments.map(function(e) {
      var metrics = [];
      if (e.val_bpb != null) metrics.push('<span style="font-weight:600;color:var(--accent)">bpb: ' + e.val_bpb.toFixed(4) + '</span>');
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
        (e.notes ? '<p style="color:var(--text-dim);font-size:0.9rem">' + e.notes + '</p>' : '') +
        (e.colab_url ? '<p><a href="' + e.colab_url + '" target="_blank">Colab 連結</a></p>' : '') +
        '</div>';
    }).join("");
}

function renderBpbChart(chartData) {
  _researchChartData = chartData;
  var canvas = document.getElementById("bpb-canvas");
  if (!canvas || !chartData.length) {
    var chartDiv = document.getElementById("bpb-chart");
    if (chartDiv) chartDiv.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:40px 0">尚無 val_bpb 數據</p>';
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
  gradient.addColorStop(0, "rgba(43, 92, 230, 0.08)");
  gradient.addColorStop(1, "rgba(43, 92, 230, 0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(pad.left, pad.top, plotW, plotH);

  // Y axis grid
  ctx.strokeStyle = "rgba(255,255,255,0.1)";
  ctx.fillStyle = "#B0A89E";
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
  areaGrad.addColorStop(0, "rgba(43, 92, 230, 0.2)");
  areaGrad.addColorStop(1, "rgba(43, 92, 230, 0.02)");
  ctx.fillStyle = areaGrad;
  ctx.fill();

  // Plot line
  ctx.strokeStyle = "#2B5CE6";
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
    ctx.fillStyle = chartData[k].kept ? "#00D4AA" : chartData[k].kept === false ? "#D94D4D" : "#6E6860";
    ctx.fill();
    ctx.strokeStyle = "#132036";
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // X label
  ctx.fillStyle = "#B0A89E";
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
    el.innerHTML = '<div class="advice-box" style="margin-top:8px;color:var(--danger)">無法檢查 GPU 狀態</div>';
  }
}

// ─── 貢獻者 ───────────────────────────────────────────────

function contributors() {
  return `
    <div class="card">
      <h2>GitHub 貢獻者</h2>
      <p style="margin-top:8px;color:var(--text-dim)">感謝所有為 MD.Piece 貢獻的開發者</p>
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
    list.innerHTML = '<p style="color:var(--danger)">' + e.message + '</p>';
  }
}

// ─── Service Worker ───────────────────────────────────────

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}

showPage("home");

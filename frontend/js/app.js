const API = "http://localhost:8000";
const GITHUB_REPO = "human530/MD.Piece";

function showPage(page) {
  const app = document.getElementById("app");
  const pages = { home, symptoms, doctors, patients, contributors };
  app.innerHTML = pages[page]?.() || "";
  if (page === "contributors") loadContributors();
}

function home() {
  return `
    <div class="card">
      <h2>歡迎使用 MD.Piece</h2>
      <p style="margin-top:8px">本平台提供醫病溝通與症狀建議服務</p>
    </div>
    <div class="card">
      <h3>快速功能</h3>
      <p>• 症狀查詢 - 輸入症狀獲得初步建議</p>
      <p>• 醫師列表 - 查看可諮詢醫師</p>
      <p>• 病患管理 - 管理病患資料</p>
    </div>`;
}

function symptoms() {
  return `
    <div class="card">
      <h2>症狀查詢</h2>
      <input id="symptom-input" placeholder="輸入症狀（英文），例如：fever, headache" />
      <button class="primary" onclick="checkSymptom()">查詢建議</button>
      <div id="advice-result"></div>
    </div>`;
}

async function checkSymptom() {
  const s = document.getElementById("symptom-input").value;
  const res = await fetch(`${API}/symptoms/advice?symptom=${s}`);
  const data = await res.json();
  document.getElementById("advice-result").innerHTML =
    `<div class="advice-box"><strong>${data.symptom}</strong>：${data.advice}</div>`;
}

function doctors() {
  return `<div class="card"><h2>醫師列表</h2><p>尚無資料</p></div>`;
}

function patients() {
  return `
    <div class="card">
      <h2>新增病患</h2>
      <input id="p-name" placeholder="姓名" />
      <input id="p-age" type="number" placeholder="年齡" />
      <button class="primary" onclick="addPatient()">新增</button>
      <div id="patient-result"></div>
    </div>`;
}

async function addPatient() {
  const name = document.getElementById("p-name").value;
  const age = document.getElementById("p-age").value;
  const res = await fetch(`${API}/patients/?name=${name}&age=${age}`, { method: "POST" });
  const data = await res.json();
  document.getElementById("patient-result").innerHTML =
    `<div class="advice-box">已新增：${data.name}，${data.age}歲</div>`;
}

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
    const res = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/contributors`);
    if (!res.ok) throw new Error("無法取得貢獻者資料");
    const data = await res.json();
    list.innerHTML = data.map(c => `
      <div class="contributor-card">
        <img src="${c.avatar_url}" alt="${c.login}" class="contributor-avatar" />
        <div class="contributor-info">
          <a href="${c.html_url}" target="_blank" rel="noopener noreferrer" class="contributor-name">${c.login}</a>
          <span class="contributor-commits">${c.contributions} 次提交</span>
        </div>
      </div>`).join("");
  } catch (e) {
    list.innerHTML = `<p style="color:#d32f2f">${e.message}</p>`;
  }
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}

showPage("home");

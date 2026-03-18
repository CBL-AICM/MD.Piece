const API = "http://localhost:8000";

function showPage(page) {
  const app = document.getElementById("app");
  const pages = { home, symptoms, doctors, patients };
  app.innerHTML = pages[page]?.() || "";
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

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}

showPage("home");

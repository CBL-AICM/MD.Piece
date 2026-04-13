const API = "http://localhost:8000";

document.getElementById("api-url").textContent = API;

(async function pingBackend() {
  const el = document.getElementById("status");
  try {
    const res = await fetch(`${API}/doctors/`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    el.textContent = `✓ 後端連線正常（目前醫師數：${data.doctors?.length ?? 0}）`;
    el.classList.add("ok");
  } catch (err) {
    el.textContent = `✗ 無法連線到 ${API}：${err.message}`;
    el.classList.add("err");
  }
})();

document.querySelectorAll(".nav-item").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
  });
});

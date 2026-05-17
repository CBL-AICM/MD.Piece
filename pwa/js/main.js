// App bootstrap + tab routing + service worker registration.

const tabs = document.querySelectorAll('nav.tabs button');
const sections = document.querySelectorAll('section.tab');

function showTab(name) {
  tabs.forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  sections.forEach(s => s.classList.toggle('hidden', s.id !== 'tab-' + name));
}
tabs.forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('service-worker.js').catch(() => { /* ignore offline */ });
}

(async function bootstrap() {
  // try cache first for instant load offline, then fetch fresh in background
  const cached = await MDP.loadCached();
  if (cached) renderAll();
  try {
    await MDP.load();
    renderAll();
  } catch (e) {
    if (!cached) {
      document.getElementById('loader').innerHTML =
        '<p>無法載入 cohort.json — 請先在 repo 根目錄執行 <code>python main.py</code> 產出資料。</p>';
      return;
    }
  }
  document.getElementById('loader').classList.add('hidden');
  document.getElementById('tab-dashboard').classList.remove('hidden');
})();

function renderAll() {
  Dashboard.render();
  PatientBrowser.render();
  WhatIf.init();
  Training.init();
  Experiment.init();
  NOf1.init();
}

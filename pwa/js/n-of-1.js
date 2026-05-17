// N-of-1 mode — match user profile to similar virtual patients, show distribution + CI.

window.NOf1 = {
  chart: null,
  init() {
    const dSel = document.getElementById('n-disease');
    dSel.innerHTML = Object.keys(MDP.cohort.diseases)
      .map(d => `<option>${d}</option>`).join('');
    document.getElementById('n-run').addEventListener('click', () => this._run());
  },

  _run() {
    const d   = document.getElementById('n-disease').value;
    const age = parseInt(document.getElementById('n-age').value, 10);
    const sex = document.getElementById('n-sex').value;
    const act = parseFloat(document.getElementById('n-activity').value);

    const pool = MDP.cohort.diseases[d].patients;
    const scored = pool.map(p => {
      const meanA = meanActivity(p);
      const score =
        Math.abs(p.age - age) * 0.05 +
        (p.sex === sex ? 0 : 0.5) +
        Math.abs(meanA - act) * 1.0;
      return { p, score, meanA };
    }).sort((a, b) => a.score - b.score).slice(0, 25);

    const futureAct = scored.map(s => s.meanA);
    const ci = bootstrapCI(futureAct);
    const recResp = countBy(scored.map(s => s.p.responder_class));
    const recSubtype = countBy(scored.map(s => s.p.subtype));

    // visualize: distribution + CI band
    if (this.chart) this.chart.destroy();
    const bins = histogram(futureAct, 8);
    this.chart = new Chart(document.getElementById('nof1-chart'), {
      type: 'bar',
      data: {
        labels: bins.labels,
        datasets: [{
          label: 'similar virtual patients — mean activity',
          data: bins.counts,
          backgroundColor: '#58a6ff',
        }],
      },
      options: { ...chartOpts(),
        plugins: { ...chartOpts().plugins,
          title: { display: true, text: `95% CI: [${ci[0].toFixed(2)}, ${ci[1].toFixed(2)}]`,
                   color: '#e6edf3' }}},
    });

    document.getElementById('nof1-summary').innerHTML = `
      <table>
      <tr><td><strong>找到 ${scored.length} 位相似虛擬患者</strong></td></tr>
      <tr><td>平均活動度</td><td>${mean(futureAct).toFixed(2)}</td></tr>
      <tr><td>95% 信賴區間</td><td>[${ci[0].toFixed(2)}, ${ci[1].toFixed(2)}]</td></tr>
      <tr><td>反應者分群</td><td>${formatCount(recResp)}</td></tr>
      <tr><td>常見 subtype</td><td>${formatCount(recSubtype)}</td></tr>
      </table>
      <div class="muted" style="margin-top:10px">
        ⚠️ 此為合成資料推論，不構成醫療建議。建議區間僅供 N-of-1 假設生成。
      </div>`;
  },
};

function meanActivity(p) {
  const a = p.timeseries.map(r => r.activity);
  return a.reduce((s,x)=>s+x,0) / Math.max(a.length, 1);
}
function mean(arr) { return arr.reduce((s,x)=>s+x,0) / Math.max(arr.length, 1); }
function bootstrapCI(arr, n = 500) {
  if (arr.length < 5) return [Math.min(...arr), Math.max(...arr)];
  const means = [];
  for (let i = 0; i < n; i++) {
    let s = 0;
    for (let j = 0; j < arr.length; j++) s += arr[Math.floor(Math.random() * arr.length)];
    means.push(s / arr.length);
  }
  means.sort((a,b) => a - b);
  return [means[Math.floor(n * 0.025)], means[Math.floor(n * 0.975)]];
}
function histogram(arr, nbins) {
  const lo = Math.min(...arr), hi = Math.max(...arr);
  const w = (hi - lo) / nbins || 1;
  const counts = Array(nbins).fill(0);
  arr.forEach(v => {
    const idx = Math.min(nbins - 1, Math.floor((v - lo) / w));
    counts[idx]++;
  });
  const labels = counts.map((_, i) => (lo + i * w).toFixed(2));
  return { labels, counts };
}
function countBy(arr) {
  const c = {};
  arr.forEach(x => c[x] = (c[x] || 0) + 1);
  return c;
}
function formatCount(c) {
  return Object.entries(c).sort((a,b) => b[1] - a[1])
    .map(([k,v]) => `${k} (${v})`).join(', ') || '—';
}

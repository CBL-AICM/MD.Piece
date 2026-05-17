// Experiment mode — virtual trial: cohort-wide reaction to a chosen treatment.

window.Experiment = {
  chart: null,
  init() {
    const dSel = document.getElementById('e-disease');
    dSel.innerHTML = Object.keys(MDP.cohort.diseases)
      .map(d => `<option>${d}</option>`).join('');
    dSel.addEventListener('change', () => this._refreshTreatments());
    this._refreshTreatments();
    document.getElementById('e-run').addEventListener('click', () => this._run());
  },

  _refreshTreatments() {
    const d = document.getElementById('e-disease').value;
    // pick treatment names from sample patient
    const patients = MDP.cohort.diseases[d].patients;
    const tx = new Set();
    patients.forEach(p => p.treatments.forEach(t => tx.add(t.id)));
    const sel = document.getElementById('e-treatment');
    sel.innerHTML = [...tx].map(t => `<option>${t}</option>`).join('');
  },

  _run() {
    const d = document.getElementById('e-disease').value;
    const tx = document.getElementById('e-treatment').value;
    const ps = MDP.cohort.diseases[d].patients;
    const on  = ps.filter(p => p.treatments.some(t => t.id === tx));
    const off = ps.filter(p => !p.treatments.some(t => t.id === tx));

    const byClass = { super:[], typical:[], partial:[], non_responder:[] };
    on.forEach(p => byClass[p.responder_class].push(meanActivity(p)));

    if (this.chart) this.chart.destroy();
    this.chart = new Chart(document.getElementById('experiment-chart'), {
      type: 'bar',
      data: {
        labels: ['super','typical','partial','non_responder'],
        datasets: [{
          label: `on ${tx} (mean activity)`,
          data: ['super','typical','partial','non_responder']
                  .map(c => mean(byClass[c] || [])),
          backgroundColor: ['#7ee787','#58a6ff','#f0c674','#ff7b72'],
        }],
      },
      options: chartOpts(),
    });

    const dist = ['super','typical','partial','non_responder'].map(c => ({
      cls: c, n: byClass[c].length,
      mean: mean(byClass[c] || []).toFixed(2),
    }));
    document.getElementById('experiment-summary').innerHTML = `
      <table><tr><th>Class</th><th>N</th><th>Mean activity</th></tr>
      ${dist.map(r => `<tr><td>${r.cls}</td><td>${r.n}</td><td>${r.mean}</td></tr>`).join('')}
      </table>
      <div class="muted" style="margin-top:8px">
        on ${tx}: n=${on.length} (mean ${mean(on.map(meanActivity)).toFixed(2)}) ·
        off ${tx}: n=${off.length} (mean ${mean(off.map(meanActivity)).toFixed(2)})
      </div>`;
  },
};

function meanActivity(p) {
  const a = p.timeseries.map(r => r.activity);
  return a.reduce((s,x)=>s+x,0) / Math.max(a.length, 1);
}
function mean(arr) {
  if (!arr.length) return 0;
  return arr.reduce((s,x)=>s+x,0) / arr.length;
}

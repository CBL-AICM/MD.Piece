// Dashboard tab — KPIs + 4 summary charts.

window.Dashboard = {
  charts: {},
  render() {
    const ps = MDP.flatPatients;
    document.getElementById('kpi-n').textContent = ps.length;
    document.getElementById('kpi-d').textContent = Object.keys(MDP.cohort.diseases).length;
    const elderly = ps.filter(p => p.is_elderly).length;
    document.getElementById('kpi-elderly').textContent =
      ((elderly / ps.length) * 100).toFixed(1) + '%';

    // unpredictability: coefficient of variation of mean activity within same disease + same treatment
    const groups = {};
    ps.forEach(p => {
      const tx = (p.treatments[0] && p.treatments[0].id) || 'none';
      const key = p.disease_id + '|' + tx;
      (groups[key] ||= []).push(meanActivity(p));
    });
    const cvs = Object.values(groups)
      .filter(arr => arr.length >= 5)
      .map(arr => stdev(arr) / (mean(arr) || 1));
    document.getElementById('kpi-cv').textContent =
      cvs.length ? mean(cvs).toFixed(2) : '—';

    this._renderDiseaseChart();
    this._renderAgePyramid();
    this._renderResponderChart();
    this._renderSexAgeChart();
  },

  _renderDiseaseChart() {
    const ctx = document.getElementById('chart-disease');
    const labels = Object.keys(MDP.cohort.diseases);
    const data = labels.map(d => MDP.cohort.diseases[d].patients.length);
    destroyAndReplace(this, 'disease', new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{ data, backgroundColor: ['#58a6ff','#7ee787','#f0c674','#ff7b72'] }],
      },
      options: chartOpts(),
    }));
  },

  _renderAgePyramid() {
    const ctx = document.getElementById('chart-age');
    const bins = ['20-35','35-55','55-70','70-90'];
    const female = bins.map(b =>
      MDP.flatPatients.filter(p => p.age_bin === b && p.sex === 'F').length);
    const male = bins.map(b =>
      -MDP.flatPatients.filter(p => p.age_bin === b && p.sex === 'M').length);
    destroyAndReplace(this, 'age', new Chart(ctx, {
      type: 'bar',
      data: {
        labels: bins,
        datasets: [
          { label: 'Female', data: female, backgroundColor: '#7ee787' },
          { label: 'Male', data: male, backgroundColor: '#58a6ff' },
        ],
      },
      options: { ...chartOpts(), indexAxis: 'y', scales: {
        x: { ticks: { callback: v => Math.abs(v), color: '#8b949e' }, grid: { color: '#30363d' } },
        y: { ticks: { color: '#8b949e' }, grid: { color: '#30363d' } },
      }},
    }));
  },

  _renderResponderChart() {
    const ctx = document.getElementById('chart-responder');
    const classes = ['typical','super','partial','non_responder'];
    const counts = classes.map(c =>
      MDP.flatPatients.filter(p => p.responder_class === c).length);
    destroyAndReplace(this, 'responder', new Chart(ctx, {
      type: 'bar',
      data: { labels: classes, datasets: [{
        label: '#', data: counts,
        backgroundColor: ['#58a6ff','#7ee787','#f0c674','#ff7b72'],
      }]},
      options: chartOpts(),
    }));
  },

  _renderSexAgeChart() {
    const ctx = document.getElementById('chart-sex-age');
    const bins = ['20-35','35-55','55-70','70-90'];
    const diseaseIds = Object.keys(MDP.cohort.diseases);
    const datasets = diseaseIds.map((d, i) => ({
      label: d.replace(/_/g, ' '),
      data: bins.map(b =>
        MDP.flatPatients.filter(p => p.age_bin === b && p.disease_id === d).length),
      backgroundColor: ['#58a6ff','#7ee787','#f0c674','#ff7b72'][i % 4],
    }));
    destroyAndReplace(this, 'sexage', new Chart(ctx, {
      type: 'bar',
      data: { labels: bins, datasets },
      options: { ...chartOpts(), scales: {
        x: { stacked: true, ticks: { color: '#8b949e' }, grid: { color: '#30363d' } },
        y: { stacked: true, ticks: { color: '#8b949e' }, grid: { color: '#30363d' } },
      }},
    }));
  },
};

function destroyAndReplace(holder, key, c) {
  if (holder.charts[key]) holder.charts[key].destroy();
  holder.charts[key] = c;
}
function meanActivity(p) {
  const a = p.timeseries.map(r => r.activity);
  return a.reduce((s,x)=>s+x,0) / Math.max(a.length, 1);
}
function mean(arr) { return arr.reduce((s,x)=>s+x,0) / Math.max(arr.length, 1); }
function stdev(arr) {
  const m = mean(arr);
  return Math.sqrt(arr.reduce((s,x)=>s+(x-m)*(x-m),0) / Math.max(arr.length, 1));
}
function chartOpts() {
  return {
    responsive: true,
    plugins: { legend: { labels: { color: '#e6edf3', font: { size: 11 } } } },
    scales: {
      x: { ticks: { color: '#8b949e' }, grid: { color: '#30363d' } },
      y: { ticks: { color: '#8b949e' }, grid: { color: '#30363d' } },
    },
  };
}

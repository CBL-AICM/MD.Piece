// Patient browser — filter list + click to view detail.

window.PatientBrowser = {
  selected: null,
  charts: {},
  render() {
    const dSel = document.getElementById('f-disease');
    dSel.innerHTML = '<option value="">（全部）</option>' +
      Object.keys(MDP.cohort.diseases).map(d =>
        `<option value="${d}">${d}</option>`).join('');
    ['f-disease','f-age','f-sex','f-resp'].forEach(id =>
      document.getElementById(id).addEventListener('change', () => this._renderList()));
    this._renderList();
  },

  _renderList() {
    const ps = MDP.filter({
      disease:   document.getElementById('f-disease').value,
      ageBin:    document.getElementById('f-age').value,
      sex:       document.getElementById('f-sex').value,
      responder: document.getElementById('f-resp').value,
    });
    const list = document.getElementById('patient-list');
    if (!ps.length) { list.innerHTML = '<p class="muted" style="padding:14px">沒有符合條件的患者。</p>'; return; }
    list.innerHTML = ps.slice(0, 200).map(p => `
      <div class="patient-row" data-pid="${p.patient_id}">
        <div class="pid">${p.patient_id}</div>
        <div class="pmeta">${p.age}y ${p.sex} · ${p.subtype} · ${p.responder_class}${p.is_elderly ? ' · 老年' : ''}</div>
      </div>`).join('');
    if (ps.length > 200) {
      list.insertAdjacentHTML('beforeend',
        `<div class="pmeta" style="padding:10px">… 還有 ${ps.length-200} 位（請更精細篩選）</div>`);
    }
    list.querySelectorAll('.patient-row').forEach(row =>
      row.addEventListener('click', () => this._selectPatient(row.dataset.pid)));
  },

  _selectPatient(pid) {
    const p = MDP.flatPatients.find(x => x.patient_id === pid);
    if (!p) return;
    this.selected = p;
    document.querySelectorAll('.patient-row').forEach(r =>
      r.classList.toggle('selected', r.dataset.pid === pid));
    document.getElementById('detail-title').textContent =
      `${p.patient_id} — ${p.disease_id}`;
    document.getElementById('detail-meta').innerHTML = `
      <span>年齡 ${p.age} · ${p.sex}</span>
      <span>subtype: ${p.subtype}</span>
      <span>responder: ${p.responder_class}</span>
      <span>placebo: ${p.placebo_shift.toFixed(2)}</span>
      <span>flares: ${p.flare_count}</span>
      <span>${p.is_elderly ? '⚠️ 老年' : ''}</span>`;

    const labels = p.timeseries.map(r => r.day);
    const acts = p.timeseries.map(r => r.activity);

    // model predictions (aligned to days >= window_size)
    const predByDay = new Map();
    if (p.model_predictions) {
      p.model_predictions.forEach(x => predByDay.set(x.day, x));
    }
    const actPred = labels.map(d => {
      const r = predByDay.get(d);
      return r ? r.activity_pred : null;
    });

    if (this.charts.activity) this.charts.activity.destroy();
    this.charts.activity = new Chart(document.getElementById('detail-activity'), {
      type: 'line',
      data: { labels, datasets: [
        { label: '真實 activity', data: acts, borderColor: '#58a6ff',
          tension: 0.2, pointRadius: 0, fill: false, borderWidth: 2 },
        ...(p.model_predictions ? [{
          label: '🤖 AI 預測', data: actPred, borderColor: '#7ee787',
          tension: 0.2, pointRadius: 0, fill: false, borderWidth: 2,
          borderDash: [5, 4],
        }] : []),
        { label: 'burden', data: p.timeseries.map(r => r.irreversible_burden),
          borderColor: '#ff7b72', borderDash: [2,2], tension: 0.2, pointRadius: 0,
          fill: false, yAxisID: 'y1' },
      ]},
      options: { ...chartOpts(),
        scales: { ...chartOpts().scales,
          y1: { position: 'right', ticks: { color: '#ff7b72' }, grid: { display: false } }}
      },
    });

    // flare probability sparkline (if model predictions available)
    const flareCanvas = document.getElementById('detail-flare');
    if (this.charts.flare) this.charts.flare.destroy();
    if (p.model_predictions) {
      flareCanvas.style.display = '';
      const fp = labels.map(d => {
        const r = predByDay.get(d);
        return r ? r.flare_prob : null;
      });
      const ft = labels.map(d => {
        const r = predByDay.get(d);
        return r ? r.flare_true : null;
      });
      this.charts.flare = new Chart(flareCanvas, {
        type: 'line',
        data: { labels, datasets: [
          { label: '🤖 flare 機率', data: fp, borderColor: '#f0c674',
            backgroundColor: 'rgba(240, 198, 116, 0.2)',
            tension: 0.2, pointRadius: 0, fill: 'origin' },
          { label: '實際 flare', data: ft.map(v => v === null ? null : v * 1.0),
            borderColor: '#ff7b72', tension: 0, pointRadius: 0,
            fill: false, borderWidth: 1.5, stepped: true },
        ]},
        options: {
          ...chartOpts(),
          plugins: { ...chartOpts().plugins,
            title: { display: true, text: 'Flare 風險：AI 預測 vs 實際', color: '#e6edf3' }},
          scales: {
            ...chartOpts().scales,
            y: { min: 0, max: 1, ticks: { color: '#8b949e' }, grid: { color: '#30363d' } },
          },
        },
      });
    } else {
      flareCanvas.style.display = 'none';
    }

    // biomarkers — pick up to 3 non-core numeric columns
    const drop = new Set(['patient_id','day','activity','irreversible_burden',
      'n_active_triggers','in_flare','life_event_active','long_tail_active','dose_any_skipped']);
    const cols = Object.keys(p.timeseries[0]).filter(c => !drop.has(c)).slice(0, 3);
    const colors = ['#7ee787','#f0c674','#ff7b72'];
    if (this.charts.bm) this.charts.bm.destroy();
    this.charts.bm = new Chart(document.getElementById('detail-biomarkers'), {
      type: 'line',
      data: { labels, datasets: cols.map((c, i) => ({
        label: c, data: p.timeseries.map(r => r[c]),
        borderColor: colors[i], tension: 0.2, pointRadius: 0, fill: false,
      })) },
      options: chartOpts(),
    });

    document.getElementById('detail-events').innerHTML =
      '<strong>事件：</strong>' + (p.life_events.map(e =>
        `<span class="ev">${e.id} · day ${Math.round(e.onset_day)} (${Math.round(e.duration_days)}d)</span>`).join('') || '<span class="ev">無</span>') +
      (p.long_tail_event ? `<br><strong>罕見事件：</strong><span class="ev" style="background:#ff7b7222">long-tail flare</span>` : '');

    // AI insight panel
    const insightEl = document.getElementById('detail-insight');
    if (p.ai_insight_lines && p.ai_insight_lines.length) {
      const maeChip = p.model_mae != null
        ? `<span class="chip ${p.model_mae < 0.26 ? 'good' : 'bad'}">MAE ${p.model_mae.toFixed(2)}</span>`
        : '';
      const rChip = p.model_flare_recall != null
        ? `<span class="chip ${p.model_flare_recall >= 0.5 ? 'good' : 'bad'}">召回 ${(p.model_flare_recall*100).toFixed(0)}%</span>`
        : '';
      const pChip = p.model_flare_precision != null
        ? `<span class="chip ${p.model_flare_precision >= 0.5 ? 'good' : 'bad'}">準確 ${(p.model_flare_precision*100).toFixed(0)}%</span>`
        : '';
      insightEl.innerHTML = `
        <h3>AI 心得</h3>
        <div class="metric-chips">${maeChip}${rChip}${pChip}</div>
        ${p.ai_insight_lines.map(l => `<div class="insight-line">${escapeHtml(l)}</div>`).join('')}
      `;
    } else {
      insightEl.innerHTML = '<p class="muted" style="margin:0">（此 cohort 未啟用 AI 預測 — 請以 <code>--with-model</code> 重跑 main.py）</p>';
    }
  },
};

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

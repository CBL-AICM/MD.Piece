// What-If Lab — run the ONNX model live in the browser with user-edited inputs.

window.WhatIf = {
  chart: null,

  init() {
    const dSel = document.getElementById('w-disease');
    dSel.innerHTML = Object.keys(MDP.cohort.diseases)
      .map(d => `<option value="${d}">${d}</option>`).join('');
    dSel.addEventListener('change', () => this._refreshPatients());
    this._refreshPatients();

    document.getElementById('w-shift').addEventListener('input', e => {
      document.getElementById('w-shift-val').textContent =
        parseFloat(e.target.value).toFixed(1);
    });
    document.getElementById('w-run').addEventListener('click', () => this._run());

    // warm up the model so the first click is fast
    const status = document.getElementById('onnx-status');
    MDP_Inference.ensureLoaded().then(() => {
      status.innerHTML = `✅ 模型已載入（${MDP_Inference.featureNames.length} 個特徵 × 7 天 window）`;
      status.classList.add('good');
    }).catch(err => {
      status.innerHTML = `❌ 模型載入失敗：${err.message}`;
      status.classList.add('bad');
    });
  },

  _refreshPatients() {
    const d = document.getElementById('w-disease').value;
    const ps = MDP.cohort.diseases[d].patients;
    const sel = document.getElementById('w-patient');
    sel.innerHTML = ps.slice(0, 50).map(p =>
      `<option value="${p.patient_id}">${p.patient_id} · ${p.age}y ${p.sex} · ${p.subtype} · ${p.responder_class}</option>`
    ).join('');
  },

  async _run() {
    const out = document.getElementById('w-output');
    const btn = document.getElementById('w-run');
    btn.disabled = true;
    btn.textContent = '🤖 推論中…';
    try {
      const d = document.getElementById('w-disease').value;
      const pid = document.getElementById('w-patient').value;
      const day = parseInt(document.getElementById('w-day').value, 10);
      const noSkips = document.getElementById('w-no-skips').checked;
      const noEvents = document.getElementById('w-no-events').checked;
      const shift = parseFloat(document.getElementById('w-shift').value);

      const patient = MDP.cohort.diseases[d].patients.find(x => x.patient_id === pid);
      if (!patient) throw new Error('找不到患者');
      if (day < 7 || day > patient.timeseries.length) {
        throw new Error(`day 必須介於 7 和 ${patient.timeseries.length} 之間`);
      }

      // baseline (use the patient's actual data)
      const baseline = await this._infer(patient, day, {});
      const overrides = {
        perfect_adherence: noSkips,
        no_life_events: noEvents,
        activity_shift: shift,
      };
      const counterfactual = await this._inferWithShift(patient, day, overrides);

      // also fetch the pre-computed prediction for cross-check (if exists)
      const preComputed = patient.model_predictions
        ? patient.model_predictions.find(x => x.day === day - 1)
        : null;

      out.innerHTML = `
        <table>
        <tr><th></th><th>活動度（次日）</th><th>Flare 機率（7d）</th></tr>
        <tr><td>實際（真值）</td>
            <td>${preComputed ? preComputed.activity_true.toFixed(2) : '—'}</td>
            <td>${preComputed ? preComputed.flare_true : '—'}</td></tr>
        <tr><td>原始模型輸入</td>
            <td>${baseline.activity_pred.toFixed(2)}</td>
            <td>${(baseline.flare_prob * 100).toFixed(0)}%</td></tr>
        <tr><td><strong>反事實輸入</strong>
            <span class="muted">${describeOverrides(overrides)}</span></td>
            <td><strong>${counterfactual.activity_pred.toFixed(2)}</strong>
              <span class="muted">(Δ ${
                (counterfactual.activity_pred - baseline.activity_pred).toFixed(2)
              })</span></td>
            <td><strong>${(counterfactual.flare_prob * 100).toFixed(0)}%</strong>
              <span class="muted">(Δ ${
                ((counterfactual.flare_prob - baseline.flare_prob) * 100).toFixed(1)
              }pp)</span></td></tr>
        </table>
        <div class="muted" style="margin-top:8px">
          ⏱ 純前端推論。打開 DevTools → Network 可看到 model.onnx 載入紀錄。
        </div>`;

      this._renderChart(patient, day, baseline, counterfactual, preComputed);
    } catch (e) {
      out.innerHTML = `<span class="bad">❌ ${e.message}</span>`;
    } finally {
      btn.disabled = false;
      btn.textContent = '🤖 重新預測';
    }
  },

  async _infer(patient, day, overrides) {
    return MDP_Inference.runPatient(patient, day, overrides);
  },

  async _inferWithShift(patient, day, overrides) {
    if (overrides.activity_shift === 0) {
      return this._infer(patient, day, overrides);
    }
    // build modified window inline: read 7-day rows, shift activity, then call runWindow
    const T = 7;
    const feats = MDP_Inference.featureNames;
    const rows = [];
    for (let d = day - T; d < day; d++) {
      const r = patient.timeseries.find(x => x.day === d);
      if (!r) throw new Error(`missing day ${d}`);
      rows.push({ ...r, activity: r.activity + overrides.activity_shift });
    }
    const matrix = rows.map(r => feats.map(f => {
      if (f === 'activity') return r.activity;
      if (f === 'life_event_active' && overrides.no_life_events) return 0;
      if (f === 'dose_any_skipped' && overrides.perfect_adherence) return 0;
      // fall back to standard feature mapping (mimic inference.js _featureValue)
      if (f === 'irreversible_burden') return r.irreversible_burden;
      if (f === 'n_active_triggers') return r.n_active_triggers;
      if (f === 'long_tail_active') return r.long_tail_active;
      if (f === 'age') return patient.age;
      if (f === 'sex_F') return patient.sex === 'F' ? 1 : 0;
      if (f.startsWith('is_')) return patient.disease_id === f.slice(3) ? 1 : 0;
      if (f.startsWith('on_')) return patient.treatments.some(t => t.id === f.slice(3)) ? 1 : 0;
      if (f.startsWith('bm_')) return r[f.slice(3)] !== undefined ? r[f.slice(3)] : 0;
      return 0;
    }));
    return MDP_Inference.runWindow(matrix);
  },

  _renderChart(patient, day, baseline, counterfactual, preComputed) {
    if (this.chart) this.chart.destroy();
    const ts = patient.timeseries;
    const labels = ts.map(r => r.day);
    const acts = ts.map(r => r.activity);
    const predLine = labels.map(d => d === day ? baseline.activity_pred : null);
    const cfLine = labels.map(d => d === day ? counterfactual.activity_pred : null);
    this.chart = new Chart(document.getElementById('w-chart'), {
      type: 'line',
      data: { labels, datasets: [
        { label: '真實 activity', data: acts, borderColor: '#58a6ff',
          tension: 0.2, pointRadius: 0, fill: false },
        { label: '🤖 原始預測', data: predLine, borderColor: '#7ee787',
          pointRadius: 6, pointBackgroundColor: '#7ee787', showLine: false },
        { label: '🧪 反事實預測', data: cfLine, borderColor: '#f0c674',
          pointRadius: 6, pointStyle: 'rectRot',
          pointBackgroundColor: '#f0c674', showLine: false },
      ]},
      options: chartOpts(),
    });
  },
};

function describeOverrides(o) {
  const parts = [];
  if (o.perfect_adherence) parts.push('完全配合服藥');
  if (o.no_life_events) parts.push('無生活事件');
  if (o.activity_shift !== 0) parts.push(`活動度位移 ${o.activity_shift > 0 ? '+' : ''}${o.activity_shift.toFixed(1)}`);
  return parts.length ? '（' + parts.join('、') + '）' : '（無變更）';
}

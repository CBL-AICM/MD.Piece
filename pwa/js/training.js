// Training mode — show 60 days of one patient, predict if flare in 61-90.

window.Training = {
  chart: null,
  current: null,
  score: { correct: 0, total: 0 },
  init() {
    this._loadScore();
    this._renderScore();
    this._nextPatient();
    document.getElementById('t-flare').addEventListener('click', () => this._answer(true));
    document.getElementById('t-noflare').addEventListener('click', () => this._answer(false));
    document.getElementById('t-next').addEventListener('click', () => this._nextPatient());
  },

  _loadScore() {
    try {
      const s = JSON.parse(localStorage.getItem('mdp-training-score') || '{}');
      if (s.total) this.score = s;
    } catch (e) { /* ignore */ }
  },
  _saveScore() {
    localStorage.setItem('mdp-training-score', JSON.stringify(this.score));
  },
  _renderScore() {
    const { correct, total } = this.score;
    document.getElementById('t-score').textContent = total
      ? `${correct}/${total} (${Math.round(correct/total*100)}%)`
      : '尚未開始';
  },

  _nextPatient() {
    document.getElementById('train-result').innerHTML = '';
    document.getElementById('train-result').className = '';
    document.getElementById('t-flare').disabled = false;
    document.getElementById('t-noflare').disabled = false;
    document.getElementById('t-next').classList.add('hidden');
    // pick patient with at least 90 days
    const candidates = MDP.flatPatients.filter(p => p.timeseries.length >= 90);
    this.current = candidates[Math.floor(Math.random() * candidates.length)];
    if (!this.current) return;
    const ts = this.current.timeseries.slice(0, 60);
    if (this.chart) this.chart.destroy();
    this.chart = new Chart(document.getElementById('train-chart'), {
      type: 'line',
      data: { labels: ts.map(r => r.day), datasets: [{
        label: `${this.current.disease_id} — first 60 days`,
        data: ts.map(r => r.activity),
        borderColor: '#58a6ff', tension: 0.2, pointRadius: 0, fill: false,
      }]},
      options: chartOpts(),
    });
  },

  _answer(userSaysFlare) {
    const truthSlice = this.current.timeseries.slice(60, 90);
    const wasFlare = truthSlice.some(r => r.in_flare === 1);
    const correct = (userSaysFlare === wasFlare);
    this.score.total += 1;
    if (correct) this.score.correct += 1;
    this._saveScore();
    this._renderScore();

    // reveal full curve
    const ts = this.current.timeseries;
    this.chart.data.labels = ts.map(r => r.day);
    this.chart.data.datasets = [
      { label: 'first 60 days (shown)', data: ts.slice(0,60).map(r => r.activity),
        borderColor: '#58a6ff', tension: 0.2, pointRadius: 0, fill: false },
      { label: 'true 61-90', data: [...Array(60).fill(null), ...ts.slice(60,90).map(r => r.activity)],
        borderColor: wasFlare ? '#ff7b72' : '#7ee787', tension: 0.2, pointRadius: 0,
        fill: false, borderDash: [4,4] },
    ];
    this.chart.update();

    const r = document.getElementById('train-result');
    r.className = correct ? 'correct' : 'wrong';
    r.innerHTML = `
      <strong>${correct ? '✅ 答對' : '❌ 答錯'}</strong> —
      實際 61-90 ${wasFlare ? '發生 flare' : '沒有 flare'}<br>
      <span class="muted">解釋：subtype=${this.current.subtype}, responder=${this.current.responder_class},
      ${this.current.life_events.filter(e => e.onset_day >= 60 && e.onset_day <= 90).length}
      件 61-90 內的 life event</span>`;
    document.getElementById('t-flare').disabled = true;
    document.getElementById('t-noflare').disabled = true;
    document.getElementById('t-next').classList.remove('hidden');
  },
};

// 患者端：每日記錄（5 層問卷 + 情緒 + 服藥）+ 檢驗白話 + 衛教知識
// 此檔案僅新增頁面，不改動 app.js 的既有功能

(function () {
  const API = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '';

  function pid() {
    return (typeof getStablePatientId === 'function')
      ? getStablePatientId()
      : (localStorage.getItem('mdpiece_patient_id') || 'guest');
  }

  // ── 5 層問卷狀態 ─────────────────────────────────
  const state = {
    schema: null,
    step: 0,
    answers: {
      overall_feeling: null,
      body_locations: [],
      symptom_types: [],
      free_text: '',
      severity: 3,
      change_pattern: null,
    },
  };

  async function loadSchema() {
    if (state.schema) return state.schema;
    const res = await fetch(`${API}/symptoms/questionnaire`);
    state.schema = await res.json();
    return state.schema;
  }

  // ── 主要 UI：每日記錄頁 ─────────────────────────
  function dailyPage() {
    return `
      <div class="page-card">
        <h2>每天三分鐘，照顧自己</h2>
        <p class="muted">填完之後，醫師回診時就能看到完整的這 30 天</p>
        <div id="daily-questionnaire" class="daily-q"></div>
        <div id="daily-result" class="daily-result" style="display:none"></div>
      </div>
    `;
  }

  async function initDaily() {
    await loadSchema();
    state.step = 0;
    renderStep();
  }

  function renderStep() {
    const root = document.getElementById('daily-questionnaire');
    if (!root) return;
    const layer = state.schema.layers[state.step];
    if (!layer) return submitAnswers();
    if (layer.type === 'single_choice' && layer.id === 'overall_feeling') {
      root.innerHTML = renderOverall(layer);
    } else if (layer.type === 'body_map') {
      root.innerHTML = renderBodyMap(layer);
    } else if (layer.type === 'multi_choice_with_text') {
      root.innerHTML = renderSymptomTypes(layer);
    } else if (layer.type === 'slider') {
      root.innerHTML = renderSlider(layer);
    } else if (layer.type === 'single_choice') {
      root.innerHTML = renderChangePattern(layer);
    }
  }

  function renderOverall(layer) {
    return `
      <h3>${layer.title}</h3>
      <p class="muted">${layer.subtitle}</p>
      <div class="opts opts-row">
        ${layer.options.map(o => `
          <button class="opt-btn" data-key="${o.key}" onclick="DailyPage.pickOverall('${o.key}')">${o.label}</button>
        `).join('')}
      </div>
    `;
  }

  function renderBodyMap(layer) {
    return `
      <h3>${layer.title}</h3>
      <p class="muted">${layer.subtitle}</p>
      <div class="bodymap-tabs">
        <button class="bm-tab active" onclick="DailyPage.flipBody('front', this)">正面</button>
        <button class="bm-tab" onclick="DailyPage.flipBody('back', this)">背面</button>
      </div>
      <div id="bm-stage" class="bm-stage" data-side="front">
        ${bodyMapDots('front')}
      </div>
      <div id="bm-selected" class="muted bm-selected">未選擇</div>
      <div class="step-actions">
        <button onclick="DailyPage.next()">下一步</button>
      </div>
    `;
  }

  function bodyMapDots(side) {
    const parts = state.schema.layers[1][side];
    return `
      <div class="bm-figure ${side}"></div>
      ${parts.map(p => `
        <button
          class="bm-dot ${state.answers.body_locations.includes(p.key) ? 'on' : ''}"
          style="left:${p.x}%;top:${p.y}%;width:${p.r * 2}%"
          onclick="DailyPage.toggleLoc('${p.key}', this)"
          title="${p.label}"
        ></button>
      `).join('')}
    `;
  }

  function renderSymptomTypes(layer) {
    return `
      <h3>${layer.title}</h3>
      <p class="muted">${layer.subtitle}</p>
      <div class="opts opts-grid">
        ${layer.options.map(o => `
          <button class="opt-btn ${state.answers.symptom_types.includes(o.key) ? 'on' : ''}"
                  onclick="DailyPage.toggleType('${o.key}', this)">${o.label}</button>
        `).join('')}
      </div>
      <div class="free-text">
        <label>${layer.free_text_label}</label>
        <textarea id="daily-free-text" rows="3" placeholder="例：早上起床膝蓋很僵硬，走樓梯會痛">${state.answers.free_text || ''}</textarea>
      </div>
      <div class="step-actions">
        <button onclick="DailyPage.next()">下一步</button>
      </div>
    `;
  }

  function renderSlider(layer) {
    return `
      <h3>${layer.title}</h3>
      <p class="muted">${layer.subtitle}</p>
      <input type="range" id="daily-severity" min="${layer.min}" max="${layer.max}"
             value="${state.answers.severity}"
             oninput="document.getElementById('daily-sev-val').textContent=this.value" />
      <div class="sev-row">
        ${layer.anchors.map(a => `<span class="muted">${a.value}<br>${a.label}</span>`).join('')}
      </div>
      <div class="sev-current">當前：<span id="daily-sev-val">${state.answers.severity}</span></div>
      <div class="step-actions">
        <button onclick="DailyPage.next()">下一步</button>
      </div>
    `;
  }

  function renderChangePattern(layer) {
    return `
      <h3>${layer.title}</h3>
      <p class="muted">${layer.subtitle}</p>
      <div class="opts opts-row">
        ${layer.options.map(o => `
          <button class="opt-btn" onclick="DailyPage.pickPattern('${o.key}')">${o.label}</button>
        `).join('')}
      </div>
    `;
  }

  // ── 互動事件 ────────────────────────────────────
  const DailyPage = {
    pickOverall(key) {
      state.answers.overall_feeling = key;
      const skip = state.schema.layers[0].skip_to_done_if || [];
      if (skip.includes(key)) {
        return submitAnswers();
      }
      state.step = 1;
      renderStep();
    },
    flipBody(side, btn) {
      document.querySelectorAll('.bm-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const stage = document.getElementById('bm-stage');
      stage.dataset.side = side;
      stage.innerHTML = bodyMapDots(side);
    },
    toggleLoc(key, btn) {
      const arr = state.answers.body_locations;
      const i = arr.indexOf(key);
      if (i >= 0) { arr.splice(i, 1); btn.classList.remove('on'); }
      else { arr.push(key); btn.classList.add('on'); }
      const all = [...state.schema.layers[1].front, ...state.schema.layers[1].back];
      const labels = arr.map(k => (all.find(p => p.key === k) || {}).label).filter(Boolean);
      const sel = document.getElementById('bm-selected');
      if (sel) sel.textContent = labels.length ? `已選：${labels.join('、')}` : '未選擇';
    },
    toggleType(key, btn) {
      const arr = state.answers.symptom_types;
      const i = arr.indexOf(key);
      if (i >= 0) { arr.splice(i, 1); btn.classList.remove('on'); }
      else { arr.push(key); btn.classList.add('on'); }
    },
    pickPattern(key) {
      state.answers.change_pattern = key;
      submitAnswers();
    },
    next() {
      if (state.step === 2) {
        state.answers.free_text = (document.getElementById('daily-free-text') || {}).value || '';
      }
      if (state.step === 3) {
        state.answers.severity = +(document.getElementById('daily-severity') || {}).value || 0;
      }
      state.step += 1;
      renderStep();
    },
  };
  window.DailyPage = DailyPage;

  // ── 送出 ─────────────────────────────────────────
  async function submitAnswers() {
    const body = { patient_id: pid(), ...state.answers };
    try {
      const res = await fetch(`${API}/symptoms/questionnaire/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      showResult(data);
    } catch (e) {
      showResult({ error: e.message });
    }
  }

  function showResult(data) {
    const root = document.getElementById('daily-questionnaire');
    const result = document.getElementById('daily-result');
    if (root) root.style.display = 'none';
    if (!result) return;
    result.style.display = 'block';
    if (data.error) {
      result.innerHTML = `<p class="muted">送出失敗：${data.error}</p>`;
      return;
    }
    result.innerHTML = `
      <h3>已記錄今天的狀況</h3>
      <p>${data.summary || '已收到'}</p>
      <p class="muted">嚴重度指數：${data.severity_index ?? '—'}</p>
      <button onclick="location.reload()">重新填寫</button>
    `;
    // 順手叫一次分流
    runTriage(data);
  }

  async function runTriage(submission) {
    try {
      const r = await fetch(`${API}/triage/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: pid(),
          symptoms: state.answers.symptom_types || [],
          body_locations: state.answers.body_locations,
          severity_index: submission.severity_index,
        }),
      });
      const t = await r.json();
      const result = document.getElementById('daily-result');
      const banner = document.createElement('div');
      banner.className = 'triage-banner level-' + t.result;
      banner.innerHTML = `
        <strong>分流：${t.result}</strong>
        <p>${t.patient_message || ''}</p>
      `;
      result.appendChild(banner);
    } catch (e) { /* silent */ }
  }

  // ── 檢驗白話頁 ───────────────────────────────────
  function labsPage() {
    return `
      <div class="page-card">
        <h2>你的檢驗結果</h2>
        <p class="muted">醫師已經幫你看過了，這裡只是讓你也安心了解</p>
        <div id="labs-list">載入中…</div>
      </div>
    `;
  }
  async function initLabs() {
    const list = document.getElementById('labs-list');
    if (!list) return;
    try {
      const res = await fetch(`${API}/vitals/lab/${pid()}/translated`);
      const data = await res.json();
      if (!data.translated || !data.translated.length) {
        list.innerHTML = '<p class="muted">目前還沒有檢驗結果</p>';
        return;
      }
      list.innerHTML = data.translated.map(t => `
        <div class="lab-card lab-${t.level}">
          <strong>${t.casual_name}</strong>
          <p>${t.message}</p>
        </div>
      `).join('');
      const re = document.createElement('p');
      re.className = 'muted';
      re.textContent = data.reassurance || '';
      list.appendChild(re);
    } catch (e) {
      list.innerHTML = `<p class="muted">載入失敗：${e.message}</p>`;
    }
  }

  // ── 疾病知識頁（含「不是你的病」）─────────────────
  function knowledgePage() {
    return `
      <div class="page-card">
        <h2>疾病衛教</h2>
        <p class="muted">了解你的病，知道哪些其實不用擔心</p>
        <select id="kn-disease" onchange="KnowledgePage.load(this.value)">
          <option value="">— 選擇疾病 —</option>
        </select>
        <div id="kn-content" style="margin-top:16px"></div>
      </div>
    `;
  }
  async function initKnowledge() {
    const sel = document.getElementById('kn-disease');
    if (!sel) return;
    try {
      const res = await fetch(`${API}/education/knowledge`);
      const data = await res.json();
      sel.innerHTML += (data.diseases || []).map(d =>
        `<option value="${d.icd10}">${d.icd10} · ${d.name}</option>`
      ).join('');
    } catch (e) {
      sel.innerHTML += `<option disabled>載入失敗</option>`;
    }
  }
  const KnowledgePage = {
    async load(code) {
      const c = document.getElementById('kn-content');
      if (!code) { c.innerHTML = ''; return; }
      try {
        const res = await fetch(`${API}/education/knowledge/${code}`);
        const d = await res.json();
        c.innerHTML = `
          <h3>${d.name}</h3>
          <h4>這是什麼？</h4><p>${d.what_is_it}</p>
          <h4>為什麼會得？</h4><p>${d.why_get_it}</p>
          <h4>日常注意事項</h4>
          <ul>
            <li>飲食：${d.daily_care.diet}</li>
            <li>睡眠：${d.daily_care.sleep}</li>
            <li>運動：${d.daily_care.exercise}</li>
            <li>壓力：${d.daily_care.stress}</li>
          </ul>
          <h4>需要特別注意的時候</h4>
          <ul>${d.watch_out.map(w => `<li>${w}</li>`).join('')}</ul>
          <h4 class="not-yours">這些不是你的病</h4>
          ${d.not_your_disease.map(n => `
            <div class="not-yours-item">
              <strong>${n.name}</strong>
              <p>${n.explain}</p>
            </div>
          `).join('')}
        `;
      } catch (e) {
        c.innerHTML = `<p class="muted">載入失敗：${e.message}</p>`;
      }
    },
  };
  window.KnowledgePage = KnowledgePage;

  // ── 對外暴露：頁面工廠 ───────────────────────────
  window.DailyFeatures = {
    dailyPage, initDaily,
    labsPage, initLabs,
    knowledgePage, initKnowledge,
  };
})();

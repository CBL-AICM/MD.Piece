(function () {
  const featureKey = document.body.dataset.feature;
  const feature = window.MDPieceFeatures && window.MDPieceFeatures[featureKey];

  if (!feature) {
    return;
  }

  document.body.style.setProperty("--feature-color", feature.color || "#91c7f2");
  document.body.style.setProperty("--feature-hover", feature.hoverColor || "#6fb0e4");
  document.title = `${feature.title} | MD.Piece`;

  document.getElementById("feature-title").textContent = feature.title;
  document.getElementById("feature-subtitle").textContent = feature.subtitle;
  document.getElementById("feature-tag").textContent = feature.tag;

  renderFragmentRail();

  const cards = document.getElementById("feature-cards");
  cards.innerHTML = feature.cards
    .map(
      (card) => `
        <article class="feature-card">
          <small>${escapeHtml(card.label)}</small>
          <strong>${escapeHtml(card.value)}</strong>
          <p>${escapeHtml(card.text)}</p>
        </article>
      `
    )
    .join("");

  const sections = document.getElementById("feature-sections");
  sections.innerHTML = feature.sections
    .map(
      (section) => `
        <section class="feature-section">
          <h2>${escapeHtml(section.title)}</h2>
          <ul class="feature-list">
            ${section.items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
          </ul>
        </section>
      `
    )
    .join("");

  const note = document.getElementById("feature-note");
  note.innerHTML = `<h2>備註</h2><p>${escapeHtml(feature.note)}</p>`;

  if (feature.customMeasurements) {
    renderCustomMeasurements(feature.customMeasurements);
  }

  if (feature.medicationCapture) {
    renderMedicationCapture(feature.medicationCapture);
  }

  if (feature.visitFragments) {
    renderVisitFragments(feature.visitFragments);
  }

  function renderFragmentRail() {
    const hero = document.querySelector(".feature-hero");

    if (!hero || !feature.fragments || !feature.fragments.length) {
      return;
    }

    const rail = document.createElement("div");
    rail.className = "feature-fragment-rail";
    rail.innerHTML = feature.fragments
      .map((fragment, index) => `<span class="feature-fragment-chip fragment-${index % 4}">${escapeHtml(fragment)}</span>`)
      .join("");
    hero.after(rail);
  }

  function renderMedicationCapture(config) {
    const storageKey = `md-piece-medication-capture-${featureKey}`;
    const extraKey = `md-piece-medication-extra-${featureKey}`;
    const customPanel = document.createElement("section");
    customPanel.className = "medication-capture-panel";
    customPanel.innerHTML = `
      <div class="med-capture-heading">
        <div>
          <p class="measurement-kicker">MED SCAN</p>
          <h2>${escapeHtml(config.title)}</h2>
          <p>${escapeHtml(config.subtitle)}</p>
        </div>
        <span class="measurement-storage-badge">先辨識，再核對</span>
      </div>
      <div class="med-capture-grid">
        <div class="med-capture-card">
          <div class="measurement-block-title">
            <h3>拍藥單或貼上文字</h3>
            <p>照片只在本機預覽；目前原型會用範例資料模擬辨識，之後可接 OCR。</p>
          </div>
          <div class="med-capture-actions">
            <label class="med-photo-button">
              <input id="med-photo-input" name="medPhoto" type="file" accept="image/*" capture="environment">
              <span>拍藥單</span>
              <small>藥袋、藥單都可以</small>
            </label>
            <button class="med-secondary-button" type="button" id="med-sample-button">載入範例</button>
            <button class="med-secondary-button" type="button" id="med-clear-button">清空重來</button>
          </div>
          <div class="med-photo-preview" id="med-photo-preview" hidden></div>
          <label class="med-text-field">
            <span>也可以整段貼上</span>
            <textarea id="med-text-input" rows="6" placeholder="${escapeHtml(config.sampleText)}"></textarea>
          </label>
          <button class="measurement-submit med-scan-button" type="button" id="med-scan-button">辨識成用藥表</button>
          <p class="med-scan-status" id="med-scan-status">尚未辨識。可以先拍照或貼上藥袋文字。</p>
        </div>
        <div class="med-capture-card">
          <div class="measurement-block-title">
            <h3>辨識結果核對</h3>
            <p>請把藥名、劑量、時間和藥袋再看一次；不確定就留待確認。</p>
          </div>
          <div class="med-result-list" id="med-result-list"></div>
        </div>
      </div>
      <div class="med-schedule-panel">
        <div class="measurement-block-title">
          <h3>今日用藥時間表</h3>
          <p>依時段整理，讓患者不用自己在腦中排序。</p>
        </div>
        <div class="med-schedule-grid" id="med-schedule-grid"></div>
      </div>
      <div class="med-extra-panel">
        <div class="measurement-block-title">
          <h3>如果今天多吃了什麼</h3>
          <p>從選單選藥名和原因，留下紀錄給回診核對。</p>
        </div>
        <form class="med-extra-form" id="med-extra-form">
          <label>
            <span>多吃/臨時吃的藥</span>
            <select name="extraMed" required></select>
          </label>
          <label>
            <span>原因</span>
            <select name="extraReason" required>
              ${config.extraReasons.map((reason) => `<option value="${escapeHtml(reason)}">${escapeHtml(reason)}</option>`).join("")}
            </select>
          </label>
          <label>
            <span>補充</span>
            <input name="extraNote" type="text" placeholder="例如：半夜頭痛、吃完比較想睡">
          </label>
          <button class="measurement-submit" type="submit">加到今日紀錄</button>
        </form>
        <div class="med-extra-list" id="med-extra-list"></div>
      </div>
    `;

    note.before(customPanel);

    const photoInput = customPanel.querySelector("#med-photo-input");
    const photoPreview = customPanel.querySelector("#med-photo-preview");
    const sampleButton = customPanel.querySelector("#med-sample-button");
    const clearButton = customPanel.querySelector("#med-clear-button");
    const scanButton = customPanel.querySelector("#med-scan-button");
    const textInput = customPanel.querySelector("#med-text-input");
    const scanStatus = customPanel.querySelector("#med-scan-status");
    const resultList = customPanel.querySelector("#med-result-list");
    const scheduleGrid = customPanel.querySelector("#med-schedule-grid");
    const extraForm = customPanel.querySelector("#med-extra-form");
    const extraMedSelect = extraForm.elements.extraMed;
    const extraList = customPanel.querySelector("#med-extra-list");

    function getMedicationRecords() {
      try {
        return JSON.parse(window.localStorage.getItem(storageKey) || "[]");
      } catch (error) {
        console.warn("Medication records unavailable.", error);
        return [];
      }
    }

    function saveMedicationRecords(records) {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(records));
      } catch (error) {
        console.warn("Medication records unavailable.", error);
      }
    }

    function getExtraRecords() {
      try {
        return JSON.parse(window.localStorage.getItem(extraKey) || "[]");
      } catch (error) {
        console.warn("Extra medication records unavailable.", error);
        return [];
      }
    }

    function saveExtraRecords(records) {
      try {
        window.localStorage.setItem(extraKey, JSON.stringify(records));
      } catch (error) {
        console.warn("Extra medication records unavailable.", error);
      }
    }

    function renderMedicationRecords(records = getMedicationRecords()) {
      const activeRecords = records.length ? records : [];
      resultList.innerHTML = activeRecords.length
        ? activeRecords.map(renderMedicationCard).join("")
        : `<p class="measurement-empty">還沒有辨識結果。先拍藥單或貼上藥袋文字。</p>`;

      scheduleGrid.innerHTML = config.slots
        .map((slot) => renderScheduleSlot(slot, activeRecords))
        .join("");

      renderExtraOptions(activeRecords);
      renderExtraRecords();
    }

    function renderMedicationCard(med, index) {
      return `
        <article class="med-result-card" data-index="${index}">
          <div>
            <small>${escapeHtml(med.purpose || "用途待確認")}</small>
            <strong>${escapeHtml(med.name)}</strong>
            <p>${escapeHtml(med.dose || "劑量待確認")}</p>
          </div>
          <div class="med-timing-row">
            ${(med.timing || ["待確認"]).map((time) => `<span>${escapeHtml(time)}</span>`).join("")}
          </div>
          ${med.caution ? `<p class="med-caution">${escapeHtml(med.caution)}</p>` : ""}
          <button class="inline-delete med-remove" type="button" data-index="${index}">移除這筆</button>
        </article>
      `;
    }

    function renderScheduleSlot(slot, records) {
      const matched = records.filter((med) => (med.timing || []).includes(slot));

      return `
        <article class="med-schedule-slot">
          <h4>${escapeHtml(slot)}</h4>
          ${
            matched.length
              ? matched.map((med) => `<p><strong>${escapeHtml(med.name)}</strong><span>${escapeHtml(med.dose || "")}</span></p>`).join("")
              : `<p class="med-slot-empty">沒有安排</p>`
          }
        </article>
      `;
    }

    function renderExtraOptions(records) {
      const options = records.length ? records : config.sampleMeds;
      extraMedSelect.innerHTML = options
        .map((med) => `<option value="${escapeHtml(med.name)}">${escapeHtml(med.name)} ${escapeHtml(med.dose || "")}</option>`)
        .join("");
    }

    function renderExtraRecords() {
      const records = getExtraRecords();
      extraList.innerHTML = records.length
        ? records
            .map(
              (record) => `
                <article class="med-extra-record">
                  <strong>${escapeHtml(record.med)}</strong>
                  <span>${escapeHtml(record.reason)}</span>
                  ${record.note ? `<p>${escapeHtml(record.note)}</p>` : ""}
                  <button class="inline-delete med-extra-remove" type="button" data-id="${escapeHtml(record.id)}">移除</button>
                </article>
              `
            )
            .join("")
        : `<p class="measurement-empty">今天還沒有額外用藥紀錄。</p>`;
    }

    function runMedicationRecognition(source) {
      const typedRecords = parseMedicationText(textInput.value, config);
      const records = typedRecords.length ? typedRecords : config.sampleMeds.map((med) => ({ ...med }));
      saveMedicationRecords(records);
      scanStatus.textContent = source === "photo"
        ? `已從照片建立 ${records.length} 筆待核對用藥。`
        : `已整理 ${records.length} 筆待核對用藥。`;
      renderMedicationRecords(records);
    }

    photoInput.addEventListener("change", () => {
      const file = photoInput.files && photoInput.files[0];

      if (!file) {
        return;
      }

      const imageUrl = URL.createObjectURL(file);
      photoPreview.hidden = false;
      photoPreview.innerHTML = `
        <img src="${imageUrl}" alt="藥單預覽">
        <span>${escapeHtml(file.name)}</span>
      `;
      runMedicationRecognition("photo");
    });

    sampleButton.addEventListener("click", () => {
      textInput.value = config.sampleText;
      runMedicationRecognition("sample");
    });

    clearButton.addEventListener("click", () => {
      saveMedicationRecords([]);
      saveExtraRecords([]);
      textInput.value = "";
      photoInput.value = "";
      photoPreview.hidden = true;
      photoPreview.innerHTML = "";
      scanStatus.textContent = "已清空。可以重新拍照或貼上藥袋文字。";
      renderMedicationRecords([]);
    });

    scanButton.addEventListener("click", () => {
      runMedicationRecognition("text");
    });

    resultList.addEventListener("click", (event) => {
      const button = event.target.closest(".med-remove");

      if (!button) {
        return;
      }

      const records = getMedicationRecords();
      records.splice(Number(button.dataset.index), 1);
      saveMedicationRecords(records);
      renderMedicationRecords(records);
    });

    extraList.addEventListener("click", (event) => {
      const button = event.target.closest(".med-extra-remove");

      if (!button) {
        return;
      }

      saveExtraRecords(getExtraRecords().filter((record) => record.id !== button.dataset.id));
      renderExtraRecords();
    });

    extraForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const formData = new FormData(extraForm);
      const record = {
        id: String(Date.now()),
        med: String(formData.get("extraMed") || "").trim(),
        reason: String(formData.get("extraReason") || "").trim(),
        note: String(formData.get("extraNote") || "").trim()
      };

      if (!record.med || !record.reason) {
        return;
      }

      saveExtraRecords([record, ...getExtraRecords()]);
      extraForm.reset();
      renderExtraRecords();
    });

    renderMedicationRecords();
  }

  function renderVisitFragments(config) {
    const currentKey = `md-piece-visit-fragments-current-${featureKey}`;
    const previousKey = `md-piece-visit-fragments-previous-${featureKey}`;
    const panel = document.createElement("section");
    panel.className = "visit-fragments-panel";
    panel.innerHTML = `
      <div class="visit-fragments-heading">
        <div>
          <p class="measurement-kicker">VISIT PIECES</p>
          <h2>${escapeHtml(config.title)}</h2>
          <p>${escapeHtml(config.subtitle)}</p>
        </div>
        <span class="measurement-storage-badge">回診後歸零</span>
      </div>
      <div class="visit-fragments-grid">
        <div class="visit-card">
          <div class="measurement-block-title">
            <h3>這次診前紀錄</h3>
            <p>點選常用碎片，或自己補一句。回診後按封存，這區會歸零。</p>
          </div>
          <div class="visit-chip-groups">
            ${config.categories
              .map(
                (group) => `
                  <section class="visit-chip-group">
                    <h4>${escapeHtml(group.label)}</h4>
                    <div>
                      ${group.chips.map((chip) => `<button type="button" data-category="${escapeHtml(group.label)}" data-text="${escapeHtml(chip)}">${escapeHtml(chip)}</button>`).join("")}
                    </div>
                  </section>
                `
              )
              .join("")}
          </div>
          <form class="visit-manual-form" id="visit-manual-form">
            <label>
              <span>分類</span>
              <select name="category">
                ${config.categories.map((group) => `<option value="${escapeHtml(group.label)}">${escapeHtml(group.label)}</option>`).join("")}
              </select>
            </label>
            <label>
              <span>補一句</span>
              <input name="text" type="text" placeholder="例如：這次最想問藥物時段">
            </label>
            <button class="measurement-submit" type="submit">加入這次</button>
          </form>
          <div class="visit-current-list" id="visit-current-list"></div>
          <button class="visit-archive-button" type="button" id="visit-archive-button">回診後封存，開始下一輪</button>
        </div>
        <div class="visit-card visit-previous-card">
          <div class="measurement-block-title">
            <h3>上一次診療碎片</h3>
            <p>封存後會留在這裡；下一次準備回診時，可以先看上次醫師處理了什麼。</p>
          </div>
          <div class="visit-previous-summary" id="visit-previous-summary"></div>
          <div class="visit-previous-list" id="visit-previous-list"></div>
        </div>
      </div>
    `;

    note.before(panel);

    const chipGroups = panel.querySelector(".visit-chip-groups");
    const manualForm = panel.querySelector("#visit-manual-form");
    const currentList = panel.querySelector("#visit-current-list");
    const archiveButton = panel.querySelector("#visit-archive-button");
    const previousSummary = panel.querySelector("#visit-previous-summary");
    const previousList = panel.querySelector("#visit-previous-list");

    function getCurrentFragments() {
      try {
        return JSON.parse(window.localStorage.getItem(currentKey) || "[]");
      } catch (error) {
        console.warn("Visit fragments unavailable.", error);
        return [];
      }
    }

    function saveCurrentFragments(records) {
      try {
        window.localStorage.setItem(currentKey, JSON.stringify(records));
      } catch (error) {
        console.warn("Visit fragments unavailable.", error);
      }
    }

    function getPreviousVisit() {
      try {
        return JSON.parse(window.localStorage.getItem(previousKey) || "null");
      } catch (error) {
        console.warn("Previous visit fragments unavailable.", error);
        return null;
      }
    }

    function savePreviousVisit(visit) {
      try {
        window.localStorage.setItem(previousKey, JSON.stringify(visit));
      } catch (error) {
        console.warn("Previous visit fragments unavailable.", error);
      }
    }

    function addCurrentFragment(category, text) {
      const trimmedText = String(text || "").trim();

      if (!trimmedText) {
        return;
      }

      const records = getCurrentFragments();
      records.push({
        id: String(Date.now()),
        category,
        text: trimmedText
      });
      saveCurrentFragments(records);
      renderVisitState();
    }

    function renderVisitState() {
      const current = getCurrentFragments();
      const previous = getPreviousVisit();

      currentList.innerHTML = current.length
        ? current.map((record) => renderVisitFragment(record, true)).join("")
        : `<p class="measurement-empty">這次還沒有診前碎片。先點一個常用項目就好。</p>`;

      archiveButton.disabled = !current.length;

      if (!previous || !previous.records || !previous.records.length) {
        previousSummary.innerHTML = `<strong>尚未封存</strong><span>回診後按左邊按鈕，這裡會出現上一回診的整理。</span>`;
        previousList.innerHTML = config.samplePrevious
          .map((item) => `<article class="visit-fragment is-sample"><small>範例 ${escapeHtml(item.category)}</small><p>${escapeHtml(item.text)}</p></article>`)
          .join("");
        return;
      }

      previousSummary.innerHTML = `<strong>${escapeHtml(previous.date)}</strong><span>${previous.records.length} 個碎片已封存</span>`;
      previousList.innerHTML = previous.records.map((record) => renderVisitFragment(record, false)).join("");
    }

    function renderVisitFragment(record, canDelete) {
      return `
        <article class="visit-fragment">
          <small>${escapeHtml(record.category)}</small>
          <p>${escapeHtml(record.text)}</p>
          ${canDelete ? `<button class="inline-delete visit-fragment-remove" type="button" data-id="${escapeHtml(record.id)}">移除</button>` : ""}
        </article>
      `;
    }

    chipGroups.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-category]");

      if (!button) {
        return;
      }

      addCurrentFragment(button.dataset.category, button.dataset.text);
    });

    manualForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const formData = new FormData(manualForm);
      addCurrentFragment(String(formData.get("category") || ""), String(formData.get("text") || ""));
      manualForm.reset();
    });

    currentList.addEventListener("click", (event) => {
      const button = event.target.closest(".visit-fragment-remove");

      if (!button) {
        return;
      }

      saveCurrentFragments(getCurrentFragments().filter((record) => record.id !== button.dataset.id));
      renderVisitState();
    });

    archiveButton.addEventListener("click", () => {
      const current = getCurrentFragments();

      if (!current.length) {
        return;
      }

      savePreviousVisit({
        date: formatVisitDate(new Date()),
        records: current
      });
      saveCurrentFragments([]);
      renderVisitState();
    });

    renderVisitState();
  }

  function renderCustomMeasurements(config) {
    const storageKey = `md-piece-custom-measurements-${featureKey}`;
    const customPanel = document.createElement("section");
    customPanel.className = "custom-measurement-panel";
    customPanel.innerHTML = `
      <div class="custom-measurement-heading">
        <div>
          <p class="measurement-kicker">HEALTH LOG</p>
          <h2>${escapeHtml(config.title)}</h2>
          <p>先點一個項目，再點常用數字與情境，少打字也能留下清楚紀錄。</p>
        </div>
        <span class="measurement-storage-badge">先記重點就好</span>
      </div>
      <div class="measurement-summary">
        <article>
          <small>已記錄</small>
          <strong id="measurement-total">0 筆</strong>
        </article>
        <article>
          <small>最近記下</small>
          <strong id="measurement-latest">尚未新增</strong>
        </article>
        <article>
          <small>可點選項目</small>
          <strong>${config.presets.length} 個</strong>
        </article>
      </div>
      <div class="measurement-workspace">
        <div class="measurement-compose">
          <div class="measurement-block-title">
            <h3>今天要記哪一項？</h3>
            <p>點選後會自動帶入名稱、單位、常用數值與情境標籤。</p>
          </div>
          <div class="measurement-presets">
            ${config.presets
              .map(
                (preset, index) => `
                  <button class="measurement-preset" type="button" data-index="${index}">
                    <span>${escapeHtml(preset.name)}</span>
                    <small>${escapeHtml(preset.unit)}</small>
                  </button>
                `
              )
              .join("")}
          </div>
          <div class="measurement-guidance">
            <p id="measurement-reference">先選一個項目，這裡會顯示一般衛教參考。</p>
            <div class="measurement-chip-row" id="measurement-value-choice-group" hidden>
              <span>數值快選</span>
              <div class="measurement-choice-list" id="measurement-value-choices"></div>
            </div>
          </div>
          <form class="measurement-form" id="measurement-form">
            <label>
              <span>項目名稱</span>
              <input name="name" type="text" placeholder="例如：血糖" required>
            </label>
            <label class="measurement-value-field">
              <span>量到的數字</span>
              <input name="value" type="text" inputmode="decimal" placeholder="例如：112" required>
            </label>
            <div class="blood-pressure-fields measurement-form-wide" hidden>
              <label>
                <span>收縮壓</span>
                <input name="systolic" type="text" inputmode="numeric" placeholder="例如：120">
              </label>
              <label>
                <span>舒張壓</span>
                <input name="diastolic" type="text" inputmode="numeric" placeholder="例如：80">
              </label>
              <p>血壓通常會記兩個數字，前面是收縮壓，後面是舒張壓。</p>
            </div>
            <div class="bmi-fields measurement-form-wide" hidden>
              <label>
                <span>身高</span>
                <input name="heightCm" type="text" inputmode="decimal" placeholder="例如：165">
              </label>
              <label>
                <span>體重</span>
                <input name="weightKg" type="text" inputmode="decimal" placeholder="例如：60">
              </label>
              <output class="bmi-result" id="bmi-result">輸入身高與體重後會自動計算 BMI</output>
            </div>
            <label>
              <span>單位</span>
              <input name="unit" type="text" placeholder="例如：mg/dL">
            </label>
            <label>
              <span>量測時間</span>
              <input name="measuredAt" type="datetime-local">
            </label>
            <label class="measurement-form-wide">
              <span>當時狀況</span>
              <input name="note" type="text" placeholder="可點下面標籤，例如：早餐前、頭暈時">
            </label>
            <div class="measurement-chip-row measurement-form-wide">
              <span>情境快選</span>
              <div class="measurement-choice-list" id="measurement-note-choices"></div>
            </div>
            <div class="measurement-chip-row measurement-form-wide">
              <span>時間快選</span>
              <div class="measurement-choice-list" id="measurement-time-choices">
                <button type="button" data-action="now">現在</button>
                <button type="button" data-note="早餐前">早餐前</button>
                <button type="button" data-note="飯後 2 小時">飯後 2 小時</button>
                <button type="button" data-note="睡前">睡前</button>
                <button type="button" data-note="運動後">運動後</button>
              </div>
            </div>
            <button class="measurement-submit" type="submit">存下紀錄</button>
          </form>
        </div>
        <div class="measurement-history">
          <div class="measurement-block-title">
            <h3>最近紀錄</h3>
            <p>新增後會依時間排在這裡，回診前可以直接掃一遍。</p>
          </div>
          <div class="measurement-list" id="measurement-list"></div>
        </div>
      </div>
    `;

    note.before(customPanel);

    const form = customPanel.querySelector("#measurement-form");
    const list = customPanel.querySelector("#measurement-list");
    const total = customPanel.querySelector("#measurement-total");
    const latest = customPanel.querySelector("#measurement-latest");
    const reference = customPanel.querySelector("#measurement-reference");
    const presetButtons = Array.from(customPanel.querySelectorAll(".measurement-preset"));
    const valueChoiceGroup = customPanel.querySelector("#measurement-value-choice-group");
    const valueChoices = customPanel.querySelector("#measurement-value-choices");
    const noteChoices = customPanel.querySelector("#measurement-note-choices");
    const timeChoices = customPanel.querySelector("#measurement-time-choices");
    const valueField = customPanel.querySelector(".measurement-value-field");
    const valueInput = form.elements.value;
    const noteInput = form.elements.note;
    const bloodPressureFields = customPanel.querySelector(".blood-pressure-fields");
    const systolicInput = form.elements.systolic;
    const diastolicInput = form.elements.diastolic;
    const bmiFields = customPanel.querySelector(".bmi-fields");
    const heightInput = form.elements.heightCm;
    const weightInput = form.elements.weightKg;
    const bmiResult = customPanel.querySelector("#bmi-result");
    let selectedPreset = null;

    function getRecords() {
      try {
        return JSON.parse(window.localStorage.getItem(storageKey) || "[]");
      } catch (error) {
        console.warn("Custom measurements unavailable.", error);
        return [];
      }
    }

    function saveRecords(records) {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(records));
      } catch (error) {
        console.warn("Custom measurements unavailable.", error);
      }
    }

    function renderRecords() {
      const records = getRecords();
      total.textContent = `${records.length} 筆`;
      latest.textContent = records[0] ? records[0].name : "尚未新增";

      if (!records.length) {
        list.innerHTML = `<p class="measurement-empty">${escapeHtml(config.emptyText || "還沒有紀錄。可以先記一筆今天最想追蹤的數據。")}</p>`;
        return;
      }

      list.innerHTML = records
        .map(
          (record) => `
            <article class="measurement-record">
              <div>
                <small>${escapeHtml(formatRecordTime(record.measuredAt))}</small>
                <strong>${escapeHtml(record.name)}</strong>
                <p>${escapeHtml(record.value)}${record.unit ? ` ${escapeHtml(record.unit)}` : ""}</p>
                ${record.note ? `<span>${escapeHtml(record.note)}</span>` : ""}
              </div>
              <button class="measurement-delete" type="button" data-id="${escapeHtml(record.id)}">移除</button>
            </article>
          `
        )
        .join("");
    }

    function selectPreset(preset, button, options = {}) {
      selectedPreset = preset || {};
      form.elements.name.value = selectedPreset.name || "";
      form.elements.unit.value = selectedPreset.unit || "";
      setMeasurementMode(selectedPreset.type || "standard");
      renderPresetChoices(selectedPreset);

      presetButtons.forEach((presetButton) => {
        const isSelected = presetButton === button;
        presetButton.classList.toggle("is-selected", isSelected);
        presetButton.setAttribute("aria-pressed", isSelected ? "true" : "false");
      });

      if (options.shouldFocus === false) {
        return;
      }

      if (selectedPreset.type === "bloodPressure") {
        systolicInput.focus();
        return;
      }

      if (selectedPreset.type === "bmi") {
        heightInput.focus();
        return;
      }

      valueInput.focus();
    }

    function renderPresetChoices(preset) {
      reference.textContent = preset.reference || "這裡提供一般衛教參考；個人目標仍以醫師或照護團隊建議為準。";

      const choices = preset.type === "bloodPressure"
        ? (preset.quickPairs || []).map(
            (pair) => `<button type="button" data-systolic="${escapeHtml(pair.systolic)}" data-diastolic="${escapeHtml(pair.diastolic)}">${escapeHtml(pair.label)}</button>`
          )
        : preset.type === "bmi"
          ? [
              ...(preset.quickHeights || []).map(
                (height) => `<button type="button" data-height="${escapeHtml(height)}">身高 ${escapeHtml(height)} cm</button>`
              ),
              ...(preset.quickWeights || []).map(
                (weight) => `<button type="button" data-weight="${escapeHtml(weight)}">體重 ${escapeHtml(weight)} kg</button>`
              )
            ]
        : (preset.quickValues || []).map(
            (value) => `<button type="button" data-value="${escapeHtml(value)}">${escapeHtml(value)}${preset.unit ? ` ${escapeHtml(preset.unit)}` : ""}</button>`
          );

      valueChoiceGroup.hidden = !choices.length;
      valueChoices.innerHTML = choices.join("");

      const noteChipText = uniqueValues([...(preset.noteChips || []), "不舒服時", "回診想問"]);
      noteChoices.innerHTML = noteChipText
        .map((chip) => `<button type="button" data-note="${escapeHtml(chip)}">${escapeHtml(chip)}</button>`)
        .join("");
    }

    presetButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const preset = config.presets[Number(button.dataset.index)];
        selectPreset(preset, button);
      });
    });

    valueChoices.addEventListener("click", (event) => {
      const button = event.target.closest("button");

      if (!button) {
        return;
      }

      if (button.dataset.systolic) {
        systolicInput.value = button.dataset.systolic;
        diastolicInput.value = button.dataset.diastolic || "";
        appendNoteChip("點選血壓快選");
        return;
      }

      if (button.dataset.height) {
        heightInput.value = button.dataset.height;
        updateBmiResult();
        weightInput.focus();
        return;
      }

      if (button.dataset.weight) {
        weightInput.value = button.dataset.weight;
        updateBmiResult();
        return;
      }

      valueInput.value = button.dataset.value || "";
      valueInput.focus();
    });

    [heightInput, weightInput].forEach((input) => {
      input.addEventListener("input", updateBmiResult);
    });

    noteChoices.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-note]");

      if (!button) {
        return;
      }

      appendNoteChip(button.dataset.note);
    });

    timeChoices.addEventListener("click", (event) => {
      const button = event.target.closest("button");

      if (!button) {
        return;
      }

      if (button.dataset.action === "now") {
        setDefaultMeasuredAt(form);
        return;
      }

      appendNoteChip(button.dataset.note);
    });

    form.addEventListener("submit", (event) => {
      event.preventDefault();

      const formData = new FormData(form);
      const isBloodPressure = form.dataset.measurementType === "bloodPressure";
      const isBmi = form.dataset.measurementType === "bmi";
      const systolic = String(formData.get("systolic") || "").trim();
      const diastolic = String(formData.get("diastolic") || "").trim();
      const heightCm = String(formData.get("heightCm") || "").trim();
      const weightKg = String(formData.get("weightKg") || "").trim();
      const bmi = calculateBmi(heightCm, weightKg);
      const bmiCategory = bmi ? getTaiwanBmiCategory(bmi) : "";
      const record = {
        id: String(Date.now()),
        name: String(formData.get("name") || "").trim(),
        value: isBloodPressure ? `${systolic}/${diastolic}` : isBmi ? String(bmi) : String(formData.get("value") || "").trim(),
        unit: String(formData.get("unit") || "").trim(),
        measuredAt: String(formData.get("measuredAt") || ""),
        note: buildRecordNote(String(formData.get("note") || "").trim(), isBmi ? `身高 ${heightCm} cm、體重 ${weightKg} kg、${bmiCategory}` : ""),
        type: isBloodPressure ? "bloodPressure" : isBmi ? "bmi" : "standard"
      };

      if (!record.name || (isBloodPressure ? (!systolic || !diastolic) : isBmi ? !bmi : !record.value)) {
        return;
      }

      const records = [record, ...getRecords()];
      saveRecords(records);
      form.reset();
      setDefaultMeasuredAt(form);
      selectPreset(config.presets[0], presetButtons[0], { shouldFocus: false });
      renderRecords();
    });

    list.addEventListener("click", (event) => {
      const deleteButton = event.target.closest(".measurement-delete");

      if (!deleteButton) {
        return;
      }

      const records = getRecords().filter((record) => record.id !== deleteButton.dataset.id);
      saveRecords(records);
      renderRecords();
    });

    setDefaultMeasuredAt(form);
    selectPreset(config.presets[0], presetButtons[0], { shouldFocus: false });
    renderRecords();

    function appendNoteChip(chip) {
      if (!chip) {
        return;
      }

      const current = noteInput.value
        .split("、")
        .map((item) => item.trim())
        .filter(Boolean);

      if (!current.includes(chip)) {
        current.push(chip);
      }

      noteInput.value = current.join("、");
    }

    function setMeasurementMode(type) {
      const isBloodPressure = type === "bloodPressure";
      const isBmi = type === "bmi";
      form.dataset.measurementType = isBloodPressure ? "bloodPressure" : isBmi ? "bmi" : "standard";
      valueField.hidden = isBloodPressure || isBmi;
      bloodPressureFields.hidden = !isBloodPressure;
      valueInput.required = !isBloodPressure && !isBmi;
      systolicInput.required = isBloodPressure;
      diastolicInput.required = isBloodPressure;

      if (isBloodPressure) {
        valueInput.value = "";
      } else {
        systolicInput.value = "";
        diastolicInput.value = "";
      }

      bmiFields.hidden = !isBmi;
      heightInput.required = isBmi;
      weightInput.required = isBmi;

      if (!isBmi) {
        heightInput.value = "";
        weightInput.value = "";
      }

      updateBmiResult();
    }

    function updateBmiResult() {
      const bmi = calculateBmi(heightInput.value, weightInput.value);

      if (!bmi) {
        bmiResult.textContent = "輸入身高與體重後會自動計算 BMI";
        bmiResult.dataset.state = "empty";
        return;
      }

      const category = getTaiwanBmiCategory(bmi);
      bmiResult.textContent = `BMI ${bmi}，${category}`;
      bmiResult.dataset.state = "ready";
    }
  }

  function calculateBmi(heightCm, weightKg) {
    const height = Number(String(heightCm).trim());
    const weight = Number(String(weightKg).trim());

    if (!height || !weight || height <= 0 || weight <= 0) {
      return "";
    }

    const heightM = height / 100;
    return (weight / (heightM * heightM)).toFixed(1);
  }

  function getTaiwanBmiCategory(bmiValue) {
    const bmi = Number(bmiValue);

    if (bmi < 18.5) {
      return "偏輕";
    }

    if (bmi < 24) {
      return "健康範圍";
    }

    if (bmi < 27) {
      return "過重範圍";
    }

    return "肥胖範圍";
  }

  function buildRecordNote(note, generatedText) {
    return [note, generatedText].filter(Boolean).join("、");
  }

  function parseMedicationText(value, config) {
    const lines = String(value || "")
      .split(/\r?\n|；|;/)
      .map((line) => line.trim())
      .filter(Boolean);

    return lines.map((line) => {
      const doseMatch = line.match(/(\d+(?:\.\d+)?\s?(?:mg|mcg|g|ml|mL|顆|錠|粒|IU|單位))/i);
      const dose = doseMatch ? doseMatch[1].replace(/\s+/, " ") : "劑量待確認";
      const nameSource = doseMatch ? line.slice(0, doseMatch.index).trim() : line;
      const name = (nameSource || line.split(/\s+/)[0] || "藥名待確認").replace(/[，,、。]+$/, "");
      const timing = (config.slots || []).filter((slot) => line.includes(slot));

      if (!timing.length && /必要時|需要時|疼痛|發燒/.test(line)) {
        timing.push("必要時");
      }

      return {
        name,
        dose,
        timing: timing.length ? uniqueValues(timing) : ["待確認"],
        purpose: "用途待確認",
        caution: "辨識後請再核對藥袋；不確定的地方可留到回診或問藥師。"
      };
    });
  }

  function formatVisitDate(date) {
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, "0");
    const dd = String(date.getDate()).padStart(2, "0");
    const hh = String(date.getHours()).padStart(2, "0");
    const min = String(date.getMinutes()).padStart(2, "0");

    return `${yyyy}/${mm}/${dd} ${hh}:${min}`;
  }

  function setDefaultMeasuredAt(scope = document) {
    const measuredAt = scope.querySelector('input[name="measuredAt"]');

    if (!measuredAt) {
      return;
    }

    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    measuredAt.value = now.toISOString().slice(0, 16);
  }

  function formatRecordTime(value) {
    if (!value) {
      return "未填時間";
    }

    return value.replace("T", " ");
  }

  function uniqueValues(values) {
    return values.filter((value, index) => value && values.indexOf(value) === index);
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
})();

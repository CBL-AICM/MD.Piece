(function () {
  const featureKey = document.body.dataset.feature;
  const feature = window.MDPieceFeatures && window.MDPieceFeatures[featureKey];

  if (!feature) {
    return;
  }

  document.title = `${feature.title} | MD.Piece`;

  document.getElementById("feature-title").textContent = feature.title;
  document.getElementById("feature-subtitle").textContent = feature.subtitle;
  document.getElementById("feature-tag").textContent = feature.tag;

  const cards = document.getElementById("feature-cards");
  cards.innerHTML = feature.cards
    .map(
      (card) => `
        <article class="feature-card">
          <small>${card.label}</small>
          <strong>${card.value}</strong>
          <p>${card.text}</p>
        </article>
      `
    )
    .join("");

  const sections = document.getElementById("feature-sections");
  sections.innerHTML = feature.sections
    .map(
      (section) => `
        <section class="feature-section">
          <h2>${section.title}</h2>
          <ul class="feature-list">
            ${section.items.map((item) => `<li>${item}</li>`).join("")}
          </ul>
        </section>
      `
    )
    .join("");

  const note = document.getElementById("feature-note");
  note.innerHTML = `<h2>備註</h2><p>${feature.note}</p>`;

  if (feature.customMeasurements) {
    renderCustomMeasurements(feature.customMeasurements);
  }

  function renderCustomMeasurements(config) {
    const storageKey = `md-piece-custom-measurements-${featureKey}`;
    const customPanel = document.createElement("section");
    customPanel.className = "custom-measurement-panel";
    customPanel.innerHTML = `
      <div class="custom-measurement-heading">
        <div>
          <p class="measurement-kicker">我的紀錄</p>
          <h2>${escapeHtml(config.title)}</h2>
          <p>選一個常用項目，或填入我的生理項目。</p>
        </div>
        <span class="measurement-storage-badge">今天也可以慢慢記</span>
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
          <small>常用項目</small>
          <strong>${config.presets.length} 個</strong>
        </article>
      </div>
      <div class="measurement-workspace">
        <div class="measurement-compose">
          <div class="measurement-block-title">
            <h3>想記哪一項？</h3>
            <p>點選常用項目會自動帶入名稱與單位，也可以直接自己輸入。</p>
          </div>
          <div class="measurement-presets">
            ${config.presets
              .map(
                (preset) => `
                  <button class="measurement-preset" type="button" data-name="${escapeHtml(preset.name)}" data-unit="${escapeHtml(preset.unit)}">
                    ${escapeHtml(preset.name)}
                  </button>
                `
              )
              .join("")}
          </div>
          <form class="measurement-form" id="measurement-form">
            <label>
              <span>項目名稱</span>
              <input name="name" type="text" placeholder="例如：血糖" required>
            </label>
            <label>
              <span>量到的數字</span>
              <input name="value" type="text" placeholder="例如：112" required>
            </label>
            <label>
              <span>單位（可不填）</span>
              <input name="unit" type="text" placeholder="例如：mg/dL">
            </label>
            <label>
              <span>量測時間</span>
              <input name="measuredAt" type="datetime-local">
            </label>
            <label class="measurement-form-wide">
              <span>當時狀況</span>
              <input name="note" type="text" placeholder="例如：早餐前、運動後、睡前">
            </label>
            <button class="measurement-submit" type="submit">存下這筆</button>
          </form>
        </div>
        <div class="measurement-history">
          <div class="measurement-block-title">
            <h3>剛剛記下的數據</h3>
            <p>新增後會依時間排在這裡，回頭查看比較方便。</p>
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
    const presetButtons = Array.from(customPanel.querySelectorAll(".measurement-preset"));

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
        list.innerHTML = `<p class="measurement-empty">還沒有紀錄。可以先記一筆今天最想追蹤的數據。</p>`;
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

    presetButtons.forEach((button) => {
      button.addEventListener("click", () => {
        form.elements.name.value = button.dataset.name || "";
        form.elements.unit.value = button.dataset.unit || "";
        form.elements.value.focus();
      });
    });

    form.addEventListener("submit", (event) => {
      event.preventDefault();

      const formData = new FormData(form);
      const record = {
        id: String(Date.now()),
        name: String(formData.get("name") || "").trim(),
        value: String(formData.get("value") || "").trim(),
        unit: String(formData.get("unit") || "").trim(),
        measuredAt: String(formData.get("measuredAt") || ""),
        note: String(formData.get("note") || "").trim()
      };

      if (!record.name || !record.value) {
        return;
      }

      const records = [record, ...getRecords()];
      saveRecords(records);
      form.reset();
      setDefaultMeasuredAt();
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

    setDefaultMeasuredAt();
    renderRecords();
  }

  function setDefaultMeasuredAt() {
    const measuredAt = document.querySelector('input[name="measuredAt"]');

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

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
})();

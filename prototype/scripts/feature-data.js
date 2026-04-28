window.MDPieceFeatureOrder = [
  "medications",
  "symptoms",
  "education",
  "condition-education",
  "symptom-analysis",
  "memo",
  "previsit",
  "labs",
  "ai-bot"
];

window.MDPieceFeatures = {
  medications: {
    title: "藥物",
    boardLines: ["藥物"],
    tag: "用藥紀錄",
    subtitle: "把目前用藥、時段與提醒放在同一頁。",
    color: "#4f88bb",
    hoverColor: "#3071a4",
    cards: [
      { label: "目前用藥", value: "4 項", text: "早餐、午餐、晚餐與睡前用藥。" },
      { label: "待補", value: "1 項", text: "自購止痛藥的品牌與次數。" },
      { label: "今日提醒", value: "1 則", text: "中午頭暈可和降壓藥一起看。" }
    ],
    sections: [
      { title: "目前清單", items: ["Metformin 500 mg 早餐後", "Amlodipine 5 mg 午餐後", "Vitamin B 群 晚餐後", "Gabapentin 300 mg 睡前"] },
      { title: "快速查看", items: ["是否有漏服", "最近是否新增自購藥", "頭暈是否集中在固定時段"] }
    ],
    note: "如果今天還會吃自購止痛藥，先把藥名與次數補進來。"
  },
  symptoms: {
    title: "症狀",
    boardLines: ["症狀"],
    tag: "每日回報",
    subtitle: "只看症狀、時間與強度。",
    color: "#87b8e5",
    hoverColor: "#70a8db",
    cards: [
      { label: "今日紀錄", value: "3 筆", text: "頭暈、疼痛與疲倦。" },
      { label: "最高強度", value: "6 / 10", text: "中午頭暈最明顯。" },
      { label: "夜間變化", value: "1 筆", text: "疼痛會影響睡眠。" }
    ],
    sections: [
      { title: "今天的症狀", items: ["頭暈 6 / 10 午餐後", "疼痛 5 / 10 睡前", "疲倦 4 / 10 下午"] },
      { title: "建議一起記", items: ["症狀前後有沒有吃藥", "發作時的血壓或血糖", "是否影響走路或睡眠"] }
    ],
    note: "頭暈與疼痛的時間都記下來，之後進症狀分析就能直接判讀。"
  },
  education: {
    title: "療效回饋",
    boardLines: ["療效", "回饋"],
    tag: "治療觀察",
    subtitle: "把服藥後感受、症狀變化與治療反應放在同一頁。",
    color: "#b8aab4",
    hoverColor: "#a694a0",
    cards: [
      { label: "今日回饋", value: "2 筆", text: "早餐後精神較穩，午餐後仍有些頭暈。" },
      { label: "療效觀察", value: "1 項", text: "止痛藥後疼痛大約下降到 3 / 10。" },
      { label: "想回診問", value: "1 件", text: "下午頭暈是否和服藥時段有關。" }
    ],
    sections: [
      { title: "今天的療效回饋", items: ["早餐後 30 分鐘精神較穩", "午餐後頭暈 4 / 10", "睡前止痛藥後疼痛下降"] },
      { title: "回診時可直接說", items: ["哪個時間最有效", "哪個時間最不舒服", "服藥後多久開始出現反應"] }
    ],
    note: "把有效和不舒服的時間一起留著，回診時會比單純說不舒服更清楚。"
  },
  "condition-education": {
    title: "生理數據紀錄",
    boardLines: ["生理數據", "紀錄"],
    tag: "自訂填寫",
    subtitle: "依照自己的照護需要，記下每天想追蹤的數字與身體狀況。",
    color: "#d8e8f6",
    hoverColor: "#c5dbef",
    cards: [
      { label: "我想追蹤", value: "我的生理項目", text: "血糖、血壓、睡眠，或任何想留意的項目。" },
      { label: "每次紀錄", value: "數值 / 單位", text: "記下量到的數字，也可以補上當時狀況。" },
      { label: "回診可用", value: "近期整理", text: "把平常的變化留住，回診時更容易說清楚。" }
    ],
    sections: [
      { title: "常見可記錄的數據", items: ["血糖 mg/dL", "血壓 mmHg", "體溫 °C", "體重 kg", "睡眠 小時"] },
      { title: "也可以記自己的項目", items: ["輸入想追蹤的項目", "填上量到的數字與單位", "補充量測時間或身體感覺"] }
    ],
    customMeasurements: {
      title: "我的健康數據",
      presets: [
        { name: "血糖", unit: "mg/dL" },
        { name: "血壓", unit: "mmHg" },
        { name: "體溫", unit: "°C" },
        { name: "體重", unit: "kg" },
        { name: "睡眠", unit: "小時" }
      ]
    },
    note: "數字不用一次填得很完整；先留下今天量到的結果和當時感覺，之後看趨勢會更清楚。"
  },
  "symptom-analysis": {
    title: "症狀分析",
    boardLines: ["症狀", "分析"],
    tag: "關聯判讀",
    subtitle: "症狀、時段與藥物放在一起看。",
    color: "#5f95c6",
    hoverColor: "#4d82b4",
    cards: [
      { label: "目前提醒", value: "2 個", text: "頭暈與降壓藥、疼痛與睡眠。" },
      { label: "最明顯", value: "頭暈", text: "常在固定時段出現。" },
      { label: "可回診討論", value: "1 件", text: "降壓藥時程是否要調整。" }
    ],
    sections: [
      { title: "目前線索", items: ["中午後頭暈較明顯", "夜間疼痛後隔天比較疲倦", "漏服後隔天波動較大"] },
      { title: "帶去回診", items: ["頭暈發作時間", "服藥時間", "血壓或血糖量測值"] }
    ],
    note: "若頭暈都集中在固定時段，回診時可以直接從藥物時程開始談。"
  },
  memo: {
    title: "memo",
    boardLines: ["memo"],
    tag: "快速備忘",
    subtitle: "先把短句留住，再慢慢整理。",
    color: "#cbc0ca",
    hoverColor: "#b8abb6",
    cards: [
      { label: "待補", value: "2 則", text: "OTC 藥名與回診問題。" },
      { label: "格式", value: "短句", text: "不需要像正式表單。" },
      { label: "用途", value: "暫存", text: "之後可轉進其他頁面。" }
    ],
    sections: [
      { title: "先記在這裡", items: ["補上自購止痛藥品牌", "整理這次回診想問的問題"] },
      { title: "之後再整理", items: ["用藥內容轉去藥物頁", "回診內容轉去診前紀錄"] }
    ],
    note: "想到什麼就先記，不必在這一頁把所有內容一次整理完。"
  },
  previsit: {
    title: "診前紀錄",
    boardLines: ["診前", "紀錄"],
    tag: "回診前整理",
    subtitle: "這次變化、想問醫師、本次目標。",
    color: "#d6e4f3",
    hoverColor: "#c0d6eb",
    cards: [
      { label: "這次變化", value: "1 筆", text: "最近兩週頭暈增加。" },
      { label: "想問醫師", value: "1 題", text: "是否與降壓藥時段有關。" },
      { label: "本次目標", value: "1 件", text: "補齊自購藥資訊。" }
    ],
    sections: [
      { title: "進診間前", items: ["先看最近最明顯的變化", "先準備一句最想問的問題", "確認有沒有漏掉自購藥"] },
      { title: "這頁要完成", items: ["這次變化", "想問醫師", "本次目標"] }
    ],
    note: "先把最近變化和最想問的一句話寫好，進診間會更容易開口。"
  },
  labs: {
    title: "檢驗報告資訊站",
    boardLines: ["檢驗報告", "資訊站"],
    tag: "報告重點",
    subtitle: "先看常用指標，再看和用藥的關聯。",
    color: "#a4c7e9",
    hoverColor: "#87b8e5",
    cards: [
      { label: "常看指標", value: "3 項", text: "HbA1c、腎功能與肝功能。" },
      { label: "先比", value: "前一次", text: "看是上升、下降還是持平。" },
      { label: "再問", value: "目前用藥", text: "變化是否會影響既有藥物。" }
    ],
    sections: [
      { title: "目前重點", items: ["HbA1c 血糖趨勢", "Creatinine / eGFR 腎功能", "AST / ALT 肝功能"] },
      { title: "看報告時", items: ["先和上次比", "再問是否影響現在的藥", "若異常，問下次多久追蹤"] }
    ],
    note: "先比前一次數值，再問醫師這些變化和目前藥物有沒有關係。"
  },
  "ai-bot": {
    title: "AI 機器人",
    boardLines: ["AI", "機器人"],
    tag: "衛教問答",
    subtitle: "可以直接做醫療衛教詢問。",
    color: "#9bb7d6",
    hoverColor: "#83a4c9",
    cards: [
      { label: "可問", value: "3 類", text: "高血壓頭暈、糖尿病照護、報告怎麼看。" },
      { label: "使用方式", value: "直接問", text: "先做成容易開口的入口。" },
      { label: "目前定位", value: "衛教", text: "不直接替代醫療判斷。" }
    ],
    sections: [
      { title: "常見提問", items: ["高血壓和頭暈要注意什麼", "糖尿病日常飲食怎麼調整", "這份報告可以先看哪幾個指標"] },
      { title: "問之前可先準備", items: ["最近症狀時間", "目前用藥", "最近量測數值"] }
    ],
    note: "如果要問得更準，先把症狀時間與目前用藥一起帶進來。"
  }
};

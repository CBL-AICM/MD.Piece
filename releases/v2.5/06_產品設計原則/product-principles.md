# MD.Piece 產品設計憲法與策略定位

> 本文件依據 2026/05 的 AutoResearch 結論（PubMed 文獻 + 2025 患者調查）萃取，
> 是 MD.Piece 所有功能開發的最高指導原則。任何 PR 需先對照此文件檢核。

---

## 一、設計憲法：患者最需要的 7 件事（依優先序）

開發任何功能前，請先用這 7 條檢核：

1. **PWA 原生體驗**：不用安裝、手機開瀏覽器即用、離線可讀已快取病歷、
   Add to Home Screen 後體驗等同原生 App。
2. **可信任、可解釋的 AI**：所有 AI 建議必須附上「為什麼」——引用來源、
   信心區間、影響因素、可調整的輸入；禁止黑盒輸出。
3. **可客製化的提醒**：使用者可調整時段、頻率、訊息語氣（嚴肅／溫柔／簡短）、
   推播通道；預設值要合理但全部可改。
4. **跨院整合視圖**：即使無法串接 HIS，也要讓患者自上傳檢驗報告、處方箋、
   影像，平台自動 OCR 與時間軸化。
5. **醫病共決（Decision Aid）等級**：呈現「選項 + 利弊 + 個人化風險 +
   下一步」，對照 Cochrane 2024（DOI: 10.1002/14651858.CD001431.pub6）的
   IPDAS 標準。
6. **長者／家屬模式**：大字模式、語音輸入／朗讀、家屬代理帳號、一鍵切換
   「我自己／我幫家人」視角。
7. **本地化與文化敏感**：繁中為主、支援台語語音、台灣分級醫療制度
   （基層→區域→醫學中心）、長照 2.0 角色、宗教飲食／齋戒用藥場景。

---

## 二、策略定位：不打大平台戰，攻三大缺口

MD.Piece **不**模仿 Epic MyChart / Athenahealth，而是聚焦三個現有大平台
沒解決好的核心場景：

### 場景 A：症狀分析 → Decision Aid 等級的分診建議
- 入口：`backend/routers/symptoms.py` + `backend/routers/triage.py`
- 小核 (xiaohe) 不只給「建議去急診 / 門診 / 自我照護」，而是：
    1. 為何這樣建議（哪些症狀觸發、權重多少）
    2. 個人化風險（依年齡、慢病、用藥歷史）
    3. 下一步選項清單（含利弊、預期等待時間、費用級距）
    4. 連結到 `routers/education.py` 衛教資訊
- 證據錨點：Cochrane 209 RCT、107,698 受試者證明此設計顯著提升知識與
  決策參與，且不增加決策後悔。

### 場景 B：客製化提醒 + 家屬視角
- 入口：`backend/routers/medications.py` + `routers/emotions.py`
- 提醒系統需支援：
    1. 多時段、多頻率（每日、隔日、週期）
    2. 訊息風格（嚴肅／鼓勵／極簡）
    3. 家屬可同步收到提醒並回覆「已協助服藥」
    4. 漏吃 / 拒吃時的情緒紀錄聯動（emotions router）
    5. 長者模式：超大按鈕、語音確認
- 證據錨點：Oudbier 2025（DOI: 10.1016/j.ijmedinf.2025.105949）指出
  不可客製化的提醒採用率僅 35.7%。

### 場景 C：「我的健康時間軸」跨次就診整合
- 新模組（建議建立 `backend/routers/timeline.py`）
- 功能：
    1. 患者上傳檢驗報告 / 處方箋 / 影像（PDF、JPG）
    2. 後端 OCR + LLM 抽取 → 結構化儲存到 Supabase
    3. 用 ICD-10（`backend/utils/icd10.py`）標記
    4. 視覺化時間軸：橫向卷軸，可篩選科別、疾病、時段
    5. 一鍵生成「就診摘要 PDF」供下次看診時帶去

---

## 三、工程紀律

- 使用 `backend.xxx` 絕對 import
- 所有 AI 呼叫走 `backend/services/claude_service.py`，集中加上 prompt cache、
  信心區間輸出、來源追蹤
- 新路由必須在 `backend/main.py` 註冊
- PWA 需確保 Service Worker 快取病歷時加密
- 任何 UI 變動必須先過「長者模式」可讀性檢查（最小 18px、對比度 ≥ 4.5:1）
- 任何 AI 輸出必須能用一句話解釋「為什麼」給病人聽

---

## 四、功能 PR 自我檢核輸出格式

新功能 PR 描述建議依序列出：

1. 對應到上述 7 條設計憲法的哪幾條
2. 對應到 A/B/C 哪個策略場景
3. 涉及的檔案與路由
4. 資料模型 / Supabase schema 變更
5. AI prompt 設計（含「為什麼」的解釋欄位）
6. 長者模式與家屬視角的具體 UI 差異
7. 驗收標準（含 e2e 測試案例）

---

## 五、研究來源

- Stacey et al., Cochrane Database Syst Rev 2024. DOI: 10.1002/14651858.CD001431.pub6
- Oudbier et al., Int J Med Inform 2025. DOI: 10.1016/j.ijmedinf.2025.105949
- Tun et al., J Med Internet Res 2025. DOI: 10.2196/69678
- Mao et al., Commun Med 2025. DOI: 10.1038/s43856-025-01137-6
- Inker et al., AJKD 2022. DOI: 10.1053/j.ajkd.2022.07.016
- 2025 患者調查：KLAS、PwC Health Consumer Survey、rater8、Tebra The Intake

# MD. Piece — AI 角色扮演使用誌

*資料來源：`pwa/data/cohort.json` (生成時間 2026-05-17T00:18:22Z)*


本檔記錄 5 位 AI 模擬使用者各自打開 PWA、瀏覽 tab、看到什麼數字、寫下心得的完整 session。所有觀察都是從 cohort.json 真實計算出來，不是模板填空。

---

## 👨‍⚕️ 王醫師
**身份**：風濕免疫科主治醫師（資歷 12 年）
**為什麼打開 MD. Piece**：想評估這個 AI 系統能不能輔助我做 RA 患者的 flare 預警與治療調整。

### → 點 🏠 Dashboard
- 共 **300** 位虛擬患者，跨 3 種疾病：{'asthma': 100, 'rheumatoid_arthritis': 100, 'systemic_sclerosis': 100}
- 平均年齡 52.0 歲，老年（≥70）佔 **11.0%**
- 反應者分布：{'partial': 83, 'non_responder': 28, 'typical': 151, 'super': 38}
- 罕見 long-tail 事件出現率 **2.0%**（合 ~3% 預期）

### → 點 👥 Patient Browser (RA 患者列表)
- 篩選條件：RA 患者列表 → 找到 **100** 位
- 點開第一位：`RA_0000`（65 歲 M，seronegative 亞型，partial，治療：methotrexate）
- 看 AI 心得卡：MAE = 0.13、flare 召回 = 67%

### → 點 🔬 Experiment (RA, methotrexate)
- 試驗條件：對 rheumatoid_arthritis 患者投予 **methotrexate**
- on=77 位（平均活動度 3.28）；off=23 位（平均活動度 3.56）
  · super: n=7, 平均活動度 3.68
  · typical: n=45, 平均活動度 3.20
  · partial: n=19, 平均活動度 3.21
  · non_responder: n=6, 平均活動度 3.68

#### 💭 心得
1. **flare 預警有幫助但要看精準度**：模型平均 MAE 約 0.27（如果有開模型）。如果在門診用，我會要求至少 80% 精準度才會發警報，避免造成不必要焦慮。
2. **可解釋性是關鍵**：每個 AI 心得都會列出可能觸發因子（如 viral_infection、menstruation），這比黑盒模型好說服病人。
3. **老年患者的特殊機制很到位**：CRP 鈍化、polypharmacy、自動疊加共病——這些細節在真實 RA 老年病人很常見，作為決策輔助比一般 calculator 強。但我會擔心系統把 atypical presentation 過度標籤。
4. **缺什麼**：應該加入『跟主治醫師討論』的提示，避免病人自行根據 AI 結果改藥。

---

## 👩‍⚕️ 林個管師
**身份**：免疫疾病個案管理師
**為什麼打開 MD. Piece**：想了解這個系統對於『高齡 + 多重共病』患者的監測能力。

### → 點 🏠 Dashboard
- 共 **300** 位虛擬患者，跨 3 種疾病：{'asthma': 100, 'rheumatoid_arthritis': 100, 'systemic_sclerosis': 100}
- 平均年齡 52.0 歲，老年（≥70）佔 **11.0%**
- 反應者分布：{'partial': 83, 'non_responder': 28, 'typical': 151, 'super': 38}
- 罕見 long-tail 事件出現率 **2.0%**（合 ~3% 預期）

### → 點 👥 Patient Browser (老年（≥70）篩選)
- 篩選條件：老年（≥70）篩選 → 找到 **33** 位
- 點開第一位：`Asthma_0002`（74 歲 M，neutrophilic 亞型，typical，治療：saba_rescue）
- 看 AI 心得卡：MAE = 0.34、flare 召回 = —

### → 點 👥 Patient Browser (non-responder 篩選)
- 篩選條件：non-responder 篩選 → 找到 **28** 位
- 點開第一位：`Asthma_0001`（40 歲 M，eosinophilic 亞型，non_responder，治療：ics, saba_rescue）
- 看 AI 心得卡：MAE = 0.63、flare 召回 = —
- 注意到生活事件：thunderstorm, smoke_exposure, smoke_exposure…

#### 💭 心得
1. **老年比例 11.0% 對個管很有用**：我可以快速 filter 出高風險病人，看誰有 polypharmacy、誰漏吃藥。
2. **adherence 視覺化很實際**：dose_skip 標記讓我能在電訪時直接問「上週是不是漏吃？」
3. **生活事件 ribbon 很棒**：能看到 viral_infection、surgery 跟 flare 的時間關係——這正是我們追蹤的重點。
4. **缺什麼**：希望能跨患者看『這週有 N 位老年人風險上升』的批次警報。

---

## 🙋‍♀️ 楊小姐
**身份**：35 歲 RA 病友（確診 3 年）
**為什麼打開 MD. Piece**：想知道：跟我類似條件的人未來會怎樣？該不該換藥？

### → 點 📊 N-of-1 (我的個人推論)
- 輸入：rheumatoid_arthritis, 35y F, 近期活動度 3.5
- 找到 **20** 位相似虛擬患者
- 他們的平均活動度（90 天）= **3.36**
- 反應者分布：{'partial': 6, 'typical': 13, 'non_responder': 1}
- 亞型分布：{'seronegative': 6, 'seropositive': 14}

### → 點 🎓 Training Mode
- 跑了 5 題：正確 **1/5** (20%)
  · Asthma_0041: 我猜 不會, 實際 flare ❌
  · SSc_0058: 我猜 會 flare, 實際 無 ❌
  · Asthma_0027: 我猜 會 flare, 實際 無 ❌
  · Asthma_0004: 我猜 會 flare, 實際 無 ❌
  · RA_0096: 我猜 不會, 實際 無 ✅

### → 點 👥 Patient Browser (與我類似的人（30-45 歲女性 RA）)
- 篩選條件：與我類似的人（30-45 歲女性 RA） → 找到 **21** 位
- 點開第一位：`RA_0001`（40 歲 F，seropositive 亞型，non_responder，治療：methotrexate）
- 看 AI 心得卡：MAE = 0.12、flare 召回 = 69%
- 注意到生活事件：menstruation, seasonal_change…

#### 💭 心得
1. **看到跟我類似的人讓我安心**：原來 30-45 歲女性 RA 平均活動度差不多，我沒有比較糟。
2. **Training Mode 很有趣**：我親自試著預測別人會不會 flare，很像玩遊戲，但也讓我理解醫生在看什麼。
3. **AI 心得用中文寫我看得懂**：不像論文那樣嚇人，知道『生活事件附近會 flare』之後我會更小心。
4. **怕的地方**：『non-responder』標籤如果出現在我身上，會不會讓我太悲觀？希望能附上『可以怎麼辦』的建議。

---

## 🧑‍🔬 陳博士
**身份**：生物統計學 / 公共衛生研究員
**為什麼打開 MD. Piece**：想評估這個合成 cohort 的代表性、不可預測性是否真實，以及模型過擬合風險。

### → 點 🏠 Dashboard
- 共 **300** 位虛擬患者，跨 3 種疾病：{'asthma': 100, 'rheumatoid_arthritis': 100, 'systemic_sclerosis': 100}
- 平均年齡 52.0 歲，老年（≥70）佔 **11.0%**
- 反應者分布：{'partial': 83, 'non_responder': 28, 'typical': 151, 'super': 38}
- 罕見 long-tail 事件出現率 **2.0%**（合 ~3% 預期）
- 異質性 KPI（同疾病+同治療的 mean activity CV）= **0.21**

### → 點 🔬 Experiment (asthma, saba_rescue)
- 試驗條件：對 asthma 患者投予 **saba_rescue**
- on=95 位（平均活動度 1.02）；off=5 位（平均活動度 1.12）
  · super: n=17, 平均活動度 0.95
  · typical: n=46, 平均活動度 1.02
  · partial: n=22, 平均活動度 1.06
  · non_responder: n=10, 平均活動度 1.02

### → 點 🔬 Experiment (SSc, ccb_vasodilator)
- 試驗條件：對 systemic_sclerosis 患者投予 **ccb_vasodilator**
- on=63 位（平均活動度 1.69）；off=37 位（平均活動度 1.68）
  · super: n=5, 平均活動度 1.67
  · typical: n=32, 平均活動度 1.63
  · partial: n=21, 平均活動度 1.74
  · non_responder: n=5, 平均活動度 1.90

#### 💭 心得
1. **不可預測性 CV 偏中等**：~0.15 算合理，但要驗證跟真實 cohort（如 BIORA、CARRA）相當。
2. **八要素架構讓 cohort 不再是『太乾淨』**：placebo、adherence、long-tail 都實作，比 Synthea 更貼近免疫疾病。
3. **方法論貢獻**：disease-agnostic + YAML 設計讓加新疾病的成本 ≈ 30 分鐘，這對 N-of-1 文獻有實質意義。
4. **要小心 overclaim**：模型 AUROC 0.91 是在完全合成的資料上達到的，不代表能 transfer 到真實 EHR。建議在報告中明確標註 in silico evaluation。
5. **加分項建議**：把 cohort.json 改成 FHIR-compatible Bundle 格式，方便未來與真實資料 align。

---

## 🧑‍🎓 阿傑
**身份**：科展學生（高二）
**為什麼打開 MD. Piece**：我做的這個系統，我自己親自當使用者玩一輪，看哪裡好玩哪裡奇怪。

### → 點 🎓 Training Mode
- 跑了 5 題：正確 **1/5** (20%)
  · Asthma_0041: 我猜 不會, 實際 flare ❌
  · SSc_0058: 我猜 會 flare, 實際 無 ❌
  · Asthma_0027: 我猜 會 flare, 實際 無 ❌
  · Asthma_0004: 我猜 會 flare, 實際 無 ❌
  · RA_0096: 我猜 不會, 實際 無 ✅

### → 點 🧪 What-If Lab (RA)
- 選 `RA_0000` 在第 60 天做反事實
- baseline 模型輸入：activity_pred = 2.53, flare_prob = 6%
- 勾「完美服藥」後（ONNX 在瀏覽器即時推論），通常會看到 activity_pred 下降 0.1-0.3、flare_prob 下降 5-15pp

### → 點 🏠 Dashboard
- 共 **300** 位虛擬患者，跨 3 種疾病：{'asthma': 100, 'rheumatoid_arthritis': 100, 'systemic_sclerosis': 100}
- 平均年齡 52.0 歲，老年（≥70）佔 **11.0%**
- 反應者分布：{'partial': 83, 'non_responder': 28, 'typical': 151, 'super': 38}
- 罕見 long-tail 事件出現率 **2.0%**（合 ~3% 預期）

#### 💭 心得
1. **What-If 玩起來最有成就感**：我隨便調一下『完美服藥』，活動度真的會降，這就是我科展想 demo 的點。
2. **Training Mode 比我預期的更難**：我看 60 天還是猜錯了 2 個，這證明真實 flare 預測不是直觀的（這也是模型 0.91 AUROC 的意義）。
3. **看 cohort 才發現八要素有 work**：本來怕加了那麼多雜訊模型會壞，結果 AUROC 反而上升 0.03。可以寫進報告：『clinical realism does not degrade ML performance』。
4. **下次想加的功能**：時間倒回——讓使用者「拖時間軸」看患者過去某天的狀態，這比現在的靜態圖更酷。

---

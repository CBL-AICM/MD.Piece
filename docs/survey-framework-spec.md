# 通用問卷引擎 — 框架規範（Survey Framework Spec）

> 對應後端 `backend/routers/surveys.py`（PR #534）。本文件是「定義一份問卷」的**契約規範**：
> 你依此格式準備題目／選項／計分，POST 進來即可收集作答並取得後台統計分析。
> 問卷定義存在 DB（`surveys` 表），可隨時新增、不需改程式碼。

---

## 1. 名詞

| 名詞 | 說明 |
|---|---|
| **survey（問卷）** | 一份問卷定義：`key` + `title` + `items[]` + `scoring`。 |
| **item（題目）** | 問卷裡的一題，有 `id` / `text` / `type`，依型別再帶 `options` / `scale` 等。 |
| **response（作答）** | 某位填答者對一份問卷的一次作答：`{item_id: value}`。 |
| **score（分數）** | 依 `scoring` 由**純程式碼**算出的數值（規則 5）。 |

---

## 2. 問卷定義（POST /surveys 的 body）

```jsonc
{
  "key": "exp3",                    // 必填：URL 用的 slug。^[a-z0-9][a-z0-9_-]{1,63}$（小寫英數 / - / _，2–64 字），全 app 唯一
  "title": "實驗三：使用負擔問卷",   // 必填：顯示標題
  "description": "評估導入後的主觀負擔與續用意願",  // 選填
  "items": [ /* 見 §3，至少 1 題 */ ],
  "scoring": { "method": "sum_likert" }  // 選填，預設 sum_likert；見 §5
}
```

規則：
- `key` 重複 → `409`；格式不合 → `400`。
- `items` 必須是非空陣列；每題 `id` 不可重複、`type` 必須合法（見 §3）。
- 僅 `role=doctor` 可建立（醫護端／研究端）。

---

## 3. 題型（item types）

每題共同欄位：`id`（字串，問卷內唯一）、`text`（題幹）、`type`。依型別再加欄位。
> 引擎會把整個 item 物件原樣存進 `items`（JSON），所以**額外欄位都會保留**，前端可自由使用。

### 3.1 `likert`（量表題，可計分）
李克特量表，作答為整數。

```jsonc
{
  "id": "q1",
  "text": "我覺得使用這個功能的負擔很小",
  "type": "likert",
  "scale": ["非常不同意", "不同意", "普通", "同意", "非常同意"],  // 建議：長度＝點數，前端據此渲染
  "min": 1,                       // 建議：作答下界
  "max": 5                        // 建議：作答上界
}
```
- **作答值**：整數（例 `1`–`5`）。
- 只有 `likert` 題會被納入 `sum_likert` 計分與「逐題 avg / 分布」統計。
- `reverse`（選填，boolean）：若你要標記反向題，可加此欄位自用；**注意目前引擎不會自動反轉計分**（見 §7 待辦）。

### 3.2 `single`（單選）
```jsonc
{
  "id": "q2",
  "text": "最常使用哪一個功能？",
  "type": "single",
  "options": ["用藥提醒", "健康時間軸", "回診報告"]
}
```
- **作答值**：所選的選項字串（或你定義的選項 id）。
- 統計：各選項計數（`option_counts`）。

### 3.3 `multi`（複選）
```jsonc
{
  "id": "q3",
  "text": "下列哪些讓你願意繼續使用？（可複選）",
  "type": "multi",
  "options": ["介面好懂", "提醒準時", "家屬看得到", "醫師會看"]
}
```
- **作答值**：字串陣列，例 `["介面好懂", "提醒準時"]`。
- 統計：每個被勾選的選項各 +1（`option_counts`）。

### 3.4 `text`（開放文字）
```jsonc
{ "id": "q4", "text": "其他建議（選填）", "type": "text" }
```
- **作答值**：字串。
- 統計：只回報「有幾人作答」（`answered`），**不彙總自由文字內容**（隱私）。

---

## 4. 提交作答（POST /surveys/{key}/responses）

```jsonc
{
  "patient_id": "u_123",          // 填答者識別（沿用 eHEALS 慣例，帶 id、不強制登入）
  "answers": {                    // {item_id: value}
    "q1": 4,
    "q2": "健康時間軸",
    "q3": ["介面好懂", "提醒準時"],
    "q4": "希望字再大一點"
  }
}
```
- 回傳：`{ id, survey_key, score, _persisted: true }`。
- `score` 由 §5 計算；非 `sum_likert` 或無 likert 題時為 `null`。
- 缺答某題沒關係（統計以「有作答者」為母數）。

---

## 5. 計分（scoring）

`scoring.method`：

| method | 行為 |
|---|---|
| `sum_likert`（預設） | 加總所有 `likert` 題的整數作答 → `score`。無 likert 作答則 `score=null`。 |
| `none` | 不計分，`score` 一律 `null`（純描述性問卷）。 |

> 計分是確定性任務，全程純程式碼、不經 LLM（規則 5）。

---

## 6. 後台統計分析（GET /surveys/{key}/stats，限 doctor）

只回**聚合**數字、**不含任何個別作答**（規則 12 / 設計憲法 7 隱私）。

```jsonc
{
  "key": "exp3",
  "title": "實驗三：使用負擔問卷",
  "respondents": 42,                       // 填答人數
  "score": {                               // 數值總分彙總（sum_likert）
    "avg": 15.3, "min": 6, "max": 20, "median": 16, "scored_responses": 42
  },
  "per_item": [
    { "id": "q1", "text": "...", "type": "likert",
      "answered": 42, "avg": 3.8, "min": 1, "max": 5,
      "distribution": { "1": 2, "2": 4, "3": 9, "4": 15, "5": 12 } },
    { "id": "q2", "text": "...", "type": "single",
      "answered": 42, "option_counts": { "健康時間軸": 20, "用藥提醒": 15, "回診報告": 7 } },
    { "id": "q3", "text": "...", "type": "multi",
      "answered": 40, "option_counts": { "介面好懂": 31, "提醒準時": 28, "家屬看得到": 12, "醫師會看": 9 } },
    { "id": "q4", "text": "...", "type": "text", "answered": 18 }
  ]
}
```

---

## 7. 目前限制 / 待辦（誠實揭露，規則 12）

- **反向題**：`reverse` 欄位目前只是標記，引擎**不會自動反轉**計分。若你的量表有反向題，先在出題時正規化，或之後再加 `scoring.reverse_items`。
- **必填驗證**：引擎不強制每題都要作答（缺答以「有作答者」為母數統計）。若需強制，前端先擋。
- **單一計分法**：目前僅 `sum_likert` / `none`。需要加權、分量表（subscale）、切點分級時再擴充 `scoring`。
- **作答端權限**：沿用 eHEALS「帶 `patient_id`、不強制登入」（規則 7，與同領域 sibling 一致）；統計端限 `doctor`。

---

## 8. 端到端範例

1. 建立問卷（doctor）
   ```
   POST /surveys
   { "key":"exp3", "title":"實驗三：使用負擔問卷",
     "items":[
       {"id":"q1","text":"使用負擔很小","type":"likert","scale":["非常不同意","不同意","普通","同意","非常同意"],"min":1,"max":5},
       {"id":"q2","text":"最常用功能","type":"single","options":["用藥提醒","健康時間軸","回診報告"]},
       {"id":"q4","text":"其他建議","type":"text"}
     ],
     "scoring":{"method":"sum_likert"} }
   ```
2. 前端取定義渲染：`GET /surveys/exp3`
3. 填答者送出：`POST /surveys/exp3/responses`（body 見 §4）
4. 後台分析：`GET /surveys/exp3/stats`（doctor）

> 把你已有的題目／選項依 §3 整理好（或直接貼給我），我可以幫你 seed 進 production。

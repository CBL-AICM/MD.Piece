# 健康積分 · 獎勵中心（Rewards）

把使用者「已經在做的事」——填問卷、每天打卡、持續紀錄、完成 eHEALS——換算成積分、
等級、徽章與可兌換獎勵，藉遊戲化提升日常紀錄與回饋的依從度。

## 設計原則

- **積分是對既有紀錄的「唯讀換算」**：App 早已把症狀／生理／情緒／睡眠／服藥／飲食
  與問卷作答各自寫進資料表，所以積分**不需要新的使用者操作、不改任何既有功能、
  也不動門診首頁與底部 tabbar**。只新增一個可選的「獎勵中心」頁（側邊欄進入）。
- **規則 5（確定性運算用純程式碼）**：得分、等級、徽章、可否兌換全是 if-else 算術，
  集中在 `backend/utils/rewards_rules.py`，零 LLM。
- **規則 7（不混寫法）**：讀取端沿用 sibling 日常紀錄 router（emotions/symptoms/
  vitals）「帶 patient_id、不強制登入」的慣例（那些底層資料本來就這樣讀，demo
  帳號也能用）。若日後全 App 改走 JWT 自存取，rewards 應一起改、勿混用。

## 計分規則（院方可在 `rewards_rules.py` 調整）

| 來源 | 給分 |
| --- | --- |
| 填問卷（每份 `survey_responses`） | +20 |
| 每日打卡（當天有任一健康紀錄） | +10／天（一天封頂一次，避免刷分） |
| 連續打卡里程碑（依最長連續天數累計） | 3 天 +15、7 天 +40、14 天 +90、30 天 +200 |
| 完成 eHEALS 健康識能量表 | +30（一次） |

- **等級**：萌芽(0)→穩定(100)→規律(300)→自律(700)→達人(1500)，由累積 `earned` 決定。
- **徽章**（確定性解鎖）：初次回饋／規律一週／規律一月／情緒覺察／用藥好夥伴／
  健康識能達成／全面紀錄。
- **可用點數** `available = earned − spent`，`spent` 為兌換紀錄成本加總。

## 兌換（對應「後續會發放獎勵」）

兌換清單由程式碼定義（示意：衛教小手冊 50、回診優先時段 120、健康小禮包 200）。
`POST /rewards/redeem` 檢查餘額後，寫入一筆 `reward_redemptions`（`status='requested'`），
**實品由院方線下發放**；前端只負責登記兌換意願。

## API（`backend/routers/rewards.py`，prefix `/rewards`）

| 方法 | 路徑 | 說明 |
| --- | --- | --- |
| GET | `/rewards/summary?patient_id=` | earned/spent/available、等級進度、連續、徽章、加分明細 |
| GET | `/rewards/catalog?patient_id=` | 兌換清單（標出目前是否買得起） |
| GET | `/rewards/redemptions?patient_id=` | 我的兌換紀錄 |
| POST | `/rewards/redeem` | `{patient_id, reward_id}`，檢查餘額後登記兌換 |

## 資料表

唯一新增的持久化狀態是 `reward_redemptions`：
- SQLite fallback：已加入 `backend/db.py` 的 `_SCHEMAS`（自動建立）。
- 正式 Supabase：執行 `docs/migration_reward_redemptions.sql`（RLS 開啟、後端 service_role
  繞過，與目前安全姿態一致）。未套用前 `summary` 仍可顯示 earned，只是無法兌換。

## 測試

- `tests/test_rewards_rules.py`：規則引擎單元測試（規則 9，驗「為什麼」）。
- 端到端（summary／catalog／redeem／餘額不足）已於 SQLite fallback 驗證通過。

## 前端

- 頁面：`app.js` 的 `rewards()` / `loadRewardsPage()` / `redeemReward()`，在 `showPage`
  的 `pages` map 註冊 `rewards`（additive）。
- 樣式：`css/rewards.css`，只用 `tokens.css` 既有設計變數，主題切換與長者模式
  （`--scale`）自動跟著走，不覆寫任何既有 class。
- 入口：側邊欄新增「獎勵中心」一項；主畫面與底部 tabbar 不變。

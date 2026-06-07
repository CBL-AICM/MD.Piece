# App 事件日誌（`app_events`）— 設計與事件目錄

> codebook v3「使用行為(40)」與「遺失與錯誤事件(30)」中標 `TEL` 的變項之底層。
> 一列＝一個事件；codebook 變項是對這張表的**衍生聚合**（規則 5，後端純程式碼算，不丟 LLM）。
> 建表 SQL：[`docs/migration_app_events.sql`](../migration_app_events.sql)

---

## 1. 設計原則

- **通用 schema，不為每個指標建一張表**：`event_type` + `event_name` + `target` + `value` + `metadata(jsonb)`。
- **前端埋點 → 後端 API 代寫**：瀏覽器不直接 insert（RLS 硬化、anon 被擋）；走 `POST /events`（後端 service_role）。
- **支援離線補送**：`occurred_at` 由前端帶（事件真正發生時間），`created_at` 為寫入時間；兩者差可偵測離線。
- **去識別化**：`metadata` 嚴禁放姓名／原始作答／自由文字內容；只放型別、計數、識別碼。
- **衍生而非預存**：streak、完成率、錯誤率等不另存欄位，查詢時聚合（避免規則 3 的冗餘狀態）。

---

## 2. 事件型別 → codebook 變項對照

### 使用行為（行為面，Perski/Michie 2017）

| event_type | event_name（例） | 餵養的 codebook 變項 |
|---|---|---|
| `session` | `start` / `end` | total_sessions, session_duration, total_time_in_app, time_of_day |
| `session` | `start`（每日去重） | total_active_days, active_days_rate, longest/current_streak, weekly_active_rate |
| `screen` | `view`（target=畫面） | risk_dashboard_views, shap_explanation_views, timeline_views, education_content_views |
| `feature` | `use`（target=功能） | feature_breadth_used, previsit_summary_generated/shared, self_assessment_completions, data_export_actions, xiaohe_chat_messages |
| `data` | `submit`（target=記錄類型） | daily_log_count/completion_rate, symptom/vital/sleep/medication/emotion entries ※ |
| `reminder` | `sent` / `responded` | reminder_response_rate, reminder_response_latency |
| `push` | `received` / `opened` / `opt_in` | push_received/opened_count, notification_opt_in |
| `session` | `onboarding_done` | onboarding_completed, onboarding_duration |

> ※ 既有 `symptom_entries`/`vital_entries`/`sleep_sessions`/`medication_logs` 仍是主資料；
> `data:submit` 事件只作「行為時間戳」用於使用率聚合，避免重複真資料。

### 遺失與錯誤事件（資料品質 + 技術）

| event_type | event_name（例） | 餵養的 codebook 變項 |
|---|---|---|
| `crash` | `app_crash` | app_crash_count |
| `error` | `runtime_error` / `page_load_error` | app_error_count, page_load_error_count |
| `api` | `failure`（value=HTTP 狀態） | api_request_failures, sync_failure_count, data_submission_failures |
| `session` | `timeout` / `login_fail` / `offline` | session_timeout_count, login_failure_count, offline_event_count |
| `edit` | `correction`（target=記錄） | correction_edit_count |
| `data` | `out_of_range` / `duplicate` / `inconsistent` | out_of_range/duplicate/inconsistent_count（亦可後端批次掃描衍生） |

> 缺漏類（overall_missing_rate, dropout, mnar_indicator, straightlining…）多由
> `survey_responses` ＋ `app_events` 的**時間序列聚合**衍生，不一定需要前端埋點；
> 缺漏機制分析參考 Courvoisier 2012（順從度隨時間衰減、缺漏常非隨機）。

---

## 3. 實作待辦（依序，尚未動工）

1. **DB**：套用 `migration_app_events.sql` 到 prod Supabase；同步把 `app_events` 加進
   `backend/db.py` 的 `_SCHEMAS`（SQLite fallback）。⚠️ 依記憶，新表要三處同步：
   `api/index.py` 路由、`vercel.json`、Supabase 表 ＋ RLS。
2. **後端**：新增 `backend/routers/events.py` — `POST /events`（批次代寫，限登入）＋
   `GET /events/agg`（後端聚合成 codebook 衍生變項，給研究後台）。在 `main.py` 註冊。
3. **前端**：埋點層（一支 `track(event_type, name, opts)`），接 session 生命週期、畫面瀏覽、
   功能點擊、reminder/push、全域 error/crash 攔截。離線佇列 + 補送。
4. **聚合**：把 §2 對照寫成純程式碼聚合（比照 `surveys.py` 的 `_adherence`/`_describe`）。

> 這條（尤其前端埋點）是獨立工程，不在本次 SR seed 範圍內。可考慮對接
> product-tracking 工具自動產生埋點。

# MD.Piece — Supabase Auth + RLS 遷移計畫

> **狀態**：Phase 0（design freeze）
> **負責**：cf.kuo@osterfith.io
> **相關 issue**：#388
> **預估**：~3 週、5 個 PR
> **決策**：隱型遷移、保留 username

---

## 1. 為什麼要做這件事

PR #386 merge 時 Supabase MCP 觸發 **critical advisory：22 / 27 tables RLS disabled**。

深入盤點後發現問題不只 RLS：

```
[ Login ]
  ├── backend/routers/auth.py (scrypt 比對) → 回傳 user object
  ├── frontend 把 user 存進 localStorage.mdpiece_user
  └── 所有後續 API 呼叫：URL path 帶 user_id，backend 不驗證

[ Effect ]
  任何人開瀏覽器 console、把 mdpiece_user 改成別人的 id
  → 用 fetch 打 /profile/{他人 id} → 拿到 / 改寫他人個資
```

`grep "X-User-Id" backend/` → 0 hit、`grep "Depends(.*user)" backend/` → 0 hit。
這是 **P0 越權漏洞**，目前的「認證」只擋未登入者。

---

## 2. 目標

把認證 / 授權從「自管 scrypt + 純前端 user_id」遷移到「Supabase Auth + RLS policy」，**過程不中斷現有 14 位使用者**。

---

## 3. 拍板決策

| 決策點 | 選擇 | 理由 |
|---|---|---|
| 既有使用者怎麼處理 | **隱型遷移** | 14 人不少、長者模式特別不友善「請重設密碼」 |
| 登入識別 | **username + email**（雙寫） | UI 維持輸 username、Supabase Auth 內部用 email = `{username}@mdpiece.life` 之類的 placeholder |
| Phase 1 是否獨立可上線 | **是** | 即使後面 Phase 失敗，Phase 1 也已堵住 P0 越權漏洞 |
| Doctor 角色 | **本次不處理** | 全部 14 人都是 patient。等 patient 跑穩再做 |

---

## 4. 27 Tables 的 user_id 對應

### A. Per-patient 資料（需要 RLS）

| Table | owner 欄位 | 型別 | 對應 user 的方式 | 備註 |
|---|---|---|---|---|
| `patient_profiles` | `user_id` | TEXT | `auth.uid()::text = user_id` | 新增（Issue #131） |
| `users` | `id` | UUID | `auth.uid()::uuid = id` | 自己看自己 |
| `medication_logs` | `patient_id` | UUID | join `medications` → patient | FK 透過 medication |
| `medications` | `patient_id` | UUID | `auth.uid()::uuid = patient_id` | 但 `patients.id ≠ users.id`！見問題 #1 |
| `emotions` | `patient_id` | UUID | 同上 | 同上 |
| `symptoms_log` | `patient_id` | UUID | FK to patients.id | 同上 |
| `medical_records` | `patient_id` | UUID | FK to patients.id | 同上 |
| `medication_changes` | `patient_id` | UUID | 同上 | 也有 doctor_id |
| `medication_effects` | `patient_id` | UUID | 同上 | |
| `doctor_notes` | `patient_id` | UUID | 同上 | |
| `alerts` | `patient_id` | UUID | 同上 | |
| `admissions` | `patient_id` | UUID | 同上 | FK to patients.id |
| `admission_medications` | `admission_id` | UUID | join → admission → patient | 兩層 |
| `admission_medication_doses` | `admission_medication_id` | UUID | join 三層 | |
| `diet_records` | `patient_id` | TEXT | `auth.uid()::text = patient_id` | 注意型別不同！ |
| `water_intake_daily` | `patient_id` | TEXT | 同上 | |
| `bell_sounds` | `owner_patient_id` | TEXT | 同上 | |
| `custom_procedure_types` | `patient_id` | TEXT | 同上 | |
| `patient_bell_prefs` | `patient_id` | TEXT | 同上 | |
| `push_subscriptions` | `patient_id` | TEXT | 同上 | |
| `reminders` | `patient_id` | TEXT | 同上 | |
| `notification_inbox` | `patient_id` | TEXT | 同上 | |
| `measurement_requests` | `patient_id` | TEXT | 同上 | 也有 doctor_id |

### B. Reference / 唯讀（不需要 per-user RLS）

| Table | 處理方式 |
|---|---|
| `disease_reference` | `FOR SELECT USING (true)`、INSERT 限 service role |
| `drug_reference` | 同上 |

### C. 多方共享（先延後）

| Table | 理由 |
|---|---|
| `doctors` | 醫病雙方都會讀；先 `FOR SELECT USING (true)`、寫入限 service role |

---

## 5. ❗ 已發現的問題

### 問題 #1：`users.id` vs `patients.id` 是否一致？

**已確認（執行 SQL 於 2026-05-25）：**

```
users    : 14 rows
patients :  5 rows
users.id ∩ patients.id = 3
```

5 個 patients 的細節：
| patients.id | name | 對應 user? |
|---|---|---|
| `51910fcd-d549-4a6f-ab6e-5e42f1a009c9` | 匿名 | ❌（孤兒，2026-05-07 建） |
| `35c88834-8674-44b8-beff-2cae0e3c80f8` | 匿名 | ✅ |
| `11111111-2222-3333-4444-555555555555` | 訪客 | ❌（hardcoded demo sentinel） |
| `37a4cbad-7152-4d17-980c-1d3d9e4fdd0e` | lisa | ✅ |
| `067cbba3-cd82-4d1d-9e3a-acadfd6c465a` | 匿名 | ✅ |

clinical data 分布：
- `medications` 33 rows，全部 patient_id 都在 `patients.id`、只有 1 個 patient_id 也在 `users.id`
- 其他 11 users 沒有對應 patient → 應該是測試帳號、沒打過卡片
- 2 個 orphan patients：1 個是 hardcoded demo（`11111111-...`）、1 個是早期未綁定的匿名測試資料

**Phase 1 遷移策略（基於此資料）：**

1. **3 users.id == patients.id 的（lisa + 2 匿名）**：什麼都不用做，本身就一致
2. **11 沒有 patient 的 users**：第一次寫 clinical data 時，由 backend 自動 `INSERT INTO patients (id, name) VALUES (user.id, user.nickname)`，行為對前端 transparent
3. **2 個 orphan patients**（51910fcd、11111111）：
   - `11111111-...` 是 demo sentinel → 維持、視為「公用 demo 帳號」
   - `51910fcd` 是 2026-05-07 建的早期匿名測試 → 可直接 `DELETE`（無真實使用者），或保留以維持 FK 完整性

→ 結論：**users 跟 patients 的對應問題**比想像簡單，**Phase 1 可以動了**。

### 問題 #2：型別不一致（UUID vs TEXT）

部分 table 用 UUID（emotions, medications）、部分用 TEXT（diet_records, reminders）。
RLS policy 要分別寫：

```sql
-- UUID 表
CREATE POLICY p ON medications FOR ALL TO authenticated
  USING (auth.uid() = patient_id);

-- TEXT 表
CREATE POLICY p ON reminders FOR ALL TO authenticated
  USING (auth.uid()::text = patient_id);
```

長期應該統一型別，但本次不動（手術式修改原則）。

### 問題 #3：admission_medications / doses 沒有直接 patient_id

兩層／三層 join 的 RLS 比較貴。可以加 `patient_id` 冗餘欄位 + trigger 維護，或用 view + SECURITY INVOKER。

**建議**：補 patient_id 欄位、trigger 同步。

---

## 6. 分階段執行

### Phase 0 — Design freeze（本 PR）
- [x] 寫本文件
- [x] 把問題 #1-3 列出來
- [x] **用 SQL 確認 users / patients 的對應關係**（已釐清，見 §5 問題 #1）

### Phase 1 — Backend 中間層加固（封住越權漏洞）

**前提**：Phase 0 問題 #1 已釐清

| Step | 動作 |
|---|---|
| 1.1 | `backend/auth/session.py`：login 成功發 JWT（HS256, 7d, secret in env） |
| 1.2 | `backend/auth/deps.py`：`current_user = Depends(_decode_jwt)`，回 `{id, username, role}` |
| 1.3 | 每個 router：把 `user_id: str` path 參數移除、改 `Depends(current_user)` |
| 1.4 | Frontend：login 存 token、所有 fetch wrap `addAuthHeader()` |
| 1.5 | 保留 `/auth/login` 舊路徑、新增 `/auth/v2/login`，feature flag `AUTH_V2_ENABLED` 一週後切完 |

**驗收**：用瀏覽器 console 改 `mdpiece_user.id` → 所有 API 回 401，無法讀寫他人資料。

### Phase 2 — Supabase Auth 並行（隱型遷移）

| Step | 動作 |
|---|---|
| 2.1 | 啟用 Supabase Auth Email provider |
| 2.2 | `backend/auth/v2_login.py`：login 流程改成 |
| | 1. 先驗 username + password（自管 scrypt） |
| | 2. 如果 user 還沒有 `supabase_user_id` 欄位 → 用 admin API 建 Supabase Auth user（email = `{user.id}@mdpiece.internal`、密碼 = 本次輸入的 password） |
| | 3. 寫回 `users.supabase_user_id` |
| | 4. 用 Supabase SDK 跟同帳號做 `signInWithPassword` 拿 JWT |
| | 5. 回前端 |
| 2.3 | 後續 backend 改驗 Supabase JWT（換 dependency） |

### Phase 3 — RLS policies

⚠️ **先在 Supabase preview branch 完整跑 e2e 再上 prod**。

| Step | 動作 |
|---|---|
| 3.1 | 給每張表加 policy（見 §4） |
| 3.2 | admission_medications / doses：加 patient_id 冗餘欄位 + trigger |
| 3.3 | backend：所有 supabase 呼叫改用 user JWT，不再用 service role（除了管理介面） |
| 3.4 | 一張一張開 RLS（不要一次 22 張），每張開完跑該 router 的 e2e |

### Phase 4 — 清理

| Step | 動作 |
|---|---|
| 4.1 | 移除 `_hash_password` / `_verify_password` |
| 4.2 | drop `users.password_hash` 欄位 |
| 4.3 | 前端 `mdpiece_user` localStorage → Supabase auth helper |
| 4.4 | 文件、CLAUDE.md 更新 |

---

## 7. Rollback

| Phase | Rollback 方法 |
|---|---|
| 1 | feature flag 關掉、回 `/auth/login` 舊路徑 |
| 2 | backend 改回直接讀 `users.password_hash` |
| 3 | `DISABLE ROW LEVEL SECURITY` 一張張關回去 |
| 4 | 不能 rollback（密碼欄位已 drop），所以 4 在 prod 跑穩兩週後才做 |

---

## 8. 還沒決定的（待 Phase 1 開工前討論）

- [ ] JWT secret 放哪？env / Supabase Vault / 第三方
- [ ] Refresh token 機制（Supabase 內建 vs 自管）
- [ ] 是否做 email 驗證（既然 placeholder email，可能無意義）
- [ ] Phase 2 雙寫期間，使用者改密碼要同步到 Supabase 嗎？
- [ ] RLS 後，admin 介面（看全部使用者）怎麼授權？

---

## 9. 相關連結

- Tracking issue: #388
- 觸發 PR: #386
- Supabase advisory: rls_disabled (critical)
- Supabase project: `tbqvpqvvvgfgaezxbhkz` (MD.piece, ap-northeast-1)

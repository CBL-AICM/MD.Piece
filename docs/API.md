# API 文件

## 基礎 URL

```
http://localhost:8000
```

## 通用說明

- 所有請求 / 回應均使用 **JSON**
- ID 欄位均為 **UUID** 格式
- 時間欄位為 **ISO 8601**（UTC）

---

## 健康檢查

```
GET /
```

回應：
```json
{ "message": "MD.Piece API is running", "version": "2.0.0" }
```

---

## 科別管理 `/departments`

### 取得所有科別
```
GET /departments/
```
回應：`{ "departments": [ { "id", "name", "code", "description", "created_at" } ] }`

### 取得單一科別
```
GET /departments/{department_id}
```

### 取得科別下的醫師
```
GET /departments/{department_id}/doctors
```
回應：`{ "department": {...}, "doctors": [...] }`

### 新增科別
```
POST /departments/
```
Body：
```json
{ "name": "心臟科", "code": "CA", "description": "心臟血管疾病" }
```

### 更新科別
```
PUT /departments/{department_id}
```

### 刪除科別
```
DELETE /departments/{department_id}
```

### 初始化預設科別
```
POST /departments/seed
```
一次建立 15 個常用科別（重複執行安全，不會重複新增）。

---

## 醫師管理 `/doctors`

### 取得所有醫師
```
GET /doctors/
```

### 取得單一醫師
```
GET /doctors/{doctor_id}
```

### 新增醫師
```
POST /doctors/
```
Body：
```json
{
  "name": "王小明",
  "specialty": "內科",
  "phone": "02-12345678",
  "department_id": "<uuid>"
}
```
> `department_id` 選填，對應 `/departments` 中的科別 ID。

### 更新醫師
```
PUT /doctors/{doctor_id}
```

### 刪除醫師
```
DELETE /doctors/{doctor_id}
```

---

## 病患管理 `/patients`

### 取得所有病患
```
GET /patients/
```

### 取得單一病患
```
GET /patients/{patient_id}
```

### 新增病患
```
POST /patients/
```
Body：
```json
{ "name": "李小花", "age": 35, "gender": "female", "phone": "0912-345678" }
```

### 更新病患
```
PUT /patients/{patient_id}
```

### 刪除病患
```
DELETE /patients/{patient_id}
```

---

## 病歷管理 `/records`

### 列出病歷（支援篩選）
```
GET /records/?patient_id=&doctor_id=&date_from=&date_to=&diagnosis=
```

### 取得單一病歷
```
GET /records/{record_id}
```

### 取得病患所有病歷
```
GET /records/patient/{patient_id}
```

### 新增病歷
```
POST /records/
```
Body：
```json
{
  "patient_id": "<uuid>",
  "doctor_id": "<uuid>",
  "visit_date": "2026-03-20T10:00:00Z",
  "symptoms": ["發燒", "頭痛"],
  "diagnosis": "上呼吸道感染",
  "prescription": "普拿疼 500mg tid",
  "notes": "建議多休息"
}
```

### 更新病歷
```
PUT /records/{record_id}
```

### 刪除病歷
```
DELETE /records/{record_id}
```

---

## 症狀分析 `/symptoms`

### 快速症狀建議
```
GET /symptoms/advice?symptom=fever
```

### AI 症狀分析
```
POST /symptoms/analyze
```
Body：
```json
{ "symptoms": ["fever", "headache", "cough"], "patient_id": "<uuid>" }
```
回應：
```json
{
  "urgency": "medium",
  "recommended_department": "內科",
  "conditions": [
    { "name": "感冒", "likelihood": "高" }
  ],
  "advice": "建議多休息、補充水分",
  "disclaimer": "此分析僅供參考，不構成醫療診斷。"
}
```

### 症狀分析歷史
```
GET /symptoms/history/{patient_id}
```

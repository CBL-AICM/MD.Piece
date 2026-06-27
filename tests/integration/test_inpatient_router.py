"""inpatient router 整合測試 — 用本地 SQLite fallback。

驗證住院模式六大功能裡的「可被確定性驗證」部分：
  F3 用藥核對：居家 vs 住院醫囑的 新增／停用／劑量改變／維持 分類正確。
  F1 交接報告：彙整居家用藥 + 個人檔案背景，且每筆標來源；LLM 離線時 situation 走 fallback。
  F2 床邊紀錄 + QPL 提問清單：寫入、查詢、標記已問。
  F6 出院清單：CTI 四支柱齊全、惡化紅旗以衛教語氣呈現。

這些測試刻意驗證「為什麼」：例如改了某顆藥的劑量，必須被歸類成 changed 而非 same——
若有人把 reconciliation 寫死成全部 same，test_med_reconciliation_classifies_changes 會失敗（規則 9）。
"""

import pytest

from fastapi.testclient import TestClient

from backend.main import app
from backend.security import create_access_token

PATIENT_ID = "inpatient-test-1"
# medications router 走 JWT（Phase 1b）；sub 設成 PATIENT_ID 才能通過 _enforce_self_patient。
# inpatient / admissions router 本身不強制 token，但帶著也不影響。
_TEST_TOKEN = create_access_token({"id": PATIENT_ID, "username": "tester", "role": "patient"})
client = TestClient(app, headers={"Authorization": f"Bearer {_TEST_TOKEN}"})


@pytest.fixture(autouse=True)
def _llm_offline(monkeypatch):
    """整合測試一律視為「LLM 離線」：讓 call_claude 直接拋錯，_safe_llm 會吞掉並回
    None，handover / discharge 的 situation 因而走可溯源 fallback（_ai='fallback'）。

    否則開發機若剛好有本機 Ollama 在跑（LLM_PROVIDER 預設 ollama →
    localhost:11434），會拿到真模型回覆使 _ai='ok'、test_handover 失敗。整合測試
    不該依賴真實 LLM——與 test_drug_search / test_diseases mock 掉 LLM 同一原則。"""
    from backend.services import llm_service

    def _offline(*args, **kwargs):
        raise RuntimeError("LLM offline (forced in tests)")

    monkeypatch.setattr(llm_service, "call_claude", _offline)
    yield


def _make_admission(diagnosis="肺炎", icd10="J18.9"):
    r = client.post("/admissions/", json={
        "patient_id": PATIENT_ID, "type": "acute",
        "diagnosis": diagnosis, "diagnosis_icd10": icd10, "ward": "5A",
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _add_home_med(name, dosage="", frequency=""):
    r = client.post("/medications/", json={
        "patient_id": PATIENT_ID, "name": name, "dosage": dosage, "frequency": frequency,
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _add_admission_med(admission_id, name, dose="", frequency=""):
    r = client.post("/admissions/medications", json={
        "admission_id": admission_id, "name": name, "dose": dose, "frequency": frequency,
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ── F3 用藥核對 ───────────────────────────────────────────

def test_med_reconciliation_classifies_changes():
    """同名同劑量=維持；同名不同劑量=改變；只在住院=新增；只在居家=停用。"""
    adm = _make_admission()
    _add_home_med("Aspirin", "100mg", "每天一次")    # 維持
    _add_home_med("Metformin", "500mg", "每天兩次")  # 劑量改變
    _add_home_med("Warfarin", "5mg")                # 住院停用（住院醫囑沒有）

    _add_admission_med(adm, "Aspirin", "100mg", "每天一次")
    _add_admission_med(adm, "Metformin", "1000mg", "每天兩次")  # 劑量被改
    _add_admission_med(adm, "Heparin", "5000U")               # 住院新增

    r = client.get("/inpatient/med-reconciliation",
                   params={"patient_id": PATIENT_ID, "admission_id": adm})
    assert r.status_code == 200, r.text
    body = r.json()
    by_name = {row["name"].lower(): row for row in body["rows"]}

    assert by_name["aspirin"]["status"] == "same"
    assert by_name["metformin"]["status"] == "changed"
    assert by_name["warfarin"]["status"] == "stopped"
    assert by_name["heparin"]["status"] == "added"

    assert body["summary"] == {"same": 1, "changed": 1, "stopped": 1, "added": 1}
    # 法規紅線：只呈現差異，必附「請與醫師或藥師確認」
    assert "醫師或藥師" in body["disclaimer"]


def test_med_reconciliation_name_match_is_case_insensitive():
    """藥名大小寫 / 空白不同仍視為同藥（避免誤判成新增+停用兩筆）。"""
    adm = _make_admission()
    _add_home_med("  aspirin ", "100mg")
    _add_admission_med(adm, "Aspirin", "100mg")
    r = client.get("/inpatient/med-reconciliation",
                   params={"patient_id": PATIENT_ID, "admission_id": adm})
    rows = r.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["status"] == "same"


# ── F1 交接報告 ───────────────────────────────────────────

def test_handover_aggregates_meds_with_source_and_fallback_situation():
    """交接報告要帶居家用藥（標來源）、背景；LLM 離線時 situation 走可溯源 fallback。"""
    adm = _make_admission(diagnosis="心衰竭")
    _add_home_med("Furosemide", "40mg", "每天一次")

    r = client.get("/inpatient/handover",
                   params={"patient_id": PATIENT_ID, "admission_id": adm})
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["format"] == "SBAR / I-PASS"
    assert len(body["medications"]) == 1
    assert body["medications"][0]["name"] == "Furosemide"
    assert body["medications"][0]["source"] == "病人自填"
    # 測試環境無 LLM → situation 必須 fallback 且包含診斷字串（可溯源）
    assert body["_ai"] == "fallback"
    assert "心衰竭" in body["situation"]
    assert "非診斷依據" in body["disclaimer"]


# ── F2 床邊紀錄 + 提問清單 ────────────────────────────────

def test_bedside_log_write_and_validation():
    adm = _make_admission()
    r = client.post("/inpatient/bedside", json={
        "patient_id": PATIENT_ID, "admission_id": adm,
        "pain": 4, "food": "half", "sleep": "poor", "mood": 3,
    })
    assert r.status_code == 200, r.text

    # pain 超出範圍要被擋（規則 12：壞資料不靜默吞下）
    bad = client.post("/inpatient/bedside", json={"patient_id": PATIENT_ID, "pain": 99})
    assert bad.status_code == 400

    lst = client.get("/inpatient/bedside",
                     params={"patient_id": PATIENT_ID, "admission_id": adm})
    assert lst.status_code == 200
    assert len(lst.json()["logs"]) == 1


def test_questions_lifecycle_and_qpl_bank():
    bank = client.get("/inpatient/qpl-bank")
    assert bank.status_code == 200 and len(bank.json()["questions"]) > 0

    adm = _make_admission()
    created = client.post("/inpatient/questions", json={
        "patient_id": PATIENT_ID, "admission_id": adm, "text": "我還要住幾天？",
    })
    assert created.status_code == 200, created.text
    qid = created.json()["id"]
    assert created.json()["status"] == "open"

    # 空白問題要被擋
    assert client.post("/inpatient/questions",
                       json={"patient_id": PATIENT_ID, "text": "  "}).status_code == 400

    asked = client.put(f"/inpatient/questions/{qid}", json={"status": "asked"})
    assert asked.status_code == 200 and asked.json()["status"] == "asked"

    lst = client.get("/inpatient/questions",
                     params={"patient_id": PATIENT_ID, "admission_id": adm})
    assert any(q["id"] == qid and q["status"] == "asked" for q in lst.json()["questions"])


# ── F6 出院清單 ───────────────────────────────────────────

def test_discharge_checklist_has_cti_pillars_and_red_flags():
    adm = _make_admission()
    _add_admission_med(adm, "Aspirin", "100mg", "每天一次")

    r = client.get("/inpatient/discharge-checklist",
                   params={"patient_id": PATIENT_ID, "admission_id": adm})
    assert r.status_code == 200, r.text
    body = r.json()

    keys = {p["key"] for p in body["pillars"]}
    assert keys == {"medication", "record", "follow_up", "red_flags"}

    red = next(p for p in body["pillars"] if p["key"] == "red_flags")
    assert len(red["items"]) > 0
    # 衛教語氣：必須是「若出現…請聯絡醫療人員」，不可下「你惡化了」這種判斷
    assert all("聯絡醫療人員" in it["label"] for it in red["items"])

    # 帶回家藥物應出現在 medication 支柱
    med = next(p for p in body["pillars"] if p["key"] == "medication")
    assert any("Aspirin" in it["label"] for it in med["items"])

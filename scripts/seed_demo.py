"""把示範資料寫入 SQLite，讓你能直接看到醫師端與患者端的視覺成果。"""
import json
import random
from datetime import datetime, timedelta, timezone

import httpx

API = "http://localhost:8000"
random.seed(42)


def post(path, payload):
    r = httpx.post(f"{API}{path}", json=payload, timeout=15)
    if not r.is_success:
        print(f"  ! {path} -> {r.status_code}: {r.text[:120]}")
    return r.json() if r.is_success else None


def make_patient(name, age, gender, codes, immuno=False):
    p = post("/patients/", {
        "name": name, "age": age, "gender": gender,
        "icd10_codes": codes,
    })
    print(f"+ patient {name} ({p['id'][:8]}…)")
    return p


def seed_symptom_history(pid, days, base_severity, locations, types,
                         worsening=False, new_location_day=None, new_location=None):
    """模擬 days 天的問卷紀錄"""
    for i in range(days):
        day_offset = days - i
        sev = base_severity + (random.random() - 0.5) * 1.5
        if worsening and i >= days - 4:  # 末 4 天惡化
            sev += (i - (days - 4)) * 0.8
        sev = max(0, min(10, round(sev, 1)))
        feeling = "good" if sev < 2 else "ok" if sev < 4 else "uncomfortable" if sev < 7 else "bad"
        locs = list(locations)
        if new_location_day is not None and i >= days - new_location_day and new_location:
            locs.append(new_location)
        body = {
            "patient_id": pid,
            "overall_feeling": feeling,
            "body_locations": locs,
            "symptom_types": types,
            "free_text": "",
            "severity": int(sev),
            "change_pattern": "gradual_worse" if worsening else "same",
        }
        post("/symptoms/questionnaire/submit", body)


def seed_emotion(pid, days, base_score, low_streak_days=0):
    for i in range(days):
        s = base_score + random.choice([-1, 0, 0, 0, 1])
        if i >= days - low_streak_days:
            s = random.choice([1, 2])
        s = max(1, min(5, s))
        post("/emotions/", {"patient_id": pid, "score": s, "note": ""})


def seed_medications_and_logs(pid, meds_spec, days, adherence_rate):
    med_ids = []
    for name, dose, freq, cat in meds_spec:
        m = post("/medications/", {
            "patient_id": pid, "name": name, "dosage": dose,
            "frequency": freq, "category": cat,
        })
        if m: med_ids.append(m["id"])
    for i in range(days):
        for mid in med_ids:
            taken = random.random() < adherence_rate
            post("/medications/log", {
                "patient_id": pid, "medication_id": mid,
                "taken": taken,
                "taken_at": (datetime.now(timezone.utc) - timedelta(days=days - i)).isoformat(),
            })
    return med_ids


def seed_doctor_note(pid, content, next_focus):
    post("/doctor-notes/", {
        "patient_id": pid, "content": content, "next_focus": next_focus,
        "tags": ["回診備註"],
    })


def seed_alert(pid, alert_type, severity, title, detail):
    post("/alerts/", {
        "patient_id": pid, "alert_type": alert_type, "severity": severity,
        "title": title, "detail": detail, "source": "demo_seed",
    })


def seed_lab(pid, code, value):
    post("/vitals/lab", {"patient_id": pid, "code": code, "value": value})


def main():
    print("=== Seeding demo data ===\n")

    # 患者 A：類風濕，狀況惡化中
    a = make_patient("王美華", 58, "女", ["M06"], immuno=True)
    seed_symptom_history(a["id"], 14, base_severity=4, locations=["left_knee", "right_knee"],
                         types=["pain", "tightness"],
                         worsening=True, new_location_day=3, new_location="chest")
    seed_emotion(a["id"], 14, base_score=3, low_streak_days=5)
    seed_medications_and_logs(a["id"], [
        ("甲氨蝶呤 (Methotrexate)", "10mg", "每週一次", "免疫抑制劑"),
        ("葉酸", "5mg", "每週一次", "維生素"),
    ], days=14, adherence_rate=0.6)
    seed_doctor_note(a["id"],
        "本次調整 MTX 劑量至 10mg；患者主訴晨僵加劇。下次回診特別觀察手指關節腫脹與肝功能。",
        "手指對稱性腫脹、ALT/AST、晨僵時間")
    seed_alert(a["id"], "missed_medication", "high",
               "連續 3 天漏服 MTX", "請於回診時與患者確認")
    seed_lab(a["id"], "CRP", 12)
    seed_lab(a["id"], "ESR", 35)
    seed_lab(a["id"], "ALT", 55)

    # 患者 B：糖尿病，控制中等
    b = make_patient("林志強", 65, "男", ["E11"])
    seed_symptom_history(b["id"], 14, base_severity=2, locations=["left_foot"], types=["numbness"])
    seed_emotion(b["id"], 14, base_score=4)
    seed_medications_and_logs(b["id"], [
        ("Metformin", "500mg", "每日兩次", "降血糖藥"),
    ], days=14, adherence_rate=0.9)
    seed_doctor_note(b["id"],
        "HbA1c 7.2% 較上次略升，建議飯後散步 30 分鐘並注意精製澱粉攝取",
        "HbA1c 走向、足部感覺變化")
    seed_lab(b["id"], "HbA1c", 7.2)
    seed_lab(b["id"], "FBS", 135)

    # 患者 C：氣喘，狀況穩定
    c = make_patient("陳曉蓉", 32, "女", ["J45"])
    seed_symptom_history(c["id"], 14, base_severity=1, locations=[], types=[])
    seed_emotion(c["id"], 14, base_score=4)
    seed_medications_and_logs(c["id"], [
        ("Symbicort", "1 噴", "每日兩次", "支氣管擴張劑"),
    ], days=14, adherence_rate=0.95)
    seed_lab(c["id"], "CRP", 2)

    # 患者 D：高血壓 + 憂鬱，心理危機（小禾偵測）
    d = make_patient("張秀芬", 72, "女", ["I10", "F32"])
    seed_symptom_history(d["id"], 14, base_severity=3, locations=["head_front"], types=["dizziness"])
    seed_emotion(d["id"], 14, base_score=2, low_streak_days=7)
    seed_medications_and_logs(d["id"], [
        ("Amlodipine", "5mg", "每日一次", "鈣離子阻斷劑"),
        ("Sertraline", "50mg", "每日一次", "抗憂鬱藥"),
    ], days=14, adherence_rate=0.7)
    seed_doctor_note(d["id"],
        "情緒低落超過 3 週，已調整抗憂鬱藥劑量。鼓勵家人陪同回診。",
        "情緒分數、是否有負面想法")

    # 模擬小禾對話（觸發靜默守護）
    crisis_msgs = [
        "今天又一個人在家，覺得好累",
        "有時候真的會想我這樣下去有什麼意義",
        "撐不下去的時候我都會想，要是消失就好了",
        "藥還是有吃，但心裡那種很想結束的感覺一直都在",
    ]
    for msg in crisis_msgs:
        post("/xiaohe/chat", {
            "user_id": d["id"], "message": msg,
            "mode": "patient", "version": "elderly",
        })

    print("\n=== 完成。可瀏覽以下網址看成果 ===")
    print(f"  患者端 PWA       :  http://localhost:3000")
    print(f"  後端 API 文件    :  http://localhost:8000/docs")
    print(f"  患者優先序 (JSON):  http://localhost:8000/doctor-dashboard/priority")
    print(f"  時間軸 (JSON)    :  http://localhost:8000/timeline/{a['id']}")
    print(f"  跨回診比較 (JSON):  http://localhost:8000/timeline/{a['id']}/compare")


if __name__ == "__main__":
    main()

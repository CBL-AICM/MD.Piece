"""MD.Piece 活世界(living world)— 每天推進一天的持續模擬。

與一次性回填(seed_backend)不同，本引擎把每位患者的「可變狀態」持久化在
正式後台的 `sim_world_state` 表，每天 tick 一次：

  1. 用真實動力學 step_dynamics 把每位 active 患者的病情**往前推一天**。
  2. **反應**：讀取 App 內的用藥變更(medications 表)，同步到模擬狀態
     → 醫病在 App 改藥，患者未來軌跡會跟著變。
  3. 依 engagement 決定今天有沒有開 App，有就寫**當天**(真實日期)的紀錄。
  4. **成長**：尚未註冊的候選者每天少量陸續註冊；部分 active 永久流失；
     進展型疾病 burden 過高有極小機率離世(停止)。
  5. 冪等：同一天重跑不會重複寫(以 last_tick_date 為界)。

排程：由 .github/workflows/world-tick.yml 每天雲端 cron 呼叫 `--tick`。

CLI:
  PYTHONPATH=. python -m ml.world --init                 # 從世代建立初始狀態(一次)
  PYTHONPATH=. python -m ml.world --init --n-per 20       # 小池測試
  PYTHONPATH=. python -m ml.world --tick                 # 推進到今天
  PYTHONPATH=. python -m ml.world --tick --date 2026-06-14
  PYTHONPATH=. python -m ml.world --status               # 看世界現況
  PYTHONPATH=. python -m ml.world --cleanup              # 刪除 sim_world_state
"""

from __future__ import annotations

import argparse
import uuid
from datetime import date, datetime, timedelta, timezone

import numpy as np

from backend.db import get_supabase
from md_piece import app_usage as au
from md_piece.cohort_generator import generate_cohort
from md_piece.disease_loader import load_disease
from md_piece.dynamics import DynamicsState, step_dynamics
from md_piece.triggers import sample_triggers
from ml.app_cohort import DISEASES
from ml.insights import DISEASE_NAME
from ml.severity import BAND_COLOR, COMORBID_ZH, DISEASE_ALLERGY, assign_severity
from ml.seed_backend import (
    COHORT_START, DISEASE_LAB, DISEASE_SYMPTOM, HOSPITALS, SHARED_PW_HASH,
    SURNAMES, TAG, _name, _uid,
)

BATCH = 500
REG_DAILY_PROB = 0.0014        # 每位候選者每天註冊機率(~1600 人約 2 年內陸續註冊)
LATE_CHURN_PROB = 0.0020       # 已過 churn 期者每天永久流失的機率
DEATH_PROB = 0.0006            # 進展型且 burden 接近上限者每天離世機率

_CFG: dict = {}


def cfg_for(did: str):
    if did not in _CFG:
        _CFG[did] = load_disease(did)
    return _CFG[did]


def _now_day(run_date: date) -> int:
    return (run_date - COHORT_START.date()).days


def _ts_on(run_date: date, hour: int, minute: int = 0) -> str:
    return datetime(run_date.year, run_date.month, run_date.day, hour, minute,
                    tzinfo=timezone.utc).isoformat()


def _rng(seed: int, day: int) -> np.random.Generator:
    return np.random.default_rng((int(seed) * 1_000_003 + day) & 0x7FFFFFFFFFFF)


def _tx_to_json(tx: dict) -> dict:
    return {k: tx[k] for k in ("id", "class", "start_day", "onset_days",
                               "effect_magnitude", "half_life_days") if k in tx}


# ---------------------------------------------------------------------------
# 初始化：由世代建立 sim_world_state
# ---------------------------------------------------------------------------

def init_world(base_seed, n_per, n_register, n_workers, run_date):
    sb = get_supabase()
    now_day = _now_day(run_date)
    print(f"[init] 生成 {len(DISEASES)}×{n_per} 並推進到第 {now_day} 天…")
    all_patients = []
    for did in DISEASES:
        cohort = generate_cohort(cfg_for(did), n_per, now_day + 1,
                                 base_seed=base_seed, n_workers=n_workers)
        all_patients.extend(cohort.patients)

    props = {p.patient_id: au.registration_propensity(p.social_profile, p.age, p.disease_id)
             for p in all_patients}
    registered = au.select_registered(props, n_register, seed=base_seed)
    sev = assign_severity(all_patients)

    rows = []
    for p in all_patients:
        ts = p.timeseries.sort_values("day")
        last = ts.iloc[-1]
        rng = np.random.default_rng(p.seed ^ 0xF00D)
        arche = au.assign_archetype(p.social_profile, p.age, rng)
        adopted = sorted(au._adopted_features(
            au.ARCHETYPE_BY_NAME[arche], p.social_profile, p.age, p.sex,
            p.comorbidities, bool(p.treatments), rng))
        band, score = sev[p.patient_id]
        join_rng = np.random.default_rng(p.seed ^ 0x5EED)
        join_day = int(join_rng.integers(0, 46))
        is_reg = p.patient_id in registered
        sim = {
            "age": p.age, "sex": p.sex, "disease_id": p.disease_id,
            "sim_day": now_day,
            "registered_sim_day": join_day if is_reg else None,
            "activity": float(last["activity"]),
            "irreversible_burden": float(last.get("irreversible_burden", 0.0)),
            "mean_act_ref": float(ts["activity"].mean()),
            "active_triggers": [],
            "treatments": [_tx_to_json(t) for t in p.treatments],
            "archetype": arche, "adopted": adopted,
            "adherence_mult": float(p.social_profile.adherence_multiplier),
            "comorbidities": list(p.comorbidities),
            "has_menstrual": (p.sex == "F" and 13 <= p.age <= 52),
            "severity_band": band, "severity_score": score,
            "tick_seed": int(p.seed),
            "churn_at_day": _churn_day(arche, p.seed),
            "nickname": _name(p.sex, np.random.default_rng(p.seed ^ 0xA11CE)),
        }
        rows.append({
            "patient_id": p.patient_id,
            "user_id": _uid(p.patient_id) if is_reg else None,
            "disease_id": p.disease_id,
            "status": "active" if is_reg else "candidate",
            "last_tick_date": None,
            "sim": sim,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    for i in range(0, len(rows), BATCH):
        sb.table("sim_world_state").upsert(rows[i:i + BATCH], on_conflict="patient_id").execute()
    n_active = sum(1 for r in rows if r["status"] == "active")
    print(f"[init] 寫入 {len(rows)} 筆狀態(active={n_active}, candidate={len(rows)-n_active})")


def _churn_day(archetype: str, seed: int) -> int | None:
    a = au.ARCHETYPE_BY_NAME[archetype]
    if a.churn is None:
        return None
    lo, hi = a.churn
    return int(np.random.default_rng(seed ^ 0xC0FFEE).integers(lo, hi + 1))


# ---------------------------------------------------------------------------
# 每日 tick
# ---------------------------------------------------------------------------

def _load_state(sb):
    rows, start = [], 0
    while True:
        page = sb.table("sim_world_state").select("*").range(start, start + 999).execute().data
        rows.extend(page)
        if len(page) < 1000:
            break
        start += 1000
    return rows


def _med_info(sb, uids):
    """uid -> {"names": set(active 用藥名), "med_id": 任一 active 用藥 id}。"""
    names: dict[str, set] = {}
    mid: dict[str, str] = {}
    for i in range(0, len(uids), 200):
        chunk = uids[i:i + 200]
        data = sb.table("medications").select("patient_id,id,name,active").in_(
            "patient_id", chunk).execute().data
        for m in data:
            if m.get("active"):
                names.setdefault(m["patient_id"], set()).add(m["name"])
                mid.setdefault(m["patient_id"], m["id"])
    return names, mid


def _sync_meds(sim, cfg, app_meds, day):
    """反應式：把 App 內新加的藥併入模擬治療；移除已停的藥效。"""
    state_ids = {t["id"] for t in sim["treatments"]}
    changed = False
    # App 有、模擬沒有 → 新增(從 cfg 模板帶參數)
    for name in app_meds - state_ids:
        tmpl = next((t for t in cfg.treatments if t["id"] == name), None)
        if tmpl is None:
            continue
        em = tmpl["effect_magnitude"]
        em = em["mean"] if isinstance(em, dict) else em
        on = tmpl.get("onset_days", 14)
        on = on["mean"] if isinstance(on, dict) else on
        sim["treatments"].append({
            "id": name, "class": tmpl.get("class", ""), "start_day": day,
            "onset_days": float(on), "effect_magnitude": float(em),
            "half_life_days": float(tmpl.get("half_life_days", 30)),
        })
        changed = True
    # 模擬有、App 明確停掉(App 有此人用藥清單但不含此藥) → 移除
    if app_meds:
        keep = [t for t in sim["treatments"] if t["id"] in app_meds]
        if len(keep) != len(sim["treatments"]):
            sim["treatments"] = keep
            changed = True
    return changed


def _day_records(sim, cfg, run_date, day, symptomatic, rng, uid, med_id):
    out: dict[str, list] = {}
    did = sim["disease_id"]
    adopted = set(sim["adopted"])
    act = sim["activity"]

    def add(table, row):
        out.setdefault(table, []).append(row)

    if "symptoms" in adopted:
        rate = 0.55 * (1.6 if symptomatic else 1.0)
        if rng.random() < min(0.95, rate):
            add("symptom_entries", {
                "patient_id": uid, "client_id": str(uuid.uuid4()),
                "category_id": DISEASE_SYMPTOM.get(did, "不適"),
                "intensity": int(np.clip(round(act / 10 * 5), 1, 5)),
                "frequency": int(rng.integers(1, 4)),
                "recorded_at": _ts_on(run_date, int(rng.integers(7, 22))),
            })
    if "medications" in adopted and sim["treatments"] and med_id:
        med_log_base = float(np.clip(0.85 / (0.5 + 0.5 * sim["adherence_mult"]), 0.1, 0.95))
        if rng.random() < med_log_base:
            add("medication_logs", {
                "patient_id": uid, "medication_id": med_id, "taken": 1,
                "taken_at": _ts_on(run_date, 8, int(rng.integers(0, 59))),
            })
    if "emotions" in adopted and rng.random() < 0.30:
        add("emotions", {
            "patient_id": uid,
            "score": int(np.clip(5 - round(act / 10 * 3) + int(rng.integers(-1, 2)), 1, 5)),
            "created_at": _ts_on(run_date, int(rng.integers(8, 23))),
        })
    if "vitals" in adopted and rng.random() < 0.25:
        metric = str(rng.choice(["blood_pressure_sys", "heart_rate", "weight"]))
        val = {"blood_pressure_sys": rng.normal(125, 12), "heart_rate": rng.normal(76, 8),
               "weight": rng.normal(62, 10)}[metric]
        add("vital_entries", {
            "patient_id": uid, "client_id": str(uuid.uuid4()), "metric_id": metric,
            "value": round(float(val), 1), "recorded_at": _ts_on(run_date, int(rng.integers(6, 22))),
        })
    if "sleep" in adopted and rng.random() < 0.30:
        add("sleep_sessions", {
            "user_id": uid, "bed_time": _ts_on(run_date - timedelta(days=1), 23),
            "wake_time": _ts_on(run_date, 7),
            "total_sleep_minutes": int(np.clip(rng.normal(400, 50), 180, 600)),
            "source": "manual",
        })
    if "diet" in adopted and rng.random() < 0.35:
        meal = str(rng.choice(["breakfast", "lunch", "dinner"]))
        add("diet_records", {
            "patient_id": uid, "meal_type": meal, "foods": "正常飲食",
            "eaten_at": _ts_on(run_date, {"breakfast": 8, "lunch": 12, "dinner": 19}[meal]),
            "calories": int(rng.normal(600, 150)),
        })
    if "memos" in adopted and rng.random() < 0.12:
        add("memos", {
            "patient_id": uid, "kind": "text",
            "content": f"今天{DISEASE_SYMPTOM.get(did,'狀況')}還可以，持續記錄。",
            "created_at": _ts_on(run_date, 21),
        })
    if "labs" in adopted and rng.random() < 0.01:
        name, unit = DISEASE_LAB.get(did, ("CRP", "mg/L"))
        add("labs", {
            "patient_id": uid, "name": name,
            "value": str(round(act * float(rng.uniform(1.5, 3.0)) + 1, 1)), "unit": unit,
            "status": "abnormal" if act > 5 else "normal", "source": "manual",
            "recorded_at": _ts_on(run_date, 10),
        })
    return out


def _register_candidate(sim, pid, day, rng):
    """候選者註冊：回傳 (user_row, profile_row, med_rows)。"""
    uid = _uid(pid)
    sex = sim["sex"]
    age = sim["age"]
    band = sim["severity_band"]
    user = {
        "id": uid, "username": (TAG + pid).lower(), "nickname": sim["nickname"],
        "role": "patient", "email": (TAG + pid).lower() + "@cohort.invalid",
        "password_hash": SHARED_PW_HASH, "avatar_color": BAND_COLOR.get(band, "#5B9FE8"),
    }
    birth_year = COHORT_START.year + 1 - age
    if sex == "F":
        h = float(np.clip(rng.normal(159, 5.5), 145, 178))
    else:
        h = float(np.clip(rng.normal(170, 6.0), 152, 190))
    w = round(float(np.clip(rng.normal(23.5, 3.2), 16, 35)) * (h / 100) ** 2, 1)
    comorbid = [COMORBID_ZH.get(c, c) for c in sim["comorbidities"]]
    prof = {
        "user_id": uid, "gender": "female" if sex == "F" else "male",
        "birthday": f"{birth_year:04d}-{int(rng.integers(1,13)):02d}-{int(rng.integers(1,29)):02d}",
        "blood": str(rng.choice(["O", "A", "B", "AB"], p=[0.44, 0.26, 0.24, 0.06])),
        "height_cm": round(h, 1), "weight_kg": w,
        "allergies": DISEASE_ALLERGY.get(sim["disease_id"], "無已知過敏"),
        "conditions": "、".join(comorbid) if comorbid else "無共病",
        "current_disease": DISEASE_NAME.get(sim["disease_id"], sim["disease_id"]),
        "meds": ", ".join(t["id"] for t in sim["treatments"]) or "—",
        "doctor_name": str(rng.choice(SURNAMES)) + "醫師",
        "hospital": str(rng.choice(HOSPITALS)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    med_rows = []
    for t in sim["treatments"]:
        med_rows.append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{pid}:{t['id']}")),
            "patient_id": uid, "name": t["id"], "frequency": "每日", "active": 1,
            "prescribed_date": (COHORT_START + timedelta(days=day)).date().isoformat(),
        })
    return user, prof, med_rows


def tick(run_date: date):
    sb = get_supabase()
    day = _now_day(run_date)
    rows = _load_state(sb)
    if not rows:
        raise SystemExit("sim_world_state 是空的；請先 --init")
    iso = run_date.isoformat()
    active_uids = [r["user_id"] for r in rows if r["status"] == "active" and r["user_id"]]
    med_names, med_id_map = _med_info(sb, active_uids)

    buf: dict[str, list] = {}
    new_users, new_profiles, new_meds, state_updates = [], [], [], []
    n_active = n_records = n_reg = n_churn = n_death = n_react = 0

    def addbuf(tbl_rows):
        for t, rs in tbl_rows.items():
            buf.setdefault(t, []).extend(rs)

    for r in rows:
        if r["last_tick_date"] and r["last_tick_date"] >= iso:
            continue                                    # 冪等：今天已處理
        sim = r["sim"]
        status = r["status"]
        did = r["disease_id"]
        cfg = cfg_for(did)
        rng = _rng(sim["tick_seed"], day)

        if status in ("churned", "deceased", "recovered"):
            r["last_tick_date"] = iso
            state_updates.append(r)
            continue

        # 反應式用藥同步(僅 active 且 App 內有此人)
        if status == "active" and r["user_id"]:
            if _sync_meds(sim, cfg, med_names.get(r["user_id"], set()), sim["sim_day"]):
                n_react += 1

        # 推進病情一天
        for tx in sim["treatments"]:
            tx["dose_multiplier_today"] = 0.0 if rng.random() < min(
                0.4, 0.08 * sim["adherence_mult"]) else 1.0
        st = DynamicsState(activity=sim["activity"],
                           irreversible_burden=sim["irreversible_burden"],
                           active_triggers=[tuple(x) for x in sim["active_triggers"]],
                           active_treatments=sim["treatments"])
        st.active_triggers.extend(sample_triggers(cfg, 1.0, rng))
        st2 = step_dynamics(st, disease_cfg=cfg, t_days=sim["sim_day"], dt_days=1.0, rng=rng)

        thr = cfg.flare["threshold"]
        symptomatic = bool(st2.activity > thr or st2.activity > sim["mean_act_ref"] * 1.2)

        if status == "active":
            n_active += 1
            arche = au.ARCHETYPE_BY_NAME[sim["archetype"]]
            dsj = sim["sim_day"] - (sim["registered_sim_day"] or 0)
            ch = sim.get("churn_at_day")
            if ch is not None and dsj > ch:
                p_active = 0.04 if symptomatic else 0.005
            else:
                p_active = arche.base * au.retention_multiplier(arche, dsj)
                if symptomatic:
                    p_active *= (1.0 + arche.reactive_gain)
            if rng.random() < min(0.98, p_active):
                recs = _day_records(sim, cfg, run_date, day, symptomatic, rng,
                                    r["user_id"], med_id_map.get(r["user_id"]))
                addbuf(recs)
                n_records += sum(len(v) for v in recs.values())
            # 永久流失
            if ch is not None and dsj > ch and rng.random() < LATE_CHURN_PROB:
                status = "churned"; n_churn += 1
            # 進展型 + burden 接近上限 → 極小機率離世
            sat = (cfg.accumulation or {}).get("saturation") if cfg.accumulation else None
            if sat and st2.irreversible_burden > 0.9 * sat and rng.random() < DEATH_PROB:
                status = "deceased"; n_death += 1

        elif status == "candidate":
            if rng.random() < REG_DAILY_PROB:
                u, pr, meds = _register_candidate(sim, r["patient_id"], day, rng)
                new_users.append(u); new_profiles.append(pr); new_meds.extend(meds)
                r["user_id"] = u["id"]
                if meds:
                    med_id_map[u["id"]] = meds[0]["id"]
                status = "active"
                sim["registered_sim_day"] = day
                n_reg += 1

        # 寫回狀態
        sim["activity"] = float(st2.activity)
        sim["irreversible_burden"] = float(st2.irreversible_burden)
        sim["active_triggers"] = [list(x) for x in st2.active_triggers]
        sim["sim_day"] = sim["sim_day"] + 1
        r["status"] = status
        r["last_tick_date"] = iso
        r["sim"] = sim
        r["updated_at"] = datetime.now(timezone.utc).isoformat()
        state_updates.append(r)

    # 寫入：先帳號(FK)，再紀錄，最後狀態
    for i in range(0, len(new_users), BATCH):
        sb.table("users").insert(new_users[i:i + BATCH]).execute()
    for i in range(0, len(new_profiles), BATCH):
        sb.table("patient_profiles").insert(new_profiles[i:i + BATCH]).execute()
    for i in range(0, len(new_meds), BATCH):
        sb.table("medications").insert(new_meds[i:i + BATCH]).execute()
    for t, rs in buf.items():
        for i in range(0, len(rs), BATCH):
            sb.table(t).insert(rs[i:i + BATCH]).execute()
    for i in range(0, len(state_updates), BATCH):
        sb.table("sim_world_state").upsert(state_updates[i:i + BATCH],
                                           on_conflict="patient_id").execute()

    print("=" * 56)
    print(f"tick {iso}(第 {day} 天)")
    print(f"  active {n_active}｜新增紀錄 {n_records} 筆｜新註冊 {n_reg}"
          f"｜流失 {n_churn}｜離世 {n_death}｜用藥反應 {n_react}")
    print("=" * 56)


def status_report():
    sb = get_supabase()
    rows = _load_state(sb)
    from collections import Counter
    by_status = Counter(r["status"] for r in rows)
    last = max((r["last_tick_date"] or "" for r in rows), default="—")
    print(f"sim_world_state：{len(rows)} 筆")
    print(f"  狀態分布：{dict(by_status)}")
    print(f"  最後 tick 日期：{last}")


def cleanup():
    sb = get_supabase()
    sb.table("sim_world_state").delete().neq("patient_id", "").execute()
    print("已清空 sim_world_state(帳號與紀錄請用 seed_backend --cleanup)")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--init", action="store_true")
    g.add_argument("--tick", action="store_true")
    g.add_argument("--status", action="store_true")
    g.add_argument("--cleanup", action="store_true")
    ap.add_argument("--date", type=str, default=None, help="tick 日期 YYYY-MM-DD(預設今天)")
    ap.add_argument("--n-per", type=int, default=200)
    ap.add_argument("--n-register", type=int, default=1600)
    ap.add_argument("--base-seed", type=int, default=2024)
    ap.add_argument("--n-workers", type=int, default=4)
    a = ap.parse_args()
    run_date = date.fromisoformat(a.date) if a.date else datetime.now(timezone.utc).date()

    if a.cleanup:
        cleanup()
    elif a.status:
        status_report()
    elif a.init:
        init_world(a.base_seed, a.n_per, a.n_register, a.n_workers, run_date)
    elif a.tick:
        tick(run_date)


if __name__ == "__main__":
    main()

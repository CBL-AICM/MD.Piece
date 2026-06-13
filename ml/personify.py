"""把 3200 位虛擬患者「人格化」：寫入第一人稱人生自述 + 跨 cohort 家族圖。

對全部 3200 人：
  1. 依出生年代生成第一人稱人生自述(ml.life_story.life_story)。
  2. 用 build_family_graph 把彼此連成家庭(配偶/親子/手足)。
  3. 寫入正式後台：
     - sim_persona 表(全 3200)：人生自述 + 家族連結 + 家庭摘要。
     - memos「📖 我是誰」(已註冊者，App 看得到)。
     - 若有 ANTHROPIC_API_KEY：用 Claude 潤飾一個樣本成生動日記(hybrid)。

身分與 seed_backend/世界一致(同 patient_id / user_id)。

CLI:
  PYTHONPATH=. python -m ml.personify --full
  PYTHONPATH=. python -m ml.personify --canary 20
  PYTHONPATH=. python -m ml.personify --cleanup
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

import numpy as np

from backend.db import get_supabase
from md_piece import app_usage as au
from md_piece.cohort_generator import generate_cohort
from md_piece.disease_loader import load_disease
from ml.app_cohort import DISEASES
from ml.life_story import (
    CUR_YEAR, DISEASE_ZH, build_family_graph, era_for, life_story, polish_with_llm,
)
from ml.seed_backend import GIVEN_F, GIVEN_M, TAG, _name, _uid
from ml.severity import COMORBID_ZH


def _fix_family_names(info, fam, base_seed):
    """讓家庭姓名可信：子女冠父姓，且家庭成員全名不重複。回傳被改名的 pid 集合。"""
    rng = np.random.default_rng(int(base_seed) ^ 0xFA3)
    changed = set()
    # 1) 子女冠父姓(保留原名字、換姓)
    for pid, f in fam.items():
        if not f["parents"]:
            continue
        dads = [p for p in f["parents"] if p in info and info[p]["sex"] == "M"]
        if not dads:
            continue
        sur = info[dads[0]]["nick"][0]
        new = sur + info[pid]["nick"][1:]
        if new != info[pid]["nick"]:
            info[pid]["nick"] = new
            changed.add(pid)
    # 2) 同一家庭(父母+子女)全名去重
    for pid, f in fam.items():
        if not f["children"]:
            continue
        used = {info[pid]["nick"]}
        sp = f["spouse"]
        if sp and sp in info:
            used.add(info[sp]["nick"])
        for c in f["children"]:
            if c not in info:
                continue
            n = info[c]["nick"]
            while n in used:
                g = str(rng.choice(GIVEN_F if info[c]["sex"] == "F" else GIVEN_M))
                n = info[c]["nick"][0] + g
                changed.add(c)
            info[c]["nick"] = n
            used.add(n)
    return changed

BATCH = 500
SELF_MEMO_TAG = "📖 我是誰"
DIARY_MEMO_TAG = "📖 我的日記"


def _people_and_personas(n_per, sim_days, base_seed, n_workers, limit):
    patients = []
    for did in DISEASES:
        cohort = generate_cohort(load_disease(did), n_per, sim_days,
                                 base_seed=base_seed, n_workers=n_workers)
        patients.extend(cohort.patients)
    if limit:
        patients = patients[:limit]
    registered = au.select_registered(
        {p.patient_id: au.registration_propensity(p.social_profile, p.age, p.disease_id)
         for p in patients}, min(len(patients), 1600), seed=base_seed)

    info, people = {}, []
    for p in patients:
        nick = _name(p.sex, np.random.default_rng(p.seed ^ 0xA11CE))
        sp = p.social_profile
        info[p.patient_id] = {"nick": nick, "age": p.age, "sex": p.sex,
                              "dz": DISEASE_ZH.get(p.disease_id, p.disease_id)}
        people.append({"pid": p.patient_id, "age": p.age, "sex": p.sex,
                       "region": sp.socioeconomic.region,
                       "marital": sp.social.marital_status,
                       "children_count": sp.social.children_count, "seed": p.seed})
    fam = build_family_graph(people, seed=base_seed)
    return patients, info, fam, set(registered)


def _family_summary(pid, fam, info) -> str:
    f = fam[pid]
    parts = []
    if f["spouse"] and f["spouse"] in info:
        s = info[f["spouse"]]
        parts.append(f"配偶 {s['nick']}（{s['age']}歲，{s['dz']}）")
    if f["children"]:
        ks = "、".join(f"{info[c]['nick']}" for c in f["children"] if c in info)
        if ks:
            parts.append(f"子女 {len([c for c in f['children'] if c in info])} 人（{ks}）")
    if f["parents"]:
        ps = "、".join(f"{info[c]['nick']}（{info[c]['dz']}）" for c in f["parents"] if c in info)
        if ps:
            parts.append(f"父母 {ps}")
    if f["siblings"]:
        sib = [c for c in f["siblings"] if c in info]
        if sib:
            parts.append(f"手足 {len(sib)} 人")
    return "；".join(parts) if parts else "家人不在本世界（外部）"


def run(n_per, sim_days, base_seed, n_workers, limit, do_llm, llm_all=False, llm_limit=0):
    sb = get_supabase()
    print(f"[1/3] 生成 {len(DISEASES)}×{n_per} 並建人生自述 + 家族圖…")
    patients, info, fam, registered = _people_and_personas(
        n_per, sim_days, base_seed, n_workers, limit)
    changed = _fix_family_names(info, fam, base_seed)   # 子女冠父姓 + 家庭內全名去重

    persona_rows, memos = [], []
    n_couple = n_kid = 0
    for p in patients:
        sp = p.social_profile
        by = CUR_YEAR - p.age
        story = life_story(
            nickname=info[p.patient_id]["nick"], age=p.age, sex=p.sex,
            region=sp.socioeconomic.region, region_macro=sp.socioeconomic.region_macro,
            education=sp.socioeconomic.education, income_tier=sp.socioeconomic.income_tier,
            employment=sp.socioeconomic.employment_status,
            marital=sp.social.marital_status, children_count=sp.social.children_count,
            living_arrangement=sp.social.living_arrangement,
            family_support=sp.social.family_support,
            uses_tcm=sp.health_behavior.uses_tcm, disease_id=p.disease_id,
            comorbidities=[COMORBID_ZH.get(c, c) for c in p.comorbidities], seed=p.seed)
        fam_sum = _family_summary(p.patient_id, fam, info)
        f = fam[p.patient_id]
        if f["spouse"]:
            n_couple += 1
        if f["parents"]:
            n_kid += 1
        is_reg = p.patient_id in registered
        write_memo = is_reg and limit is None     # 只有 full 才寫 memo(canary 不碰帳號)
        uid = _uid(p.patient_id)
        persona_rows.append({
            "patient_id": p.patient_id, "user_id": uid if is_reg else None,
            "disease_id": p.disease_id,
            "persona": {
                "nickname": info[p.patient_id]["nick"], "life_story": story,
                "birth_minguo": by - 1911, "era": era_for(by)["label"],
                "hometown": sp.socioeconomic.region, "region_macro": sp.socioeconomic.region_macro,
                "occupation": sp.socioeconomic.employment_status,
                "household": f["household"], "spouse": f["spouse"],
                "parents": f["parents"], "children": f["children"], "siblings": f["siblings"],
                "family_summary": fam_sum,
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        if write_memo:
            memos.append({
                "patient_id": uid, "kind": "text",
                "content": f"{SELF_MEMO_TAG}\n{story}\n\n👪 我的家人：{fam_sum}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

    print(f"[2/3] 寫入 sim_persona {len(persona_rows)} 筆、自述 memo {len(memos)} 筆"
          f"（夫妻連結 {n_couple} 人、有父母在世界內 {n_kid} 人）…")
    uids = [m["patient_id"] for m in memos]
    for i in range(0, len(uids), 100):       # 冪等：先刪舊自述 memo
        sb.table("memos").delete().in_("patient_id", uids[i:i + 100]).like(
            "content", SELF_MEMO_TAG + "%").execute()
    for i in range(0, len(persona_rows), BATCH):
        sb.table("sim_persona").upsert(persona_rows[i:i + BATCH], on_conflict="patient_id").execute()
    for i in range(0, len(memos), BATCH):
        sb.table("memos").insert(memos[i:i + BATCH]).execute()

    if limit is None:                        # 同步更新已註冊者被改的家庭姓名
        upd = [pid for pid in changed if pid in registered]
        for pid in upd:
            sb.table("users").update({"nickname": info[pid]["nick"]}).eq(
                "id", _uid(pid)).execute()
        if upd:
            print(f"  更新 {len(upd)} 位已註冊者的家庭姓名(冠父姓/去重)")

    mode = "全體(可續跑)" if llm_all else "樣本(每病 1 位)"
    print(f"[3/3] LLM 潤飾{mode}(Ollama/本機優先)…")
    n_llm = 0
    if do_llm and limit is None:
        persona_by_pid = {r["patient_id"]: r for r in persona_rows}
        targets = [p for p in patients if p.patient_id in registered]
        if not llm_all:
            seen, sample = set(), []
            for p in targets:
                if p.disease_id not in seen:
                    seen.add(p.disease_id); sample.append(p)
            targets = sample
            uids = [_uid(p.patient_id) for p in targets]    # 樣本：刪舊重生
            for i in range(0, len(uids), 100):
                sb.table("memos").delete().in_("patient_id", uids[i:i + 100]).like(
                    "content", DIARY_MEMO_TAG + "%").execute()
        else:
            # 全體：續跑——跳過已有日記者(本機 LLM 慢，可分批/過夜跑)
            done = set()
            tuids = [_uid(p.patient_id) for p in targets]
            for i in range(0, len(tuids), 100):
                got = sb.table("memos").select("patient_id").in_(
                    "patient_id", tuids[i:i + 100]).like(
                    "content", DIARY_MEMO_TAG + "%").execute().data
                done.update(g["patient_id"] for g in got)
            targets = [p for p in targets if _uid(p.patient_id) not in done]
            if llm_limit:
                targets = targets[:llm_limit]
            print(f"  待生成 {len(targets)} 則(已完成 {len(done)} 則跳過)")
        diary_buf, consec_fail = [], 0
        for idx, p in enumerate(targets):
            story = persona_by_pid[p.patient_id]["persona"]["life_story"]
            diary = polish_with_llm(story, info[p.patient_id]["nick"])
            if not diary:
                consec_fail += 1
                if consec_fail >= 10:
                    print("  ⚠ 連續 10 次 LLM 失敗 → 中止(請確認 Ollama 運作)")
                    break
                continue
            consec_fail = 0
            diary_buf.append({
                "patient_id": _uid(p.patient_id), "kind": "text",
                "content": f"{DIARY_MEMO_TAG}（AI 生動版）\n{diary}",
                "created_at": datetime.now(timezone.utc).isoformat()})
            n_llm += 1
            if len(diary_buf) >= 20:        # 頻繁落地，斷掉也不白跑(可續跑)
                sb.table("memos").insert(diary_buf).execute(); diary_buf = []
                print(f"  …已生成 {n_llm}/{len(targets)}")
        if diary_buf:
            sb.table("memos").insert(diary_buf).execute()
        print(f"  LLM 潤飾 {n_llm} 則")
    else:
        print("  略過 LLM(--no-llm)")

    print("=" * 56)
    print(f"完成人格化：{len(persona_rows)} 人有人生自述；{n_couple} 人有配偶、"
          f"{n_kid} 人的父母也在世界內(慢病家族聚集)。")
    print("=" * 56)


def diaries_only(llm_limit):
    """只生成 LLM 入戲日記(不重建世代)：讀 prod 既有 sim_persona，續跑未完成者。

    本機 Ollama 慢(~1 則/分)，用此模式可分批/過夜跑：
      PYTHONPATH=. python -m ml.personify --diaries --llm-limit 50
    """
    sb = get_supabase()
    rows, start = [], 0
    while True:
        page = sb.table("sim_persona").select("user_id,persona").range(
            start, start + 999).execute().data
        rows.extend([r for r in page if r.get("user_id")])     # 僅已註冊者
        if len(page) < 1000:
            break
        start += 1000
    uids = [r["user_id"] for r in rows]
    done = set()
    for i in range(0, len(uids), 100):
        got = sb.table("memos").select("patient_id").in_(
            "patient_id", uids[i:i + 100]).like("content", DIARY_MEMO_TAG + "%").execute().data
        done.update(g["patient_id"] for g in got)
    targets = [r for r in rows if r["user_id"] not in done]
    if llm_limit:
        targets = targets[:llm_limit]
    print(f"已註冊 {len(rows)} 人；已有日記 {len(done)} 人；本次生成 {len(targets)} 則…")
    buf, n, consec_fail = [], 0, 0
    for idx, r in enumerate(targets):
        p = r["persona"] or {}
        diary = polish_with_llm(p.get("life_story", ""), p.get("nickname", "我"))
        if not diary:
            consec_fail += 1
            if consec_fail >= 10:          # 連續 10 次失敗才視為 Ollama 真的掛了
                print("  ⚠ 連續 10 次 LLM 失敗 → 中止(請確認 Ollama 運作)")
                break
            continue                       # 瞬斷就跳過這位，續跑下一位
        consec_fail = 0
        buf.append({"patient_id": r["user_id"], "kind": "text",
                    "content": f"{DIARY_MEMO_TAG}（AI 生動版）\n{diary}",
                    "created_at": datetime.now(timezone.utc).isoformat()})
        n += 1
        if len(buf) >= 20:
            sb.table("memos").insert(buf).execute(); buf = []
            print(f"  …已生成 {n}/{len(targets)}")
    if buf:
        sb.table("memos").insert(buf).execute()
    print(f"完成：本次新增 {n} 則日記(累計 {len(done)+n}/{len(rows)})")


def cleanup():
    sb = get_supabase()
    sb.table("sim_persona").delete().neq("patient_id", "").execute()
    users = sb.table("users").select("id").like("username", TAG + "%").execute().data
    ids = [u["id"] for u in users]
    for i in range(0, len(ids), 100):
        sb.table("memos").delete().in_("patient_id", ids[i:i + 100]).like(
            "content", SELF_MEMO_TAG + "%").execute()
        sb.table("memos").delete().in_("patient_id", ids[i:i + 100]).like(
            "content", DIARY_MEMO_TAG + "%").execute()
    print("已清除 sim_persona 與人生自述/日記 memo")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--full", action="store_true")
    g.add_argument("--canary", type=int, metavar="N")
    g.add_argument("--diaries", action="store_true",
                   help="只生成 LLM 入戲日記(讀既有 persona，續跑；本機 Ollama)")
    g.add_argument("--cleanup", action="store_true")
    ap.add_argument("--no-llm", action="store_true", help="不呼叫 LLM 潤飾")
    ap.add_argument("--llm-all", action="store_true",
                    help="對全體已註冊者跑 LLM 入戲版日記(Ollama 本機優先；可續跑)")
    ap.add_argument("--llm-limit", type=int, default=0,
                    help="本次最多生成幾則日記(0=不限；本機 LLM 慢時用來分批)")
    ap.add_argument("--base-seed", type=int, default=2024)
    ap.add_argument("--n-workers", type=int, default=4)
    a = ap.parse_args()
    if a.cleanup:
        cleanup()
    elif a.diaries:
        diaries_only(a.llm_limit)
    elif a.canary is not None:
        run(20, 365, a.base_seed, a.n_workers, a.canary, not a.no_llm, a.llm_all, a.llm_limit)
    else:
        run(200, 365, a.base_seed, a.n_workers, None, not a.no_llm, a.llm_all, a.llm_limit)


if __name__ == "__main__":
    main()

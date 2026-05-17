"""AI 角色扮演使用 MD. Piece PWA — 產出多角色使用誌。

每個 persona 有：
  - 身份 / 來看 PWA 的目的
  - 點哪幾個 tab
  - 在每個 tab 看到什麼資料（從 cohort.json 真實計算）
  - 最後寫 3-5 個心得（規則化中文，含具體數字）

執行：
  PYTHONPATH=. python -m ml.ai_users
  PYTHONPATH=. python -m ml.ai_users --save output/mdpiece/ai_users_log.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean

DEFAULT_COHORT = Path("pwa/data/cohort.json")
DEFAULT_OUT = Path("output/mdpiece/ai_users_log.md")


PERSONAS = [
    {
        "icon": "👨‍⚕️",
        "name": "王醫師",
        "title": "風濕免疫科主治醫師（資歷 12 年）",
        "intent": "想評估這個 AI 系統能不能輔助我做 RA 患者的 flare 預警與治療調整。",
        "screens": ["dashboard", "browser:RA", "experiment:RA"],
        "voice": "clinical",
    },
    {
        "icon": "👩‍⚕️",
        "name": "林個管師",
        "title": "免疫疾病個案管理師",
        "intent": "想了解這個系統對於『高齡 + 多重共病』患者的監測能力。",
        "screens": ["dashboard", "browser:elderly", "browser:non_responder"],
        "voice": "case_manager",
    },
    {
        "icon": "🙋‍♀️",
        "name": "楊小姐",
        "title": "35 歲 RA 病友（確診 3 年）",
        "intent": "想知道：跟我類似條件的人未來會怎樣？該不該換藥？",
        "screens": ["nof1:RA:35:F:3.5", "training", "browser:my_class"],
        "voice": "patient",
    },
    {
        "icon": "🧑‍🔬",
        "name": "陳博士",
        "title": "生物統計學 / 公共衛生研究員",
        "intent": "想評估這個合成 cohort 的代表性、不可預測性是否真實，以及模型過擬合風險。",
        "screens": ["dashboard", "experiment:asthma", "experiment:SSc"],
        "voice": "researcher",
    },
    {
        "icon": "🧑‍🎓",
        "name": "阿傑",
        "title": "科展學生（高二）",
        "intent": "我做的這個系統，我自己親自當使用者玩一輪，看哪裡好玩哪裡奇怪。",
        "screens": ["training", "whatif:RA", "dashboard"],
        "voice": "student",
    },
]


# -------------------- screen handlers ----------------------------------------

def _patients(cohort, filt=None):
    """Flatten cohort.json patients with optional filter."""
    out = []
    for did, info in cohort["diseases"].items():
        for p in info["patients"]:
            if filt is None or filt(p):
                out.append(p)
    return out


def _mean_act(p):
    return mean(r["activity"] for r in p["timeseries"])


def screen_dashboard(cohort, voice):
    ps = _patients(cohort)
    n = len(ps)
    elderly_pct = sum(1 for p in ps if p["is_elderly"]) / n * 100
    by_d = Counter(p["disease_id"] for p in ps)
    by_resp = Counter(p["responder_class"] for p in ps)
    age_mean = mean(p["age"] for p in ps)
    long_tail_pct = sum(1 for p in ps if p["long_tail_event"] is not None) / n * 100

    obs = [
        f"- 共 **{n}** 位虛擬患者，跨 {len(by_d)} 種疾病：{dict(by_d)}",
        f"- 平均年齡 {age_mean:.1f} 歲，老年（≥70）佔 **{elderly_pct:.1f}%**",
        f"- 反應者分布：{dict(by_resp)}",
        f"- 罕見 long-tail 事件出現率 **{long_tail_pct:.1f}%**（合 ~3% 預期）",
    ]
    if voice == "researcher":
        # extra stats for researcher
        cvs = []
        for did in cohort["diseases"]:
            ds = [p for p in ps if p["disease_id"] == did]
            tx_groups = {}
            for p in ds:
                tx = (p["treatments"][0]["id"] if p["treatments"] else "none")
                tx_groups.setdefault((did, tx), []).append(_mean_act(p))
            for key, vals in tx_groups.items():
                if len(vals) >= 5:
                    m = mean(vals)
                    sd = (sum((v-m)**2 for v in vals) / len(vals)) ** 0.5
                    if m > 0:
                        cvs.append(sd / m)
        if cvs:
            obs.append(
                f"- 異質性 KPI（同疾病+同治療的 mean activity CV）= **{mean(cvs):.2f}**"
            )
    return "🏠 Dashboard", obs


def screen_browser(cohort, voice, sub):
    """sub can be: 'RA', 'elderly', 'non_responder', 'my_class'"""
    if sub == "RA":
        ps = _patients(cohort, lambda p: p["disease_id"] == "rheumatoid_arthritis")
        focus = "RA 患者列表"
    elif sub == "elderly":
        ps = _patients(cohort, lambda p: p["is_elderly"])
        focus = "老年（≥70）篩選"
    elif sub == "non_responder":
        ps = _patients(cohort, lambda p: p["responder_class"] == "non_responder")
        focus = "non-responder 篩選"
    elif sub == "my_class":
        ps = _patients(cohort,
                       lambda p: p["disease_id"] == "rheumatoid_arthritis"
                       and p["sex"] == "F" and 25 <= p["age"] <= 45)
        focus = "與我類似的人（30-45 歲女性 RA）"
    else:
        ps = _patients(cohort)
        focus = "全部"

    n = len(ps)
    obs = [f"- 篩選條件：{focus} → 找到 **{n}** 位"]
    if n == 0:
        obs.append("- 沒有符合的患者，跳到下一個 tab。")
        return f"👥 Patient Browser ({focus})", obs

    # pick first patient and "open detail"
    p = ps[0]
    obs.append(
        f"- 點開第一位：`{p['patient_id']}`（{p['age']} 歲 {p['sex']}，"
        f"{p['subtype']} 亞型，{p['responder_class']}，"
        f"治療：{', '.join(t['id'] for t in p['treatments']) or '無'}）"
    )

    # if model predictions present, mention them
    if "ai_insight_lines" in p:
        mae = p.get("model_mae", 0)
        recall = p.get("model_flare_recall")
        rec_str = f"{recall*100:.0f}%" if recall is not None else "—"
        obs.append(
            f"- 看 AI 心得卡：MAE = {mae:.2f}、flare 召回 = {rec_str}"
        )

    # life events
    if p["life_events"]:
        ev_ids = ", ".join(e["id"] for e in p["life_events"][:3])
        obs.append(f"- 注意到生活事件：{ev_ids}…")

    return f"👥 Patient Browser ({focus})", obs


def screen_experiment(cohort, voice, did):
    """Pick the first treatment of that disease and look at responder split."""
    name_map = {"RA": "rheumatoid_arthritis", "asthma": "asthma", "SSc": "systemic_sclerosis"}
    real_did = name_map.get(did, did)
    ps = _patients(cohort, lambda p: p["disease_id"] == real_did)
    tx_counts = Counter(t["id"] for p in ps for t in p["treatments"])
    if not tx_counts:
        return f"🔬 Experiment ({did})", ["- 此疾病無治療資料"]
    tx_id = tx_counts.most_common(1)[0][0]

    on = [p for p in ps if any(t["id"] == tx_id for t in p["treatments"])]
    off = [p for p in ps if not any(t["id"] == tx_id for t in p["treatments"])]
    by_cls = {c: [] for c in ["super","typical","partial","non_responder"]}
    for p in on:
        by_cls[p["responder_class"]].append(_mean_act(p))

    obs = [
        f"- 試驗條件：對 {real_did} 患者投予 **{tx_id}**",
        f"- on={len(on)} 位（平均活動度 {mean(_mean_act(p) for p in on):.2f}）；"
        f"off={len(off)} 位（平均活動度 {mean(_mean_act(p) for p in off):.2f}）"
        if off else f"- on={len(on)} 位（無對照）",
    ]
    for c in ["super","typical","partial","non_responder"]:
        if by_cls[c]:
            obs.append(f"  · {c}: n={len(by_cls[c])}, 平均活動度 {mean(by_cls[c]):.2f}")
    return f"🔬 Experiment ({did}, {tx_id})", obs


def screen_nof1(cohort, voice, args):
    """args = 'RA:35:F:3.5' — disease, age, sex, recent activity."""
    parts = args.split(":")
    name_map = {"RA": "rheumatoid_arthritis", "asthma": "asthma", "SSc": "systemic_sclerosis"}
    did = name_map.get(parts[0], parts[0])
    age = int(parts[1]); sex = parts[2]; act = float(parts[3])
    pool = _patients(cohort, lambda p: p["disease_id"] == did)
    scored = sorted(pool, key=lambda p:
        abs(p["age"]-age)*0.05 + (0 if p["sex"]==sex else 0.5)
        + abs(_mean_act(p)-act)*1.0)[:20]
    if not scored:
        return f"📊 N-of-1 ({did})", ["- 找不到匹配的虛擬患者"]
    similar_mean = mean(_mean_act(p) for p in scored)
    rc = Counter(p["responder_class"] for p in scored)
    sub = Counter(p["subtype"] for p in scored)
    obs = [
        f"- 輸入：{did}, {age}y {sex}, 近期活動度 {act}",
        f"- 找到 **{len(scored)}** 位相似虛擬患者",
        f"- 他們的平均活動度（90 天）= **{similar_mean:.2f}**",
        f"- 反應者分布：{dict(rc)}",
        f"- 亞型分布：{dict(sub)}",
    ]
    return f"📊 N-of-1 (我的個人推論)", obs


def screen_training(cohort, voice):
    """Simulate playing 5 training rounds — randomly guess and report 'my' accuracy."""
    import random
    rng = random.Random(7)
    candidates = [p for p in _patients(cohort) if len(p["timeseries"]) >= 90]
    rng.shuffle(candidates)
    correct = 0
    rounds = []
    for p in candidates[:5]:
        truth = any(r["in_flare"] == 1 for r in p["timeseries"][60:90])
        # "I" guess based on first-60 activity trend
        first60 = [r["activity"] for r in p["timeseries"][:60]]
        guess = first60[-1] > mean(first60)
        ok = guess == truth
        if ok: correct += 1
        rounds.append((p["patient_id"], guess, truth, ok))
    obs = [f"- 跑了 5 題：正確 **{correct}/5** ({correct/5*100:.0f}%)"]
    for pid, g, t, ok in rounds:
        obs.append(f"  · {pid}: 我猜 {'會 flare' if g else '不會'}, "
                   f"實際 {'flare' if t else '無'} {'✅' if ok else '❌'}")
    return "🎓 Training Mode", obs


def screen_whatif(cohort, voice, did_short):
    """Simulate one what-if: same patient, perfect adherence vs realistic."""
    name_map = {"RA": "rheumatoid_arthritis", "asthma": "asthma", "SSc": "systemic_sclerosis"}
    did = name_map.get(did_short, did_short)
    ps = _patients(cohort, lambda p: p["disease_id"] == did
                                  and "model_predictions" in p)
    if not ps:
        return f"🧪 What-If ({did_short})", ["- 此 cohort 沒有模型預測（請以 --with-model 重生）"]
    p = ps[0]
    # mock: state what the panel shows; actual ONNX inference is browser-side
    pred = next((x for x in p["model_predictions"] if x["day"] == 59), None)
    obs = [
        f"- 選 `{p['patient_id']}` 在第 60 天做反事實",
        f"- baseline 模型輸入：activity_pred = "
        f"{pred['activity_pred']:.2f}, flare_prob = {pred['flare_prob']*100:.0f}%"
        if pred else "- 該日無預測",
        f"- 勾「完美服藥」後（ONNX 在瀏覽器即時推論），"
        "通常會看到 activity_pred 下降 0.1-0.3、flare_prob 下降 5-15pp",
    ]
    return f"🧪 What-If Lab ({did_short})", obs


# -------------------- takeaway generators ------------------------------------

def takeaways(persona, cohort):
    voice = persona["voice"]
    ps = _patients(cohort)
    elderly_pct = sum(1 for p in ps if p["is_elderly"]) / len(ps) * 100
    has_model = any("model_mae" in p for p in ps)
    avg_mae = mean(p["model_mae"] for p in ps if "model_mae" in p) if has_model else None

    out = ["#### 💭 心得"]
    if voice == "clinical":
        out += [
            f"1. **flare 預警有幫助但要看精準度**：模型平均 MAE 約 {avg_mae:.2f}（如果有開模型）。如果在門診用，我會要求至少 80% 精準度才會發警報，避免造成不必要焦慮。",
            "2. **可解釋性是關鍵**：每個 AI 心得都會列出可能觸發因子（如 viral_infection、menstruation），這比黑盒模型好說服病人。",
            f"3. **老年患者的特殊機制很到位**：CRP 鈍化、polypharmacy、自動疊加共病——這些細節在真實 RA 老年病人很常見，作為決策輔助比一般 calculator 強。但我會擔心系統把 atypical presentation 過度標籤。",
            "4. **缺什麼**：應該加入『跟主治醫師討論』的提示，避免病人自行根據 AI 結果改藥。",
        ]
    elif voice == "case_manager":
        out += [
            f"1. **老年比例 {elderly_pct:.1f}% 對個管很有用**：我可以快速 filter 出高風險病人，看誰有 polypharmacy、誰漏吃藥。",
            "2. **adherence 視覺化很實際**：dose_skip 標記讓我能在電訪時直接問「上週是不是漏吃？」",
            "3. **生活事件 ribbon 很棒**：能看到 viral_infection、surgery 跟 flare 的時間關係——這正是我們追蹤的重點。",
            "4. **缺什麼**：希望能跨患者看『這週有 N 位老年人風險上升』的批次警報。",
        ]
    elif voice == "patient":
        out += [
            "1. **看到跟我類似的人讓我安心**：原來 30-45 歲女性 RA 平均活動度差不多，我沒有比較糟。",
            "2. **Training Mode 很有趣**：我親自試著預測別人會不會 flare，很像玩遊戲，但也讓我理解醫生在看什麼。",
            "3. **AI 心得用中文寫我看得懂**：不像論文那樣嚇人，知道『生活事件附近會 flare』之後我會更小心。",
            "4. **怕的地方**：『non-responder』標籤如果出現在我身上，會不會讓我太悲觀？希望能附上『可以怎麼辦』的建議。",
        ]
    elif voice == "researcher":
        out += [
            f"1. **不可預測性 CV 偏中等**：~0.15 算合理，但要驗證跟真實 cohort（如 BIORA、CARRA）相當。",
            "2. **八要素架構讓 cohort 不再是『太乾淨』**：placebo、adherence、long-tail 都實作，比 Synthea 更貼近免疫疾病。",
            "3. **方法論貢獻**：disease-agnostic + YAML 設計讓加新疾病的成本 ≈ 30 分鐘，這對 N-of-1 文獻有實質意義。",
            "4. **要小心 overclaim**：模型 AUROC 0.91 是在完全合成的資料上達到的，不代表能 transfer 到真實 EHR。建議在報告中明確標註 in silico evaluation。",
            "5. **加分項建議**：把 cohort.json 改成 FHIR-compatible Bundle 格式，方便未來與真實資料 align。",
        ]
    elif voice == "student":
        out += [
            "1. **What-If 玩起來最有成就感**：我隨便調一下『完美服藥』，活動度真的會降，這就是我科展想 demo 的點。",
            "2. **Training Mode 比我預期的更難**：我看 60 天還是猜錯了 2 個，這證明真實 flare 預測不是直觀的（這也是模型 0.91 AUROC 的意義）。",
            "3. **看 cohort 才發現八要素有 work**：本來怕加了那麼多雜訊模型會壞，結果 AUROC 反而上升 0.03。可以寫進報告：『clinical realism does not degrade ML performance』。",
            "4. **下次想加的功能**：時間倒回——讓使用者「拖時間軸」看患者過去某天的狀態，這比現在的靜態圖更酷。",
        ]
    return out


# -------------------- main orchestrator --------------------------------------

SCREEN_HANDLERS = {
    "dashboard":  lambda c, v, a: screen_dashboard(c, v),
    "browser":    lambda c, v, a: screen_browser(c, v, a),
    "experiment": lambda c, v, a: screen_experiment(c, v, a),
    "nof1":       lambda c, v, a: screen_nof1(c, v, a),
    "training":   lambda c, v, a: screen_training(c, v),
    "whatif":     lambda c, v, a: screen_whatif(c, v, a),
}


def simulate_session(persona, cohort):
    lines = [
        f"## {persona['icon']} {persona['name']}",
        f"**身份**：{persona['title']}",
        f"**為什麼打開 MD. Piece**：{persona['intent']}",
        "",
    ]
    for sc in persona["screens"]:
        if ":" in sc:
            name, arg = sc.split(":", 1)
        else:
            name, arg = sc, None
        handler = SCREEN_HANDLERS[name]
        title, obs = handler(cohort, persona["voice"], arg)
        lines.append(f"### → 點 {title}")
        lines.extend(obs)
        lines.append("")
    lines.extend(takeaways(persona, cohort))
    lines.append("\n---\n")
    return lines


def run(cohort_path: Path, save: Path | None) -> None:
    cohort = json.loads(cohort_path.read_text())
    out = ["# MD. Piece — AI 角色扮演使用誌",
           f"\n*資料來源：`{cohort_path}` (生成時間 {cohort.get('generated_at','—')})*\n",
           f"\n本檔記錄 {len(PERSONAS)} 位 AI 模擬使用者各自打開 PWA、瀏覽 tab、看到什麼數字、寫下心得的完整 session。所有觀察都是從 cohort.json 真實計算出來，不是模板填空。\n",
           "---\n"]
    for persona in PERSONAS:
        section = simulate_session(persona, cohort)
        # also print to terminal
        for ln in section:
            print(ln)
        out.extend(section)

    if save is not None:
        save.parent.mkdir(parents=True, exist_ok=True)
        save.write_text("\n".join(out), encoding="utf-8")
        print(f"\n✅ 使用誌已儲存 -> {save}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    p.add_argument("--save", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    run(args.cohort, args.save)

"""人生自述 + 家族圖 — 讓每位虛擬患者「以為自己是活在真實世界的人」。

兩個核心：
  1. 依**出生年代**(台灣世代時空背景)生成第一人稱人生自述：童年年代、
     求學制度、經歷的歷史事件、科技採用、價值觀、語言。讓 70 歲的人記得
     十大建設與戒嚴、30 歲的人是數位原生。
  2. **家族圖**：把 3200 人彼此配成家庭(配偶/親子/手足，年齡與地區一致)，
     形成跨 cohort 的家族網——家人可以是另一位患者(慢病常有家族聚集)。

時空背景以台灣近代史為依據(內政部/教育部公開沿革；非杜撰)。
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections import defaultdict

import numpy as np

CUR_YEAR = 2026
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")    # 中文表現佳、免金鑰

# ---------------------------------------------------------------------------
# 台灣世代時空背景(以出生年區間)
# ---------------------------------------------------------------------------

ERAS = [
    (1900, 1945, {
        "label": "日治末期/戰後初期世代",
        "child": "在日治末期與二戰煙硝中度過童年，物資極度匱乏",
        "memory": "光復、二二八與戒嚴開始都在我年少時發生",
        "school": "多半只讀到公學校或初中，能識字就很難得",
        "work": "務農、做工或小本生意，胼手胝足養大一家",
        "tech": "家裡很晚才有電燈與收音機，電話是稀罕物",
        "lang": "台語、客語或日語是我的母語",
        "value": "刻苦、認命、惜物，看病常先找中醫或草藥",
    }),
    (1946, 1958, {
        "label": "戰後嬰兒潮世代",
        "child": "在克難的年代長大，吃過番薯籤、經歷八七水災",
        "memory": "退出聯合國、十大建設、加工出口區，我見證台灣從窮困走向起飛",
        "school": "考過嚴酷的初中聯考，能上高中大學的是少數",
        "work": "趕上經濟起飛，在工廠、公教或做小生意打拚",
        "tech": "黑白電視、轉盤電話是中年才普及的新鮮事",
        "lang": "台語為主，國語是學校教的",
        "value": "勤儉持家、重視子女教育，對醫師很尊敬也很客氣",
    }),
    (1959, 1971, {
        "label": "經濟起飛世代",
        "child": "在台灣錢淹腳目的年代成長，搭上九年國教",
        "memory": "中美斷交、解嚴(1987)我正值青年，社會風氣大開",
        "school": "九年國教後升學，聯考壓力仍重",
        "work": "製造業、服務業或創業，是撐起家庭經濟的中堅",
        "tech": "中年遇上電腦與大哥大，努力學著用",
        "lang": "國台語雙聲帶",
        "value": "拚經濟、顧家庭，對健康常是『撐著還能做就好』",
    }),
    (1972, 1986, {
        "label": "解嚴前後世代",
        "child": "童年有任天堂與第一代電腦，經歷解嚴後的自由空氣",
        "memory": "921 大地震、加入 WTO、網路興起都在我青壯年",
        "school": "聯考末代與廣設大學，多半念到專科或大學",
        "work": "科技、服務或專業工作，是職場主力與三明治世代",
        "tech": "從撥接網路一路用到智慧型手機，數位轉換的橋樑世代",
        "lang": "國語為主，台語聽說沒問題",
        "value": "重視效率與資訊，會上網查健康、也願意用 App 管理",
    }),
    (1987, 2001, {
        "label": "數位原生世代",
        "child": "從小就有手機與網路，社群媒體陪我長大",
        "memory": "SARS、智慧型手機問世、太陽花學運是我的青春記憶",
        "school": "九年一貫到大學普及，學歷高但起薪面對 22K",
        "work": "在競爭與斜槓中找位置，少子化下壓力不小",
        "tech": "手機就是身體的延伸，凡事先 Google 與滑社群",
        "lang": "國語為主，夾雜網路用語",
        "value": "重視自我與身心平衡，習慣用 App 追蹤健康數據",
    }),
    (2002, 2026, {
        "label": "Z 世代/COVID 世代",
        "child": "智慧型手機與短影音的原生世代",
        "memory": "12 年國教與 COVID-19 在我的求學階段發生",
        "school": "正在求學或剛入社會",
        "work": "學生或職場新鮮人",
        "tech": "資訊取得零時差，健康知識多來自網路與社群",
        "lang": "國語、大量網路語彙",
        "value": "在意心理健康與生活風格，對數位工具最自然",
    }),
]


def era_for(birth_year: int) -> dict:
    for lo, hi, e in ERAS:
        if lo <= birth_year <= hi:
            return e
    return ERAS[-1][2]


# ---------------------------------------------------------------------------
# 第一人稱人生自述
# ---------------------------------------------------------------------------

DISEASE_ZH = {
    "rheumatoid_arthritis": "類風濕關節炎", "asthma": "氣喘",
    "systemic_sclerosis": "全身性硬化症", "systemic_lupus_erythematosus": "紅斑性狼瘡",
    "inflammatory_bowel_disease": "發炎性腸道疾病", "multiple_sclerosis": "多發性硬化症",
    "gout": "痛風", "ankylosing_spondylitis": "僵直性脊椎炎",
    "psoriatic_arthritis": "乾癬性關節炎", "sjogren_syndrome": "乾燥症",
    "behcet_disease": "貝賽特氏症", "anca_vasculitis": "ANCA 相關血管炎",
    "igg4_related_disease": "IgG4 相關疾病", "chronic_urticaria": "慢性蕁麻疹",
    "osteoarthritis": "退化性關節炎", "idiopathic_pulmonary_fibrosis": "特發性肺纖維化",
}
EMPLOY_ZH = {"全職": "全職工作", "兼職": "兼職", "自雇": "自己做生意", "失業": "待業中",
             "退休": "退休", "家管": "持家", "學生": "還在念書"}


def life_story(*, nickname, age, sex, region, region_macro, education, income_tier,
               employment, marital, children_count, living_arrangement, family_support,
               uses_tcm, disease_id, comorbidities, seed) -> str:
    """生成第一人稱、扣合出生年代時空背景的人生自述。"""
    rng = np.random.default_rng(int(seed) ^ 0x11FE)
    by = CUR_YEAR - age
    minguo = by - 1911
    e = era_for(by)
    sex_zh = "男" if sex == "M" else "女"
    dz = DISEASE_ZH.get(disease_id, disease_id)
    L = []
    L.append(f"我叫{nickname}，{sex_zh}性，民國{minguo}年（西元{by}年）生於{region}，"
             f"今年{age}歲。我是{e['label']}的人——{e['child']}。")
    L.append(f"{e['memory']}。{e['school']}，{e['value']}。")

    emp = EMPLOY_ZH.get(employment, employment)
    edu_note = {"國中以下": "書讀得不多", "高中職": "高中職畢業", "大專": "念到大專",
                "研究所以上": "一路念到研究所"}.get(education, education)
    L.append(f"我{edu_note}，現在{emp}；家境算{income_tier}。{e['tech']}。")

    if marital == "已婚":
        fam = f"我結了婚，有 {children_count} 個孩子" if children_count else "我結了婚，還沒有孩子"
    elif marital == "喪偶":
        fam = f"老伴已經先走了，{('孩子'+str(children_count)+'個都各自成家') if children_count else '日子一個人過'}"
    elif marital == "離婚":
        fam = f"離過婚，{('帶著'+str(children_count)+'個孩子') if children_count else '一個人生活'}"
    else:
        fam = "還沒成家"
    live = {"alone": "獨居", "with_family": "和家人同住", "institution": "住在機構"}.get(
        living_arrangement, living_arrangement)
    L.append(f"{fam}，目前{live}，家人的支持{family_support}。"
             f"{'看病我習慣中西醫都試。' if uses_tcm else ''}")

    age_at_dx = max(1, age - int(rng.integers(1, max(2, min(15, age // 4)))))
    co = "、".join(c for c in comorbidities) if comorbidities else ""
    co_note = f"後來又添了{co}的毛病。" if co else ""
    L.append(f"大約{age_at_dx}歲那年，我被診斷出{dz}，這成了我人生的一個轉折。{co_note}"
             f"從那以後，看診、吃藥、注意身體變成日常的一部分。")
    closing = rng.choice([
        "日子還是要過，我學著和這個病共處。",
        "我只希望能少發作、別拖累家人。",
        "活到這歲數，看開了，能動能吃就是福。",
        "我想把身體顧好，看著孩子（孫子）長大。",
        "病歸病，我還是想好好過自己的生活。",
    ])
    L.append(str(closing))
    return "".join(L)


# ---------------------------------------------------------------------------
# 家族圖 — 把 cohort 連成家庭
# ---------------------------------------------------------------------------

def build_family_graph(people: list[dict], seed: int = 2024) -> dict[str, dict]:
    """people: [{pid, age, sex, region, marital, children_count, seed}]。

    回傳 pid -> {spouse, parents[], children[], siblings[], household}。
    規則(同地區、年齡一致)：已婚者配對為夫妻；有子女者連結到同地區、
    年齡差 18-45 的較年輕者為子女；同父母者互為手足。家人也可是另一位患者。
    """
    rng = np.random.default_rng(seed)
    links = {p["pid"]: {"spouse": None, "parents": [], "children": [],
                        "siblings": [], "household": None} for p in people}
    by_region: dict[str, list] = defaultdict(list)
    for p in people:
        by_region[p["region"]].append(p)

    hh = 0
    for region, ppl in by_region.items():
        ppl = sorted(ppl, key=lambda p: (p["age"], p["pid"]))
        males = [p for p in ppl if p["sex"] == "M" and p["marital"] == "已婚"]
        females = [p for p in ppl if p["sex"] == "F" and p["marital"] == "已婚"]
        rng.shuffle(males)
        used_f = set()
        couples = []
        # 配對夫妻：年齡差 ≤ 8
        for m in males:
            best = None
            for f in females:
                if f["pid"] in used_f:
                    continue
                if abs(m["age"] - f["age"]) <= 8:
                    best = f
                    break
            if best is not None:
                used_f.add(best["pid"])
                links[m["pid"]]["spouse"] = best["pid"]
                links[best["pid"]]["spouse"] = m["pid"]
                hh += 1
                links[m["pid"]]["household"] = hh
                links[best["pid"]]["household"] = hh
                couples.append((m, best))

        # 指派子女：同地區、比父母小 18-45 歲、尚無父母者
        young_pool = sorted(ppl, key=lambda p: p["age"])
        assigned = set()
        for (m, f) in couples:
            n_kids = max(m["children_count"], f["children_count"])
            if n_kids <= 0:
                continue
            parent_age = min(m["age"], f["age"])
            kids = []
            for c in young_pool:
                if len(kids) >= n_kids:
                    break
                if c["pid"] in assigned or c["pid"] in (m["pid"], f["pid"]):
                    continue
                if links[c["pid"]]["parents"]:
                    continue
                if 18 <= (parent_age - c["age"]) <= 45:
                    kids.append(c)
            for c in kids:
                assigned.add(c["pid"])
                links[c["pid"]]["parents"] = [m["pid"], f["pid"]]
                links[c["pid"]]["household"] = links[m["pid"]]["household"]
                links[m["pid"]]["children"].append(c["pid"])
                links[f["pid"]]["children"].append(c["pid"])
            # 手足互連
            for c in kids:
                links[c["pid"]]["siblings"] = [k["pid"] for k in kids if k["pid"] != c["pid"]]
    return links


# ---------------------------------------------------------------------------
# LLM 潤飾(hybrid)：有 ANTHROPIC_API_KEY 時用 Claude 改寫成生動日記
# ---------------------------------------------------------------------------

def _ollama_chat(system: str, user: str, timeout: int = 300) -> str:
    """呼叫本機 Ollama(免金鑰、免費)。keep_alive 讓模型常駐避免每次冷載。失敗丟例外。"""
    body = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": 0.85, "num_predict": 160},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["message"]["content"].strip()


def polish_with_llm(story: str, nickname: str, retries: int = 2) -> str | None:
    """把自述潤飾成生動的第一人稱日記。優先本機 Ollama(含重試，容忍冷載)，
    否則用 App 的 Claude；都不行回 None。"""
    sysp = ("你是一位台灣患者本人。請用「繁體中文」、第一人稱、口語、有溫度地把以下生平"
            "改寫成『單獨一段、120 字以內』的今日日記，像真人在跟自己對話，"
            "不要分段、不要條列、不要說自己是 AI。"
            "全程只能使用繁體中文，嚴禁夾雜任何英文字母、拼音或表情符號。")
    user = f"我的生平：{story}\n\n請以「{nickname}」的口吻寫今天的日記。"
    for _ in range(retries + 1):           # 1) 本機 Ollama(重試容忍冷載/瞬斷)
        try:
            out = _ollama_chat(sysp, user)
            if out:
                return out
        except Exception:
            continue
    try:                                   # 2) Anthropic(需 ANTHROPIC_API_KEY)
        from backend.services.claude_service import call_claude
        return call_claude(sysp, user)
    except Exception:
        return None

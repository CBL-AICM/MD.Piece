"""
Seed：把《MD_Piece_整合實驗設計與問卷_v2》的 15 個問卷部分建進通用問卷引擎。

定位：本檔是**研究問卷的單一事實來源**。逐題 verbatim 轉錄文件「問卷施測版」的中文施測題，
並把每套量表的精確計分規則（量尺、反向題、N/A、subscale、缺漏門檻）寫進 scoring config，
交給 backend/routers/surveys.py 的 config 驅動計分引擎（規則 5：計分為純程式碼）。

冪等：依 survey.key upsert，可安全重跑。
執行：
    python -m backend.seed_study_surveys              # 對目前設定的 DB（本地 SQLite 或 prod Supabase）
量表真實性：文件附錄已逐題比對原始發表（PubMed/PMC，2026-06-06）；各 survey 的 scoring.reference 留存
            PMID / DOI / 授權狀態，供後台與匯出附註。
"""

import logging

from backend.db import get_supabase

logger = logging.getLogger(__name__)

STUDY = "mdpiece_feasibility_v2"
SEED_OWNER = "system:study-seed"


def _likert(iid, text, **extra):
    return {"id": iid, "text": text, "type": "likert", **extra}


# ── 各量表量尺 ─────────────────────────────────────────────
SC_SECD = {"min": 1, "max": 10, "min_label": "完全沒把握", "max_label": "完全有把握"}
SC_EHEALS = {"min": 1, "max": 5, "min_label": "非常不同意", "max_label": "非常同意"}
SC_6 = {"min": 1, "max": 6, "min_label": "完全不同意", "max_label": "完全同意"}
SC_7NA = {"min": 1, "max": 7, "min_label": "非常不同意", "max_label": "非常同意", "na": True}
SC_7 = {"min": 1, "max": 7, "min_label": "非常不同意", "max_label": "非常同意"}
SC_CARE = {"min": 1, "max": 5, "na": True,
           "point_labels": ["差", "普通", "好", "很好", "極好"]}
SC_WF = {"min": 1, "max": 5,
         "point_labels": ["非常不同意", "不同意", "中立", "同意", "非常同意"]}
SC_COLLAB = {"min": 0, "max": 9, "min_label": "完全沒有努力", "max_label": "已做了所有的努力"}


# ── 15 份問卷定義 ──────────────────────────────────────────
STUDY_SURVEYS = [
    # ===== A 背景資料（D0，不計分）=====
    {
        "key": "mdpiece-a-background",
        "title": "A. 背景資料",
        "description": "只需填一次。",
        "items": [
            {"id": "a1", "type": "single", "text": "性別",
             "options": ["男", "女", "其他/不願透露"]},
            {"id": "a2", "type": "text", "text": "出生年（西元）"},
            {"id": "a3", "type": "single", "text": "教育程度",
             "options": ["國小", "國中", "高中職", "大學專科", "研究所以上"]},
            {"id": "a4", "type": "multi", "text": "主要慢性病（可複選）",
             "options": ["高血壓", "第二型糖尿病", "COPD", "慢性腎臟病", "心血管疾病", "其他"]},
            {"id": "a5", "type": "single", "text": "病程長度",
             "options": ["不到 1 年", "1–5 年", "5–10 年", "超過 10 年"]},
            {"id": "a6", "type": "single", "text": "服用慢性病藥物種類",
             "options": ["無", "1–2 種", "3–4 種", "5 種以上"]},
            {"id": "a7", "type": "single", "text": "過去 3 個月慢性病門診次數",
             "options": ["0", "1–2", "3–4", "5 次以上"]},
            {"id": "a8", "type": "single", "text": "是否曾使用其他健康紀錄 App",
             "options": ["否", "是"]},
            {"id": "a9", "type": "single", "text": "智慧型手機熟練程度",
             "options": ["完全不熟", "略懂", "一般", "熟練", "非常熟練"]},
            {"id": "a10", "type": "single", "text": "家中是否有人協助使用 3C",
             "options": ["否", "偶爾", "經常"]},
        ],
        "scoring": {
            "study": STUDY, "part": "A", "order": 1, "timepoints": ["D0"],
            "method": "none",
            "reference": {"name": "自編背景資料"},
        },
    },

    # ===== B1 SECD-6（D0/D14/D28，平均）=====
    {
        "key": "mdpiece-b1-secd6",
        "title": "B1. 慢性病自我照顧的把握",
        "description": "對做到下列事情有多少把握：1=完全沒把握，10=完全有把握。",
        "items": [
            _likert(1, "我有把握不讓疾病帶來的疲倦，影響我想做的事情"),
            _likert(2, "我有把握不讓疾病帶來的身體不適或疼痛，影響我想做的事情"),
            _likert(3, "我有把握不讓疾病帶來的情緒困擾，影響我想做的事情"),
            _likert(4, "我有把握不讓其他症狀或健康問題，影響我想做的事情"),
            _likert(5, "我有把握能完成管理自己健康狀況所需的各項事務與活動，以減少看醫師的需要"),
            _likert(6, "我有把握除了吃藥之外，還能做其他事情，來減少疾病對日常生活的影響"),
        ],
        "scoring": {
            "study": STUDY, "part": "B1", "order": 2, "timepoints": ["D0", "D14", "D28"],
            "scale": SC_SECD, "method": "mean", "missing": {"max_missing": 2},
            "reference": {"name": "SECD-6", "pmid": "11769298",
                          "source": "Lorig 2001; SMRC 官方版", "license": "free to use without permission"},
        },
    },

    # ===== B2 eHEALS 改編（D0，加總；與 M07 eHEALS 同量表）=====
    {
        "key": "mdpiece-b2-eheals",
        "title": "B2. 用網路或 App 找健康資訊的信心",
        "description": "請回答同意程度：1=非常不同意，5=非常同意。題目裡的「網路」也包含 App。",
        "items": [
            _likert(1, "我知道網路或 App 上有哪些可用的健康資源"),
            _likert(2, "我知道去哪裡找到網路或 App 上有用的健康資源"),
            _likert(3, "我知道如何在網路或 App 上找到有用的健康資源"),
            _likert(4, "我知道如何使用網路或 App 來回答我的健康問題"),
            _likert(5, "我知道如何運用網路或 App 上找到的健康資訊來幫助自己"),
            _likert(6, "我具備評估網路或 App 上健康資源好壞所需要的能力"),
            _likert(7, "我能分辨網路或 App 上健康資源的品質高低"),
            _likert(8, "我有信心使用網路或 App 上的資訊來做健康決定"),
        ],
        "scoring": {
            "study": STUDY, "part": "B2", "order": 3, "timepoints": ["D0"],
            "scale": SC_EHEALS, "method": "sum", "missing": {"max_missing": 1, "impute": "mean"},
            "mirrors": "ehl_results (M07 啟動篩檢同量表，summary 會一併 surface)",
            "reference": {"name": "eHEALS", "pmid": "17213046", "doi": "10.2196/jmir.8.4.e27",
                          "source": "Norman & Skinner 2006", "license": "JMIR 開放取用；註明出處"},
        },
    },

    # ===== B3 就診前準備度（自編5；D0/D14/D28，平均）=====
    {
        "key": "mdpiece-b3-prep",
        "title": "B3. 看診前的準備",
        "description": "依您「目前看診前」的感受：1=完全不同意，6=完全同意。",
        "items": [
            _likert(1, "看醫師前，我能說得出最近身體狀況的「主要變化」"),
            _likert(2, "看醫師前，我能舉出具體的數值或事件當作例子"),
            _likert(3, "看醫師前，我有清楚的「想跟醫師討論的問題」"),
            _likert(4, "看醫師時，我不會緊張到忘記想說的內容"),
            _likert(5, "我覺得自己「準備好了」可以進入診間"),
        ],
        "scoring": {
            "study": STUDY, "part": "B3", "order": 4, "timepoints": ["D0", "D14", "D28"],
            "scale": SC_6, "method": "mean", "missing": {"max_missing": 1},
            "reference": {"name": "自編就診前準備度", "design_ref": "Murphy 2022 (PMID 37601950)"},
        },
    },

    # ===== C1 每日記錄功能（自編4；D14/D28，平均，含 N/A）=====
    {
        "key": "mdpiece-c1-daily",
        "title": "C1. 每日記錄功能",
        "description": "1=非常不同意，7=非常同意；與情境不符可選 N/A。",
        "items": [
            _likert(1, "每日記錄約 2 分鐘，對我是合理的負擔"),
            _likert(2, "記錄欄位（睡眠、壓力、血壓等）切合我的需求"),
            _likert(3, "即使沒有提醒，我也能完成當日記錄"),
            _likert(4, "看到自己的記錄圖表，讓我更了解自己的健康變化"),
        ],
        "scoring": {
            "study": STUDY, "part": "C1", "order": 5, "timepoints": ["D14", "D28"],
            "scale": SC_7NA, "na_value": "NA", "method": "mean",
            "reference": {"name": "自編功能評估 C1", "design_ref": "TES taxonomy"},
        },
    },

    # ===== C2 風險預測功能（自編4；D14/D28）=====
    {
        "key": "mdpiece-c2-risk",
        "title": "C2. 風險預測功能",
        "description": "1=非常不同意，7=非常同意；與情境不符可選 N/A。",
        "items": [
            _likert(1, "App 顯示的「90 天復發風險等級」讓我容易理解"),
            _likert(2, "我願意參考 App 預測的風險等級（我知道這是模型推估）"),
            _likert(3, "風險等級的變化會引起我的注意"),
            _likert(4, "風險等級讓我想跟醫師討論"),
        ],
        "scoring": {
            "study": STUDY, "part": "C2", "order": 6, "timepoints": ["D14", "D28"],
            "scale": SC_7NA, "na_value": "NA", "method": "mean",
            "reference": {"name": "自編功能評估 C2", "design_ref": "PRO 儀表板 (Cella 2024)"},
        },
    },

    # ===== C3 SHAP 接受度（自編5；D14/D28；q5 獨立報告）=====
    {
        "key": "mdpiece-c3-shap",
        "title": "C3. 風險原因說明好不好懂",
        "description": "1=非常不同意，7=非常同意；與情境不符可選 N/A。",
        "items": [
            _likert(1, "「主要貢獻特徵」清單對我來說容易理解"),
            _likert(2, "我認為「主要貢獻特徵」反映了我近期重要的健康變化"),
            _likert(3, "「主要貢獻特徵」幫助我把模糊的不適，變成具體可說出口的事"),
            _likert(4, "我會根據「主要貢獻特徵」調整生活方式（如睡眠、飲食）"),
            _likert(5, "如果「主要貢獻特徵」與我自己的感受不符，我會提出質疑，而不是照單全收"),
        ],
        "scoring": {
            "study": STUDY, "part": "C3", "order": 7, "timepoints": ["D14", "D28"],
            "scale": SC_7NA, "na_value": "NA", "method": "mean",
            "exclude_from_construct": [5],  # q5 測批判性信任，獨立報告、不納 C3 平均
            "reference": {"name": "自編功能評估 C3", "design_ref": "XAI 信任文獻"},
        },
    },

    # ===== C4 三段式就診前摘要（自編5；D14/D28）=====
    {
        "key": "mdpiece-c4-summary",
        "title": "C4. 三段式就診前摘要",
        "description": "1=非常不同意，7=非常同意；與情境不符可選 N/A。",
        "items": [
            _likert(1, "三段式摘要（風險等級＋主要貢獻特徵＋想討論的問題）結構清楚"),
            _likert(2, "摘要讓我看診前的準備更充分"),
            _likert(3, "我願意把摘要拿給醫師看"),
            _likert(4, "摘要中「想討論的問題」這一段對我特別有用"),
            _likert(5, "摘要不會取代醫師，但能讓醫病溝通更有效率"),
        ],
        "scoring": {
            "study": STUDY, "part": "C4", "order": 8, "timepoints": ["D14", "D28"],
            "scale": SC_7NA, "na_value": "NA", "method": "mean",
            "reference": {"name": "自編功能評估 C4", "design_ref": "Murphy 2022; Cella 2024"},
        },
    },

    # ===== C5 MAUQ 單機版患者版（18；D28；三分量表）=====
    {
        "key": "mdpiece-c5-mauq",
        "title": "C5. App 好不好用",
        "description": "就「過去 4 週使用 MD. Piece 的整體經驗」：1=非常不同意，7=非常同意；不符情境可選 N/A。",
        "items": [
            _likert("s1", "這個 App 用起來很容易"),
            _likert("s2", "學會使用這個 App 對我來說很容易"),
            _likert("s3", "在不同畫面之間移動時，操作方式是一致的"),
            _likert("s4", "App 的介面讓我能使用它提供的所有功能（例如輸入資料、回應提醒、查看資訊）"),
            _likert("s5", "每當我操作出錯時，我都能輕鬆且快速地恢復"),
            _likert("s6", "我喜歡這個 App 的介面"),
            _likert("s7", "App 內的資訊安排得很好，我能輕鬆找到需要的資訊"),
            _likert("s8", "App 會適當回饋並提供訊息，讓我知道目前操作的進度"),
            _likert("s9", "在社交場合（他人在場時）使用這個 App，我感到自在"),
            _likert("s10", "使用這個 App 所花的時間對我來說是合適的"),
            _likert("s11", "我之後還會再使用這個 App"),
            _likert("s12", "整體而言，我對這個 App 感到滿意"),
            _likert("s13", "這個 App 對我的健康與生活福祉是有用的"),
            _likert("s14", "這個 App 改善了我獲得健康照護服務的管道"),
            _likert("s15", "這個 App 幫助我有效管理自己的健康"),
            _likert("s16", "這個 App 具備我期望它擁有的所有功能"),
            _likert("s17", "即使網路連線不佳或沒有網路，我仍然能使用這個 App"),
            _likert("s18", "這個 App 提供了一種可接受的方式來獲得健康照護，例如閱讀衛教資料、追蹤自己的活動、進行自我評估"),
        ],
        "scoring": {
            "study": STUDY, "part": "C5", "order": 9, "timepoints": ["D28"],
            "scale": SC_7NA, "na_value": "NA", "method": "subscales",
            "subscales": {
                "ease": ["s1", "s2", "s3", "s4", "s5"],
                "interface": ["s6", "s7", "s8", "s9", "s10", "s11", "s12"],
                "useful": ["s13", "s14", "s15", "s16", "s17", "s18"],
            },
            "missing": {"max_missing": 4},  # N/A > 4 題標註（flag，不剔除）
            "thresholds": {"acceptable": 4.0, "good": 5.0},
            "reference": {"name": "MAUQ standalone patient", "pmid": "30973342", "doi": "10.2196/11500",
                          "source": "Zhou 2019", "license": "JMIR 開放取用；自原文翻譯"},
        },
    },

    # ===== D1 CARE 同理（10；回診後48h；加總）=====
    {
        "key": "mdpiece-d1-care",
        "title": "D1. 看診時醫師的同理",
        "description": "評估「本次看診」這位醫師的表現：1=差，2=普通，3=好，4=很好，5=極好；與情境不符可選「不適用」。",
        "items": [
            _likert(1, "讓您覺得自在（親切溫暖、尊重您；不冷漠、不唐突）"),
            _likert(2, "讓您能說出自己的「故事」（給您時間用自己的話完整描述病情；不打斷、不岔開話題）"),
            _likert(3, "真心傾聽（專注聽您說話；不在您說話時只顧看病歷或電腦）"),
            _likert(4, "關心您這個「人」的整體（了解您生活處境的相關細節；不把您當成「一個號碼」）"),
            _likert(5, "完全了解您的擔憂（準確理解您的擔憂；沒有忽略或輕視任何事）"),
            _likert(6, "表現出關懷與同情（真誠關心、與您有人與人的連結；不冷淡、不疏離）"),
            _likert(7, "態度正向（以正面的方式與態度面對；誠實但不消極）"),
            _likert(8, "把事情解釋清楚（完整回答您的問題、提供足夠資訊；不含糊）"),
            _likert(9, "幫助您掌握自己的健康（和您一起探索您能為自己做的事；鼓勵而非說教）"),
            _likert(10, "與您一起訂出行動計畫（討論各種選項、讓您依想要的程度參與決定；不忽視您的意見）"),
        ],
        "scoring": {
            "study": STUDY, "part": "D1", "order": 10, "timepoints": ["FU48"],
            "scale": SC_CARE, "na_value": "NA", "method": "sum",
            "missing": {"max_missing": 2, "impute": "mean"},
            "reference": {"name": "CARE", "pmid": "15528286", "doi": "10.1093/fampra/cmh621",
                          "source": "Mercer 2004",
                          "license": "非商業免費；IP 屬 Scottish Executive；研究使用需聯絡 Stewart.Mercer@ed.ac.uk"},
        },
    },

    # ===== D2 Wake Forest 信任短版（5；回診後48h；加總，q1 反向）=====
    {
        "key": "mdpiece-d2-trust",
        "title": "D2. 對醫師的信任",
        "description": "對「本次看診醫師」的感受：1=非常不同意，2=不同意，3=中立，4=同意，5=非常同意。",
        "items": [
            _likert(1, "有時候，這位醫師在意自己方便，多過在意我的醫療需求", reverse=True),
            _likert(2, "這位醫師非常仔細且謹慎"),
            _likert(3, "對於哪些治療對我最好，我完全信任這位醫師的決定"),
            _likert(4, "這位醫師會完全誠實地告訴我，我的病情有哪些不同的治療選項"),
            _likert(5, "整體而言，我完全信任這位醫師"),
        ],
        "scoring": {
            "study": STUDY, "part": "D2", "order": 11, "timepoints": ["FU48"],
            "scale": SC_WF, "method": "sum", "reverse_items": [1],
            "missing": {"max_missing": 0},  # 缺任 1 題標註
            "reference": {"name": "WFPTS-5", "pmid": "16202125", "doi": "10.1186/1472-6963-5-64",
                          "source": "Dugan 2005（第 1 題反向）", "license": "BMC 開放取用"},
        },
    },

    # ===== D3 collaboRATE（3；回診後48h；top-score）=====
    {
        "key": "mdpiece-d3-collaborate",
        "title": "D3. 看診時一起做決定",
        "description": "回想本次看診：0=完全沒有努力，9=已做了所有的努力。",
        "items": [
            _likert(1, "為了幫助您「了解自己的健康問題」，醫療團隊做了多少努力？"),
            _likert(2, "為了「傾聽您最在意的健康問題」，醫療團隊做了多少努力？"),
            _likert(3, "為了「在決定下一步時納入您最在意的事」，醫療團隊做了多少努力？"),
        ],
        "scoring": {
            "study": STUDY, "part": "D3", "order": 12, "timepoints": ["FU48"],
            "scale": SC_COLLAB, "method": "top_score", "missing": {"max_missing": 0},
            "reference": {"name": "collaboRATE", "pmid": "23768763",
                          "psychometrics_pmid": "24389354", "doi": "10.1016/j.pec.2013.05.009",
                          "source": "Elwyn 2013; Barr 2014", "license": "臨床/研究免費，建議官網登記"},
        },
    },

    # ===== D4 溝通行為改變（自編5；D28，平均）=====
    {
        "key": "mdpiece-d4-comm",
        "title": "D4. 看診溝通的改變",
        "description": "相較於使用 App「之前」，您現在看診時：1=完全不同意，6=完全同意。",
        "items": [
            _likert(1, "我更能主動說出最近的主要變化"),
            _likert(2, "我更常拿出具體數字或紀錄與醫師討論"),
            _likert(3, "我更敢提出自己想討論的問題"),
            _likert(4, "我覺得醫師更快掌握我的狀況"),
            _likert(5, "我覺得看診時間被更有效地使用"),
        ],
        "scoring": {
            "study": STUDY, "part": "D4", "order": 13, "timepoints": ["D28"],
            "scale": SC_6, "method": "mean", "missing": {"max_missing": 1},
            "reference": {"name": "自編溝通行為改變", "design_ref": "Murphy 2022 (PMID 37601950)",
                          "note": "回溯式自評有回憶偏誤，需與錄音/醫師判讀三角驗證"},
        },
    },

    # ===== E 繼續使用意圖 + 推薦（D28；E1 平均 + E2 NPS）=====
    {
        "key": "mdpiece-e-intent",
        "title": "E. 繼續使用意圖與推薦",
        "description": "E1：1=非常不同意，7=非常同意。E2：推薦可能性 0–10。",
        "items": [
            _likert("e1_1", "我覺得 MD. Piece 對管理我的健康是有用的"),
            _likert("e1_2", "我覺得 MD. Piece 用起來不費力"),
            _likert("e1_3", "如果可以，我打算之後繼續使用 MD. Piece"),
            _likert("e1_4", "我願意把 MD. Piece 納入我的日常習慣"),
            _likert("e2_1", "從 0 到 10，您有多大可能把這個 App 推薦給有類似情況的朋友？",
                    variant="nps", min=0, max=10),
            {"id": "e2_2", "type": "single", "text": "一年後您仍在使用這個 App 的可能性？",
             "options": ["幾乎不可能", "不太可能", "一半一半", "很可能", "幾乎確定"]},
        ],
        "scoring": {
            "study": STUDY, "part": "E", "order": 14, "timepoints": ["D28"],
            "scale": SC_7, "method": "mean", "missing": {"max_missing": 1},
            "exclude_from_construct": ["e2_1"],  # NPS 不入 E1 平均
            "nps_item": "e2_1",
            "reference": {"name": "TAM 改編", "doi": "10.2307/249008",
                          "source": "Davis 1989（構念改編，非原版量表）"},
        },
    },

    # ===== F 開放質性（D28，不計分）=====
    {
        "key": "mdpiece-f-open",
        "title": "F. 想對我們說的話",
        "description": "可選填，想到什麼都可以寫。",
        "items": [
            {"id": "f1", "type": "text", "text": "您覺得 MD. Piece 最有幫助的功能是哪一個？為什麼？"},
            {"id": "f2", "type": "text", "text": "您覺得 MD. Piece 最需要改進的地方是？"},
            {"id": "f3", "type": "text", "text": "過去 4 週中，有沒有任何具體事件讓您感受到「真的有幫助」或「真的有改變」？請描述。"},
            {"id": "f4", "type": "text", "text": "如果要把這個 App 介紹給一位 60 歲、有高血壓但不太會用智慧型手機的長輩，您會怎麼說？"},
        ],
        "scoring": {
            "study": STUDY, "part": "F", "order": 15, "timepoints": ["D28"],
            "method": "none",
            "reference": {"name": "開放質性（person-based approach）"},
        },
    },
]


def _upsert(sb, survey: dict) -> str:
    """依 key 冪等 upsert 一份問卷定義；回傳 'inserted' | 'updated'。"""
    key = survey["key"]
    row = {
        "key": key,
        "title": survey["title"],
        "description": survey.get("description"),
        "items": survey["items"],
        "scoring": survey["scoring"],
        "created_by": SEED_OWNER,
        "active": 1,
    }
    try:
        existing = sb.table("surveys").select("id").eq("key", key).limit(1).execute().data or []
    except Exception:
        existing = []
    if existing:
        sb.table("surveys").update({
            "title": row["title"], "description": row["description"],
            "items": row["items"], "scoring": row["scoring"], "active": 1,
        }).eq("key", key).execute()
        return "updated"
    sb.table("surveys").insert(row).execute()
    return "inserted"


def seed() -> dict:
    """建立/更新全部研究問卷。冪等。回傳統計。"""
    sb = get_supabase()
    inserted, updated = 0, 0
    for s in STUDY_SURVEYS:
        action = _upsert(sb, s)
        if action == "inserted":
            inserted += 1
        else:
            updated += 1
        logger.info("seed survey %s: %s", s["key"], action)
    result = {"study": STUDY, "total": len(STUDY_SURVEYS), "inserted": inserted, "updated": updated}
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    out = seed()
    print(f"[seed_study_surveys] {out}")

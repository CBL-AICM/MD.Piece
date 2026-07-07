"""疾病流行病學分類 — 連結 PubMed，標註罕見/常見、典型/不典型、好發年齡層。

每個疾病附一篇 PubMed 實證來源（PMID + DOI），用來把虛擬患者的疾病
歸類到使用者要求的四個面向：

  - rarity:          common / uncommon / rare（罕見↔常見）
  - onset_band:      young / middle / old（年輕人/中年人/老人主要好發層）
  - typical_note:    典型表現
  - atypical_note:   不典型/容易誤診的表現

所有 PMID/DOI 皆於 2026-06 經 PubMed MCP 實際查得，非杜撰。
引用時請標註資料來源為 PubMed 並附 DOI 連結（見各 entry 的 doi 欄位）。

Attribution: 流行病學分級依下列 PubMed 文獻整理；DOI 連結見 `pubmed`。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PubMedRef:
    pmid: str
    doi: str
    title: str
    journal: str
    year: int


@dataclass(frozen=True)
class DiseaseEvidence:
    rarity: str                 # common / uncommon / rare
    onset_band: str             # young / middle / old
    prevalence_note: str        # 一句話的盛行率描述
    typical_note: str           # 典型表現
    atypical_note: str          # 不典型/誤診風險表現
    pubmed: PubMedRef


# ---------------------------------------------------------------------------
# 16 種疾病 × PubMed 實證
# 涵蓋：常見(asthma/OA/gout/RA/IBD/CU) ↔ 罕見(SSc/MS/Behçet/AAV/IgG4-RD/IPF)
#       年輕(SLE/IBD/MS/AS/Behçet) ↔ 中年(RA/SSc/PsA/Sjögren/CU) ↔ 老年(gout/AAV/IgG4/OA/IPF)
# ---------------------------------------------------------------------------

DISEASE_EVIDENCE: dict[str, DiseaseEvidence] = {
    "rheumatoid_arthritis": DiseaseEvidence(
        rarity="common",
        onset_band="middle",
        prevalence_note="全球盛行率約 0.5–1%，女性為主。",
        typical_note="對稱性小關節多發炎、晨僵 >1 小時、RF/anti-CCP 陽性。",
        atypical_note="血清陰性、老年發病(EORA)以大關節/類風濕多肌痛表現、回紋型風濕症。",
        pubmed=PubMedRef("36068354", "10.1038/s41584-022-00827-y",
                         "Global epidemiology of rheumatoid arthritis",
                         "Nat Rev Rheumatol", 2022),
    ),
    "asthma": DiseaseEvidence(
        rarity="common",
        onset_band="young",
        prevalence_note="兒童約 14%、成人數%，全球逾 3 億人；最常見慢性呼吸道病。",
        typical_note="陣發性喘鳴、夜咳、可逆性呼氣氣流受限。",
        atypical_note="咳嗽變異型、成人晚發嗜伊紅性、運動誘發、職業型。",
        pubmed=PubMedRef("39384302", "10.1183/16000617.0095-2024",
                         "Epidemiology of severe asthma in children: a systematic review and meta-analysis",
                         "Eur Respir Rev", 2024),
    ),
    "systemic_sclerosis": DiseaseEvidence(
        rarity="rare",
        onset_band="middle",
        prevalence_note="盛行率約 1–2/萬，屬罕見自體免疫病，女性為主。",
        typical_note="雷諾現象起始、皮膚硬化、ANA/抗 Scl-70/抗著絲點陽性。",
        atypical_note="無皮膚硬化型(sine scleroderma)、快速進展型、以間質肺病/肺高壓首發。",
        pubmed=PubMedRef("28413064", "10.1016/S0140-6736(17)30933-9",
                         "Systemic sclerosis", "Lancet", 2017),
    ),
    "systemic_lupus_erythematosus": DiseaseEvidence(
        rarity="uncommon",
        onset_band="young",
        prevalence_note="盛行率約 43–100/10萬；好發育齡女性(女:男 ~9:1)。",
        typical_note="頰部紅斑、關節炎、腎炎、ANA/抗 dsDNA 陽性、多系統侵犯。",
        atypical_note="晚發型、男性、單一系統(僅血液/僅腎)、藥物誘發型。",
        pubmed=PubMedRef("36241363", "10.1136/ard-2022-223035",
                         "Global epidemiology of systemic lupus erythematosus: a comprehensive systematic analysis",
                         "Ann Rheum Dis", 2023),
    ),
    "inflammatory_bowel_disease": DiseaseEvidence(
        rarity="common",
        onset_band="young",
        prevalence_note="西方盛行率達 0.3–0.7% 並全球上升；好發 15–35 歲，次峰 50–70。",
        typical_note="慢性腹瀉/血便、腹痛、體重下降、內視鏡黏膜發炎。",
        atypical_note="以腸外表現(關節/皮膚/眼)首發、老年發病、無症狀型。",
        pubmed=PubMedRef("29050646", "10.1016/S0140-6736(17)32448-0",
                         "Worldwide incidence and prevalence of inflammatory bowel disease in the 21st century",
                         "Lancet", 2017),
    ),
    "multiple_sclerosis": DiseaseEvidence(
        rarity="uncommon",
        onset_band="young",
        prevalence_note="盛行率約 30–300/10萬，隨緯度上升；好發 20–40 歲女性。",
        typical_note="復發緩解型、視神經炎/感覺異常、MRI 多發脫髓鞘病灶。",
        atypical_note="原發進展型(PPMS)、腫瘤樣脫髓鞘、晚發型、脊髓為主。",
        pubmed=PubMedRef("35938654", "10.1212/CON.0000000000001136",
                         "Epidemiology and Pathophysiology of Multiple Sclerosis",
                         "Continuum (Minneap Minn)", 2022),
    ),
    "gout": DiseaseEvidence(
        rarity="common",
        onset_band="old",
        prevalence_note="盛行率約 1–4%(年長男性可達 5%+)；最常見發炎性關節炎。",
        typical_note="急性單關節炎(足拇趾)、高尿酸血症、尿酸結晶。",
        atypical_note="多關節痛風石型、早發型(有家族/腎病)、停經後女性。",
        pubmed=PubMedRef("32541923", "10.1038/s41584-020-0441-1",
                         "Global epidemiology of gout: prevalence, incidence, treatment patterns and risk factors",
                         "Nat Rev Rheumatol", 2020),
    ),
    "ankylosing_spondylitis": DiseaseEvidence(
        rarity="uncommon",
        onset_band="young",
        prevalence_note="盛行率約 0.1–0.5%；好發 <45 歲(常 20 多歲)男性、HLA-B27。",
        typical_note="發炎性下背痛、晨僵、薦腸關節炎、活動後改善。",
        atypical_note="非放射學軸性脊椎關節炎、女性、以周邊關節/葡萄膜炎首發。",
        pubmed=PubMedRef("33754220", "10.1007/s10067-021-05679-7",
                         "Ankylosing spondylitis risk factors: a systematic literature review",
                         "Clin Rheumatol", 2021),
    ),
    "psoriatic_arthritis": DiseaseEvidence(
        rarity="uncommon",
        onset_band="middle",
        prevalence_note="盛行率約 0.1–0.25%；乾癬患者約 20–30% 併發，好發 30–50 歲。",
        typical_note="不對稱寡關節炎、指/趾炎、附著點炎、乾癬病灶。",
        atypical_note="關節炎早於皮膚、軸性為主、毀損性(arthritis mutilans)。",
        pubmed=PubMedRef("38857765", "10.1016/j.jaad.2024.03.058",
                         "Psoriatic arthritis: A comprehensive review for the dermatologist part I",
                         "J Am Acad Dermatol", 2024),
    ),
    "sjogren_syndrome": DiseaseEvidence(
        rarity="uncommon",
        onset_band="middle",
        prevalence_note="原發型盛行率約 0.01–0.6%(依準則)；強烈女性偏向、好發 40–60。",
        typical_note="乾眼乾口、抗 SSA/SSB 陽性、唾液腺腫。",
        atypical_note="以全身/腺體外(關節、肺、神經)首發、年輕發病、淋巴瘤轉化。",
        pubmed=PubMedRef("38110617", "10.1038/s41584-023-01057-6",
                         "Epidemiology of Sjögren syndrome", "Nat Rev Rheumatol", 2023),
    ),
    "behcet_disease": DiseaseEvidence(
        rarity="rare",
        onset_band="young",
        prevalence_note="整體罕見，惟絲路沿線(土耳其)達 0.1–0.4%；好發 20–40 歲。",
        typical_note="反覆口腔+生殖器潰瘍、葡萄膜炎、皮膚病灶、針刺反應。",
        atypical_note="血管型(動脈瘤/血栓)、神經型、腸道型。",
        pubmed=PubMedRef("38674208", "10.3390/medicina60040562",
                         "Behçet's Disease, Pathogenesis, Clinical Features, and Treatment Approaches",
                         "Medicina (Kaunas)", 2024),
    ),
    "anca_vasculitis": DiseaseEvidence(
        rarity="rare",
        onset_band="old",
        prevalence_note="罕見，盛行率約 13–20/10萬、年發生率 1–2/10萬；好發 50–70 歲。",
        typical_note="肺-腎症候群、ENT 侵犯、ANCA(PR3/MPO)陽性、壞死性小血管炎。",
        atypical_note="侷限型(僅 ENT)、單一器官、ANCA 陰性。",
        pubmed=PubMedRef("36927642", "10.1136/ard-2022-223764",
                         "EULAR recommendations for the management of ANCA-associated vasculitis: 2022 update",
                         "Ann Rheum Dis", 2023),
    ),
    "igg4_related_disease": DiseaseEvidence(
        rarity="rare",
        onset_band="old",
        prevalence_note="罕見且近年才被定義；好發 50–70 歲男性。",
        typical_note="多器官腫瘤樣腫大(胰、唾液腺、後腹膜)、血清 IgG4 升高、席紋狀纖維化。",
        atypical_note="單一器官型、血清 IgG4 正常、以過敏/淋巴結腫表現。",
        pubmed=PubMedRef("39707927", "10.1002/ueg2.12738",
                         "Update on Autoimmune Pancreatitis and IgG4-Related Disease",
                         "United European Gastroenterol J", 2024),
    ),
    "chronic_urticaria": DiseaseEvidence(
        rarity="common",
        onset_band="middle",
        prevalence_note="點盛行率約 0.5–1%、終生約 1.4%；好發 20–40 歲女性。",
        typical_note="反覆風疹塊 >6 週、可伴血管性水腫、抗組織胺反應。",
        atypical_note="誘發型(冷/壓力/膽鹼性)、自體免疫型、難治型。",
        pubmed=PubMedRef("40451490", "10.1016/j.jaci.2025.05.019",
                         "Chronic spontaneous urticaria and chronic inducible urticaria",
                         "J Allergy Clin Immunol", 2025),
    ),
    "osteoarthritis": DiseaseEvidence(
        rarity="common",
        onset_band="old",
        prevalence_note="極常見，成人達 7–15%+；老年人失能首因。",
        typical_note="膝/髖/手關節活動痛、休息改善、骨刺、關節間隙變窄。",
        atypical_note="侵蝕性手部 OA、快速破壞型髖 OA、年輕創傷後續發型。",
        pubmed=PubMedRef("39103081", "10.1016/j.joca.2024.07.014",
                         "Osteoarthritis year in review 2024: Epidemiology and therapy",
                         "Osteoarthritis Cartilage", 2024),
    ),
    "idiopathic_pulmonary_fibrosis": DiseaseEvidence(
        rarity="rare",
        onset_band="old",
        prevalence_note="罕見，盛行率約 10–60/10萬；好發 >60 歲男性、吸菸者。",
        typical_note="進行性呼吸困難、乾咳、爆裂音、HRCT 呈 UIP 型。",
        atypical_note="併肺氣腫型(CPFE)、以急性惡化首發、家族型。",
        pubmed=PubMedRef("37156412", "10.1016/j.lpm.2023.104166",
                         "Idiopathic pulmonary fibrosis", "Presse Med", 2023),
    ),
}


# 數位健康使用流失(attrition)依據 — 驅動 app_usage 的留存/流失模型
ATTRITION_REF = PubMedRef(
    "15829473", "10.2196/jmir.7.1.e11",
    "The law of attrition", "J Med Internet Res", 2005,
)


def evidence_for(disease_id: str) -> DiseaseEvidence | None:
    """取得疾病的流行病學分類；未知疾病回傳 None。"""
    return DISEASE_EVIDENCE.get(disease_id)


def rarity_of(disease_id: str) -> str:
    ev = DISEASE_EVIDENCE.get(disease_id)
    return ev.rarity if ev else "unknown"


def onset_band_of(disease_id: str) -> str:
    ev = DISEASE_EVIDENCE.get(disease_id)
    return ev.onset_band if ev else "unknown"

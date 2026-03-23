"""
慢性病知識理解度差異分析
Chronic Disease Knowledge Comprehension Gap Analysis

可在 Kaggle / Colab / 本地直接執行，產出視覺化圖表。
不需 GPU，純 CPU 分析。
"""

import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import pandas as pd

matplotlib.rcParams["font.family"] = ["Noto Sans CJK TC", "Noto Sans CJK SC",
                                       "Microsoft JhengHei", "SimHei", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False

# ── 資料定義 ──────────────────────────────────────────

KNOWLEDGE_DIMENSIONS = {
    "disease_awareness": "疾病認知",
    "symptom_recognition": "症狀辨識",
    "medication_knowledge": "用藥知識",
    "self_management": "自我管理",
    "emergency_response": "緊急應變",
    "complication_awareness": "併發症認知",
}

DISEASES = {
    "E11": "第二型糖尿病",
    "I10": "高血壓",
    "J45": "氣喘",
    "J44": "COPD",
    "N18": "慢性腎臟病",
    "I50": "心臟衰竭",
    "M06": "類風濕性關節炎",
    "G20": "巴金森氏症",
    "F32": "重鬱症",
    "C50": "乳癌",
}

CATEGORIES = {
    "代謝疾病": ["E11"],
    "心血管疾病": ["I10", "I50"],
    "呼吸系統": ["J45", "J44"],
    "腎臟疾病": ["N18"],
    "肌肉骨骼": ["M06"],
    "神經退化": ["G20"],
    "精神疾病": ["F32"],
    "腫瘤追蹤": ["C50"],
}

# 基準數據（文獻綜合值，0-4 分制）
BASELINE = {
    "E11": [2.8, 2.1, 2.5, 2.0, 1.8, 1.5],
    "I10":  [3.0, 1.6, 2.3, 2.2, 1.9, 1.4],
    "J45":  [3.2, 2.8, 2.0, 2.5, 2.6, 1.8],
    "J44":  [2.2, 2.0, 1.8, 1.5, 1.7, 1.2],
    "N18":  [2.0, 1.5, 2.1, 1.8, 1.6, 1.3],
    "I50":  [2.3, 2.2, 2.0, 1.7, 2.1, 1.4],
    "M06":  [2.5, 2.6, 2.2, 2.3, 1.5, 1.6],
    "G20":  [2.4, 2.3, 2.1, 1.6, 1.4, 1.3],
    "F32":  [1.8, 1.5, 1.7, 1.4, 1.2, 1.0],
    "C50":  [3.1, 2.5, 2.3, 2.0, 2.2, 2.0],
}

DIM_KEYS = list(KNOWLEDGE_DIMENSIONS.keys())
DIM_LABELS = list(KNOWLEDGE_DIMENSIONS.values())


def build_dataframe():
    """將基準數據轉為 DataFrame"""
    rows = []
    for code, scores in BASELINE.items():
        for i, dim in enumerate(DIM_KEYS):
            rows.append({
                "icd10": code,
                "disease": DISEASES[code],
                "dimension": dim,
                "dimension_label": DIM_LABELS[i],
                "score": scores[i],
                "gap": 4.0 - scores[i],
            })
    return pd.DataFrame(rows)


def plot_heatmap(df):
    """熱力圖：疾病 × 知識維度 理解度矩陣"""
    pivot = df.pivot_table(index="disease", columns="dimension_label", values="score")
    pivot = pivot[DIM_LABELS]  # 保持維度順序

    fig, ax = plt.subplots(figsize=(12, 8))
    im = ax.imshow(pivot.values, cmap="RdYlGn", aspect="auto", vmin=0, vmax=4)

    ax.set_xticks(range(len(DIM_LABELS)))
    ax.set_xticklabels(DIM_LABELS, rotation=45, ha="right", fontsize=11)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=11)

    # 標註數值
    for i in range(len(pivot.index)):
        for j in range(len(DIM_LABELS)):
            val = pivot.values[i, j]
            color = "white" if val < 1.8 else "black"
            ax.text(j, i, f"{val:.1f}", ha="center", va="center", fontsize=10,
                    fontweight="bold", color=color)

    plt.colorbar(im, ax=ax, label="理解度 (0-4)", shrink=0.8)
    ax.set_title("慢性病知識理解度矩陣\n(0=完全不了解, 4=能自主應用)", fontsize=14, pad=15)
    plt.tight_layout()
    plt.savefig("knowledge_heatmap.png", dpi=150, bbox_inches="tight")
    plt.show()
    print("✓ 已儲存 knowledge_heatmap.png")


def plot_gap_ranking(df):
    """缺口排行：哪些疾病×維度組合最需要加強"""
    top = df.nlargest(15, "gap")

    fig, ax = plt.subplots(figsize=(10, 8))
    labels = [f"{r['disease']} - {r['dimension_label']}" for _, r in top.iterrows()]
    colors = plt.cm.Reds(np.linspace(0.4, 0.9, len(top)))

    bars = ax.barh(range(len(top)), top["gap"].values, color=colors)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("知識缺口 (理想值 4.0 - 實際分數)", fontsize=11)
    ax.set_title("前 15 大知識缺口排行\n（衛教優先介入目標）", fontsize=14)
    ax.invert_yaxis()

    for bar, val in zip(bars, top["gap"].values):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}", va="center", fontsize=9)

    plt.tight_layout()
    plt.savefig("knowledge_gap_ranking.png", dpi=150, bbox_inches="tight")
    plt.show()
    print("✓ 已儲存 knowledge_gap_ranking.png")


def plot_radar_comparison(df, codes=None):
    """雷達圖：選定疾病的六維度比較"""
    if codes is None:
        codes = ["E11", "I10", "F32", "C50"]  # 預設比較組

    angles = np.linspace(0, 2 * np.pi, len(DIM_LABELS), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
    colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6"]

    for i, code in enumerate(codes):
        if code not in BASELINE:
            continue
        values = BASELINE[code] + [BASELINE[code][0]]
        ax.plot(angles, values, "o-", linewidth=2, label=DISEASES[code],
                color=colors[i % len(colors)])
        ax.fill(angles, values, alpha=0.1, color=colors[i % len(colors)])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(DIM_LABELS, fontsize=11)
    ax.set_ylim(0, 4)
    ax.set_yticks([1, 2, 3, 4])
    ax.set_yticklabels(["1-聽過", "2-基本了解", "3-清楚理解", "4-能教導"], fontsize=8)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=10)
    ax.set_title("慢性病知識理解度雷達圖", fontsize=14, pad=20)

    plt.tight_layout()
    plt.savefig("knowledge_radar.png", dpi=150, bbox_inches="tight")
    plt.show()
    print("✓ 已儲存 knowledge_radar.png")


def plot_category_comparison(df):
    """分類群組平均理解度比較"""
    cat_data = []
    for cat, codes in CATEGORIES.items():
        cat_scores = df[df["icd10"].isin(codes)].groupby("dimension_label")["score"].mean()
        overall = df[df["icd10"].isin(codes)]["score"].mean()
        cat_data.append({"category": cat, "overall_mean": overall})

    cat_df = pd.DataFrame(cat_data).sort_values("overall_mean")

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.cm.RdYlGn(np.linspace(0.2, 0.8, len(cat_df)))
    bars = ax.barh(cat_df["category"], cat_df["overall_mean"], color=colors)

    ax.axvline(x=2.0, color="red", linestyle="--", alpha=0.5, label="基本了解門檻")
    ax.axvline(x=3.0, color="green", linestyle="--", alpha=0.5, label="清楚理解門檻")
    ax.set_xlabel("平均理解度 (0-4)", fontsize=11)
    ax.set_xlim(0, 4)
    ax.set_title("各慢性病分類的平均知識理解度", fontsize=14)
    ax.legend(fontsize=9)

    for bar, val in zip(bars, cat_df["overall_mean"]):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                f"{val:.2f}", va="center", fontsize=10, fontweight="bold")

    plt.tight_layout()
    plt.savefig("knowledge_category.png", dpi=150, bbox_inches="tight")
    plt.show()
    print("✓ 已儲存 knowledge_category.png")


def plot_dimension_boxplot(df):
    """箱形圖：各知識維度在不同疾病間的分數分佈"""
    fig, ax = plt.subplots(figsize=(10, 6))

    dim_groups = [df[df["dimension_label"] == d]["score"].values for d in DIM_LABELS]
    bp = ax.boxplot(dim_groups, labels=DIM_LABELS, patch_artist=True, vert=True)

    colors = plt.cm.Set3(np.linspace(0, 1, len(DIM_LABELS)))
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)

    ax.axhline(y=2.0, color="red", linestyle="--", alpha=0.4)
    ax.set_ylabel("理解度分數 (0-4)", fontsize=11)
    ax.set_title("各知識維度的跨疾病分數分佈", fontsize=14)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig("knowledge_boxplot.png", dpi=150, bbox_inches="tight")
    plt.show()
    print("✓ 已儲存 knowledge_boxplot.png")


def print_summary(df):
    """輸出文字摘要"""
    print("=" * 60)
    print("慢性病知識理解度差異分析 — 摘要報告")
    print("=" * 60)

    # 整體統計
    print(f"\n分析疾病數：{df['icd10'].nunique()}")
    print(f"知識維度數：{df['dimension'].nunique()}")
    print(f"總體平均理解度：{df['score'].mean():.2f} / 4.00")
    print(f"總體平均缺口：{df['gap'].mean():.2f}")

    # 各疾病排名
    print("\n── 各疾病平均理解度排名 ──")
    disease_avg = df.groupby("disease")["score"].mean().sort_values()
    for rank, (disease, score) in enumerate(disease_avg.items(), 1):
        bar = "█" * int(score * 5) + "░" * (20 - int(score * 5))
        print(f"  {rank:2d}. {disease:<12s} {bar} {score:.2f}")

    # 各維度排名
    print("\n── 各維度平均理解度排名 ──")
    dim_avg = df.groupby("dimension_label")["score"].mean().sort_values()
    for rank, (dim, score) in enumerate(dim_avg.items(), 1):
        bar = "█" * int(score * 5) + "░" * (20 - int(score * 5))
        print(f"  {rank:2d}. {dim:<10s} {bar} {score:.2f}")

    # Top 5 缺口
    print("\n── 前 5 大知識缺口（最需衛教介入）──")
    top5 = df.nlargest(5, "gap")
    for i, (_, r) in enumerate(top5.iterrows(), 1):
        print(f"  {i}. {r['disease']} × {r['dimension_label']}"
              f"  (分數={r['score']:.1f}, 缺口={r['gap']:.1f})")

    # 關鍵發現
    print("\n── 關鍵發現 ──")
    worst_disease = disease_avg.index[0]
    best_disease = disease_avg.index[-1]
    worst_dim = dim_avg.index[0]
    best_dim = dim_avg.index[-1]
    print(f"  • 理解度最低的疾病：{worst_disease}（平均 {disease_avg.iloc[0]:.2f}）")
    print(f"  • 理解度最高的疾病：{best_disease}（平均 {disease_avg.iloc[-1]:.2f}）")
    print(f"  • 最弱的知識維度：{worst_dim}（平均 {dim_avg.iloc[0]:.2f}）")
    print(f"  • 最強的知識維度：{best_dim}（平均 {dim_avg.iloc[-1]:.2f}）")
    print(f"  • 疾病間理解度差距：{disease_avg.iloc[-1] - disease_avg.iloc[0]:.2f} 分")
    print(f"  • 維度間理解度差距：{dim_avg.iloc[-1] - dim_avg.iloc[0]:.2f} 分")


def main():
    print("建構分析資料...")
    df = build_dataframe()

    # 文字摘要
    print_summary(df)

    # 視覺化
    print("\n\n正在產出視覺化圖表...\n")
    plot_heatmap(df)
    plot_gap_ranking(df)
    plot_radar_comparison(df)
    plot_category_comparison(df)
    plot_dimension_boxplot(df)

    # 匯出原始數據
    df.to_csv("knowledge_analysis_results.csv", index=False, encoding="utf-8-sig")
    print("\n✓ 已匯出 knowledge_analysis_results.csv")
    print("\n分析完成！")


if __name__ == "__main__":
    main()

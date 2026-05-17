# Inflammatory Bowel Disease (`inflammatory_bowel_disease`)

- 動力學類型：`chronic_relapsing`
- 患者數：**200**，平均年齡 44.7 歲，老年 13 位
- 90 天 flare 平均：**0.80**
- 模型 MAE 平均：**0.140**，flare 召回平均 45%，準確率平均 63%

## 亞型分布
| Subtype | n |
|---|---|
| uc | 105 |
| crohn | 95 |

## 反應者分布
| Class | n |
|---|---|
| typical | 94 |
| partial | 62 |
| super | 26 |
| non_responder | 18 |

## 處方治療頻率
| Treatment | n |
|---|---|
| mesalazine | 144 |
| azathioprine | 79 |
| prednisone | 51 |
| anti_tnf | 47 |

## 圖
- [活動度軌跡 (cohort)](../figures/inflammatory_bowel_disease_cohort.png)
- [Flare 直方圖](../figures/inflammatory_bowel_disease_flares.png)
- [單一患者範例](../figures/inflammatory_bowel_disease_single.png)
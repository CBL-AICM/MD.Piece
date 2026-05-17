# Inflammatory Bowel Disease (`inflammatory_bowel_disease`)

- 動力學類型：`chronic_relapsing`
- 患者數：**200**，平均年齡 44.7 歲，老年 13 位
- 90 天 flare 平均：**0.80**
- 模型 MAE 平均：**0.177**，flare 召回平均 54%，準確率平均 61%

## 亞型分布
| Subtype | n |
|---|---|
| uc | 109 |
| crohn | 91 |

## 反應者分布
| Class | n |
|---|---|
| typical | 108 |
| partial | 53 |
| non_responder | 20 |
| super | 19 |

## 處方治療頻率
| Treatment | n |
|---|---|
| mesalazine | 143 |
| azathioprine | 77 |
| prednisone | 48 |
| anti_tnf | 37 |

## 圖
- [活動度軌跡 (cohort)](../figures/inflammatory_bowel_disease_cohort.png)
- [Flare 直方圖](../figures/inflammatory_bowel_disease_flares.png)
- [單一患者範例](../figures/inflammatory_bowel_disease_single.png)
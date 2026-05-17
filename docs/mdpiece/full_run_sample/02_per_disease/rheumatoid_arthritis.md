# Rheumatoid Arthritis (`rheumatoid_arthritis`)

- 動力學類型：`chronic_relapsing`
- 患者數：**200**，平均年齡 52.0 歲，老年 19 位
- 90 天 flare 平均：**3.37**
- 模型 MAE 平均：**0.160**，flare 召回平均 67%，準確率平均 88%

## 亞型分布
| Subtype | n |
|---|---|
| seropositive | 145 |
| seronegative | 55 |

## 反應者分布
| Class | n |
|---|---|
| typical | 119 |
| partial | 47 |
| non_responder | 18 |
| super | 16 |

## 處方治療頻率
| Treatment | n |
|---|---|
| methotrexate | 146 |
| nsaid | 122 |
| tnf_inhibitor | 46 |
| prednisone | 30 |

## 圖
- [活動度軌跡 (cohort)](../figures/rheumatoid_arthritis_cohort.png)
- [Flare 直方圖](../figures/rheumatoid_arthritis_flares.png)
- [單一患者範例](../figures/rheumatoid_arthritis_single.png)
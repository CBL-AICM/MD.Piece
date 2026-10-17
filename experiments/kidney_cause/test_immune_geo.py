# -*- coding: utf-8 -*-
"""immune_geo 的關鍵邏輯檢查（不碰結果）：python -m pytest test_immune_geo.py"""
import numpy as np
import pandas as pd
import pytest

import immune_geo as ig


def test_dx_code_maps_both_series_spellings():
    # 兩系列大小寫／寫法不同，同一病要對到同一代碼；FSGS/MCD 合併類不可誤判成 FSGS 或 MCD
    assert ig.dx_code("diagnosis: Systemic Lupus Erythematosus") == ig.dx_code("diagnosis: Systemic lupus erythematosus") == "SLE"
    assert ig.dx_code("diagnosis: ANCA Associated Vasculitis") == ig.dx_code("diagnosis: ANCA-associated vasculitis") == "ANCA"
    assert ig.dx_code("diagnosis: Focal Segmental Glomerular Sclerosis/Minimal Change Disease") == "FSGS_MCD"
    assert ig.dx_code("diagnosis: Focal segmental glomerulosclerosis and minimal change disease") == "FSGS_MCD"
    assert ig.dx_code("diagnosis: Focal Segmental Glomerular Sclerosis") == "FSGS"
    assert ig.dx_code("") == "LD"
    with pytest.raises(ValueError):
        ig.dx_code("diagnosis: something new")  # 未知診斷要報錯，不可默默歸類


def test_panel_score_uses_training_fold_only():
    # 測試折的極端值不可影響標準化參數（否則交叉驗證會洩漏）
    tr = pd.DataFrame({"a": [0.0, 1.0, 2.0], "b": [1.0, 1.0, 4.0]})
    te = pd.DataFrame({"a": [100.0], "b": [1.0]})
    ps = ig.PanelScore({"p": ["a", "b"]}).fit(tr)
    assert ps.mu_["a"] == 1.0  # 只來自訓練資料，te 的 100 沒有進來
    # a 的 z＝(100−1)/sd(0,1,2)，b 的 z＝(1−2)/sd(1,1,4)；路徑分數為兩者平均
    expect = ((100 - 1) / np.std([0, 1, 2]) + (1 - 2) / np.std([1, 1, 4])) / 2
    assert np.isclose(ps.transform(te)[0, 0], expect)


def test_batch_center_reference_excludes_platform_only_diseases():
    # 參考只取共有類別；平台獨有疾病（SLE、ANCA）的值改變時，校正後的共有類別不能跟著變
    m = pd.DataFrame({"platform": ["A", "A", "A", "B", "B", "B"], "dx": ["LD", "DN", "ANCA", "LD", "DN", "SLE"]})
    X = pd.DataFrame({"g": [1.0, 3.0, 9.0, 5.0, 7.0, 0.0]})
    c1 = ig.batch_center(m, X)
    X2 = X.copy()
    X2.loc[[2, 5], "g"] = [100.0, -100.0]
    c2 = ig.batch_center(m, X2)
    shared = m.dx.isin(ig.SHARED).values
    assert np.allclose(c1[shared], c2[shared])
    # 兩平台的共有類別校正後落在同一位置（平台差被移除）
    assert np.allclose(c1.g[[0, 1]].values, c1.g[[3, 4]].values)

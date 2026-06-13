"""Test — 人生自述(時空背景) + 家族圖一致性。"""

from __future__ import annotations

from ml.life_story import CUR_YEAR, build_family_graph, era_for, life_story


def test_era_by_birth_year():
    assert "戰後嬰兒潮" in era_for(1950)["label"]
    assert "經濟起飛" in era_for(1965)["label"]
    assert "數位原生" in era_for(1995)["label"]


def _story(age, sex="F", **o):
    base = dict(nickname="測試", age=age, sex=sex, region="臺北市", region_macro="北部",
                education="高中職", income_tier="中等", employment="退休" if age >= 65 else "全職",
                marital="已婚", children_count=2, living_arrangement="with_family",
                family_support="高", uses_tcm=True, disease_id="rheumatoid_arthritis",
                comorbidities=[], seed=42)
    base.update(o)
    return life_story(**base)


def test_life_story_is_first_person_and_era_grounded():
    old = _story(78)                       # 約 1948 生 → 戰後嬰兒潮
    young = _story(30)                     # 約 1996 生 → 數位原生
    assert old.startswith("我叫") and "歲" in old
    assert ("十大建設" in old or "番薯籤" in old or "聯考" in old)   # 老年人的時空記憶
    assert ("手機" in young or "網路" in young or "社群" in young)   # 年輕人的時空記憶
    assert "類風濕關節炎" in old                                    # 病名入戲
    assert "民國" in old


def test_family_graph_mutual_and_age_consistent():
    people = []
    # 同地區一對夫妻(同齡) + 兩個可當子女的年輕人
    people.append({"pid": "p_dad", "age": 60, "sex": "M", "region": "臺中市",
                   "marital": "已婚", "children_count": 2, "seed": 1})
    people.append({"pid": "p_mom", "age": 58, "sex": "F", "region": "臺中市",
                   "marital": "已婚", "children_count": 2, "seed": 2})
    people.append({"pid": "p_kid1", "age": 30, "sex": "F", "region": "臺中市",
                   "marital": "未婚", "children_count": 0, "seed": 3})
    people.append({"pid": "p_kid2", "age": 28, "sex": "M", "region": "臺中市",
                   "marital": "未婚", "children_count": 0, "seed": 4})
    fam = build_family_graph(people, seed=2024)
    # 夫妻互連
    assert fam["p_dad"]["spouse"] == "p_mom"
    assert fam["p_mom"]["spouse"] == "p_dad"
    # 子女被指派、且比父母小 ≥18 歲
    kids = set(fam["p_dad"]["children"])
    assert kids and kids == set(fam["p_mom"]["children"])
    for k in kids:
        kid_age = next(p["age"] for p in people if p["pid"] == k)
        assert 60 - kid_age >= 18
        assert set(fam[k]["parents"]) == {"p_dad", "p_mom"}
    # 無自連
    for pid, f in fam.items():
        assert f["spouse"] != pid
        assert pid not in f["children"] and pid not in f["parents"]

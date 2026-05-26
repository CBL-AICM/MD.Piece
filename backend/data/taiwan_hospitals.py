"""
台灣主要醫院 lat/lng 清單。

設計憲法第 7 條（本地化）：先收錄台灣分級醫療中的「醫學中心」與
「區域醫院」級別常見院所，覆蓋大多數住院情境。座標為各院公開
地址對應之大致中心點，地理圍欄半徑 300m 已足以涵蓋一般 GPS 誤差
與院區範圍。

清單只在後端 GET /admissions/hospitals 用，不直接寫進 DB；
admissions row 只存使用者選定的 hospital_name + lat + lng。
這樣未來增刪不必跑 migration。
"""

# 結構：(name, lat, lng, region)
# region 只供前端分組顯示用（北/中/南/東），不影響地理判定。
TAIWAN_HOSPITALS: list[dict] = [
    # ── 北部 ────────────────────────────────────────────────
    {"name": "台大醫院（總院）",         "lat": 25.0411, "lng": 121.5167, "region": "north"},
    {"name": "台北榮民總醫院",           "lat": 25.1207, "lng": 121.5197, "region": "north"},
    {"name": "三軍總醫院（內湖）",       "lat": 25.0731, "lng": 121.5916, "region": "north"},
    {"name": "馬偕紀念醫院（台北院區）", "lat": 25.0577, "lng": 121.5224, "region": "north"},
    {"name": "馬偕紀念醫院（淡水院區）", "lat": 25.1781, "lng": 121.4395, "region": "north"},
    {"name": "新光吳火獅紀念醫院",       "lat": 25.0966, "lng": 121.5198, "region": "north"},
    {"name": "國泰綜合醫院（仁愛院區）", "lat": 25.0395, "lng": 121.5468, "region": "north"},
    {"name": "萬芳醫院",                 "lat": 24.9994, "lng": 121.5582, "region": "north"},
    {"name": "台北市立聯合醫院（仁愛院區）", "lat": 25.0388, "lng": 121.5455, "region": "north"},
    {"name": "台北長庚紀念醫院",         "lat": 25.0598, "lng": 121.5491, "region": "north"},
    {"name": "林口長庚紀念醫院",         "lat": 25.0631, "lng": 121.3654, "region": "north"},
    {"name": "桃園長庚紀念醫院",         "lat": 25.0335, "lng": 121.3654, "region": "north"},
    {"name": "衛福部桃園醫院",           "lat": 24.9926, "lng": 121.3147, "region": "north"},
    {"name": "國軍桃園總醫院",           "lat": 24.9494, "lng": 121.2353, "region": "north"},
    {"name": "新竹馬偕紀念醫院",         "lat": 24.8062, "lng": 121.0006, "region": "north"},
    {"name": "台北慈濟醫院（新店）",     "lat": 24.9690, "lng": 121.5377, "region": "north"},
    {"name": "亞東紀念醫院",             "lat": 25.0117, "lng": 121.4503, "region": "north"},

    # ── 中部 ────────────────────────────────────────────────
    {"name": "台中榮民總醫院",           "lat": 24.1817, "lng": 120.6066, "region": "central"},
    {"name": "中國醫藥大學附設醫院",     "lat": 24.1564, "lng": 120.6873, "region": "central"},
    {"name": "中山醫學大學附設醫院",     "lat": 24.1190, "lng": 120.6498, "region": "central"},
    {"name": "彰化基督教醫院",           "lat": 24.0822, "lng": 120.5395, "region": "central"},
    {"name": "童綜合醫院（梧棲院區）",   "lat": 24.2553, "lng": 120.5414, "region": "central"},
    {"name": "嘉義基督教醫院",           "lat": 23.4762, "lng": 120.4647, "region": "central"},
    {"name": "嘉義長庚紀念醫院",         "lat": 23.4632, "lng": 120.4093, "region": "central"},

    # ── 南部 ────────────────────────────────────────────────
    {"name": "成大醫院",                 "lat": 22.9994, "lng": 120.2204, "region": "south"},
    {"name": "奇美醫院（永康院區）",     "lat": 23.0282, "lng": 120.2533, "region": "south"},
    {"name": "高雄醫學大學附設醫院",     "lat": 22.6485, "lng": 120.3104, "region": "south"},
    {"name": "高雄長庚紀念醫院",         "lat": 22.7170, "lng": 120.3611, "region": "south"},
    {"name": "高雄榮民總醫院",           "lat": 22.6953, "lng": 120.3149, "region": "south"},
    {"name": "義大醫院",                 "lat": 22.7363, "lng": 120.3958, "region": "south"},
    {"name": "屏東基督教醫院",           "lat": 22.6688, "lng": 120.4855, "region": "south"},

    # ── 東部 ────────────────────────────────────────────────
    {"name": "花蓮慈濟醫院",             "lat": 23.9968, "lng": 121.6004, "region": "east"},
    {"name": "羅東博愛醫院",             "lat": 24.6789, "lng": 121.7686, "region": "east"},
    {"name": "台東馬偕紀念醫院",         "lat": 22.7647, "lng": 121.1429, "region": "east"},
]

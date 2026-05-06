"""產生藥單 / 藥袋 OCR 回歸測試的合成圖片。

執行：
    python3 tests/e2e/fixtures/generate_rx_images.py

會在 tests/e2e/fixtures/ 底下產出 6 張不同情境的藥單 / 藥袋。

需要：
    pip install pillow
    系統字型 /usr/share/fonts/truetype/wqy/wqy-zenhei.ttc（Ubuntu: apt install fonts-wqy-zenhei）
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).parent
FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"


def f(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, size)


def make_rx_a4(meds, hospital, date, doctor, patient, mr, fname):
    """A4 處方箋格式 — 多種藥列表"""
    W, H = 1200, 1700
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 30), hospital, font=f(48), fill="black")
    d.line([(40, 130), (W - 40, 130)], fill="black", width=2)
    d.text((40, 150), f"病患姓名: {patient}", font=f(28), fill="black")
    d.text((600, 150), f"病歷號: {mr}", font=f(28), fill="black")
    d.text((40, 190), f"開立日期: {date}", font=f(28), fill="black")
    d.text((600, 190), f"醫師: {doctor}", font=f(28), fill="black")
    d.line([(40, 240), (W - 40, 240)], fill="black", width=2)
    d.text((50, 250), "藥品名稱", font=f(26), fill="black")
    d.text((420, 250), "劑量", font=f(26), fill="black")
    d.text((600, 250), "頻率", font=f(26), fill="black")
    d.text((830, 250), "用法", font=f(26), fill="black")
    d.text((1020, 250), "天數", font=f(26), fill="black")
    d.line([(40, 295), (W - 40, 295)], fill="black", width=2)
    y = 310
    for n, ds, fr, us, du in meds:
        d.text((50, y), n, font=f(24), fill="black")
        d.text((420, y), ds, font=f(24), fill="black")
        d.text((600, y), fr, font=f(24), fill="black")
        d.text((830, y), us, font=f(24), fill="black")
        d.text((1020, y), du, font=f(24), fill="black")
        y += 50
    img.save(OUT_DIR / fname, "JPEG", quality=92)


def make_bag(drug_name_en, drug_name_tw, dose, freq, time, days, notes, hospital, date, fname):
    """單包藥袋格式 — 一張一藥、含詳細用藥指示"""
    W, H = 1000, 1400
    img = Image.new("RGB", (W, H), "#fdfaf2")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 110], fill="#2d5b8a")
    d.text((40, 30), hospital, font=f(40), fill="white")
    d.text((40, 130), "病患姓名 林淑芬       病歷號 5544332", font=f(28), fill="black")
    d.text((40, 175), f"處方日期 {date}", font=f(28), fill="black")
    d.line([(40, 240), (W - 40, 240)], fill="black", width=3)
    d.text((40, 270), "藥品名稱 / Drug Name", font=f(24), fill="gray")
    d.text((40, 310), drug_name_en, font=f(48), fill="black")
    d.text((40, 375), drug_name_tw, font=f(32), fill="black")
    d.rectangle([40, 440, W - 40, 660], outline="black", width=2)
    d.text((60, 460), f"單次劑量: {dose}", font=f(28), fill="black")
    d.text((60, 505), f"服用頻率: {freq}", font=f(28), fill="black")
    d.text((60, 550), f"服用時間: {time}", font=f(28), fill="black")
    d.text((60, 595), f"療  程: {days}", font=f(28), fill="black")
    d.text((40, 690), "用藥提示:", font=f(26), fill="black")
    yy = 730
    for n in notes:
        d.text((50, yy), "‧ " + n, font=f(22), fill="black")
        yy += 38
    img.save(OUT_DIR / fname, "JPEG", quality=92)


# ── 6 個 fixture ──────────────────────────────────────────

# 1. 過敏 / 感冒處方 (4 藥)
make_rx_a4(
    meds=[
        ("Levocetirizine HCl 5mg",  "1 錠",  "每日 1 次", "睡前服用", "7 天"),
        ("Amoxicillin 500mg",       "1 顆",  "一天三次",  "飯後服用", "7 天"),
        ("Acetaminophen 500mg",     "1 錠",  "需要時",    "口服",     "PRN"),
        ("Loratadine 10mg",         "1 錠",  "每日 1 次", "飯後服用", "14 天"),
    ],
    hospital="長庚紀念醫院", date="2024-04-22", doctor="林醫師",
    patient="王小明", mr="12345678",
    fname="rx_allergy_4drugs.jpg",
)

# 2. 心血管處方 (3 藥)
make_rx_a4(
    meds=[
        ("Amlodipine 5mg",     "1 錠", "每日 1 次", "睡前服用", "30 天"),
        ("Atorvastatin 20mg",  "1 錠", "每日 1 次", "睡前服用", "30 天"),
        ("Aspirin 100mg",      "1 錠", "每日 1 次", "飯後服用", "30 天"),
    ],
    hospital="台大醫院", date="2024-06-15", doctor="張心臟",
    patient="李大華", mr="11223344",
    fname="rx_cardio_3drugs.jpg",
)

# 3. 感冒處方 (3 藥)
make_rx_a4(
    meds=[
        ("Acetaminophen 500mg",   "1 錠", "每 6 小時", "需要時",   "5 天"),
        ("Pseudoephedrine 30mg",  "1 錠", "一天三次",  "飯後服用", "5 天"),
        ("Bromhexine 8mg",        "1 錠", "一天三次",  "飯後服用", "5 天"),
    ],
    hospital="馬偕紀念醫院", date="2024-07-02", doctor="王感冒",
    patient="陳小美", mr="77665544",
    fname="rx_cold_3drugs.jpg",
)

# 4. 藥袋 — 降血糖
make_bag(
    drug_name_en="Metformin HCl 500mg",
    drug_name_tw="(降血糖錠 / Glucophage)",
    dose="1 錠 (500mg)",
    freq="一天兩次 (BID)",
    time="早晚飯後服用",
    days="30 天",
    notes=[
        "此藥用於控制第二型糖尿病的血糖。",
        "請隨餐或飯後服用，可減少胃部不適。",
        "服藥期間請避免飲酒，會增加乳酸中毒風險。",
        "若出現嚴重腹瀉、噁心、呼吸困難應立即就醫。",
    ],
    hospital="台北榮民總醫院", date="2024/05/10",
    fname="bag_metformin.jpg",
)

# 5. 藥袋 — 抗生素
make_bag(
    drug_name_en="Amoxicillin 500mg",
    drug_name_tw="(安莫西林膠囊 / Amoxil)",
    dose="1 顆 (500mg)",
    freq="每 8 小時 (Q8H)",
    time="飯前服用",
    days="7 天",
    notes=[
        "此藥為抗生素，請務必按時服用，療程結束前不可自行停藥。",
        "若對盤尼西林過敏請立即告知醫師。",
        "可能副作用：腹瀉、噁心、皮疹。",
    ],
    hospital="高雄醫學大學附設醫院", date="2024/08/08",
    fname="bag_antibiotic.jpg",
)

# 6. 藥袋 — 止痛 (PRN)
make_bag(
    drug_name_en="Ibuprofen 400mg",
    drug_name_tw="(布洛芬 / Brufen)",
    dose="1 錠 (400mg)",
    freq="需要時 (PRN)",
    time="飯後服用",
    days="14 天",
    notes=[
        "此藥為非類固醇消炎止痛藥 (NSAID)。",
        "請勿空腹服用，會增加胃潰瘍風險。",
        "24 小時內勿超過 4 顆。",
        "孕婦、腎功能不佳者請告知醫師。",
    ],
    hospital="奇美醫院", date="2024/09/03",
    fname="bag_painkiller.jpg",
)

print(f"Generated 6 fixture images in {OUT_DIR}/")

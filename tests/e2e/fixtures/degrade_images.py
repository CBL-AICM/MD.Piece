"""把乾淨的合成藥單做各種劣化，模擬真實手機拍照條件。

執行：
    python3 tests/e2e/fixtures/degrade_images.py

需要先跑 generate_rx_images.py 產生 base fixtures。
產出 4 個劣化等級的變體，讓 E2E 可以驗證 pipeline 在差圖上的容錯。
"""
import math
import random
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter

OUT_DIR = Path(__file__).parent
random.seed(42)  # 固定 seed 讓劣化結果可重現

# 取 3 張代表性 base 圖（含藥單 + 藥袋 + 多藥處方）
BASES = [
    "rx_allergy_4drugs.jpg",
    "bag_metformin.jpg",
    "rx_cardio_3drugs.jpg",
]


def downscale(im: Image.Image, max_edge: int) -> Image.Image:
    """縮到 max_edge 內 — 模擬遠拍 / 低解析度上傳"""
    w, h = im.size
    scale = max_edge / max(w, h)
    if scale >= 1:
        return im
    return im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def add_noise(im: Image.Image, level: int = 25) -> Image.Image:
    """加 Gaussian-ish 雜訊 — 模擬低光高 ISO"""
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y][:3]
            n = lambda: random.randint(-level, level)
            px[x, y] = (
                max(0, min(255, r + n())),
                max(0, min(255, g + n())),
                max(0, min(255, b + n())),
            )
    return im


def rotate_slight(im: Image.Image, deg: float) -> Image.Image:
    """傾斜幾度 — 模擬手抖"""
    return im.rotate(deg, resample=Image.BICUBIC, fillcolor="white", expand=True)


def lower_contrast(im: Image.Image, factor: float) -> Image.Image:
    """降對比 — 模擬曝光不足 / 反光"""
    return ImageEnhance.Contrast(im).enhance(factor)


def blur(im: Image.Image, radius: float) -> Image.Image:
    """模糊 — 模擬失焦"""
    return im.filter(ImageFilter.GaussianBlur(radius=radius))


def jpeg_compress(im: Image.Image, fname: Path, quality: int) -> None:
    """以指定 JPEG quality 存檔（低 quality 會壓出 block artifact）"""
    im.convert("RGB").save(fname, "JPEG", quality=quality)


PIPELINES = {
    # 等級 1：輕度（手機正常光線、稍微遠一點）
    "_d1_light": lambda im: jpeg_compress(downscale(im, 1280), None, 75),
    # 等級 2：中度（傾斜 + 對比稍低）
    "_d2_medium": lambda im: jpeg_compress(
        lower_contrast(rotate_slight(downscale(im, 1024), 3), 0.85),
        None, 65,
    ),
    # 等級 3：重度（很模糊 + 對比差 + 低解析度）
    "_d3_heavy": lambda im: jpeg_compress(
        blur(lower_contrast(downscale(im, 800), 0.7), 1.2),
        None, 55,
    ),
    # 等級 4：極差（強雜訊 + 旋轉 + 模糊 + 縮很小）— 看 pipeline 多會掛
    "_d4_extreme": lambda im: jpeg_compress(
        add_noise(blur(rotate_slight(downscale(im, 640), 7), 0.8), 30),
        None, 50,
    ),
}


def run_pipeline(im: Image.Image, suffix: str, fname: Path) -> Image.Image:
    """In-place pipeline applies funcs and writes file at end."""
    if suffix == "_d1_light":
        out = downscale(im.copy(), 1280)
        jpeg_compress(out, fname, 75)
    elif suffix == "_d2_medium":
        out = downscale(im.copy(), 1024)
        out = rotate_slight(out, 3)
        out = lower_contrast(out, 0.85)
        jpeg_compress(out, fname, 65)
    elif suffix == "_d3_heavy":
        out = downscale(im.copy(), 800)
        out = lower_contrast(out, 0.7)
        out = blur(out, 1.2)
        jpeg_compress(out, fname, 55)
    elif suffix == "_d4_extreme":
        out = downscale(im.copy(), 640)
        out = rotate_slight(out, 7)
        out = blur(out, 0.8)
        out = add_noise(out, 30)
        jpeg_compress(out, fname, 50)


count = 0
for base in BASES:
    src = OUT_DIR / base
    if not src.exists():
        print(f"⚠️  Skip {base} — run generate_rx_images.py first")
        continue
    im = Image.open(src)
    stem = src.stem
    for suffix in PIPELINES:
        out_name = f"{stem}{suffix}.jpg"
        run_pipeline(im, suffix, OUT_DIR / out_name)
        print(f"  → {out_name} ({(OUT_DIR / out_name).stat().st_size // 1024} KB)")
        count += 1

print(f"\nGenerated {count} degraded variants.")

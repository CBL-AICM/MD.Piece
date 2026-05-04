"""Generate PWA icons from source image."""
from pathlib import Path
from PIL import Image

SRC = Path(r"C:\Users\tpc10\Desktop\AIMD\md_piece\picture\cf1035fd0b08013233d5f4487c1f9553.jpg")
OUT = Path(r"C:\Users\tpc10\md.piece\frontend\icons")

img = Image.open(SRC).convert("RGB")
W, H = img.size

cx, cy = W // 2, int(H * 0.55)
half = 480
left, top = cx - half, cy - half
right, bottom = cx + half, cy + half
cropped = img.crop((left, top, right, bottom))

PAD_RATIO = 0.08
side = cropped.size[0]
canvas_side = int(side * (1 + PAD_RATIO * 2))
canvas = Image.new("RGB", (canvas_side, canvas_side), (255, 255, 255))
offset = (canvas_side - side) // 2
canvas.paste(cropped, (offset, offset))

base = canvas

png_sizes = [72, 96, 128, 144, 152, 192, 384, 512]
for size in png_sizes:
    resized = base.resize((size, size), Image.LANCZOS)
    out_path = OUT / f"icon-{size}.png"
    resized.save(out_path, "PNG", optimize=True)
    print(f"wrote {out_path}")

for size in (16, 32, 512):
    resized = base.resize((size, size), Image.LANCZOS)
    out_path = OUT / f"favicon-{size}.png"
    resized.save(out_path, "PNG", optimize=True)
    print(f"wrote {out_path}")

ico_path = Path(r"C:\Users\tpc10\md.piece\frontend\favicon.ico")
ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
base.save(ico_path, format="ICO", sizes=ico_sizes)
print(f"wrote {ico_path}")

logo_png = OUT / "logo.png"
base.resize((512, 512), Image.LANCZOS).save(logo_png, "PNG", optimize=True)
print(f"wrote {logo_png}")

logo_jpg = OUT / "logo.jpg"
base.resize((512, 512), Image.LANCZOS).save(logo_jpg, "JPEG", quality=92)
print(f"wrote {logo_jpg}")

core_png = OUT / "logo-core.png"
base.resize((512, 512), Image.LANCZOS).save(core_png, "PNG", optimize=True)
print(f"wrote {core_png}")

core_jpg = OUT / "logo-core.jpg"
base.resize((512, 512), Image.LANCZOS).save(core_jpg, "JPEG", quality=92)
print(f"wrote {core_jpg}")

print("done")

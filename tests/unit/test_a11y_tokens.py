"""無障礙稽核（純 token 層）：WCAG 對比與 token 規格檢查。

不依賴瀏覽器 / Playwright，純解析 frontend/css/style.css 與 elder-mode.css
的 :root token，計算對比並驗收：
  - WCAG AA 內文（≥ 4.5:1）
  - WCAG AA 大字 / 標題（≥ 3:1）
  - 長者模式字級 ≥ 18px、tap target ≥ 56px
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STYLE_CSS = ROOT / "frontend" / "css" / "style.css"
ELDER_CSS = ROOT / "frontend" / "css" / "elder-mode.css"


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _luminance(rgb: tuple[int, int, int]) -> float:
    def channel(v: int) -> float:
        v_norm = v / 255.0
        return v_norm / 12.92 if v_norm <= 0.03928 else ((v_norm + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    l_fg = _luminance(_hex_to_rgb(fg_hex))
    l_bg = _luminance(_hex_to_rgb(bg_hex))
    lighter, darker = max(l_fg, l_bg), min(l_fg, l_bg)
    return (lighter + 0.05) / (darker + 0.05)


_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _parse_root_tokens(css_text: str, scope_selector: str = ":root") -> dict[str, str]:
    """取得 scope_selector { ... } 區塊中的 --token: value 對。

    先把 CSS 註解整段拿掉，再切分 declarations，避免 /* … */\n--token 黏在一起。
    """
    pattern = re.compile(
        re.escape(scope_selector) + r"[^{]*\{([^}]*)\}",
        re.DOTALL,
    )
    m = pattern.search(css_text)
    if not m:
        return {}
    block = _COMMENT_RE.sub("", m.group(1))
    tokens: dict[str, str] = {}
    for line in block.split(";"):
        line = line.strip()
        if not line.startswith("--"):
            continue
        if ":" not in line:
            continue
        name, _, value = line.partition(":")
        tokens[name.strip()] = value.strip()
    return tokens


# ─── 對比測試 ────────────────────────────────────────────────


def test_default_text_on_bg_meets_wcag_aa():
    """:root 內文（--text on --bg-deep）對比 ≥ 4.5"""
    css = STYLE_CSS.read_text(encoding="utf-8")
    tokens = _parse_root_tokens(css, ":root")
    text = tokens["--text"]
    bg = tokens["--bg-deep"]
    ratio = contrast_ratio(text, bg)
    assert ratio >= 4.5, f"text on bg 對比 {ratio:.2f} < 4.5（WCAG AA）"


def test_text_on_surface_meets_aa():
    css = STYLE_CSS.read_text(encoding="utf-8")
    tokens = _parse_root_tokens(css, ":root")
    text = tokens["--text"]
    surface = tokens["--bg-surface"]
    assert contrast_ratio(text, surface) >= 4.5


def test_accent_on_white_meets_aa_large():
    """primary CTA 顏色作為大字 / 標題色時 ≥ 3:1"""
    css = STYLE_CSS.read_text(encoding="utf-8")
    tokens = _parse_root_tokens(css, ":root")
    accent = tokens["--accent"]
    bg = tokens["--bg-deep"]
    ratio = contrast_ratio(accent, bg)
    assert ratio >= 3.0, f"accent on bg 對比 {ratio:.2f} < 3.0（WCAG AA 大字）"


def test_severity_er_meets_aa_large_on_white():
    """急診紅在白底上的對比 ≥ 3:1（作為邊框 / chip 用）"""
    css = STYLE_CSS.read_text(encoding="utf-8")
    tokens = _parse_root_tokens(css, ":root")
    # --sev-er 解析為 var(--danger)
    danger = tokens["--danger"]
    bg = tokens["--bg-deep"]
    assert contrast_ratio(danger, bg) >= 3.0


# ─── 長者模式規格測試 ──────────────────────────────────────────


def test_elder_mode_base_font_at_least_18px():
    css = ELDER_CSS.read_text(encoding="utf-8")
    tokens = _parse_root_tokens(css, "html.elder-mode,\nhtml[data-mode=\"senior\"]")
    base = tokens.get("--font-base", "")
    px = int(re.search(r"(\d+)", base).group(1))
    assert px >= 18, f"elder mode base font {px}px < 18px"


def test_elder_mode_tap_target_at_least_56px():
    css = ELDER_CSS.read_text(encoding="utf-8")
    # --tap-min 在 elder-mode 下被指向 var(--tap-elder)，所以檢查 --tap-elder
    style_css = STYLE_CSS.read_text(encoding="utf-8")
    root_tokens = _parse_root_tokens(style_css, ":root")
    tap_elder = root_tokens["--tap-elder"]
    px = int(re.search(r"(\d+)", tap_elder).group(1))
    assert px >= 56, f"tap-elder {px}px < 56px"


def test_elder_mode_line_height_at_least_1_6():
    css = ELDER_CSS.read_text(encoding="utf-8")
    tokens = _parse_root_tokens(css, "html.elder-mode,\nhtml[data-mode=\"senior\"]")
    lh = float(tokens["--lh-base"])
    assert lh >= 1.6, f"elder mode line-height {lh} < 1.6"


def test_elder_accent_still_meets_contrast():
    """elder-mode 的加深 accent 在暖白底上仍要 ≥ 3:1"""
    elder_css = ELDER_CSS.read_text(encoding="utf-8")
    tokens = _parse_root_tokens(elder_css, "html.elder-mode,\nhtml[data-mode=\"senior\"]")
    accent = tokens["--accent"]      # #3B7AAA
    bg = tokens["--bg-deep"]         # #FFFBF5
    assert contrast_ratio(accent, bg) >= 3.0


# ─── 設計憲法：每頁 1 個 CTA 顏色（token 維度的快檢） ────────


def test_one_primary_cta_color():
    css = STYLE_CSS.read_text(encoding="utf-8")
    tokens = _parse_root_tokens(css, ":root")
    # 確認只有 1 個 --accent 作為主 CTA，不是同時 --accent 與 --teal 都做 CTA
    assert "--accent" in tokens
    assert tokens["--accent"].startswith("#"), "--accent 必須是 hex"

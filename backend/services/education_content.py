"""讀取 content/education/*.md 衛教文章。

檔名規則決定語言版本：
- ``<slug>.md`` → 預設語言（zh-TW）
- ``<slug>.<lang>.md`` → 該 lang 版本（如 ``foo.en.md``）

兩種變體共用同一個 ``slug``（在 frontmatter 設定，或從檔名推導）。
取卡片或全文時可帶 ``lang``，找不到指定語言會 fallback 到預設語言。

文章用 YAML-style frontmatter 加 Markdown 本文。為了不引入額外套件，
這裡只解析需要的 frontmatter 欄位（字串、布林、字串清單）。審稿在 GitHub PR 上做。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from functools import lru_cache
from pathlib import Path
from typing import Optional
import logging
import re

logger = logging.getLogger(__name__)

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content" / "education"

DEFAULT_LANG = "zh-TW"
SUPPORTED_LANGS = ("zh-TW", "en")

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_LIST_ITEM_RE = re.compile(r"^\s*-\s*(.*\S)\s*$")
_KEY_VALUE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")


def _detect_lang_from_stem(stem: str) -> tuple[str, str]:
    """``<slug>.en`` → ``(slug, 'en')``；``slug`` → ``(slug, DEFAULT_LANG)``。"""
    for lang in SUPPORTED_LANGS:
        if lang == DEFAULT_LANG:
            continue
        suffix = "." + lang
        if stem.endswith(suffix):
            return stem[: -len(suffix)], lang
    return stem, DEFAULT_LANG


@dataclass
class Article:
    slug: str
    title: str
    summary: str = ""
    icd10: Optional[str] = None
    dimension: Optional[str] = None
    category: Optional[str] = None  # disease | quick_tip | news
    tags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    featured: bool = False
    reviewed_at: Optional[str] = None
    lang: str = DEFAULT_LANG
    body: str = ""

    def to_card(self) -> dict:
        d = asdict(self)
        d.pop("body", None)
        return d

    def to_full(self) -> dict:
        return asdict(self)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_scalar(raw: str):
    raw = raw.strip()
    if raw.lower() in {"true", "yes"}:
        return True
    if raw.lower() in {"false", "no"}:
        return False
    # Inline list: [a, b, "c, d"] — supports unquoted CJK items, quoted commas,
    # apostrophes inside words, and YAML-style escapes.
    if raw.startswith("[") and raw.endswith("]"):
        return _split_inline_list(raw[1:-1])
    return _strip_quotes(raw)


def _split_inline_list(body: str) -> list[str]:
    """Split YAML-ish inline list. Quotes only count at item boundaries —
    apostrophes inside words (Children's Health, O'Brien) stay literal.
    Inside a quoted item, a doubled quote escapes to a literal one
    (YAML 'a''b' → a'b). Inside a double-quoted item, backslash escapes
    are honoured (YAML "a\\"b" → a"b, "\\n" → newline).
    """
    items: list[str] = []
    buf: list[str] = []
    quote: Optional[str] = None
    in_value = False
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        if quote is not None:
            # Backslash escapes inside double-quoted scalars (YAML).
            if quote == '"' and ch == "\\" and i + 1 < n:
                nxt = body[i + 1]
                buf.append({"n": "\n", "t": "\t", "r": "\r"}.get(nxt, nxt))
                i += 2
                continue
            if ch == quote:
                # YAML doubled-quote escape: '' → ' (and "" → ").
                if i + 1 < n and body[i + 1] == quote:
                    buf.append(ch)
                    i += 2
                    continue
                quote = None
                i += 1
                continue
            buf.append(ch)
            i += 1
            continue
        if not in_value:
            if ch.isspace():
                i += 1
                continue
            if ch in {'"', "'"}:
                quote = ch
                in_value = True
                i += 1
                continue
        if ch == ",":
            items.append("".join(buf).strip())
            buf = []
            in_value = False
            i += 1
            continue
        in_value = True
        buf.append(ch)
        i += 1
    if in_value:
        items.append("".join(buf).strip())
    return [item for item in items if item]


def _parse_frontmatter(text: str) -> dict:
    """Tiny YAML subset: top-level scalars and lists of strings."""
    data: dict = {}
    current_key: Optional[str] = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        list_match = _LIST_ITEM_RE.match(line)
        if list_match and current_key is not None:
            data.setdefault(current_key, []).append(_strip_quotes(list_match.group(1)))
            continue
        kv_match = _KEY_VALUE_RE.match(line)
        if not kv_match:
            continue
        key, raw_value = kv_match.group(1), kv_match.group(2)
        if raw_value.strip() == "":
            current_key = key
            data[key] = []
        else:
            current_key = None
            data[key] = _parse_scalar(raw_value)
    return data


def _load_article(path: Path) -> Optional[Article]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return None

    match = _FRONTMATTER_RE.match(raw)
    if not match:
        logger.warning("Missing frontmatter in %s, skipping", path.name)
        return None

    meta = _parse_frontmatter(match.group(1))
    body = match.group(2).strip()

    title = meta.get("title")
    if not title:
        logger.warning("Missing title in %s, skipping", path.name)
        return None

    clean_stem, file_lang = _detect_lang_from_stem(path.stem)
    # frontmatter 也可顯式覆寫 lang；否則由檔名推導
    lang = str(meta.get("lang") or file_lang)
    slug = meta.get("slug") or clean_stem
    return Article(
        slug=str(slug),
        title=str(title),
        summary=str(meta.get("summary", "")),
        icd10=meta.get("icd10") or None,
        dimension=meta.get("dimension") or None,
        category=(str(meta.get("category")).lower() if meta.get("category") else None),
        tags=list(meta.get("tags") or []),
        sources=list(meta.get("sources") or []),
        featured=bool(meta.get("featured", False)),
        reviewed_at=meta.get("reviewed_at") or None,
        lang=lang,
        body=body,
    )


@lru_cache(maxsize=1)
def _load_all_cached() -> tuple[Article, ...]:
    if not CONTENT_DIR.exists():
        return ()
    articles: list[Article] = []
    for path in sorted(CONTENT_DIR.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        article = _load_article(path)
        if article:
            articles.append(article)
    return tuple(articles)


def reload_articles() -> int:
    _load_all_cached.cache_clear()
    return len(_load_all_cached())


def _normalize_lang(lang: Optional[str]) -> str:
    if not lang:
        return DEFAULT_LANG
    if lang in SUPPORTED_LANGS:
        return lang
    # 接受常見變體：en-US → en，zh-Hant → zh-TW
    base = lang.split("-")[0].lower()
    if base == "en":
        return "en"
    if base == "zh":
        return "zh-TW"
    return DEFAULT_LANG


def list_articles(
    icd10: Optional[str] = None,
    dimension: Optional[str] = None,
    tag: Optional[str] = None,
    featured_only: bool = False,
    lang: Optional[str] = None,
) -> list[Article]:
    """回傳指定語言的卡片清單；該 slug 沒有指定語言版本時 fallback 到預設語言。"""
    items = list(_load_all_cached())
    target_lang = _normalize_lang(lang)

    # 同 slug 多語言版本：先建索引，找不到目標語言的就回退到 DEFAULT_LANG。
    by_slug: dict[str, dict[str, Article]] = {}
    for a in items:
        by_slug.setdefault(a.slug, {})[a.lang] = a

    resolved: list[Article] = []
    for slug, variants in by_slug.items():
        article = variants.get(target_lang) or variants.get(DEFAULT_LANG)
        if article is None:
            # 萬一連 DEFAULT_LANG 都沒有（理論上不會），取任意一個
            article = next(iter(variants.values()))
        resolved.append(article)

    if icd10:
        prefix = icd10[:3].upper()
        resolved = [a for a in resolved if (a.icd10 or "").upper().startswith(prefix)]
    if dimension:
        resolved = [a for a in resolved if a.dimension == dimension]
    if tag:
        resolved = [a for a in resolved if tag in a.tags]
    if featured_only:
        resolved = [a for a in resolved if a.featured]
    # 維持原本相對順序（按檔名字母序）
    return sorted(resolved, key=lambda a: a.slug)


def get_article(slug: str, lang: Optional[str] = None) -> Optional[Article]:
    target_lang = _normalize_lang(lang)
    fallback: Optional[Article] = None
    for article in _load_all_cached():
        if article.slug != slug:
            continue
        if article.lang == target_lang:
            return article
        if article.lang == DEFAULT_LANG:
            fallback = article
    return fallback

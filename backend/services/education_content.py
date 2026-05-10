"""讀取 content/education/*.md 衛教文章。

文章用 YAML-style frontmatter 加 Markdown 本文。為了不引入額外套件，
這裡只解析需要的 frontmatter 欄位（字串、布林、字串清單）。審稿在 GitHub PR 上做。

文獻來源（sources）規範：每篇衛教文必須附 ≥3 條文獻，其中至少 2 條為
peer-reviewed 期刊文章，期刊 Impact Factor > 5。建議格式：

    sources:
      - "作者 et al. (YYYY). 文章標題. 期刊名 (IF=XX.X). doi:10.xxxx/yyyy"

解析時會用正規式抓出 `IF=XX.X` 與 `doi:` 給前端顯示徽章。
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

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_LIST_ITEM_RE = re.compile(r"^\s*-\s*(.*\S)\s*$")
_KEY_VALUE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")

_IF_RE = re.compile(r"IF\s*=\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
_YEAR_RE = re.compile(r"\((\d{4})\)|\b(20\d{2}|19\d{2})\b")
_DOI_RE = re.compile(r"doi[:\s]\s*(10\.[^\s,;]+)", re.IGNORECASE)
_PMID_RE = re.compile(r"PMID[:\s]\s*(\d+)", re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s]+")

# 已知高 IF 期刊清單（IF > 5），供 LLM 與審稿者參考
HIGH_IF_JOURNALS = {
    "NEJM": 158.5, "New England Journal of Medicine": 158.5,
    "Lancet": 98.4, "The Lancet": 98.4,
    "JAMA": 63.1, "Journal of the American Medical Association": 63.1,
    "BMJ": 93.6, "British Medical Journal": 93.6,
    "Nature Medicine": 58.7, "Nat Med": 58.7,
    "Cell": 45.5,
    "Lancet Oncology": 51.1, "Lancet Diabetes Endocrinol": 44.0,
    "Lancet Neurology": 48.0, "Lancet Respir Med": 76.2,
    "JAMA Internal Medicine": 22.5, "JAMA Cardiology": 24.0,
    "JAMA Oncology": 22.5, "JAMA Neurology": 20.4,
    "Circulation": 37.8, "European Heart Journal": 37.6,
    "Diabetes Care": 16.2, "Diabetologia": 8.4,
    "Hypertension": 7.7, "JACC": 21.7,
    "Annals of Internal Medicine": 19.6,
    "Gut": 23.0, "Hepatology": 12.9,
    "Kidney International": 14.8, "JASN": 13.6,
    "Chest": 9.6, "American Journal of Respiratory and Critical Care Medicine": 24.7,
    "Stroke": 7.8, "Neurology": 7.7,
    "Cochrane Database of Systematic Reviews": 8.4,
}


def _parse_source(text: str) -> dict:
    """從來源字串抽 metadata（impact factor / 年份 / doi / pmid / url）。

    解析失敗的欄位會以 None 表示，原始字串保留在 `text` 供前端 fallback。
    """
    if not text:
        return {"text": "", "impact_factor": None, "year": None, "doi": None, "pmid": None, "url": None, "is_peer_reviewed": False}

    if_match = _IF_RE.search(text)
    impact_factor = float(if_match.group(1)) if if_match else None

    year_match = _YEAR_RE.search(text)
    year = None
    if year_match:
        year = year_match.group(1) or year_match.group(2)

    doi_match = _DOI_RE.search(text)
    doi = doi_match.group(1).rstrip(".)") if doi_match else None

    pmid_match = _PMID_RE.search(text)
    pmid = pmid_match.group(1) if pmid_match else None

    url_match = _URL_RE.search(text)
    url = url_match.group(0).rstrip(".)") if url_match else None

    journal = None
    for name in HIGH_IF_JOURNALS:
        if name.lower() in text.lower():
            journal = name
            if impact_factor is None:
                impact_factor = HIGH_IF_JOURNALS[name]
            break

    return {
        "text": text,
        "journal": journal,
        "impact_factor": impact_factor,
        "year": year,
        "doi": doi,
        "pmid": pmid,
        "url": url,
        "is_peer_reviewed": impact_factor is not None or pmid is not None or doi is not None,
    }


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
    body: str = ""

    def parsed_sources(self) -> list[dict]:
        return [_parse_source(s) for s in self.sources]

    def has_high_if_sources(self, min_count: int = 2, min_if: float = 5.0) -> bool:
        """檢查是否符合「至少 N 條 IF > min_if 文獻」的規範。"""
        good = [
            s for s in self.parsed_sources()
            if s["impact_factor"] is not None and s["impact_factor"] > min_if
        ]
        return len(good) >= min_count

    def to_card(self) -> dict:
        d = asdict(self)
        d.pop("body", None)
        d["parsed_sources"] = self.parsed_sources()
        d["meets_evidence_standard"] = self.has_high_if_sources()
        return d

    def to_full(self) -> dict:
        d = asdict(self)
        d["parsed_sources"] = self.parsed_sources()
        d["meets_evidence_standard"] = self.has_high_if_sources()
        return d


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

    slug = meta.get("slug") or path.stem
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


def list_articles(
    icd10: Optional[str] = None,
    dimension: Optional[str] = None,
    tag: Optional[str] = None,
    featured_only: bool = False,
) -> list[Article]:
    items = list(_load_all_cached())
    if icd10:
        prefix = icd10[:3].upper()
        items = [a for a in items if (a.icd10 or "").upper().startswith(prefix)]
    if dimension:
        items = [a for a in items if a.dimension == dimension]
    if tag:
        items = [a for a in items if tag in a.tags]
    if featured_only:
        items = [a for a in items if a.featured]
    return items


def get_article(slug: str) -> Optional[Article]:
    for article in _load_all_cached():
        if article.slug == slug:
            return article
    return None

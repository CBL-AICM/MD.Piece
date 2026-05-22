"""最新醫療資訊：抓 RSS（預設衛福部新聞），TTL 快取，失敗回空陣列。

設計原則：
- 只用 stdlib（urllib、xml.etree、html、re），不引入新依賴
- 一小時 TTL，失敗或逾時直接回 [] 並記 log，不擋整個頁面
- 來源設定：
  - 多來源：``NEWS_FEED_URLS``（逗號分隔），各來源 round-robin merge
  - 單一來源：``NEWS_FEED_URL``（舊版相容）
  - 都沒設則用衛福部
"""
from __future__ import annotations

import logging
import os
import re
import time
import urllib.request
from html import unescape
from typing import Any
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# 衛福部新聞 RSS（中文官方來源）。可由環境變數加 NEWS_FEED_URLS 補上元氣網、健康 2.0 等。
DEFAULT_FEED_URLS = ("https://www.mohw.gov.tw/rss-16-1.html",)
USER_AGENT = "MD.Piece/1.0 (+https://www.mdpiece.life)"
TTL_SECONDS = 3600
FETCH_TIMEOUT = 4.0

_TAG_RE = re.compile(r"<[^>]+>")

_cache: dict[str, Any] = {"items": [], "fetched_at": 0.0, "key": None}


def _configured_urls() -> tuple[str, ...]:
    """讀環境設定的 RSS 來源清單。NEWS_FEED_URLS 優先，否則退 NEWS_FEED_URL，再退預設。"""
    multi = os.getenv("NEWS_FEED_URLS", "").strip()
    if multi:
        urls = tuple(u.strip() for u in multi.split(",") if u.strip())
        if urls:
            return urls
    single = os.getenv("NEWS_FEED_URL", "").strip()
    if single:
        return (single,)
    return DEFAULT_FEED_URLS


def _strip_html(raw: str) -> str:
    if not raw:
        return ""
    text = unescape(raw)
    text = _TAG_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _findtext(node: ET.Element, *names: str) -> str:
    """rss 2.0 / atom 各自的欄位都試一輪。"""
    for name in names:
        el = node.find(name)
        if el is None:
            # atom namespace
            el = node.find("{http://www.w3.org/2005/Atom}" + name)
        if el is not None:
            if el.text:
                return el.text.strip()
            href = el.attrib.get("href")
            if href:
                return href.strip()
    return ""


def _parse_feed(xml_text: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("news_feed: parse error %s", exc)
        return []

    items: list[dict] = []

    # RSS 2.0: <rss><channel><item>...
    for item in root.iter("item"):
        title = _findtext(item, "title")
        if not title:
            continue
        link = _findtext(item, "link", "guid")
        desc = _findtext(item, "description", "summary")
        pub = _findtext(item, "pubDate", "published", "updated")
        items.append({
            "title": _strip_html(title),
            "summary": _strip_html(desc)[:200],
            "link": link,
            "published": pub,
        })

    # Atom: <feed><entry>...
    if not items:
        ns = "{http://www.w3.org/2005/Atom}"
        for entry in root.iter(ns + "entry"):
            title = _findtext(entry, "title")
            if not title:
                continue
            link = _findtext(entry, "link", "id")
            summary = _findtext(entry, "summary", "content")
            pub = _findtext(entry, "updated", "published")
            items.append({
                "title": _strip_html(title),
                "summary": _strip_html(summary)[:200],
                "link": link,
                "published": pub,
            })

    return items


def _fetch_single(url: str) -> list[dict]:
    """單一 RSS 來源抓取 + 解析；失敗回 []。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            raw = resp.read()
        # 多數中文官方 RSS 是 UTF-8，少數 big5；先試 utf-8、退 big5
        for enc in ("utf-8", "big5", "latin-1"):
            try:
                xml_text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            xml_text = raw.decode("utf-8", errors="ignore")
        items = _parse_feed(xml_text)
    except Exception as exc:  # 網路/timeout/HTTP 錯誤一律記 log 但不擋頁面
        logger.warning("news_feed: fetch failed (%s): %s", url, exc)
        return []
    for item in items:
        item["source"] = url
    return items


def _interleave(feeds: list[list[dict]]) -> list[dict]:
    """round-robin 合併多個 feed，確保 top N 不會被單一來源壟斷。"""
    merged: list[dict] = []
    if not feeds:
        return merged
    max_len = max(len(f) for f in feeds)
    for i in range(max_len):
        for f in feeds:
            if i < len(f):
                merged.append(f[i])
    return merged


def fetch_news(limit: int = 6) -> list[dict]:
    """回傳近期新聞 list（最多 ``limit`` 則）。失敗時回 []。"""
    urls = _configured_urls()
    cache_key = "|".join(urls)
    now = time.time()
    if (
        _cache["items"]
        and _cache["key"] == cache_key
        and (now - _cache["fetched_at"]) < TTL_SECONDS
    ):
        return _cache["items"][:limit]

    per_feed = [_fetch_single(u) for u in urls]
    merged = _interleave(per_feed)

    _cache["items"] = merged
    _cache["fetched_at"] = now
    _cache["key"] = cache_key
    return merged[:limit]


def reset_cache() -> None:
    _cache["items"] = []
    _cache["fetched_at"] = 0.0
    _cache["key"] = None

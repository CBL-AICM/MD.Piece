"""最新醫療資訊：抓 RSS（預設衛福部新聞），TTL 快取，失敗回空陣列。

設計原則：
- 只用 stdlib（urllib、xml.etree、html、re），不引入新依賴
- 一小時 TTL，失敗或逾時直接回 [] 並記 log，不擋整個頁面
- feed URL 可用環境變數 ``NEWS_FEED_URL`` 切換來源
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

# 衛福部新聞 RSS（中文官方來源）。可由環境變數覆寫成國健署/疾管署/CDC 等。
DEFAULT_FEED_URL = "https://www.mohw.gov.tw/rss-16-1.html"
USER_AGENT = "MD.Piece/1.0 (+https://www.mdpiece.life)"
TTL_SECONDS = 3600
FETCH_TIMEOUT = 4.0

_TAG_RE = re.compile(r"<[^>]+>")

_cache: dict[str, Any] = {"items": [], "fetched_at": 0.0, "url": None}


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


def fetch_news(limit: int = 6) -> list[dict]:
    """回傳近期新聞 list（最多 ``limit`` 則）。失敗時回 []。"""
    url = os.getenv("NEWS_FEED_URL", DEFAULT_FEED_URL)
    now = time.time()
    if (
        _cache["items"]
        and _cache["url"] == url
        and (now - _cache["fetched_at"]) < TTL_SECONDS
    ):
        return _cache["items"][:limit]

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
        items = []

    _cache["items"] = items
    _cache["fetched_at"] = now
    _cache["url"] = url
    return items[:limit]


def reset_cache() -> None:
    _cache["items"] = []
    _cache["fetched_at"] = 0.0
    _cache["url"] = None

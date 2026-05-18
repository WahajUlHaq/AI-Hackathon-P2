"""
Agent 1b — URL Scraper
======================
Libraries: requests, BeautifulSoup4 (primary), newspaper3k (fallback)
LLM      : None — pure Python, deterministic
Spec     : stage1_parsers.md § "Agent 1b — URL Scraper"
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

try:
    from bs4 import BeautifulSoup
    _BS4_OK = True
except ImportError:
    _BS4_OK = False

try:
    from newspaper import Article
    _NEWSPAPER_OK = True
except ImportError:
    _NEWSPAPER_OK = False

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

CREDIBILITY_MAP: dict[str, float] = {
    "reuters.com": 0.85, "bloomberg.com": 0.85, "ft.com": 0.85,
    "bbc.com": 0.80, "bbc.co.uk": 0.80, "nytimes.com": 0.80, "wsj.com": 0.80,
    "techcrunch.com": 0.70, "theverge.com": 0.70,
    "wired.com": 0.70, "arstechnica.com": 0.70,
}
PAYWALL_KEYWORDS = [
    "subscribe to read", "subscribe now", "sign up to continue",
    "create a free account", "buy a subscription",
]
STALE_DAYS = 7


def parse(source: dict[str, Any]) -> dict[str, Any]:
    label       = source.get("label", "Unknown URL")
    url         = source.get("content", "").strip()
    received_at = source.get("received_at", datetime.now(timezone.utc).isoformat())

    if not url:
        return _noise_block(label, url, received_at, "empty URL")
    if not _REQUESTS_OK:
        return _noise_block(label, url, received_at, "requests library not available")

    domain = _extract_domain(url)

    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15, allow_redirects=True)
    except requests.exceptions.ConnectionError:
        return _noise_block(label, url, received_at, "connection error")
    except requests.exceptions.Timeout:
        return _noise_block(label, url, received_at, "request timeout")
    except Exception as exc:
        return _noise_block(label, url, received_at, f"fetch error: {exc}")

    if resp.status_code == 404:
        return _noise_block(label, url, received_at, "page not found")
    if resp.status_code >= 400:
        return _noise_block(label, url, received_at, f"HTTP {resp.status_code}")

    html = resp.text
    raw_text, publish_date, author, scrape_method = "", None, None, "beautifulsoup"

    if _BS4_OK:
        raw_text, publish_date, author = _extract_bs4(html)

    word_count = len(raw_text.split())
    if (word_count < 50 or _is_paywall(raw_text, html)) and _NEWSPAPER_OK:
        np_text, np_date, np_author = _extract_newspaper(url)
        if len(np_text.split()) > word_count:
            raw_text, publish_date, author, scrape_method = (
                np_text, np_date or publish_date, np_author or author, "newspaper3k"
            )

    word_count = len(raw_text.split())
    page_title = _get_title(html) if _BS4_OK else ""

    if "404" in page_title.lower():
        return _noise_block(label, url, received_at, "page not found")
    if word_count < 50:
        return _noise_block(label, url, received_at, "too short")
    if _is_paywall(raw_text, html):
        return _noise_block(label, url, received_at, "paywall detected")

    effective_date = publish_date or received_at
    is_stale       = _check_stale(effective_date)
    credibility    = _get_credibility(domain)
    timestamp      = publish_date if publish_date else received_at

    return {
        "source_type"       : "URL",
        "source_label"      : label,
        "raw_text"          : raw_text.strip(),
        "timestamp"         : timestamp,
        "credibility_score" : credibility,
        "domain"            : "news",
        "is_stale"          : is_stale,
        "is_noise"          : False,
        "noise_reason"      : None,
        "word_count"        : word_count,
        "language"          : "en",
        "extraction_method" : scrape_method,
        "metadata"          : {
            "url": url, "domain": domain,
            "publish_date": publish_date, "author": author, "scrape_method": scrape_method,
        },
    }


def _extract_bs4(html: str) -> tuple[str, str | None, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()

    publish_date = None
    for attr in ("article:published_time", "og:updated_time", "datePublished"):
        meta = soup.find("meta", property=attr) or soup.find("meta", itemprop=attr)
        if meta and meta.get("content"):
            publish_date = _normalise_date(meta["content"])
            break
    if not publish_date:
        time_tag = soup.find("time", attrs={"datetime": True})
        if time_tag:
            publish_date = _normalise_date(time_tag["datetime"])

    author = None
    for attr in ("author", "article:author"):
        meta = soup.find("meta", attrs={"name": attr}) or soup.find("meta", property=attr)
        if meta and meta.get("content"):
            author = meta["content"].strip()
            break

    container = (
        soup.find("article") or soup.find("main")
        or soup.find(id=re.compile(r"content|article|main", re.I))
        or soup.body
    )
    parts: list[str] = []
    if container:
        for p in container.find_all(["p", "h1", "h2", "h3", "li"]):
            t = p.get_text(separator=" ", strip=True)
            if len(t) > 20:
                parts.append(t)
    return " ".join(parts), publish_date, author


def _extract_newspaper(url: str) -> tuple[str, str | None, str | None]:
    try:
        article = Article(url)
        article.download()
        article.parse()
        date_str = article.publish_date.strftime("%Y-%m-%dT%H:%M:%SZ") if article.publish_date else None
        author   = ", ".join(article.authors) if article.authors else None
        return article.text, date_str, author
    except Exception:
        return "", None, None


def _get_title(html: str) -> str:
    try:
        soup = BeautifulSoup(html, "html.parser")
        return soup.title.string if soup.title else ""
    except Exception:
        return ""


def _is_paywall(text: str, html: str) -> bool:
    combined = (text + html).lower()
    return sum(1 for kw in PAYWALL_KEYWORDS if kw in combined) >= 2


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.removeprefix("www.")
    except Exception:
        return url


def _get_credibility(domain: str) -> float:
    for key, score in CREDIBILITY_MAP.items():
        if domain.endswith(key):
            return score
    if any(s in domain for s in ["blogspot", "wordpress", "medium.com", "substack"]):
        return 0.40
    return 0.55


def _normalise_date(raw: str) -> str | None:
    try:
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw[:25], fmt)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue
        return None
    except Exception:
        return None


def _check_stale(date_str: str) -> bool:
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days > STALE_DAYS
    except Exception:
        return False


def _noise_block(label: str, url: str, received_at: str, reason: str) -> dict[str, Any]:
    return {
        "source_type": "URL", "source_label": label, "raw_text": "",
        "timestamp": received_at, "credibility_score": 0.0, "domain": "news",
        "is_stale": False, "is_noise": True, "noise_reason": reason,
        "word_count": 0, "language": "en", "extraction_method": "none",
        "metadata": {"url": url, "domain": _extract_domain(url) if url else "",
                     "publish_date": None, "author": None, "scrape_method": "none"},
    }

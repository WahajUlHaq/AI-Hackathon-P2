"""
Agent 1e — Feed Parser (Mock Social/News Feed)
==============================================
Library : json, re, string processing
LLM     : None — pure Python, deterministic
Spec    : stage1_parsers.md § "Agent 1e — Feed Parser"
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

STALE_DAYS = 7

# ---------------------------------------------------------------------------
# Sentiment keyword banks
# ---------------------------------------------------------------------------
NEGATIVE_KEYWORDS = [
    "layoff", "layoffs", "fired", "job search", "worried", "stock crash",
    "sell", "avoid", "resign", "leaving", "cut", "cuts", "downgrade",
    "bankruptcy", "loss", "losses", "fraud", "scandal", "collapse",
]
POSITIVE_KEYWORDS = [
    "hiring", "opportunity", "buy the dip", "strong fundamentals",
    "growth", "record", "beat", "upgrade", "raise", "bullish",
    "partnership", "expansion", "profit",
]
NEUTRAL_KEYWORDS = [
    "news", "update", "report", "announced", "statement", "filing",
    "conference", "release", "earnings",
]

# ---------------------------------------------------------------------------
# Baseline posts per 6-hour window (for spike detection)
# ---------------------------------------------------------------------------
BASELINE_POSTS = 170  # approximate 7-day average


def parse(source: dict[str, Any]) -> dict[str, Any]:
    """
    Parse a mock social/news feed source.

    The feed ``content`` field may be:
    - A JSON array of post objects: ``[{"text": "...", "author": "...", ...}, ...]``
    - A JSON object with a ``posts`` key
    - A plain newline-separated text block (one post per line)

    Returns a ContentBlock (id omitted — set by runner).
    """
    label       = source.get("label", "Unknown Feed")
    content     = source.get("content", "")
    received_at = source.get("received_at", datetime.now(timezone.utc).isoformat())

    if not content or not content.strip():
        return _noise_block(label, received_at, "empty content")

    posts = _extract_posts(content)
    if not posts:
        return _noise_block(label, received_at, "no posts could be extracted")

    # ── Sentiment analysis ──────────────────────────────────────────────────
    sentiment_score, neg_count, pos_count = _compute_sentiment(posts)

    # ── Topic extraction ────────────────────────────────────────────────────
    topic_counts = _extract_topics(posts)

    # ── Volume spike ────────────────────────────────────────────────────────
    post_count     = len(posts)
    volume_spike   = round(((post_count - BASELINE_POSTS) / BASELINE_POSTS) * 100, 1)

    # ── Verified employee signals ───────────────────────────────────────────
    verified_count = _count_verified_employees(posts)

    # ── Build prose ─────────────────────────────────────────────────────────
    raw_text = _build_prose(
        label, received_at, post_count, volume_spike,
        topic_counts, sentiment_score, verified_count,
    )

    # ── Staleness ───────────────────────────────────────────────────────────
    is_stale = _check_stale(received_at)

    # ── Credibility ─────────────────────────────────────────────────────────
    credibility = _compute_credibility(post_count, verified_count)

    word_count = len(raw_text.split())

    return {
        "source_type"       : "MockFeed",
        "source_label"      : label,
        "raw_text"          : raw_text,
        "timestamp"         : received_at,
        "credibility_score" : credibility,
        "domain"            : "social",
        "is_stale"          : is_stale,
        "is_noise"          : False,
        "noise_reason"      : None,
        "word_count"        : word_count,
        "language"          : "en",
        "extraction_method" : "keyword_matching",
        "metadata"          : {
            "post_count"       : post_count,
            "volume_spike_pct" : max(0, volume_spike),
            "sentiment_score"  : round(sentiment_score, 2),
            "top_topics"       : dict(list(topic_counts.items())[:5]),
            "verified_employees": verified_count,
        },
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_posts(content: str) -> list[str]:
    """Return list of post text strings from various feed formats."""
    content = content.strip()

    # Try JSON
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return [_get_text(item) for item in data if _get_text(item)]
        if isinstance(data, dict):
            for key in ("posts", "items", "data", "entries", "results"):
                if key in data and isinstance(data[key], list):
                    return [_get_text(i) for i in data[key] if _get_text(i)]
            # Single post object
            text = _get_text(data)
            return [text] if text else []
    except (json.JSONDecodeError, TypeError):
        pass

    # Fall back to newline-separated plain text
    lines = [l.strip() for l in content.splitlines() if len(l.strip()) > 10]
    return lines


def _get_text(item: Any) -> str:
    """Extract text from a post dict or string."""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("text", "content", "body", "message", "post", "tweet"):
            if key in item and isinstance(item[key], str):
                return item[key].strip()
        # Concatenate all string values
        return " ".join(str(v) for v in item.values() if isinstance(v, str)).strip()
    return ""


def _compute_sentiment(posts: list[str]) -> tuple[float, int, int]:
    """Return (sentiment_score, neg_count, pos_count)."""
    neg_count = 0
    pos_count = 0
    combined  = " ".join(posts).lower()

    for kw in NEGATIVE_KEYWORDS:
        neg_count += len(re.findall(r"\b" + re.escape(kw) + r"\b", combined))
    for kw in POSITIVE_KEYWORDS:
        pos_count += len(re.findall(r"\b" + re.escape(kw) + r"\b", combined))

    total = neg_count + pos_count
    if total == 0:
        return 0.0, 0, 0
    score = (pos_count - neg_count) / total
    return score, neg_count, pos_count


def _extract_topics(posts: list[str]) -> dict[str, int]:
    """Count occurrences of each topic keyword across all posts."""
    all_keywords = NEGATIVE_KEYWORDS + POSITIVE_KEYWORDS + NEUTRAL_KEYWORDS
    combined     = " ".join(posts).lower()
    counts: dict[str, int] = {}
    for kw in all_keywords:
        n = len(re.findall(r"\b" + re.escape(kw) + r"\b", combined))
        if n > 0:
            counts[kw] = n
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def _count_verified_employees(posts: list[str]) -> int:
    """Heuristic: count posts mentioning resume updates or job searching."""
    signals = ["updating my resume", "open to work", "just got laid off",
               "looking for opportunities", "new chapter", "#opentowork"]
    count = 0
    for post in posts:
        lower = post.lower()
        if any(sig in lower for sig in signals):
            count += 1
    return count


def _build_prose(
    label: str,
    received_at: str,
    post_count: int,
    volume_spike: float,
    topic_counts: dict[str, int],
    sentiment_score: float,
    verified_count: int,
) -> str:
    date_str = received_at[:10]
    lines: list[str] = []

    # Header
    spike_str = f" — {volume_spike:.0f}% above 7-day average" if volume_spike > 0 else ""
    lines.append(
        f"Social sentiment analysis ({date_str}): {post_count} posts mentioning "
        f"{label.split('—')[0].strip()} in last 6 hours{spike_str}."
    )

    # Top topics
    top_topics = list(topic_counts.items())[:5]
    if top_topics:
        topic_strs = [f"'{kw}' ({cnt} posts)" for kw, cnt in top_topics]
        lines.append(f"Dominant topics: {', '.join(topic_strs)}.")

    # Sentiment
    if sentiment_score <= -0.6:
        label_str = "strongly negative"
    elif sentiment_score <= -0.2:
        label_str = "negative"
    elif sentiment_score < 0.2:
        label_str = "neutral"
    elif sentiment_score < 0.6:
        label_str = "positive"
    else:
        label_str = "strongly positive"
    lines.append(f"Sentiment score: {sentiment_score:.2f} ({label_str}).")

    # Verified employees
    if verified_count > 0:
        lines.append(
            f"{verified_count} verified employee{'s' if verified_count > 1 else ''} "
            f"posted about updating resume{'s' if verified_count > 1 else ''}."
        )

    return " ".join(lines)


def _compute_credibility(post_count: int, verified_count: int) -> float:
    """Social feeds are inherently lower credibility (0.55–0.70)."""
    base = 0.55
    if post_count > 500:
        base += 0.05
    if verified_count > 5:
        base += 0.05
    return min(base, 0.70)


def _check_stale(date_str: str) -> bool:
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days > STALE_DAYS
    except Exception:
        return False


def _noise_block(label: str, received_at: str, reason: str) -> dict[str, Any]:
    return {
        "source_type": "MockFeed", "source_label": label, "raw_text": "",
        "timestamp": received_at, "credibility_score": 0.0, "domain": "social",
        "is_stale": False, "is_noise": True, "noise_reason": reason,
        "word_count": 0, "language": "en", "extraction_method": "keyword_matching",
        "metadata": {"post_count": 0, "volume_spike_pct": 0,
                     "sentiment_score": 0.0, "top_topics": {}, "verified_employees": 0},
    }

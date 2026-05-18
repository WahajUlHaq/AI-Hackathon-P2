"""
Agent 1d — JSON Parser
======================
Library : Python json module
LLM     : None — pure Python, deterministic
Spec    : stage1_parsers.md § "Agent 1d — JSON Parser"
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

STALE_DAYS = 7

# Semantic fields the parser understands
RATING_KEYS    = {"rating", "recommendation", "action", "grade"}
SCORE_KEYS     = {"score", "confidence", "probability"}
TARGET_KEYS    = {"price_target", "new_target", "target", "target_price"}
PREV_TARGET_KEYS = {"previous_target", "prev_target", "old_target", "prior_target"}
ANALYST_KEYS   = {"analyst", "firm", "bank", "source", "institution"}
DATE_KEYS      = {"date", "timestamp", "published", "report_date", "as_of"}


def parse(source: dict[str, Any]) -> dict[str, Any]:
    label       = source.get("label", "Unknown JSON")
    content     = source.get("content", "")
    received_at = source.get("received_at", datetime.now(timezone.utc).isoformat())

    if not content or not content.strip():
        return _noise_block(label, received_at, "empty content")

    # --- Parse JSON (with fallback to plain text) ---------------------------
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Treat malformed JSON as plain text
        return {
            "source_type": "JSON", "source_label": label,
            "raw_text": content.strip(),
            "timestamp": received_at, "credibility_score": 0.50,
            "domain": "news", "is_stale": False, "is_noise": False,
            "noise_reason": None, "word_count": len(content.split()),
            "language": "en", "extraction_method": "plaintext_fallback",
            "metadata": {"parse_error": "JSONDecodeError", "analysts": 0},
        }

    # --- Handle list vs dict ------------------------------------------------
    items: list[dict] = []
    if isinstance(data, list):
        items = [i for i in data if isinstance(i, dict)]
    elif isinstance(data, dict):
        items = [data]
    else:
        return _noise_block(label, received_at, "unsupported JSON root type")

    if not items:
        return _noise_block(label, received_at, "no structured objects found")

    # --- Flatten and convert to prose ---------------------------------------
    flat_items = [_flatten(item) for item in items]
    raw_text, meta = _to_prose(label, flat_items, received_at)

    credibility = _compute_credibility(flat_items)
    is_stale    = _check_stale(meta.get("detected_date") or received_at)
    word_count  = len(raw_text.split())

    return {
        "source_type"       : "JSON",
        "source_label"      : label,
        "raw_text"          : raw_text,
        "timestamp"         : meta.get("detected_date") or received_at,
        "credibility_score" : credibility,
        "domain"            : "finance",
        "is_stale"          : is_stale,
        "is_noise"          : False,
        "noise_reason"      : None,
        "word_count"        : word_count,
        "language"          : "en",
        "extraction_method" : "json",
        "metadata"          : meta,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _flatten(obj: dict, prefix: str = "", sep: str = ".") -> dict[str, Any]:
    """Recursively flatten a nested dict into dot-notation key-value pairs."""
    out: dict[str, Any] = {}
    for k, v in obj.items():
        key = f"{prefix}{sep}{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key, sep))
        elif isinstance(v, list):
            if all(isinstance(i, (str, int, float, bool)) for i in v):
                out[key] = ", ".join(str(i) for i in v)
            else:
                for idx, item in enumerate(v):
                    if isinstance(item, dict):
                        out.update(_flatten(item, f"{key}[{idx}]", sep))
                    else:
                        out[f"{key}[{idx}]"] = item
        else:
            out[key] = v
    return out


def _find_val(flat: dict, keys: set[str], exclude_keys: set[str] | None = None) -> Any:
    """
    Case-insensitive key lookup across a set of candidate keys.
    Exact match is tried before substring match.
    Keys in ``exclude_keys`` are never returned (prevents e.g. 'target'
    matching 'previous_target').
    """
    lk = {k.lower(): v for k, v in flat.items()}
    excluded = {e.lower() for e in (exclude_keys or set())}

    # 1. Exact match
    for candidate in sorted(keys, key=len, reverse=True):  # longest first
        if candidate.lower() in lk and candidate.lower() not in excluded:
            return lk[candidate.lower()]

    # 2. Substring match (skip if the actual key is in exclude set)
    for candidate in sorted(keys, key=len, reverse=True):
        for actual_key in lk:
            if actual_key in excluded:
                continue
            if candidate.lower() == actual_key or candidate.lower() in actual_key.lower():
                return lk[actual_key]
    return None


def _pct_change(old: Any, new: Any) -> float | None:
    try:
        o, n = float(old), float(new)
        if o == 0:
            return None
        return ((n - o) / abs(o)) * 100
    except (TypeError, ValueError):
        return None


def _to_prose(label: str, flat_items: list[dict], received_at: str) -> tuple[str, dict]:
    """Convert flattened JSON items to human-readable prose."""
    detected_date = None
    lines: list[str] = []
    analysts       = 0
    consensus      = "unknown"
    targets: list[float] = []
    prev_targets:  list[float] = []
    ratings: list[str]   = []

    for item in flat_items:
        analyst_name = _find_val(item, ANALYST_KEYS)
        rating       = _find_val(item, RATING_KEYS)
        new_target   = _find_val(item, TARGET_KEYS, exclude_keys=PREV_TARGET_KEYS)
        prev_target  = _find_val(item, PREV_TARGET_KEYS)
        date_val     = _find_val(item, DATE_KEYS)

        if date_val and not detected_date:
            detected_date = _normalise_date(str(date_val))

        # Check if this looks like an analyst record
        if analyst_name or rating or new_target:
            analysts += 1
            entry_parts: list[str] = []

            if analyst_name:
                entry_parts.append(str(analyst_name))
            if rating:
                entry_parts.append(f"Rating: {rating}")
                ratings.append(str(rating).upper())
            if new_target:
                t_float = _safe_float(new_target)
                if t_float is not None:
                    targets.append(t_float)
                if prev_target:
                    p_float = _safe_float(prev_target)
                    if p_float is not None:
                        prev_targets.append(p_float)
                    pct = _pct_change(p_float, t_float)
                    pct_str = f" ({pct:+.1f}%)" if pct is not None else ""
                    entry_parts.append(
                        f"target ${new_target} (was ${prev_target}{pct_str})"
                    )
                else:
                    entry_parts.append(f"target ${new_target}")

            # Add remaining key-value pairs
            known = ANALYST_KEYS | RATING_KEYS | TARGET_KEYS | PREV_TARGET_KEYS | DATE_KEYS
            for k, v in item.items():
                if k.lower() not in known and v not in (None, "", []):
                    entry_parts.append(f"{k}: {v}")

            lines.append(". ".join(entry_parts) + ".")
        else:
            # Generic key-value rendering
            kv = ", ".join(f"{k}={v}" for k, v in item.items() if v not in (None, ""))
            if kv:
                lines.append(kv)

    # Consensus
    neg_ratings = {"sell", "underweight", "underperform", "strong sell", "reduce"}
    pos_ratings = {"buy", "overweight", "outperform", "strong buy", "accumulate"}
    lower_ratings = [r.lower() for r in ratings]
    neg_count = sum(1 for r in lower_ratings if any(n in r for n in neg_ratings))
    pos_count = sum(1 for r in lower_ratings if any(p in r for p in pos_ratings))
    if neg_count > pos_count:
        consensus = "bearish"
    elif pos_count > neg_count:
        consensus = "bullish"
    elif ratings:
        consensus = "neutral"

    # Date header
    date_display = detected_date or received_at[:10]
    header = f"Report from {label} ({date_display}):"
    full_text = header + "\n" + "\n".join(lines)

    # Average target change
    avg_change = None
    if targets and prev_targets and len(targets) == len(prev_targets):
        changes = [_pct_change(p, t) for p, t in zip(prev_targets, targets) if _pct_change(p, t) is not None]
        if changes:
            avg_change = round(sum(changes) / len(changes), 1)

    meta = {
        "analysts"             : analysts,
        "consensus"            : consensus,
        "avg_target_change_pct": avg_change,
        "detected_date"        : detected_date,
    }
    return full_text.strip(), meta


def _compute_credibility(flat_items: list[dict]) -> float:
    """Score based on structural quality of JSON."""
    if not flat_items:
        return 0.60

    has_rating  = any(_find_val(i, RATING_KEYS)  for i in flat_items)
    has_target  = any(_find_val(i, TARGET_KEYS)  for i in flat_items)
    has_date    = any(_find_val(i, DATE_KEYS)    for i in flat_items)
    has_analyst = any(_find_val(i, ANALYST_KEYS) for i in flat_items)

    if has_rating and has_target:
        return 0.88
    if has_date and (has_analyst or has_rating):
        return 0.85
    # Depth heuristic
    avg_keys = sum(len(i) for i in flat_items) / len(flat_items)
    if avg_keys > 10:
        return 0.60  # deeply nested, unclear schema
    return 0.70


def _safe_float(val: Any) -> float | None:
    try:
        return float(str(val).replace("$", "").replace(",", ""))
    except (ValueError, TypeError):
        return None


def _normalise_date(raw: str) -> str | None:
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(raw[:25], fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return None


def _check_stale(date_str: str) -> bool:
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days > STALE_DAYS
    except Exception:
        return False


def _noise_block(label: str, received_at: str, reason: str) -> dict[str, Any]:
    return {
        "source_type": "JSON", "source_label": label, "raw_text": "",
        "timestamp": received_at, "credibility_score": 0.0, "domain": "finance",
        "is_stale": False, "is_noise": True, "noise_reason": reason,
        "word_count": 0, "language": "en", "extraction_method": "json",
        "metadata": {"analysts": 0, "consensus": None, "avg_target_change_pct": None},
    }

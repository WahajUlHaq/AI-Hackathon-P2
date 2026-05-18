"""
Agent 1c — CSV Parser
=====================
Library : Python csv module / pandas (optional)
LLM     : None — pure Python, deterministic
Spec    : stage1_parsers.md § "Agent 1c — CSV Parser"
"""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    _PANDAS_OK = True
except ImportError:
    _PANDAS_OK = False

STALE_DAYS = 7
DATE_HEADERS = re.compile(r"date|week|day|time|period|month|year", re.I)
NUMERIC_HEADERS = re.compile(r"price|close|open|high|low|volume|value|amount|count|num", re.I)


def parse(source: dict[str, Any]) -> dict[str, Any]:
    label       = source.get("label", "Unknown CSV")
    content     = source.get("content", "")
    received_at = source.get("received_at", datetime.now(timezone.utc).isoformat())

    if not content or not content.strip():
        return _noise_block(label, received_at, "empty content")

    rows, headers = _parse_csv(content)
    if not rows:
        return _noise_block(label, received_at, "no rows parsed")

    # Auto-detect column types
    date_cols    = [h for h in headers if DATE_HEADERS.search(h)]
    numeric_cols = [h for h in headers if NUMERIC_HEADERS.search(h) and h not in date_cols]

    # Build time range from date columns
    time_range = None
    if date_cols:
        dates = [r.get(date_cols[0], "") for r in rows if r.get(date_cols[0])]
        if len(dates) >= 2:
            time_range = f"{dates[0]} to {dates[-1]}"

    # Detect trend for first numeric column
    trend_detected = None
    trend_col      = None
    if numeric_cols:
        trend_col    = numeric_cols[0]
        trend_result = _compute_trend(rows, trend_col)
        if trend_result is not None:
            trend_detected = {"column": trend_col, "change_percent": round(trend_result, 1)}

    # Build prose summary
    raw_text = _build_prose(label, headers, rows, date_cols, numeric_cols, time_range, trend_detected)

    # Credibility
    credibility = _compute_credibility(headers, date_cols, numeric_cols, label)

    # Staleness — based on last date in dataset or received_at
    last_date_str = None
    if date_cols and rows:
        last_date_str = rows[-1].get(date_cols[0])
    is_stale = _check_stale(last_date_str or received_at)

    word_count = len(raw_text.split())

    return {
        "source_type"       : "CSV",
        "source_label"      : label,
        "raw_text"          : raw_text,
        "timestamp"         : received_at,
        "credibility_score" : credibility,
        "domain"            : "finance",
        "is_stale"          : is_stale,
        "is_noise"          : False,
        "noise_reason"      : None,
        "word_count"        : word_count,
        "language"          : "en",
        "extraction_method" : "pandas" if _PANDAS_OK else "csv",
        "metadata"          : {
            "rows"          : len(rows),
            "columns"       : headers,
            "time_range"    : time_range,
            "trend_detected": trend_detected,
        },
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_csv(content: str) -> tuple[list[dict], list[str]]:
    """Parse CSV string into list of dicts and header list."""
    try:
        reader  = csv.DictReader(io.StringIO(content.strip()))
        headers = reader.fieldnames or []
        if not headers:
            # Auto-generate column names
            lines   = content.strip().splitlines()
            if not lines:
                return [], []
            col_count = len(next(csv.reader([lines[0]])))
            headers   = [f"col_{i+1}" for i in range(col_count)]
            reader    = csv.DictReader(io.StringIO(content.strip()), fieldnames=headers)
        rows = list(reader)
        return rows, list(headers)
    except Exception as exc:
        logger.error("CSV parse failed: %s", exc)
        return [], []


def _to_float(val: str) -> float | None:
    """Convert a string like '$162.00' or '8.2M' to float."""
    if not val:
        return None
    val = val.strip().replace(",", "").replace("$", "").replace("%", "")
    multipliers = {"k": 1e3, "m": 1e6, "b": 1e9}
    if val and val[-1].lower() in multipliers:
        try:
            return float(val[:-1]) * multipliers[val[-1].lower()]
        except ValueError:
            pass
    try:
        return float(val)
    except ValueError:
        return None


def _compute_trend(rows: list[dict], col: str) -> float | None:
    """Return % change from first to last non-null numeric value."""
    values = [_to_float(r.get(col, "")) for r in rows]
    values = [v for v in values if v is not None]
    if len(values) < 2:
        return None
    first, last = values[0], values[-1]
    if first == 0:
        return None
    return ((last - first) / abs(first)) * 100


def _build_prose(
    label: str,
    headers: list[str],
    rows: list[dict],
    date_cols: list[str],
    numeric_cols: list[str],
    time_range: str | None,
    trend_detected: dict | None,
) -> str:
    lines: list[str] = []

    header_line = f"Data source: {label}."
    if time_range:
        header_line += f" Period: {time_range}."
    lines.append(header_line)

    # Column header
    lines.append("  " + " | ".join(headers))

    # Data rows
    for r in rows:
        row_parts = [str(r.get(h, "")) if r.get(h, "") is not None else "" for h in headers]
        lines.append("  " + " | ".join(row_parts))

    # Trend summary
    if trend_detected:
        col    = trend_detected["column"]
        change = trend_detected["change_percent"]
        direction = "rose" if change > 0 else "fell"
        lines.append(f"Trend: {col} {direction} {abs(change):.1f}% over {len(rows)} rows.")

    # Volume / secondary numeric trend
    secondary = [c for c in numeric_cols if trend_detected and c != trend_detected.get("column")]
    for col in secondary[:1]:
        t = _compute_trend(rows, col)
        if t is not None:
            direction = "increased" if t > 0 else "decreased"
            lines.append(f"{col} {direction} {abs(t):.1f}%.")

    return "\n".join(lines)


def _compute_credibility(
    headers: list[str], date_cols: list[str], numeric_cols: list[str], label: str
) -> float:
    lower = label.lower()
    if any(kw in lower for kw in ["dashboard", "export", "bloomberg", "refinitiv"]):
        return 0.85
    if date_cols and numeric_cols:
        return 0.80
    if not date_cols:
        return 0.60
    return 0.65


def _check_stale(date_str: str) -> bool:
    if not date_str:
        return False
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(date_str[:19], fmt[:len(date_str)])
            dt = dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).days > STALE_DAYS
        except ValueError:
            continue
    return False


def _noise_block(label: str, received_at: str, reason: str) -> dict[str, Any]:
    return {
        "source_type": "CSV", "source_label": label, "raw_text": "",
        "timestamp": received_at, "credibility_score": 0.0, "domain": "finance",
        "is_stale": False, "is_noise": True, "noise_reason": reason,
        "word_count": 0, "language": "en", "extraction_method": "csv",
        "metadata": {"rows": 0, "columns": [], "time_range": None, "trend_detected": None},
    }

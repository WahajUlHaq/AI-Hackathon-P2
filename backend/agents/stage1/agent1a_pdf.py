"""
Agent 1a — PDF Parser
=====================
Library  : pdfplumber (primary), PyPDF2 (fallback)
LLM      : ❌ None — pure Python, deterministic
Spec     : stage1_parsers.md § "Agent 1a — PDF Parser"
"""

from __future__ import annotations

import base64
import io
import re
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional imports — graceful degradation if libs are missing
# ---------------------------------------------------------------------------
try:
    import pdfplumber
    _PDFPLUMBER_OK = True
except ImportError:
    _PDFPLUMBER_OK = False
    logger.warning("pdfplumber not installed — will use PyPDF2 only")

try:
    import PyPDF2
    _PYPDF2_OK = True
except ImportError:
    _PYPDF2_OK = False
    logger.warning("PyPDF2 not installed — PDF parsing may fail")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DATE_PATTERN = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},?\s+\d{4}\b"
    r"|"
    r"\b\d{4}[-/]\d{2}[-/]\d{2}\b"
)

CREDIBILITY_SIGNALS = {
    "official": 0.60,
    "press release": 0.60,
    "board": 0.60,
    "academic": 0.75,
    "cited": 0.75,
    "references": 0.75,
    "leaked": 0.40,
    "unverified": 0.40,
    "internal memo": 0.45,
}

STALE_DAYS = 7


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(source: dict[str, Any]) -> dict[str, Any]:
    """
    Parse a PDF source and return a ContentBlock (without the 'id' field —
    the runner assigns IDs after collecting all results).

    Parameters
    ----------
    source : dict
        {
            "label"      : str   — human name of source
            "type"       : "PDF"
            "content"    : str   — file path OR base64-encoded PDF bytes
            "received_at": str   — ISO-8601 datetime string
        }

    Returns
    -------
    dict  — ContentBlock (id omitted, set by runner)
    """
    label       = source.get("label", "Unknown PDF")
    content     = source.get("content", "")
    received_at = source.get("received_at", datetime.now(timezone.utc).isoformat())

    raw_text       = ""
    pages          = 0
    author         = None
    has_tables     = False
    detected_date  = None
    fallback_used  = False
    is_noise       = False
    noise_reason   = None

    # ── Step 1: Resolve content to bytes ────────────────────────────────────
    try:
        pdf_bytes = _resolve_bytes(content)
        # ── Step 2: Extract text ─────────────────────────────────────────────────
        if _PDFPLUMBER_OK:
            raw_text, pages, has_tables, fallback_used = _extract_pdfplumber(pdf_bytes)

        if not raw_text and _PYPDF2_OK:
            raw_text, pages = _extract_pypdf2(pdf_bytes)
            fallback_used = True
    except Exception as exc:
        logger.warning("PDF byte resolution failed: %s. Using raw content as text.", exc)
        raw_text = content
        pages = 1

    if not raw_text:
        return _noise_block(label, received_at, "no text could be extracted")

    # ── Step 3: Check for password protection ────────────────────────────────
    if _is_password_protected(raw_text):
        return _noise_block(label, received_at, "password protected")

    # ── Step 4: Clean text ───────────────────────────────────────────────────
    raw_text = _clean_text(raw_text)

    # ── Step 5: Detect document date ─────────────────────────────────────────
    detected_date = _detect_date(raw_text)

    # ── Step 6: Detect author ────────────────────────────────────────────────
    author = _detect_author(raw_text)

    # ── Step 7: Staleness check ──────────────────────────────────────────────
    doc_date   = detected_date or received_at[:10]
    is_stale   = _check_stale(doc_date)

    # ── Step 8: Credibility ──────────────────────────────────────────────────
    credibility = _compute_credibility(raw_text.lower())

    word_count = len(raw_text.split())

    timestamp = detected_date + "T00:00:00Z" if detected_date else received_at

    return {
        "source_type"       : "PDF",
        "source_label"      : label,
        "raw_text"          : raw_text,
        "timestamp"         : timestamp,
        "credibility_score" : credibility,
        "domain"            : "news",
        "is_stale"          : is_stale,
        "is_noise"          : is_noise,
        "noise_reason"      : noise_reason,
        "word_count"        : word_count,
        "language"          : "en",
        "extraction_method" : "PyPDF2" if fallback_used else "pdfplumber",
        "metadata"          : {
            "pages"         : pages,
            "author"        : author,
            "has_tables"    : has_tables,
            "detected_date" : detected_date,
            "fallback_used" : fallback_used,
            "stale_reason"  : None,
        },
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _resolve_bytes(content: str) -> bytes:
    """Return raw PDF bytes from a file path or base64 string."""
    if not content:
        raise ValueError("empty content")

    # Try as file path first
    try:
        with open(content, "rb") as fh:
            return fh.read()
    except (OSError, FileNotFoundError):
        pass

    # Try base64 decode
    try:
        # Strip data-URI prefix if present
        if "," in content:
            content = content.split(",", 1)[1]
        return base64.b64decode(content)
    except Exception:
        raise ValueError("content is neither a valid file path nor valid base64")


def _extract_pdfplumber(pdf_bytes: bytes) -> tuple[str, int, bool, bool]:
    """Return (raw_text, page_count, has_tables, fallback_used=False)."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages      = len(pdf.pages)
            texts      = []
            has_tables = False
            for page in pdf.pages:
                text = page.extract_text() or ""
                texts.append(text)
                if page.extract_tables():
                    has_tables = True
            return "\n".join(texts), pages, has_tables, False
    except Exception as exc:
        logger.warning("pdfplumber failed (%s) — will try PyPDF2", exc)
        return "", 0, False, True


def _extract_pypdf2(pdf_bytes: bytes) -> tuple[str, int]:
    """Return (raw_text, page_count) using PyPDF2."""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        pages  = len(reader.pages)
        texts  = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(texts), pages
    except Exception as exc:
        logger.error("PyPDF2 failed: %s", exc)
        return "", 0


def _is_password_protected(text: str) -> bool:
    """Heuristic: if extraction returned an encrypted-marker string."""
    markers = ["PdfReadError", "password", "encrypted", "PyCryptodome"]
    low = text.lower()
    return any(m.lower() in low for m in markers) and len(text) < 50


def _clean_text(text: str) -> str:
    """Strip excessive whitespace and common header/footer noise."""
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)
    # Strip leading/trailing whitespace per line
    lines = [line.strip() for line in text.splitlines()]
    # Remove very short lines that are typically page numbers / headers
    lines = [l for l in lines if not re.fullmatch(r"\d{1,4}", l)]
    return "\n".join(lines).strip()


def _detect_date(text: str) -> str | None:
    """Return first date found in text as YYYY-MM-DD, or None."""
    months = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
    }
    m = DATE_PATTERN.search(text)
    if not m:
        return None
    raw = m.group(0)
    # Already numeric YYYY-MM-DD / YYYY/MM/DD
    numeric = re.fullmatch(r"(\d{4})[-/](\d{2})[-/](\d{2})", raw)
    if numeric:
        return f"{numeric.group(1)}-{numeric.group(2)}-{numeric.group(3)}"
    # Spelled-out month
    parts  = raw.replace(",", "").split()
    month  = months.get(parts[0].lower(), "01")
    day    = parts[1].zfill(2)
    year   = parts[2]
    return f"{year}-{month}-{day}"


def _detect_author(text: str) -> str | None:
    """Very simple heuristic: look for 'From:' / 'Author:' / 'By ' lines."""
    for line in text.splitlines():
        stripped = line.strip()
        for prefix in ("From:", "Author:", "By ", "Authored by"):
            if stripped.startswith(prefix):
                candidate = stripped[len(prefix):].strip()
                if 2 < len(candidate) < 60:
                    return candidate
    return None


def _compute_credibility(lower_text: str) -> float:
    for signal, score in CREDIBILITY_SIGNALS.items():
        if signal in lower_text:
            return score
    return 0.50


def _check_stale(date_str: str) -> bool:
    try:
        doc_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        today    = datetime.now(timezone.utc).date()
        return (today - doc_date).days > STALE_DAYS
    except Exception:
        return False


def _noise_block(label: str, received_at: str, reason: str) -> dict[str, Any]:
    return {
        "source_type"       : "PDF",
        "source_label"      : label,
        "raw_text"          : "",
        "timestamp"         : received_at,
        "credibility_score" : 0.0,
        "domain"            : "news",
        "is_stale"          : False,
        "is_noise"          : True,
        "noise_reason"      : reason,
        "word_count"        : 0,
        "language"          : "en",
        "extraction_method" : "none",
        "metadata"          : {
            "pages"         : 0,
            "author"        : None,
            "has_tables"    : False,
            "detected_date" : None,
            "fallback_used" : False,
            "stale_reason"  : None,
        },
    }

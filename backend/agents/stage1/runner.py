"""
Stage 1 Runner
==============
Dispatches sources to the 5 parser agents in parallel using ThreadPoolExecutor.
Spec: stage1_parsers.md § "Stage 1 Runner" and "Parallel Execution Flow"
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from agents.stage1 import agent1a_pdf, agent1b_url, agent1c_csv, agent1d_json, agent1e_feed

logger = logging.getLogger(__name__)

# Map source type strings -> parser modules
_PARSER_MAP = {
    "PDF"      : agent1a_pdf,
    "URL"      : agent1b_url,
    "CSV"      : agent1c_csv,
    "JSON"     : agent1d_json,
    "FEED"     : agent1e_feed,
    "MOCKFEED" : agent1e_feed,
}

_LABEL_MAP = {
    "PDF"      : "1a-PDF ",
    "URL"      : "1b-URL ",
    "CSV"      : "1c-CSV ",
    "JSON"     : "1d-JSON",
    "FEED"     : "1e-Feed",
    "MOCKFEED" : "1e-Feed",
}

MAX_WORKERS = 5


def run(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Run all 5 parser agents in parallel and return unified content_blocks.

    Parameters
    ----------
    sources : list[dict]
        Each dict: { "label": str, "type": str, "content": str, "received_at": str }

    Returns
    -------
    dict
        {
            "content_blocks"   : list[ContentBlock],
            "ingestion_summary": dict
        }
    """
    if not sources:
        return {
            "content_blocks"   : [],
            "ingestion_summary": _empty_summary(),
        }

    print(f"\n[Stage 1] Starting {len(sources)} parallel parser(s)...")
    start_ms = time.time()

    # ── Submit all sources to thread pool ────────────────────────────────────
    seen_urls: set[str] = set()   # duplicate URL detection
    futures: dict[Any, dict] = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for source in sources:
            src_type = source.get("type", "").upper()
            parser   = _PARSER_MAP.get(src_type, agent1e_feed)  # default: MockFeed

            # Duplicate URL detection (before dispatching)
            if src_type == "URL":
                url = source.get("content", "").strip()
                if url in seen_urls:
                    # Submit a synthetic noise result
                    future = executor.submit(_already_duplicate, source)
                    futures[future] = source
                    continue
                seen_urls.add(url)

            future = executor.submit(parser.parse, source)
            futures[future] = source

        # ── Collect results ──────────────────────────────────────────────────
        raw_results: list[dict] = []
        for future in as_completed(futures):
            source = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                logger.error(
                    "Parser crashed for source '%s': %s",
                    source.get("label"), exc, exc_info=True,
                )
                result = _error_noise_block(source, str(exc))
            raw_results.append(result)

    elapsed_ms = int((time.time() - start_ms) * 1000)

    # ── Sort by received_at / timestamp ──────────────────────────────────────
    raw_results.sort(key=lambda b: b.get("timestamp", ""))

    # ── Assign IDs cb_001 … cb_N ────────────────────────────────────────────
    content_blocks: list[dict] = []
    for idx, block in enumerate(raw_results, start=1):
        block["id"] = f"cb_{idx:03d}"
        content_blocks.append(block)

    # ── Build ingestion summary ───────────────────────────────────────────────
    noise_filtered = sum(1 for b in content_blocks if b.get("is_noise"))
    stale_flagged  = sum(1 for b in content_blocks if b.get("is_stale"))
    domains        = sorted({b.get("domain", "unknown") for b in content_blocks if not b.get("is_noise")})
    types_used     = sorted({b.get("source_type", "?") for b in content_blocks})

    ingestion_summary = {
        "total_sources"       : len(sources),
        "noise_filtered"      : noise_filtered,
        "stale_flagged"       : stale_flagged,
        "domains_detected"    : domains,
        "source_types_used"   : types_used,
        "parallel_execution_ms": elapsed_ms,
    }

    # ── Console output ────────────────────────────────────────────────────────
    _print_summary(content_blocks, ingestion_summary)

    return {
        "content_blocks"   : content_blocks,
        "ingestion_summary": ingestion_summary,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _print_summary(blocks: list[dict], summary: dict) -> None:
    for block in blocks:
        src_type  = block.get("source_type", "?").upper()
        tag       = _LABEL_MAP.get(src_type, src_type[:6].ljust(6))
        label     = block.get("source_label", "?")[:35]
        is_noise  = block.get("is_noise", False)

        if is_noise:
            reason = block.get("noise_reason", "noise")
            print(f"  [{tag}] {label:<35} -> NOISE ({reason})")
            continue

        wc          = block.get("word_count", 0)
        credibility = block.get("credibility_score", 0)
        meta        = block.get("metadata", {})

        # Type-specific detail
        detail = f"{wc} words, credibility={credibility:.2f}"
        if src_type == "CSV" and meta.get("trend_detected"):
            td  = meta["trend_detected"]
            pct = td.get("change_percent", 0)
            detail = f"{meta.get('rows', '?')} rows, trend={pct:+.1f}%"
        elif src_type == "JSON" and meta.get("analysts"):
            detail = f"{meta['analysts']} analyst(s), consensus={meta.get('consensus', '?')}"
        elif src_type == "MOCKFEED":
            detail = (
                f"{meta.get('post_count', 0)} posts, "
                f"sentiment={meta.get('sentiment_score', 0):.2f}"
            )

        print(f"  [{tag}] {label:<35} -> {detail}")

    noise  = summary["noise_filtered"]
    stale  = summary["stale_flagged"]
    total  = summary["total_sources"]
    ms     = summary["parallel_execution_ms"]
    good   = total - noise
    print(
        f"[Stage 1] Done — {good} block(s) ready, "
        f"{noise} noise, {stale} stale ({ms}ms parallel)\n"
    )


def _already_duplicate(source: dict[str, Any]) -> dict[str, Any]:
    """Return a noise block for a URL submitted twice."""
    return {
        "source_type"       : "URL",
        "source_label"      : source.get("label", "?"),
        "raw_text"          : "",
        "timestamp"         : source.get("received_at", datetime.now(timezone.utc).isoformat()),
        "credibility_score" : 0.0,
        "domain"            : "news",
        "is_stale"          : False,
        "is_noise"          : True,
        "noise_reason"      : "duplicate",
        "word_count"        : 0,
        "language"          : "en",
        "extraction_method" : "none",
        "metadata"          : {},
    }


def _error_noise_block(source: dict[str, Any], error: str) -> dict[str, Any]:
    return {
        "source_type"       : source.get("type", "?"),
        "source_label"      : source.get("label", "?"),
        "raw_text"          : "",
        "timestamp"         : source.get("received_at", datetime.now(timezone.utc).isoformat()),
        "credibility_score" : 0.0,
        "domain"            : "unknown",
        "is_stale"          : False,
        "is_noise"          : True,
        "noise_reason"      : f"parser exception: {error}",
        "word_count"        : 0,
        "language"          : "en",
        "extraction_method" : "none",
        "metadata"          : {},
    }


def _empty_summary() -> dict[str, Any]:
    return {
        "total_sources"        : 0,
        "noise_filtered"       : 0,
        "stale_flagged"        : 0,
        "domains_detected"     : [],
        "source_types_used"    : [],
        "parallel_execution_ms": 0,
    }

# Stage 1 — Reasoning & Decisions Trace
**Module**: `agents/stage1/`
**Version**: 1.0.0
**Created**: 2026-05-16T04:00:00+05:00

---

## Overview

This file captures the **design reasoning** and **architectural decisions** made during
the implementation of the Stage 1 parser agents — the "why" behind every non-trivial choice.

---

## RD-01 · Why No LLM in Stage 1?

**Decision**: Zero LLM calls in all Stage 1 parsers.

**Reasoning**:
- Stage 1 is a purely mechanical ingestion layer. Its job is to **extract and normalize**,
  not to **understand or interpret**. Adding an LLM would introduce:
  - Latency: each LLM call adds 500ms–3s per source
  - Cost: 5 sources × LLM call = significant token usage per pipeline run
  - Non-determinism: same source could produce different extracted text
- Deterministic Python is faster, cheaper, and easier to test and debug.
- LLM understanding is deferred to Stage 2 (Flag Agent) which receives the normalized
  `ContentBlock[]` pool.

---

## RD-02 · Why `ThreadPoolExecutor` Instead of `asyncio`?

**Decision**: Use `concurrent.futures.ThreadPoolExecutor` for parallelism.

**Reasoning**:
- All 5 parser libraries (`pdfplumber`, `requests`, `csv`, `json`) are **synchronous and
  blocking**. They do not provide `async` interfaces.
- `asyncio` would require wrapping every blocking call in `loop.run_in_executor()`, adding
  complexity with no benefit.
- `ThreadPoolExecutor` releases the GIL for I/O-bound operations (network, file reads),
  meaning URL scraping (the bottleneck at ~1500ms) runs concurrently with the other 4 parsers.
- Result: wall time ≈ max(individual times) ≈ 1159ms instead of sum ≈ 1800ms.

---

## RD-03 · Why Noise Blocks Instead of Exceptions?

**Decision**: All parser failures return a structured noise ContentBlock rather than raising
an exception.

**Reasoning**:
- The runner collects results from `as_completed()`. If an agent raises, the runner catches
  it and wraps it in an error noise block anyway — so consistency is better achieved by
  having agents themselves return noise blocks.
- Downstream (Stage 2+) consumers can skip noise blocks by filtering `is_noise=True`.
- A crashed thread would silently reduce the result count — noise blocks make failures
  **visible and auditable** in the ingestion summary.
- `noise_reason` field provides human-readable explanation for every failure mode.

---

## RD-04 · Why Primary + Fallback Library Pattern?

**Decision**: Every agent that can fail (PDF, URL) has a primary library and a
deterministic fallback.

**Reasoning**:
- `pdfplumber` is best for structured PDFs with text layers, but fails on password-protected,
  scanned, or corrupted PDFs.
- `PyPDF2` has broader format tolerance but produces lower-quality text (no table awareness).
- Better to degrade gracefully to partial output than to fail entirely.
- Same logic for URL: BeautifulSoup gives more control over extraction logic, but
  `newspaper3k` is tuned specifically for news article extraction and handles
  complex modern layouts more reliably.

---

## RD-05 · Why Return `id` from Runner, Not from Agents?

**Decision**: The `id` field (`cb_001`…`cb_N`) is assigned by the runner **after** all
results are collected and sorted, not by individual agents.

**Reasoning**:
- Agents run concurrently. If they self-assigned IDs, there would be a race condition.
- IDs must be sequential and contiguous in final sort order (by `timestamp`/`received_at`).
- The runner is the only component with a global view of all results simultaneously.

---

## RD-06 · Why Sort by `timestamp` (received_at)?

**Decision**: Sort content blocks by `timestamp` before ID assignment.

**Reasoning**:
- `cb_001` should be the oldest source (earliest received_at) for intuitive chronological ordering.
- Downstream agents in Stage 2+ can process blocks in natural time order.
- The detected date inside the document (e.g., PDF authorship date) is used as `timestamp`
  when available; otherwise `received_at` is used as the fallback.

---

## RD-07 · Why Convert CSV/JSON to Prose?

**Decision**: CSV and JSON content is converted to human-readable prose rather than
forwarded as structured data.

**Reasoning**:
- Stage 2 onwards uses LLM agents that consume `raw_text`.
- LLMs process natural language more reliably than raw tabular/JSON data.
- Prose summaries pre-compute the key insight (e.g., "Close_Price fell 17.9%") so the LLM
  doesn't need to re-derive it.
- This is a deliberate **schema-boundary decision**: structured data → prose at Stage 1;
  prose → structured intelligence at Stage 3+.

---

## RD-08 · Credibility Score Design Philosophy

**Decision**: Use rule-based credibility scoring per agent, not a single global scorer.

**Reasoning**:
- Different source types have fundamentally different trust signals:
  - A PDF's credibility depends on its keyword content (official, leaked, academic).
  - A URL's credibility depends on its domain reputation.
  - A CSV's credibility depends on its structural completeness.
  - A JSON's credibility depends on semantic richness (has rating? has target?).
  - A Feed's credibility is inherently lower (social, unverified).
- A global scorer would lose these type-specific nuances.
- Scores are floats in [0.0, 1.0] for easy downstream comparison and filtering.

---

## RD-09 · Why `exclude_keys` in `_find_val`?

**Decision**: Added `exclude_keys: set[str] | None` parameter to the JSON agent's
`_find_val` helper.

**Reasoning**:
- Initial implementation used substring matching: if `"target"` is in `TARGET_KEYS`,
  it would match any key containing `"target"` — including `"previous_target"`.
- This caused `new_target` and `prev_target` to resolve to the same key, showing
  `+0.0%` change for all analysts.
- Fix: `_find_val(item, TARGET_KEYS, exclude_keys=PREV_TARGET_KEYS)` tells the function
  to skip any key that is in the exclusion set, regardless of substring match.
- Exact match is also tried before substring match (sorted by length, longest first)
  to prefer more specific key names.
- See `error_recovery.md` for the full bug/fix narrative.

---

## RD-10 · Why Hardcode Domain Values per Agent?

**Decision**: Each agent hardcodes `domain` to a specific value (PDF/URL=`"news"`,
CSV/JSON=`"finance"`, Feed=`"social"`).

**Reasoning**:
- Stage 1 parsers don't use LLMs and can't semantically classify domain from content.
- The spec explicitly defines expected domain values per source type.
- Domain is a coarse category used by downstream agents for filtering (e.g., Stage 2 Flag
  Agent may apply different thresholds for finance vs. social domains).
- A more sophisticated domain classifier would belong in Stage 2+, not Stage 1.

---

## RD-11 · Why `STALE_DAYS = 7` and Where Is It Defined?

**Decision**: Each agent defines its own `STALE_DAYS = 7` constant locally.

**Reasoning**:
- The spec defines 7 days as the staleness threshold uniformly.
- Defined locally (not in a shared config) to keep each agent self-contained and
  independently importable without shared state.
- In production, this would be moved to a shared `config.py` or environment variable
  to allow per-source-type tuning.

---

## RD-12 · Why Monkey-Patch PDF in Demo?

**Decision**: `demo_stage1.py` replaces `agent1a_pdf.parse` with a demo function that
injects sample text directly, bypassing file/base64 loading.

**Reasoning**:
- The demo should run without requiring a real PDF file on disk.
- The monkey-patch calls all the same helper functions (`_compute_credibility`,
  `_detect_date`, `_check_stale`) to validate real logic, only skipping the
  `_resolve_bytes` step.
- In production, callers pass a real file path or base64-encoded PDF bytes.
- This keeps the demo self-contained while proving the agent logic is correct.

---

## RD-13 · Why `max_workers=5` Specifically?

**Decision**: `ThreadPoolExecutor(max_workers=5)`.

**Reasoning**:
- There are exactly 5 parser types. Setting `max_workers=5` guarantees all 5 can run
  simultaneously with no queueing.
- A lower value (e.g., 3) would serialize some parsers, defeating the parallelism goal.
- A higher value provides no benefit for 5 sources but wastes thread overhead.
- For batches with N > 5 sources of the same type, the executor naturally queues them.

---

## RD-14 · Duplicate URL Detection Strategy

**Decision**: Duplicates are detected via `seen_urls: set[str]` in the runner **before**
submitting to the thread pool.

**Reasoning**:
- Detecting duplicates post-parse would waste the network round-trip.
- The set is maintained in the runner (single thread) so there is no race condition.
- Only URL-type sources are deduplicated this way; other types (PDF, CSV, JSON, Feed)
  are assumed to be uniquely identified by their label in the demo context.
- In production, a content-hash-based deduplication would be added for all types.

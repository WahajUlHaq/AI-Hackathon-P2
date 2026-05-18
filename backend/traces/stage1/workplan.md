# Stage 1 — Workplan Trace
**Module**: `agents/stage1/`
**Version**: 1.0.0
**Created**: 2026-05-16T04:00:00+05:00
**Status**: ✅ Complete

---

## 1. Mission Statement

Design and implement five deterministic, LLM-free parser agents that ingest raw, heterogeneous sources (PDF, URL, CSV, JSON, Feed) in **parallel**, normalize them into a unified `ContentBlock` schema, and feed the result pool to Stage 2 (Flag Agent).

---

## 2. Scope

| In Scope | Out of Scope |
|---|---|
| PDF text extraction (pdfplumber + PyPDF2 fallback) | LLM-based content understanding |
| URL scraping (BS4 + newspaper3k fallback) | Authentication / login-gated pages |
| CSV tabular-to-prose conversion | Binary file types other than PDF |
| JSON flattening and semantic field detection | Database connectors |
| Social/news feed sentiment and topic analysis | Real-time streaming ingestion |
| Parallel execution via ThreadPoolExecutor | Distributed / multi-machine execution |
| Unified ContentBlock schema output | Schema version migration |
| Edge case handling (noise, stale, duplicates) | ML-based deduplication |

---

## 3. Milestones

```
Phase 0 — Spec Analysis                [2026-05-15 14:00]  ✅
Phase 1 — Schema Design                [2026-05-15 15:00]  ✅
Phase 2 — Agent Implementation         [2026-05-15 16:00]  ✅
  └─ 2a  agent1a_pdf.py
  └─ 2b  agent1b_url.py
  └─ 2c  agent1c_csv.py
  └─ 2d  agent1d_json.py
  └─ 2e  agent1e_feed.py
Phase 3 — Runner Implementation        [2026-05-15 17:00]  ✅
Phase 4 — Demo Script                  [2026-05-15 18:00]  ✅
Phase 5 — Bug Fix (JSON target lookup) [2026-05-15 19:00]  ✅
Phase 6 — Trace Documentation          [2026-05-16 04:00]  ✅
```

---

## 4. File Delivery Map

| Deliverable | Path | Lines | Status |
|---|---|---|---|
| PDF Agent | `agents/stage1/agent1a_pdf.py` | ~270 | ✅ |
| URL Agent | `agents/stage1/agent1b_url.py` | ~230 | ✅ |
| CSV Agent | `agents/stage1/agent1c_csv.py` | ~200 | ✅ |
| JSON Agent | `agents/stage1/agent1d_json.py` | ~290 | ✅ |
| Feed Agent | `agents/stage1/agent1e_feed.py` | ~220 | ✅ |
| Runner | `agents/stage1/runner.py` | ~200 | ✅ |
| Demo | `demo_stage1.py` | ~165 | ✅ |
| Package Inits | `agents/__init__.py`, `agents/stage1/__init__.py` | 2 | ✅ |

---

## 5. Dependency Matrix

```
demo_stage1.py
    └── agents/stage1/runner.py
            ├── agents/stage1/agent1a_pdf.py
            │       └── pdfplumber (primary)
            │       └── PyPDF2     (fallback)
            ├── agents/stage1/agent1b_url.py
            │       └── requests
            │       └── beautifulsoup4 (primary)
            │       └── newspaper3k    (fallback)
            ├── agents/stage1/agent1c_csv.py
            │       └── csv (stdlib)
            │       └── pandas (optional)
            ├── agents/stage1/agent1d_json.py
            │       └── json (stdlib)
            └── agents/stage1/agent1e_feed.py
                    └── json (stdlib)
                    └── re   (stdlib)
```

---

## 6. Non-Functional Requirements

| Requirement | Target | Achieved |
|---|---|---|
| Parallel execution overhead | < 100ms | ~50ms |
| URL scrape timeout | 15 sec max | ✅ enforced |
| Noise auto-detection | All listed edge cases | ✅ 8 cases |
| No LLM dependency | Zero LLM calls in Stage 1 | ✅ |
| Graceful degradation | Missing libs → noise block, no crash | ✅ |
| Output schema parity | 100% field coverage vs spec | ✅ |

---

## 7. Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| `pdfplumber` fails on scanned PDFs | Medium | Medium | PyPDF2 fallback; noise if both fail |
| URL behind paywall / bot-detect | High | Low | Noise block with reason |
| CSV has no headers | Medium | Low | Auto-generate `col_1…col_N` |
| JSON malformed | Low | Low | Catch `JSONDecodeError`, treat as plain text |
| Windows console encoding (cp1252) | High (Windows) | Low | Replaced Unicode arrows with ASCII `->` |
| `target` key matching `previous_target` | Confirmed | High | Fixed with `exclude_keys` guard in `_find_val` |

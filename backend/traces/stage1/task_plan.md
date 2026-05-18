# Stage 1 — Task Plan Trace
**Module**: `agents/stage1/`
**Version**: 1.0.0
**Created**: 2026-05-16T04:00:00+05:00

---

## Task Breakdown (Atomic Units)

Each task is annotated with: `ID | Owner | Priority | Status | Depends On`

---

### T-01 · Spec Analysis
**Priority**: P0 | **Status**: ✅ Done | **Depends On**: —

- Read `stage1_parsers.md` in full (477 lines)
- Extract: 5 agent definitions, ContentBlock schema, credibility tables, staleness rules, noise rules, edge cases, console output format
- Cross-reference runner behaviour (ThreadPoolExecutor, ID assignment, ingestion summary)
- Identify library requirements: `pdfplumber`, `PyPDF2`, `requests`, `beautifulsoup4`, `newspaper3k`, `pandas`

**Acceptance Criteria**:
- [ ] All 10 ContentBlock fields understood
- [ ] All 5 agent credibility tables noted
- [ ] All 8 edge cases identified
- [ ] Runner execution flow mapped

---

### T-02 · Dependency Installation
**Priority**: P0 | **Status**: ✅ Done | **Depends On**: T-01

```
pip install pdfplumber PyPDF2 requests beautifulsoup4 newspaper3k lxml pandas --quiet
```

- Used `--quiet` to suppress verbose output
- `lxml` added as optional HTML parser (faster than `html.parser` for BS4)
- All libs installed with exit code 0

---

### T-03 · Package Scaffolding
**Priority**: P0 | **Status**: ✅ Done | **Depends On**: T-02

- Created `agents/__init__.py`
- Created `agents/stage1/__init__.py`
- Both contain minimal package declaration header

---

### T-04 · Agent 1a — PDF Parser (`agent1a_pdf.py`)
**Priority**: P1 | **Status**: ✅ Done | **Depends On**: T-03

Sub-tasks:
- [x] `_resolve_bytes(content)` — try file path first, then base64 decode
- [x] `_extract_pdfplumber(pdf_bytes)` — page text + table detection
- [x] `_extract_pypdf2(pdf_bytes)` — fallback extraction
- [x] `_is_password_protected(text)` — heuristic on error strings
- [x] `_clean_text(text)` — strip whitespace, page numbers
- [x] `_detect_date(text)` — regex for spelled-out and numeric dates
- [x] `_detect_author(text)` — heuristic on "From:", "Author:", "By "
- [x] `_compute_credibility(lower_text)` — keyword signal table
- [x] `_check_stale(date_str)` — 7-day threshold
- [x] `parse(source)` — top-level orchestrator returning ContentBlock

**Key Design Decisions**:
- Base64 content tried after file path (supports both demo + production modes)
- Date regex covers both `"May 12, 2026"` and `"2026-05-12"` formats
- Noise block returned (not exception raised) on any failure

---

### T-05 · Agent 1b — URL Scraper (`agent1b_url.py`)
**Priority**: P1 | **Status**: ✅ Done | **Depends On**: T-03

Sub-tasks:
- [x] `_extract_domain(url)` — strips `www.` prefix
- [x] HTTP GET with realistic User-Agent, 15s timeout
- [x] `_extract_bs4(html)` — remove noise tags, extract `<article>/<main>/<body>`, parse meta for date/author
- [x] `_extract_newspaper(url)` — newspaper3k fallback
- [x] `_is_paywall(text, html)` — keyword count ≥ 2
- [x] `_get_credibility(domain)` — domain-map lookup + blog heuristic
- [x] `_normalise_date(raw)` — multiple format attempts
- [x] `_check_stale(date_str)` — 7-day threshold
- [x] `parse(source)` — orchestrator with fallback chaining

**Key Design Decisions**:
- BeautifulSoup tries `lxml` parser first (faster), falls back to `html.parser`
- newspaper3k re-fetches URL independently (not reuse of response) to get clean article parse
- Word count checked post-extraction before and after fallback to pick best result

---

### T-06 · Agent 1c — CSV Parser (`agent1c_csv.py`)
**Priority**: P1 | **Status**: ✅ Done | **Depends On**: T-03

Sub-tasks:
- [x] `_parse_csv(content)` — csv.DictReader with auto-header generation on failure
- [x] Column type detection via regex patterns for DATE_HEADERS and NUMERIC_HEADERS
- [x] `_to_float(val)` — handles `$`, `,`, `%`, `K`/`M`/`B` suffixes
- [x] `_compute_trend(rows, col)` — % change first→last non-null value
- [x] `_build_prose(...)` — human-readable summary with trend sentences
- [x] `_compute_credibility(...)` — based on header quality and label signals
- [x] `parse(source)` — orchestrator

**Key Design Decisions**:
- Prose format chosen over raw data to make CSV content consumable by downstream LLM agents in Stage 2+
- Trend computed on first numeric column; secondary columns shown as supplementary lines
- Domain hardcoded to `"finance"` as per spec

---

### T-07 · Agent 1d — JSON Parser (`agent1d_json.py`)
**Priority**: P1 | **Status**: ✅ Done | **Depends On**: T-03

Sub-tasks:
- [x] `_flatten(obj)` — recursive dot-notation flattening, list unrolling
- [x] `_find_val(flat, keys, exclude_keys)` — exact-then-substring lookup with exclusion guard
- [x] `_to_prose(label, flat_items, received_at)` — analyst record detection, consensus computation
- [x] `_pct_change(old, new)` — safe float division
- [x] `_compute_credibility(flat_items)` — structural quality scoring
- [x] `_normalise_date(raw)` — multi-format ISO parsing
- [x] `parse(source)` — list and dict root handling, JSONDecodeError fallback

**Key Design Decisions**:
- `exclude_keys` parameter added to `_find_val` after bug where `"target"` (in `TARGET_KEYS`) matched `"previous_target"` via substring — see `error_recovery.md`
- Consensus computed from rating strings using positive/negative keyword sets
- `JSONDecodeError` → treat as plain text, not noise (content may still be useful)

---

### T-08 · Agent 1e — Feed Parser (`agent1e_feed.py`)
**Priority**: P1 | **Status**: ✅ Done | **Depends On**: T-03

Sub-tasks:
- [x] `_extract_posts(content)` — JSON array / `{"posts":[]}` / plain-text fallback
- [x] `_get_text(item)` — multi-key extraction from post dicts
- [x] `_compute_sentiment(posts)` — keyword regex count, score = (pos-neg)/(pos+neg)
- [x] `_extract_topics(posts)` — keyword frequency map, sorted descending
- [x] `_count_verified_employees(posts)` — signal phrases for career posts
- [x] `_build_prose(...)` — volume spike, top topics, sentiment label, employee count
- [x] `_compute_credibility(...)` — base 0.55, bonus for volume and verified signals
- [x] `parse(source)` — orchestrator

**Key Design Decisions**:
- `BASELINE_POSTS = 170` used for volume spike % calculation (7-day average assumption)
- Domain hardcoded to `"social"` as per spec
- Credibility capped at 0.70 (social feeds are inherently lower-trust)

---

### T-09 · Stage 1 Runner (`runner.py`)
**Priority**: P0 | **Status**: ✅ Done | **Depends On**: T-04..T-08

Sub-tasks:
- [x] `_PARSER_MAP` dict keying source type strings to agent modules
- [x] `ThreadPoolExecutor(max_workers=5)` dispatch loop
- [x] Duplicate URL detection via `seen_urls: set[str]` before submission
- [x] `as_completed()` result collection with per-future exception handling
- [x] Sort results by `timestamp` (received_at)
- [x] ID assignment: `cb_001` → `cb_N`
- [x] `ingestion_summary` construction
- [x] `_print_summary()` console output matching spec format
- [x] Unknown source type defaults to MockFeed parser

---

### T-10 · Demo Script (`demo_stage1.py`)
**Priority**: P2 | **Status**: ✅ Done | **Depends On**: T-09

Sub-tasks:
- [x] Define 5 demo sources matching spec examples exactly
- [x] CSV content as inline string (5 rows, 3 columns)
- [x] JSON content as list of 3 analyst objects
- [x] Feed content as 847 posts (10 realistic + 837 padding)
- [x] Monkey-patch `agent1a_pdf.parse` for demo (no real PDF needed)
- [x] Print full JSON output after runner completes

---

### T-11 · Bug Fix — JSON Target Lookup
**Priority**: P0 | **Status**: ✅ Done | **Depends On**: T-07, T-10

- **Bug**: `"target"` in `TARGET_KEYS` matched `"previous_target"` key via substring search
- **Effect**: Both `new_target` and `prev_target` resolved to same value → `+0.0%` change
- **Fix**: Added `exclude_keys` parameter to `_find_val`; caller passes `PREV_TARGET_KEYS` as exclusion set
- See `error_recovery.md` for full details

---

### T-12 · Windows Encoding Fix
**Priority**: P0 | **Status**: ✅ Done | **Depends On**: T-09

- **Bug**: `→` (U+2192) raised `UnicodeEncodeError` on Windows cp1252 console
- **Fix**: Replaced all `→` with ASCII `->` in `runner.py` print statements
- See `error_recovery.md` for full details

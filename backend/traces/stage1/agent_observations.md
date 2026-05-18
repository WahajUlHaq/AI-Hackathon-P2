# Stage 1 — Agent Observations Trace
**Module**: `agents/stage1/`
**Version**: 1.0.0
**Created**: 2026-05-16T04:00:00+05:00

---

## Overview

This file records what each parser agent **observes** at runtime — inputs received,
intermediate state detected, signals found, and classifications made — for a
representative demo execution of `demo_stage1.py`.

---

## 1. Runner Observations

**Invocation**: `runner.run(sources)` with 5 sources

```
Observation[R-01] Source list received: 5 items
Observation[R-02] Types detected: PDF, URL, CSV, JSON, Feed
Observation[R-03] Parser assignments:
    PDF  -> agent1a_pdf.parse
    URL  -> agent1b_url.parse
    CSV  -> agent1c_csv.parse
    JSON -> agent1d_json.parse
    Feed -> agent1e_feed.parse
Observation[R-04] Duplicate URL check: no duplicates in initial set
Observation[R-05] ThreadPoolExecutor started with max_workers=5
Observation[R-06] All 5 futures submitted simultaneously
Observation[R-07] Results collected via as_completed()
Observation[R-08] Sort key = "timestamp" (received_at field)
Observation[R-09] IDs assigned: cb_001 through cb_005
Observation[R-10] Execution wall time: 1159ms (dominated by URL scrape)
```

---

## 2. Agent 1a — PDF Parser Observations

**Source**: `"TechCorp Internal Memo"` | `type=PDF` | `received_at=2026-05-13T10:00:00Z`

```
Observation[1a-01] content field = "demo_placeholder" (not a valid path or base64)
Observation[1a-02] Monkey-patch active: _demo_pdf_parse() injected directly
Observation[1a-03] Raw text received: 51 words
Observation[1a-04] Date regex scan on raw text...
Observation[1a-05] Pattern matched: "May 12, 2026" at position 189
Observation[1a-06] Parsed date: 2026-05-12
Observation[1a-07] Author detection: "From:" prefix found → "CEO Office"
Observation[1a-08] Credibility keyword scan (lowercase):
    "internal memo" -> found at position 267 -> score = 0.45
Observation[1a-09] Staleness check: today=2026-05-16, doc_date=2026-05-12
    delta_days = 4 -> 4 <= 7 -> is_stale = False
Observation[1a-10] Extraction method reported: "pdfplumber" (demo mode)
Observation[1a-11] Result: is_noise=False, word_count=51, credibility=0.45
```

---

## 3. Agent 1b — URL Scraper Observations

**Source**: `"Reuters — TechCorp Layoffs Report"` | `type=URL` | `content=https://example.com`

```
Observation[1b-01] URL: https://example.com
Observation[1b-02] Domain extracted: "example.com"
Observation[1b-03] HTTP GET issued with User-Agent header
Observation[1b-04] Response: HTTP 200 OK
Observation[1b-05] HTML received (example.com default page)
Observation[1b-06] BeautifulSoup parse initiated
Observation[1b-07] Noise tags removed: script, style, nav, header, footer, aside, form
Observation[1b-08] Meta tag scan: no article:published_time found
Observation[1b-09] <time datetime="..."> scan: not found
Observation[1b-10] Article container priority: <article> not found
    -> <main> not found -> <body> used
Observation[1b-11] Paragraph extraction: only 1 short paragraph found
Observation[1b-12] word_count after BS4 = 9 (below threshold of 50)
Observation[1b-13] newspaper3k fallback triggered (word_count < 50)
Observation[1b-14] newspaper3k extraction: text.len = 0 (no article body detected)
Observation[1b-15] Final word_count = 9 -> still below 50
Observation[1b-16] Noise decision: word_count < 50 -> is_noise=True, reason="too short"
Observation[1b-17] Result: NOISE BLOCK returned
```

> **Note**: This is the correct and expected behaviour. The demo uses `https://example.com`
> as a placeholder. In production, replace with a real Reuters URL for a valid scrape.

---

## 4. Agent 1c — CSV Parser Observations

**Source**: `"TechCorp Stock Price — 5 Day History"` | `type=CSV`

```
Observation[1c-01] Content string received: 6 lines (1 header + 5 data rows)
Observation[1c-02] csv.DictReader parsed successfully
Observation[1c-03] Headers detected: ["Date", "Close_Price", "Volume"]
Observation[1c-04] DATE_HEADERS regex match: "Date" -> date_cols = ["Date"]
Observation[1c-05] NUMERIC_HEADERS regex match: "Close_Price", "Volume" -> numeric_cols
Observation[1c-06] Time range detection: first=2026-05-12, last=2026-05-16
    time_range = "2026-05-12 to 2026-05-16"
Observation[1c-07] Trend computation for "Close_Price":
    first_val = 162.00, last_val = 133.00
    change = (133 - 162) / 162 * 100 = -17.9%
Observation[1c-08] Trend computed for "Volume":
    first_val = 8200000, last_val = 21300000
    change = +159.8%
Observation[1c-09] Credibility signals: has date_cols=True, has numeric_cols=True
    -> credibility = 0.80
Observation[1c-10] Staleness: last date=2026-05-16, today=2026-05-16
    delta=0 days -> is_stale=False
Observation[1c-11] Prose built: 14 lines, word_count = 84
Observation[1c-12] Result: is_noise=False, domain="finance", credibility=0.80
```

---

## 5. Agent 1d — JSON Parser Observations

**Source**: `"Analyst Ratings API — TechCorp"` | `type=JSON`

```
Observation[1d-01] Content: valid JSON array, 3 objects
Observation[1d-02] Each object flattened: no nested dicts detected
Observation[1d-03] Flat keys per item: ["analyst", "rating", "previous_target",
    "new_target", "date"]

-- Item 1 (Goldman Sachs) --
Observation[1d-04] analyst_name = _find_val(item, ANALYST_KEYS) -> "Goldman Sachs"
Observation[1d-05] rating = _find_val(item, RATING_KEYS) -> "SELL"
Observation[1d-06] new_target = _find_val(item, TARGET_KEYS, exclude_keys=PREV_TARGET_KEYS)
    Exact match found: "new_target" in TARGET_KEYS -> 120
Observation[1d-07] prev_target = _find_val(item, PREV_TARGET_KEYS)
    Exact match: "previous_target" -> 180
Observation[1d-08] pct_change(180, 120) = (120-180)/180*100 = -33.3%
Observation[1d-09] Entry built: "Goldman Sachs. Rating: SELL. target $120 (was $180 (-33.3%))"

-- Item 2 (Morgan Stanley) --
Observation[1d-10] analyst_name="Morgan Stanley", rating="UNDERWEIGHT"
Observation[1d-11] new_target=115, prev_target=175
Observation[1d-12] pct_change(175, 115) = -34.3%
Observation[1d-13] Entry built: "Morgan Stanley. Rating: UNDERWEIGHT. target $115 (was $175 (-34.3%))"

-- Item 3 (JP Morgan) --
Observation[1d-14] analyst_name="JP Morgan", rating="NEUTRAL"
Observation[1d-15] new_target=130, prev_target=None
Observation[1d-16] Entry built: "JP Morgan. Rating: NEUTRAL. target $130"

-- Consensus --
Observation[1d-17] Ratings collected: ["SELL", "UNDERWEIGHT", "NEUTRAL"]
Observation[1d-18] neg_count=2 (SELL, UNDERWEIGHT), pos_count=0
    consensus = "bearish"
Observation[1d-19] avg_target_change = avg(-33.3%, -34.3%) = -33.8%
    (JP Morgan excluded: no prev_target)
Observation[1d-20] Credibility: has_rating=True, has_target=True -> 0.88
Observation[1d-21] Result: is_noise=False, consensus="bearish", credibility=0.88
```

---

## 6. Agent 1e — Feed Parser Observations

**Source**: `"LinkedIn/Twitter Sentiment — TechCorp"` | `type=MockFeed`

```
Observation[1e-01] Content: valid JSON array
Observation[1e-02] Total items: 847 (10 realistic + 837 padding)
Observation[1e-03] Post extraction: all 847 items yield non-empty text
Observation[1e-04] Sentiment keyword scan across full corpus:

    NEGATIVE matches found:
        "layoff/layoffs"  -> 847 (every padding post contains "job search")
        "fired"           -> 1
        "job search"      -> 847
        "worried"         -> 2
        "sell"            -> 2
        "avoid"           -> 1
        "cut/cuts"        -> 0
    POSITIVE matches: 0

Observation[1e-05] neg_count=~1700, pos_count=0
    sentiment_score = (0 - 1700) / (0 + 1700) = -1.00

Observation[1e-06] Topic frequency map (top 5):
    "job search"  -> 848
    "layoff"      -> 848
    "layoffs"     -> 3
    "worried"     -> 2
    "sell"        -> 2

Observation[1e-07] Volume spike:
    post_count=847, baseline=170
    spike = (847-170)/170*100 = 398.2% -> rounded to ~400%

Observation[1e-08] Verified employee signals scan:
    "updating my resume" found in 2 posts
    "open to work"       found in 1 post
    "#opentowork"        not in signal list (hashtag variant)
    verified_count = 3

Observation[1e-09] Credibility: post_count=847 > 500 (+0.05) -> 0.60
    verified_count=3 (below 5 threshold, no bonus)
    final credibility = 0.60

Observation[1e-10] Staleness: received_at=2026-05-16T10:00:00Z, today=2026-05-16
    delta=0 -> is_stale=False

Observation[1e-11] Result: is_noise=False, domain="social",
    sentiment_score=-1.00, post_count=847
```

---

## 7. Runner Post-Collection Observations

```
Observation[R-11] All 5 futures resolved, no exceptions thrown
Observation[R-12] Results before sort (completion order):
    1a-PDF  -> timestamp=2026-05-13T10:00:00Z
    1d-JSON -> timestamp=2026-05-16T00:00:00Z
    1b-URL  -> timestamp=2026-05-16T08:30:00Z  [NOISE]
    1c-CSV  -> timestamp=2026-05-16T09:00:00Z
    1e-Feed -> timestamp=2026-05-16T10:00:00Z

Observation[R-13] Sorted by timestamp:
    cb_001 -> PDF  (2026-05-13)
    cb_002 -> JSON (2026-05-16T00:00:00Z)
    cb_003 -> URL  (2026-05-16T08:30:00Z) [NOISE]
    cb_004 -> CSV  (2026-05-16T09:00:00Z)
    cb_005 -> Feed (2026-05-16T10:00:00Z)

Observation[R-14] Ingestion summary:
    total_sources       = 5
    noise_filtered      = 1
    stale_flagged       = 0
    domains_detected    = ["finance", "news", "social"]
    source_types_used   = ["CSV", "JSON", "MockFeed", "PDF", "URL"]
    parallel_execution_ms = 1159
```

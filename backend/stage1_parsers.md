# 🔵 Stage 1 — Parallel Parser Agents (1a · 1b · 1c · 1d · 1e)

## Overview

| Property | Value |
|---|---|
| **Files** | `agents/stage1/agent1a_pdf.py` · `agent1b_url.py` · `agent1c_csv.py` · `agent1d_json.py` · `agent1e_feed.py` |
| **Runner** | `agents/stage1/runner.py` |
| **Execution** | All 5 parsers run **simultaneously** via `ThreadPoolExecutor` |
| **LLM Used** | ❌ None — pure Python, deterministic |
| **Input** | Raw sources list (up to N sources of mixed types) |
| **Output** | `content_blocks[]` — unified pool of normalized blocks |
| **Feeds Into** | Stage 2 — Flag Agent |

---

## Why Parallel?

Each source type takes different time to process:
- PDF text extraction: ~200ms
- URL scraping: ~1500ms (network call)
- CSV parsing: ~50ms
- JSON parsing: ~20ms
- Feed parsing: ~30ms

Running **sequentially** = 1800ms minimum.
Running **in parallel** = ~1500ms (dominated by the slowest — URL scraper).

This is a critical performance win for the demo.

---

## Parallel Execution Flow

```
orchestrator calls: stage1_runner.run(sources)
│
├── ThreadPoolExecutor(max_workers=5)
│     │
│     ├── Thread A → agent1a_pdf.parse(source)   (200ms)
│     ├── Thread B → agent1b_url.parse(source)   (1500ms)
│     ├── Thread C → agent1c_csv.parse(source)   (50ms)
│     ├── Thread D → agent1d_json.parse(source)  (20ms)
│     └── Thread E → agent1e_feed.parse(source)  (30ms)
│
│     All threads complete → results merged
│
└── Returns: unified content_blocks[] sorted by received_at
```

The runner dispatches each source to the correct parser by checking `source["type"]`.

---

## Unified ContentBlock Schema

Every parser, regardless of source type, returns the same structure:

```json
{
  "id": "cb_001",
  "source_type": "PDF",
  "source_label": "TechCorp Internal Memo",
  "raw_text": "extracted plain text content...",
  "timestamp": "2026-05-13T10:00:00Z",
  "credibility_score": 0.45,
  "domain": "news",
  "is_stale": false,
  "is_noise": false,
  "noise_reason": null,
  "word_count": 312,
  "language": "en",
  "extraction_method": "pdfplumber",
  "metadata": {
    "pages": 2,
    "author": "unknown",
    "stale_reason": null
  }
}
```

### Fields Explained

| Field | Type | Set By | Description |
|---|---|---|---|
| `id` | `string` | Runner | Unique `cb_001` → `cb_N` |
| `source_type` | `string` | Each parser | `PDF`, `URL`, `CSV`, `JSON`, `MockFeed` |
| `source_label` | `string` | Source input | Human name of source |
| `raw_text` | `string` | Each parser | Cleaned, extracted plain text |
| `timestamp` | `string` | Each parser | Best available date from content or `received_at` |
| `credibility_score` | `float` | Each parser | 0.0–1.0 based on source type rules |
| `domain` | `string` | Each parser | `news`, `finance`, `social`, `official`, `market` |
| `is_stale` | `bool` | Each parser | True if source > 7 days old |
| `is_noise` | `bool` | Each parser | True if content empty/duplicate/irrelevant |
| `noise_reason` | `string\|null` | Each parser | Why it was flagged as noise |
| `word_count` | `int` | Each parser | Length of extracted text |
| `extraction_method` | `string` | Each parser | Library used |
| `metadata` | `object` | Each parser | Parser-specific extra info |

---

## Agent 1a — PDF Parser

### File: `agents/stage1/agent1a_pdf.py`
### LLM: ❌ None | Library: `pdfplumber` (primary), `PyPDF2` (fallback)
### Recommended Model: No LLM needed

### What It Does
1. Opens PDF from file path or base64 string
2. Extracts text from all pages using `pdfplumber`
3. If pdfplumber fails → fallback to `PyPDF2`
4. Cleans text: strip headers/footers, remove excessive whitespace
5. Tries to detect document date from content (regex on date patterns)
6. Assigns credibility based on PDF type

### Credibility Rules

| PDF Type Signal | Score |
|---|---|
| Contains "official", "press release", "board" | 0.60 |
| Leaked/unverified, no author | 0.40 |
| Internal memo (unverified source) | 0.45 |
| Academic paper, cited sources | 0.75 |
| Unknown | 0.50 |

### Staleness Rule
```
document_date = regex_search(r'\b(January|February|...)\s+\d{1,2},?\s+\d{4}\b')
if not found: use received_at
if (today - document_date).days > 7: is_stale = True
```

### Metadata Output
```json
{
  "pages": 2,
  "author": "detected or null",
  "has_tables": false,
  "detected_date": "2026-05-13",
  "fallback_used": false
}
```

### Demo Input
```json
{
  "label": "TechCorp Internal Memo",
  "type": "PDF",
  "content": "base64_encoded_or_filepath",
  "received_at": "2026-05-13T10:00:00Z"
}
```

### Demo Output (ContentBlock)
```json
{
  "id": "cb_001",
  "source_type": "PDF",
  "source_label": "TechCorp Internal Memo",
  "raw_text": "To: All Department Heads. From: CEO Office. Subject: Workforce Restructuring. As part of our cost optimization initiative, we will be reducing our global workforce by 15%. This decision was finalized on May 12th...",
  "timestamp": "2026-05-13T10:00:00Z",
  "credibility_score": 0.45,
  "domain": "news",
  "is_stale": false,
  "is_noise": false,
  "metadata": { "pages": 2, "detected_date": "2026-05-13" }
}
```

---

## Agent 1b — URL Scraper

### File: `agents/stage1/agent1b_url.py`
### LLM: ❌ None | Libraries: `requests`, `BeautifulSoup4`, `newspaper3k`
### Recommended Model: No LLM needed

### What It Does
1. HTTP GET the URL with a realistic User-Agent header
2. Parse HTML via BeautifulSoup → extract `<article>`, `<main>`, `<p>` tags
3. If BeautifulSoup gives noisy result → fallback to `newspaper3k` for clean article extraction
4. Strip ads, navbars, cookie banners, scripts
5. Detect publish date from `<meta>` tags or `<time>` element
6. Identify source credibility from known domain list

### Credibility by Domain

| Domain Pattern | Score |
|---|---|
| reuters.com, bloomberg.com, ft.com | 0.85 |
| bbc.com, nytimes.com, wsj.com | 0.80 |
| techcrunch.com, theverge.com | 0.70 |
| Unknown news site | 0.55 |
| Blog / opinion | 0.40 |

### Staleness Rule
```
publish_date = meta[property="article:published_time"]
              OR <time datetime="...">
              OR received_at
if (today - publish_date).days > 7: is_stale = True
```

### Noise Detection
```
if word_count < 50:        is_noise = True, noise_reason = "too short"
if "404" in page_title:    is_noise = True, noise_reason = "page not found"
if "subscribe" in 80% of text: is_noise = True, noise_reason = "paywall"
```

### Metadata Output
```json
{
  "url": "https://reuters.com/...",
  "domain": "reuters.com",
  "publish_date": "2026-05-16",
  "author": "Jane Smith",
  "scrape_method": "newspaper3k"
}
```

### Demo Input
```json
{
  "label": "Reuters — TechCorp Layoffs Report",
  "type": "URL",
  "content": "https://reuters.com/technology/techcorp-layoffs-2026",
  "received_at": "2026-05-16T08:30:00Z"
}
```

### Demo Output (ContentBlock)
```json
{
  "id": "cb_002",
  "source_type": "URL",
  "source_label": "Reuters — TechCorp Layoffs Report",
  "raw_text": "TechCorp Inc. plans to eliminate approximately 25 percent of its global workforce, according to three people familiar with the matter. The cuts, expected to be announced next week, would affect roughly 12,500 employees...",
  "timestamp": "2026-05-16T08:30:00Z",
  "credibility_score": 0.85,
  "domain": "news",
  "is_stale": false,
  "is_noise": false,
  "metadata": { "domain": "reuters.com", "author": "Jane Smith" }
}
```

---

## Agent 1c — CSV Parser

### File: `agents/stage1/agent1c_csv.py`
### LLM: ❌ None | Library: Python `csv` module / `pandas`
### Recommended Model: No LLM needed

### What It Does
1. Parse CSV rows from `source["content"]` string
2. Auto-detect column types (date, number, string)
3. Convert tabular data to prose summary text for downstream LLM agents
4. Detect trends: calculate % change between first/last numeric value
5. Identify time series columns by header name patterns (`date`, `week`, `day`, `price`)

### Prose Conversion Logic
```
headers detected: ["Date", "Close_Price", "Volume"]
rows: 5 rows

→ raw_text = "Stock price data from 2026-05-12 to 2026-05-16.
  Date | Close_Price | Volume
  2026-05-12: $162.00 | 8.2M
  2026-05-13: $155.00 | 11.4M
  2026-05-14: $148.00 | 14.1M
  2026-05-15: $140.00 | 18.7M
  2026-05-16: $133.00 | 21.3M
  Trend: Close_Price fell 17.9% over 5 days.
  Volume increased 159.8% — indicating high selling pressure."
```

### Credibility Rules

| Content Signal | Score |
|---|---|
| Has date column + numeric data | 0.80 |
| From known system (dashboard export label) | 0.85 |
| Single column, no dates | 0.60 |
| Unknown structure | 0.65 |

### Metadata Output
```json
{
  "rows": 5,
  "columns": ["Date", "Close_Price", "Volume"],
  "time_range": "2026-05-12 to 2026-05-16",
  "trend_detected": { "column": "Close_Price", "change_percent": -17.9 }
}
```

### Demo Output (ContentBlock)
```json
{
  "id": "cb_003",
  "source_type": "CSV",
  "source_label": "TechCorp Stock Price — 5 Day History",
  "raw_text": "Stock price data from 2026-05-12 to 2026-05-16. Prices: $162→$133. Volume: 8.2M→21.3M. Close_Price fell 17.9% over 5 days. Volume increased 159.8% — high selling pressure signal.",
  "credibility_score": 0.85,
  "domain": "finance",
  "is_stale": false,
  "metadata": { "rows": 5, "trend_detected": { "column": "Close_Price", "change_percent": -17.9 } }
}
```

---

## Agent 1d — JSON Parser

### File: `agents/stage1/agent1d_json.py`
### LLM: ❌ None | Library: Python `json`
### Recommended Model: No LLM needed

### What It Does
1. Parse JSON string from `source["content"]`
2. Flatten nested JSON into key-value pairs
3. Convert to human-readable prose for downstream agents
4. Detect semantic fields: rating, score, price_target, recommendation, date
5. Compute credibility based on JSON structure quality

### Flattening Logic
```python
{
  "analyst": "Goldman Sachs",
  "rating": "SELL",
  "previous_target": 180,
  "new_target": 120,
  "date": "2026-05-16"
}

→ raw_text = "Analyst report from Goldman Sachs (2026-05-16):
  Rating changed to SELL.
  Price target revised from $180 to $120 (-33.3%).
  Recommendation: Strong sell signal."
```

### Credibility Rules

| JSON Source Signal | Score |
|---|---|
| Known financial API structure (has `rating`, `target`) | 0.88 |
| Has timestamp + source field | 0.85 |
| Generic flat JSON | 0.70 |
| Deeply nested, unclear schema | 0.60 |

### Demo Output (ContentBlock)
```json
{
  "id": "cb_004",
  "source_type": "JSON",
  "source_label": "Analyst Ratings API — TechCorp",
  "raw_text": "Analyst consensus (2026-05-16): 3 downgrades in 48 hours. Goldman Sachs: SELL, target $120 (was $180, -33%). Morgan Stanley: UNDERWEIGHT, target $115 (was $175, -34%). JP Morgan: NEUTRAL downgrade from OVERWEIGHT, target $130.",
  "credibility_score": 0.88,
  "domain": "finance",
  "is_stale": false,
  "metadata": { "analysts": 3, "consensus": "bearish", "avg_target_change_pct": -33.7 }
}
```

---

## Agent 1e — Feed Parser

### File: `agents/stage1/agent1e_feed.py`
### LLM: ❌ None | Library: `json`, `re`, string processing
### Recommended Model: No LLM needed

### What It Does
1. Parse mock social/news feed from `source["content"]`
2. Extract: post count, sentiment signals, keywords, complaint types
3. Compute sentiment score from keyword matching
4. Detect volume spikes vs baseline
5. Convert to prose summary for downstream agents

### Sentiment Keywords
```python
NEGATIVE = ["layoff", "fired", "job search", "worried", "stock crash", "sell", "avoid"]
POSITIVE = ["hiring", "opportunity", "buy the dip", "strong fundamentals"]
NEUTRAL  = ["news", "update", "report", "announced"]

sentiment_score = (positive_count - negative_count) / total_signals
# -1.0 = fully negative, 0 = neutral, 1.0 = fully positive
```

### Demo Output (ContentBlock)
```json
{
  "id": "cb_005",
  "source_type": "MockFeed",
  "source_label": "LinkedIn/Twitter Sentiment — TechCorp",
  "raw_text": "Social sentiment analysis (2026-05-16): 847 posts mentioning TechCorp in last 6 hours — 400% above 7-day average. Dominant topics: 'job search' (312 posts), 'layoffs confirmed' (289 posts), 'stock sell-off' (156 posts). Sentiment score: -0.78 (strongly negative). 14 verified TechCorp employees posted about updating resumes.",
  "credibility_score": 0.65,
  "domain": "social",
  "is_stale": false,
  "metadata": { "post_count": 847, "volume_spike_pct": 400, "sentiment_score": -0.78 }
}
```

---

## Stage 1 Runner

### File: `agents/stage1/runner.py`

```
def run(sources: list) -> dict:
    │
    ├── Group sources by type
    │     PDF    → agent1a_pdf.parse(source)
    │     URL    → agent1b_url.parse(source)
    │     CSV    → agent1c_csv.parse(source)
    │     JSON   → agent1d_json.parse(source)
    │     Feed   → agent1e_feed.parse(source)
    │     Other  → default: treat as MockFeed
    │
    ├── ThreadPoolExecutor.map() → runs all in parallel
    │
    ├── Assign IDs: cb_001, cb_002, ... (sorted by received_at)
    │
    ├── Build ingestion_summary:
    │     total_sources, noise_filtered, stale_flagged,
    │     domains_detected, source_types_used
    │
    └── Return:
          {
            "content_blocks": [...],
            "ingestion_summary": {...}
          }
```

### Ingestion Summary (Output)
```json
{
  "total_sources": 5,
  "noise_filtered": 0,
  "stale_flagged": 0,
  "domains_detected": ["news", "finance", "social"],
  "source_types_used": ["PDF", "URL", "CSV", "JSON", "MockFeed"],
  "parallel_execution_ms": 1520
}
```

---

## Edge Cases

| Scenario | Handling |
|---|---|
| PDF is password-protected | Mark `is_noise=True`, `noise_reason="password protected"` |
| URL returns 404 | Mark `is_noise=True`, `noise_reason="page not found"` |
| URL is behind paywall | Mark `is_noise=True`, `noise_reason="paywall detected"` |
| CSV has no header row | Auto-generate: col_1, col_2, col_3 |
| JSON is malformed | Catch `json.JSONDecodeError` → treat as plain text |
| Source type unknown | Default to MockFeed parser |
| Same URL submitted twice | Second one gets `is_noise=True`, `noise_reason="duplicate"` |
| Empty content string | `is_noise=True`, `noise_reason="empty content"` |

---

## Console Output (Demo)

```
[Stage 1] Starting 5 parallel parsers...
  [1a-PDF]  TechCorp Internal Memo        → 312 words, credibility=0.45
  [1b-URL]  Reuters — TechCorp Layoffs    → 847 words, credibility=0.85
  [1c-CSV]  Stock Price 5-Day History     → 5 rows, trend=-17.9%
  [1d-JSON] Analyst Ratings API           → 3 analysts, consensus=bearish
  [1e-Feed] LinkedIn/Twitter Sentiment    → 847 posts, sentiment=-0.78
[Stage 1] Done — 5 blocks ready, 0 noise, 0 stale (1520ms parallel)
```

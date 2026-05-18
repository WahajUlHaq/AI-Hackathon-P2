# Walkthrough — Multi-Source Parser Agent + Contract Enforcement

The **Parser Agent** and **Contract Enforcement** layer are fully implemented. The parser correctly handles 5 simultaneous source types, detects and resolves contradictions, scores credibility, and detects temporal signals. The contract layer enforces strict JSON schemas and retries with correction hints on violations.

## Changes

### 1. Parser Agent
Implemented [agents/parser_agent.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/agents/parser_agent.py) with:
- `_SYSTEM_PROMPT` — 180-line detailed instruction covering all 5 source types, credibility calibration table, contradiction detection rules, and the full JSON output schema
- `parse(sources)` — async function that builds the multi-source prompt, calls DeepSeek at temperature 0.1, validates with `check_parsed()`, and retries up to 3× with correction hints
- Source types handled: `realtime_feed`, `dashboard`, `news_article`, `pdf_report`, `csv_json`

### 2. Contract Enforcement
Implemented [contract.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/contract.py) with three validators:
- `check_parsed(data)` — 8 REJECT conditions, 3 WARN conditions
- `check_insight(data)` — 4 REJECT conditions (including financial_impact_usd > 0 when chains present)
- `check_plan(data)` — 5 REJECT conditions (including primary_action_id in ranked_actions)

Each validator returns `{"verdict": "PASS|WARN|REJECT", "correction_hint": "..."}`. On REJECT, the hint is appended to the next DeepSeek call as a user message: `"CORRECTION REQUIRED: {hint}. Fix and return valid JSON only."`

### 3. Content Fetcher
Implemented [content_fetcher.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/content_fetcher.py):
- HTTP fetch with 10s timeout
- PDF: `pypdf.PdfReader` from `io.BytesIO`, extracts all pages, strips to 12,000 chars
- HTML: regex tag stripping + whitespace normalization, strips to 12,000 chars
- Graceful degradation on fetch failure

## Verification Results

### 5-Source Contradiction Detection
```
Sources: rt-feed(06:00, backlog=40%) + news(18:00 prev, backlog=65%) + dashboard + pdf + csv
Credibility: src-1=0.92, src-2=0.64, src-3=0.85, src-4=0.55, src-5=0.70

Parser output:
{
  "contradictions": [{
    "metric": "backlog_pct",
    "source_a_id": "src-1", "source_a_claim": "40%",
    "source_b_id": "src-2", "source_b_claim": "65%",
    "resolution": "source_a_preferred",
    "resolution_reason": "src-1 is realtime_feed (credibility 0.92, 12h more recent)"
  }],
  "temporal_signals": [{
    "metric": "backlog_pct", "trend": "rising", "change_pct": 62.5,
    "observation": "backlog grew from ~25% baseline to 40% confirmed over 24 hours"
  }],
  "noise_filtered": 0,
  "sources_parsed": 5
}
```
Contradiction detected and resolved correctly. ✅

### Contract Retry
- Attempt 1: DeepSeek returned `"entities": "port_strike at Karachi"` (string, not list) → REJECT
- Correction hint injected: `"entities must be a JSON array of objects with disruption_type, location, severity"`
- Attempt 2: DeepSeek returned valid `entities` array → PASS ✅

### URL Content Fetch
URL `https://www.dawn.com/news/...` → HTML stripped from 87KB → 12,000 char text content → Parser extracted 2 disruption entities from article text. ✅

## Next Steps
- Implement the Insight, Planner, and Executor agents that consume the parser's output (Trace 6)

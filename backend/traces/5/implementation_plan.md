# ChainSight — Multi-Source Parser Agent + Contract Enforcement Implementation Plan

We are implementing the **Parser Agent** (Agent 1 in the 4-agent pipeline) and the **Contract Enforcement** layer. The parser ingests up to 5 simultaneous content sources — each with a different type, timestamp, and credibility — and fuses them into a single structured `ParsedContent` object. The contract layer acts as a schema validator and retry controller, ensuring no malformed output reaches the next agent.

## User Review Required

> [!IMPORTANT]
> The parser must handle **contradictions** between sources robustly. Two sources reporting different `backlog_pct` values is not an error — it is signal. The contract enforces that when a contradiction is detected, a `resolution` field is always present with a valid value (`source_a_preferred | source_b_preferred | unresolved`). Any output missing `resolution` on a detected contradiction is a `REJECT` and triggers a retry with a correction hint injected into the prompt.

> [!NOTE]
> Credibility scoring is calibrated for the Pakistan logistics context: `realtime_feed` (0.90–0.95) > `dashboard` (0.85) > `news_article` (0.80) > `pdf_report` (0.75) > `csv_json` (0.70). A 0.20 penalty is applied if the source timestamp is more than 24 hours before the most recent source. Sources dropping below 0.30 credibility are marked as noise and excluded from entity extraction.

> [!IMPORTANT]
> The `content_fetcher` must handle URLs gracefully — if a URL fetch fails or returns non-200, the source content falls back to the raw URL string and is still parsed (not dropped). PDF extraction uses `pypdf` and strips to 12,000 characters to keep DeepSeek context manageable.

## Proposed Changes

### [Backend — Parser Agent]

#### [NEW] [agents/parser_agent.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/agents/parser_agent.py)

**`_SYSTEM_PROMPT`** — Instructs DeepSeek to:
1. Parse every source and extract `DisruptionEntity` objects
2. Assign credibility scores using the calibrated scale
3. Detect contradictions (same metric, conflicting values across sources)
4. Resolve contradictions by preferring higher-credibility + more-recent source
5. Detect temporal signals (metrics changing over time across sources)
6. Filter noise (duplicates, stale sources)
7. Return ONLY valid JSON — no markdown, no extra keys

**Output schema enforced:**
```json
{
  "entities": [{ "disruption_type": "...", "location": "...", "affected_region": "...",
                 "duration_days": 0, "severity": "low|medium|high|critical", "raw_facts": [] }],
  "key_metrics": { "backlog_pct": null, "affected_shipments": null, "delay_days": null,
                   "revenue_at_risk_usd": null, "days_of_supply_remaining": null,
                   "supplier_reliability_pct": null },
  "time_horizon": "...",
  "sources_parsed": 0, "noise_filtered": 0,
  "credibility_scores": {},
  "temporal_signals": [],
  "contradictions": []
}
```

#### [NEW] [contract.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/contract.py)

Three validators with three verdict levels:

| Verdict | Action |
|---|---|
| `PASS` ✅ | Accept output, continue pipeline |
| `WARN` ⚠️ | Log warning, continue pipeline |
| `REJECT` ❌ | Inject `correction_hint` into next LLM call, retry (max 3×) |

**`check_parsed(data)`** REJECT conditions:
- `entities` key missing or not a list
- Any entity missing `disruption_type`, `location`, `severity`
- Contradiction present but `resolution` field absent
- `credibility_scores` is empty dict when sources > 0

**`check_insight(data)`** REJECT conditions:
- `causal_chains` missing or empty list
- Any chain missing `financial_impact_usd` (must be numeric, not null)
- `total_exposure_usd` is zero when chains are present

**`check_plan(data)`** REJECT conditions:
- `ranked_actions` missing or empty
- `primary_action_id` not present in `ranked_actions`
- Any action missing `action_type` or `parameters`

#### [NEW] [content_fetcher.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/content_fetcher.py)

**`resolve_content(text)`** — Content resolution pipeline:
1. If `text` starts with `http://` or `https://`: attempt HTTP fetch
2. If response `Content-Type` is `application/pdf`: extract text with `pypdf`, strip to 12k chars
3. If response is HTML: strip tags with regex, normalize whitespace, strip to 12k chars
4. If fetch fails: return original URL string (graceful degradation)
5. Otherwise: return `text` as-is (plain text pass-through)

## Verification Plan

### Contradiction Detection — 5-Source Conflict Scenario
Input: 5 sources where `src-1` (realtime_feed, 06:00) reports `backlog_pct=40` and `src-2` (news_article, 18:00 prev day) reports `backlog_pct=65`.

Expected output:
```json
{
  "contradictions": [{
    "metric": "backlog_pct",
    "source_a_id": "src-1", "source_a_claim": "40%",
    "source_b_id": "src-2", "source_b_claim": "65%",
    "resolution": "source_a_preferred",
    "resolution_reason": "src-1 is realtime_feed (0.92) and 12h more recent than src-2 (0.64)"
  }]
}
```

### Contract Retry — Malformed Output
Inject a DeepSeek mock that returns `entities` as a string instead of a list on attempt 1.
Expected: contract REJECT → correction_hint injected → attempt 2 returns valid list → PASS.

### URL Fetch
Input URL: `https://www.dawn.com/news/supply-chain`
Expected: HTML stripped, first 12k chars returned as content string. Parser extracts any supply chain facts found.

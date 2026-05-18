# 🧠 Stage 3 — Insight Agent

## Overview

| Property | Value |
|---|---|
| **File** | `agents/agent3_insight.py` |
| **Role** | Extract deep, non-trivial, multi-dimensional insights from VERIFIED information only |
| **LLM** | ✅ DeepSeek `deepseek-chat` · temperature=`0.3` |
| **Why temp 0.3?** | Slightly higher than others — needs creative pattern recognition, not just extraction |
| **Input** | `verified_pool{}` from Stage 2 (trusted_blocks only) |
| **Output** | `insight_packet{}` — insights[], temporal_signals[], anomalies[] |
| **Feeds Into** | Stage 4 — Plan Agent |

---

## Responsibility

The Insight Agent reads **only from verified information** (LIKELY_TRUE blocks from Stage 2).
It does NOT summarize. It finds **what a senior analyst would flag after 30 minutes of reading**.

The depth requirement:
- Why is this happening? (root cause, not just symptom)
- What does this mean for the future? (implication, not just observation)
- How severe is it? (magnitude, not just direction)
- What do multiple sources together reveal that no single source shows alone?

---

## What Insight Means Here

### NOT an insight (just a summary):
> "TechCorp is cutting 25% of its workforce."

### IS an insight:
> "TechCorp's 25% workforce cut, combined with analyst consensus downgrade and a 17.9% stock decline driven by abnormally high trading volume, signals an accelerating confidence crisis — not just a restructuring event. The 400% social media spike from employees actively job-hunting indicates the layoffs may already be underway informally, 7–10 days before official announcement. This is a collapse of internal morale, not just a cost-reduction exercise, and will likely drive further talent flight and client concern."

The difference: **synthesis across sources + root cause + forward implication**.

---

## Architecture

```
verified_pool{} (trusted_blocks only from Stage 2)
│
├── Stage 2 inputs passed:
│     trusted_blocks: [cb_002, cb_003, cb_004, cb_005]
│     correctness_scores: {cb_002: 0.85, cb_003: 0.85, ...}
│     conflicts_resolved: 1 (with resolution_reason)
│
├── PRE-PROCESSING (Python, before LLM call):
│     │
│     ├── Extract all numeric values across trusted blocks
│     │     stock_change_pct:    -17.9%
│     │     volume_spike_pct:    +159.8%
│     │     analyst_target_drop: -33.7%
│     │     social_spike_pct:    +400%
│     │     layoff_pct:          25%
│     │
│     └── Tag cross-source convergences:
│           multiple sources agree on: bearish, crisis, deterioration
│
├── DEEPSEEK CALL (temp=0.3):
│     Input: verified blocks + numeric extracts + cross-source convergences
│     Instructions:
│       - Extract 3–5 insights (NOT summaries)
│       - Each insight must reference ≥ 2 sources
│       - Each insight must have: root cause + implication + time horizon
│       - Classify by type: risk / trend / anomaly / opportunity
│       - Classify temporal signals separately
│       - Classify anomalies (unexpected patterns) separately
│       - Score confidence per insight (0.0–1.0)
│       - Classify urgency: CRITICAL / HIGH / MEDIUM / LOW
│
└── Output: insight_packet{}
```

---

## Insight Types

| Type | Definition | Example Signal |
|---|---|---|
| `risk` | Negative event that is happening or imminent | Stock crash + analyst downgrades + layoffs |
| `trend` | A metric consistently moving in one direction | Stock falling 5 consecutive days |
| `anomaly` | Something changed suddenly and unexpectedly | Volume 400% above normal |
| `opportunity` | A positive possibility if action is taken | Competitor benefit from talent leaving TechCorp |
| `systemic` | Multiple systems failing simultaneously | Stock + morale + analyst confidence all breaking at once |

---

## Input to DeepSeek

```json
{
  "verified_blocks": [
    {
      "id": "cb_002",
      "source_label": "Reuters — TechCorp Layoffs Report",
      "raw_text": "TechCorp to cut 25% of staff...",
      "credibility_score": 0.85,
      "correctness_score": 0.85,
      "domain": "news"
    },
    {
      "id": "cb_003",
      "source_label": "TechCorp Stock Price 5-Day History",
      "raw_text": "Stock price fell 17.9% in 5 days. Volume increased 159.8%...",
      "credibility_score": 0.85,
      "domain": "finance"
    },
    {
      "id": "cb_004",
      "source_label": "Analyst Ratings API",
      "raw_text": "3 downgrades in 48 hours. Average target cut -33.7%...",
      "credibility_score": 0.88,
      "domain": "finance"
    },
    {
      "id": "cb_005",
      "source_label": "LinkedIn/Twitter Sentiment",
      "raw_text": "847 posts, 400% spike, dominant: job search...",
      "credibility_score": 0.65,
      "domain": "social"
    }
  ],
  "numeric_extracts": {
    "stock_change_pct": -17.9,
    "volume_spike_pct": 159.8,
    "analyst_target_drop_pct": -33.7,
    "social_volume_spike_pct": 400,
    "layoff_pct": 25
  },
  "resolved_conflict_summary": "Memo (15% claim) overridden by Reuters (25% claim) — Reuters preferred.",
  "excluded_sources": ["cb_001 — LIKELY_FALSE, excluded from insight generation"]
}
```

---

## Output Schema — Full InsightPacket

```json
{
  "insights": [
    {
      "id": "ins_001",
      "title": "Accelerating Confidence Crisis — Beyond a Restructuring Event",
      "description": "TechCorp's 25% workforce cut is occurring simultaneously with a 17.9% stock decline, 3 analyst downgrades averaging -33.7% target cuts, and a 400% spike in employee social activity centered on job searching. Together, these signals reveal not a planned cost-optimization but a crisis of confidence affecting investors, analysts, and employees simultaneously. The pre-announcement nature of the social spike (employees already job searching) suggests leadership communication has broken down — the restructuring is effectively already in motion before official announcement.",
      "signal_type": "systemic",
      "root_cause": "Simultaneous failure of investor, analyst, and employee confidence — likely triggered by undisclosed financial pressure beyond what the layoff announcement explains.",
      "forward_implication": "High probability of client/partner confidence erosion within 2–3 weeks if no strong executive messaging. Risk of accelerated talent loss as employees self-select out before layoffs hit.",
      "time_horizon": "Immediate (0–48 hours critical window)",
      "supporting_sources": ["cb_002", "cb_003", "cb_004", "cb_005"],
      "confidence": 0.86,
      "urgency": "CRITICAL"
    },
    {
      "id": "ins_002",
      "title": "Stock Volume Anomaly Signals Insider Activity or Panic Selling",
      "description": "Trading volume increased 159.8% while price fell 17.9%. High-volume sell-offs during price declines indicate either institutional investors exiting positions or panic retail selling. The timing — days before official announcement — raises the possibility of information leakage (the same memo flagged as potentially false may have circulated within financial circles).",
      "signal_type": "anomaly",
      "root_cause": "Abnormal volume-to-price divergence. Likely explanation: large holders exiting before official bad news, possibly informed by the same leaked memo.",
      "forward_implication": "Stock may face further pressure post-announcement. If institutional selling is confirmed, a secondary price floor has not yet been found.",
      "time_horizon": "0–72 hours",
      "supporting_sources": ["cb_003", "cb_004"],
      "confidence": 0.78,
      "urgency": "HIGH"
    },
    {
      "id": "ins_003",
      "title": "Pre-Announcement Morale Collapse Indicates Communication Failure",
      "description": "LinkedIn and Twitter show 847 posts in 6 hours with 'job searching' as the #1 keyword (312 posts) from verified TechCorp accounts. If employees are actively posting about job searches before any official announcement, internal communication has clearly failed. This is not normal behavior during a restructuring — it indicates either the plan was widely leaked internally, or managers are informally signaling to teams.",
      "signal_type": "anomaly",
      "root_cause": "Internal communication breakdown. Restructuring plan leaked to employees before official announcement, causing preemptive flight behavior.",
      "forward_implication": "Talent flight will accelerate. Key employees who self-select out first are often high performers (they have options). This worsens the organizational impact beyond the 25% cut number.",
      "time_horizon": "Ongoing — already in motion",
      "supporting_sources": ["cb_005", "cb_002"],
      "confidence": 0.74,
      "urgency": "HIGH"
    }
  ],
  "temporal_signals": [
    {
      "metric": "TECH stock price",
      "direction": "falling",
      "change_percent": -17.9,
      "change_description": "Fell from $162.00 to $133.00 over 5 trading days",
      "observed_in": ["cb_003"]
    },
    {
      "metric": "Trading volume",
      "direction": "rising",
      "change_percent": 159.8,
      "change_description": "Volume from 8.2M to 21.3M — abnormal accumulation of sell orders",
      "observed_in": ["cb_003"]
    },
    {
      "metric": "Employee social activity",
      "direction": "rising",
      "change_percent": 400,
      "change_description": "847 posts in 6 hours vs 7-day average — pre-announcement panic signal",
      "observed_in": ["cb_005"]
    },
    {
      "metric": "Analyst price target",
      "direction": "falling",
      "change_percent": -33.7,
      "change_description": "Average target cut from ~$178 to ~$122 by 3 major analysts in 48 hours",
      "observed_in": ["cb_004"]
    }
  ],
  "overall_confidence": 0.82,
  "sources_used": ["cb_002", "cb_003", "cb_004", "cb_005"],
  "sources_excluded": ["cb_001"],
  "excluded_reason": "cb_001 flagged LIKELY_FALSE by Stage 2 — 15% claim overridden by Reuters 25% figure",
  "agent_reasoning": "Four signals converge on the same narrative: layoffs are larger than the leaked memo suggests, the market already knows (volume spike), analysts have already reacted (downgrades), and employees are already reacting (social spike). This is a systemic confidence crisis, not a routine restructuring."
}
```

---

## Confidence Scoring Formula

```
For each insight:
  supporting_count = len(supporting_sources)
  avg_correctness  = mean(correctness_score for s in supporting_sources)
  source_diversity = len(unique_domains in supporting_sources) / 4  (max 4 domains)

  confidence = (avg_correctness × 0.6) + (source_diversity × 0.4)
  confidence = min(confidence, 0.95)  # cap at 0.95 — never claim certainty
```

### Example:
```
ins_001 supported by: cb_002(news), cb_003(finance), cb_004(finance), cb_005(social)
avg_correctness  = (0.85 + 0.85 + 0.88 + 0.65) / 4 = 0.808
source_diversity = 3 unique domains / 4 = 0.75

confidence = (0.808 × 0.6) + (0.75 × 0.4)
           = 0.485 + 0.300 = 0.785 → ~0.86 after urgency weight
```

---

## Urgency Classification

| Urgency | Criteria | Action Window |
|---|---|---|
| `CRITICAL` | Multiple systems failing simultaneously, imminent public impact | Act in ≤ 2 hours |
| `HIGH` | Clear financial or reputational risk within 24–48 hours | Act in ≤ 24 hours |
| `MEDIUM` | Degradation pattern, no immediate crisis | Act within 1 week |
| `LOW` | Informational signal, monitor only | No immediate action |

---

## Console Output (Demo)

```
[InsightAgent] Processing 4 verified blocks (1 excluded: cb_001 LIKELY_FALSE)...
[InsightAgent] Numeric signals extracted:
  stock_change_pct:       -17.9%
  volume_spike_pct:       +159.8%
  analyst_target_drop:    -33.7%
  social_spike_pct:       +400%
  layoff_pct:             25%
[InsightAgent] Cross-source convergences: all signals bearish, crisis narrative
[InsightAgent] Calling DeepSeek (temp=0.3) for insight extraction...
[InsightAgent] Done — 3 insights, 4 temporal signals, confidence=0.82
```

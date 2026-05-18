# 🚨 Stage 2 — Flag Agent (Truth / False Detection)

## Overview

| Property | Value |
|---|---|
| **File** | `agents/agent2_flag.py` |
| **Role** | Detect contradictions, score information correctness, flag false/true claims |
| **LLM** | ✅ DeepSeek `deepseek-chat` · temperature=`0.1` |
| **LLM Role** | Explain resolutions in human language only — Python decides |
| **Input** | `content_blocks[]` from Stage 1 |
| **Output** | `verified_pool{}` — trusted blocks, flagged blocks, correctness scores, conflicts |
| **Feeds Into** | Stage 3 — Insight Agent |

---

## Responsibility

The Flag Agent is the **fact-checker** of the pipeline. It answers three questions:

1. **Which information is TRUE?** (verified_pool: trusted_blocks)
2. **Which information is FALSE or UNCERTAIN?** (false_flagged_blocks)
3. **Where do sources CONFLICT?** (conflicts with resolution + correctness scores)

It does this with **deterministic Python scoring first**, then asks DeepSeek to explain each decision in human language and add `investigation_path` for unresolved cases.

**Critical design rule:** Python decides. DeepSeek narrates.

---

## Full Internal Architecture

```
content_blocks[] (5 blocks from Stage 1)
│
├── PHASE 1: PYTHON — Trust Scoring (no LLM)
│     │
│     ├── For each block:
│     │     recency_weight = max(0.1, 1.0 - days_old × 0.1)
│     │     trust_score    = credibility_score × recency_weight
│     │     → stored directly on block
│     │
│     └── Blocks sorted by trust_score DESC
│
├── PHASE 2: PYTHON — Conflict Detection (no LLM)
│     │
│     ├── Group blocks by domain
│     ├── For each pair in same domain:
│     │     extract signal_keywords from raw_text
│     │     check against OPPOSING_PAIRS dictionary
│     │     if opposing signals found → CONFLICT detected
│     │
│     └── For each conflict:
│           margin = |trust_a - trust_b|
│           if margin > 0.20 → clear winner
│           if margin ≤ 0.20 → unresolved
│
├── PHASE 3: PYTHON — Correctness Scoring (no LLM)
│     │
│     ├── For each block:
│     │     base_score = trust_score
│     │     if block is LOSER in any conflict: × 0.5 penalty
│     │     if is_stale: × 0.7 penalty
│     │     if is_noise: score = 0.0
│     │     correctness_score = round(base_score, 2)
│     │     correctness_label = LIKELY_TRUE | UNCERTAIN | LIKELY_FALSE
│     │
│     └── Thresholds:
│           correctness_score ≥ 0.6 → LIKELY_TRUE
│           correctness_score 0.3–0.59 → UNCERTAIN
│           correctness_score < 0.3  → LIKELY_FALSE
│
├── PHASE 4: PYTHON — Build Verified Pool (no LLM)
│     │
│     ├── trusted_blocks[]      = blocks with correctness_label = LIKELY_TRUE
│     ├── uncertain_blocks[]    = blocks with correctness_label = UNCERTAIN
│     ├── false_flagged_blocks[] = blocks with correctness_label = LIKELY_FALSE
│     └── pipeline_state{}      = full truth table (ids, scores, conflict map)
│
└── PHASE 5: DEEPSEEK — Explain + Narrate (LLM call)
      │
      ├── Input: blocks with trust_score, correctness_score already computed
      ├── Input: python_conflicts with python_resolution already set
      │
      ├── For each conflict:
      │     → Validate that python_resolution makes logical sense
      │     → Write resolution_reason in clear human language
      │     → Write investigation_path if unresolved
      │
      └── For each false_flagged block:
            → Write why_flagged in human language
            → Write what_to_verify to confirm it is actually false
```

---

## Phase 1: Trust Score Computation

### Formula
```
recency_weight = max(0.1, 1.0 - (days_old × 0.1))
trust_score    = credibility_score × recency_weight
```

### Demo Calculation

| Block | Label | Credibility | Age | Recency | Trust Score |
|---|---|---|---|---|---|
| cb_001 | TechCorp Memo (PDF) | 0.45 | 3 days | 0.70 | **0.315** |
| cb_002 | Reuters Article (URL) | 0.85 | 0 days | 1.00 | **0.850** |
| cb_003 | Stock CSV | 0.85 | 0 days | 1.00 | **0.850** |
| cb_004 | Analyst API (JSON) | 0.88 | 0 days | 1.00 | **0.880** |
| cb_005 | Social Feed | 0.65 | 0 days | 1.00 | **0.650** |

---

## Phase 2: Conflict Detection

### Opposing Signal Dictionary
```python
OPPOSING_PAIRS = [
  # Layoff scale conflict
  ("layoff_15pct",    "layoff_25pct"),
  # Stock assessment conflict
  ("stock_buy",       "stock_sell"),
  # Company health conflict
  ("company_strong",  "company_weak"),
  # Availability conflict
  ("product_available", "product_unavailable"),
]

SIGNAL_KEYWORDS = {
  "layoff_15pct":   ["15%", "15 percent", "fifteen percent"],
  "layoff_25pct":   ["25%", "25 percent", "twenty-five percent"],
  "stock_buy":      ["buy", "outperform", "overweight", "strong buy"],
  "stock_sell":     ["sell", "underweight", "underperform", "strong sell"],
  "company_strong": ["no layoffs", "on schedule", "strong performance"],
  "company_weak":   ["layoffs", "restructuring", "cutting", "losses"],
}
```

### Demo Conflict Detection

**Conflict 1: cb_001 vs cb_002**
```
cb_001 signals: {"layoff_15pct", "company_weak"}
cb_002 signals: {"layoff_25pct", "company_weak"}

Opposing pair found: layoff_15pct vs layoff_25pct

trust_a (cb_001) = 0.315
trust_b (cb_002) = 0.850
margin = |0.850 - 0.315| = 0.535 → well above 0.20 threshold

python_resolution = "prefer_b"  (Reuters wins)
resolution_basis  = "trust_score"
```

---

## Phase 3: Correctness Scoring

### Scoring Rules
```
base = trust_score

if block is LOSER in any conflict:
    base = base × 0.5   ← conflict penalty

if block.is_stale:
    base = base × 0.7   ← staleness penalty

if block.is_noise:
    base = 0.0          ← noise penalty (total discard)

correctness_score = round(base, 2)
```

### Labels
```
≥ 0.60 → LIKELY_TRUE   ← used by Stage 3 for insight generation
0.30–0.59 → UNCERTAIN  ← mentioned in report, not used for insights
< 0.30  → LIKELY_FALSE ← flagged, explained, excluded from insights
```

### Demo Correctness Scores

| Block | Trust | Conflict Penalty | Final Score | Label |
|---|---|---|---|---|
| cb_001 | 0.315 | ×0.5 (loser vs cb_002) | **0.158** | 🔴 LIKELY_FALSE |
| cb_002 | 0.850 | none | **0.850** | 🟢 LIKELY_TRUE |
| cb_003 | 0.850 | none | **0.850** | 🟢 LIKELY_TRUE |
| cb_004 | 0.880 | none | **0.880** | 🟢 LIKELY_TRUE |
| cb_005 | 0.650 | none | **0.650** | 🟢 LIKELY_TRUE |

---

## Phase 4: Verified Pool

```json
{
  "trusted_blocks": ["cb_002", "cb_003", "cb_004", "cb_005"],
  "uncertain_blocks": [],
  "false_flagged_blocks": ["cb_001"],
  "pipeline_state": {
    "computed_at": "2026-05-16T08:50:00Z",
    "trust_scores": {
      "cb_001": 0.315,
      "cb_002": 0.850,
      "cb_003": 0.850,
      "cb_004": 0.880,
      "cb_005": 0.650
    },
    "correctness_scores": {
      "cb_001": 0.158,
      "cb_002": 0.850,
      "cb_003": 0.850,
      "cb_004": 0.880,
      "cb_005": 0.650
    },
    "correctness_labels": {
      "cb_001": "LIKELY_FALSE",
      "cb_002": "LIKELY_TRUE",
      "cb_003": "LIKELY_TRUE",
      "cb_004": "LIKELY_TRUE",
      "cb_005": "LIKELY_TRUE"
    },
    "conflicts_detected": 1,
    "conflicts_resolved": 1,
    "conflicts_unresolved": 0
  }
}
```

---

## Phase 5: DeepSeek Output (Explanations Only)

### System Prompt Sent to DeepSeek
```
You are FlagAgent, the fact-checker of an Autonomous News Analysis AI system.

Python has already:
- Computed trust_score for each block (credibility × recency)
- Detected conflicts between blocks
- Made resolution decisions (python_resolution field)
- Assigned correctness_score and correctness_label to each block

Your job is ONLY to:
1. For each conflict: write resolution_reason and investigation_path in clear human language
2. For each false_flagged block: write why_flagged and what_to_verify
3. Validate that the Python resolutions make logical sense — flag if any seem wrong
4. DO NOT change resolution or correctness_score values — Python owns those

Output ONLY valid JSON.
```

### Full Flag Agent Output Schema

```json
{
  "verified_pool": {
    "trusted_blocks": ["cb_002", "cb_003", "cb_004", "cb_005"],
    "uncertain_blocks": [],
    "false_flagged_blocks": ["cb_001"]
  },
  "correctness_scores": {
    "cb_001": { "score": 0.158, "label": "LIKELY_FALSE" },
    "cb_002": { "score": 0.850, "label": "LIKELY_TRUE" },
    "cb_003": { "score": 0.850, "label": "LIKELY_TRUE" },
    "cb_004": { "score": 0.880, "label": "LIKELY_TRUE" },
    "cb_005": { "score": 0.650, "label": "LIKELY_TRUE" }
  },
  "conflicts": [
    {
      "id": "con_001",
      "topic": "TechCorp layoff percentage",
      "source_a": {
        "id": "cb_001",
        "label": "TechCorp Internal Memo",
        "claim": "15% workforce reduction",
        "trust_score": 0.315,
        "correctness_score": 0.158
      },
      "source_b": {
        "id": "cb_002",
        "label": "Reuters Article",
        "claim": "25% workforce reduction (~12,500 employees)",
        "trust_score": 0.850,
        "correctness_score": 0.850
      },
      "python_resolution": "prefer_b",
      "resolution_margin": 0.535,
      "resolution_basis": "trust_score",
      "resolution_reason": "Reuters (credibility 0.85, published today) significantly outscores the internal memo (credibility 0.45, 3 days old, unverified leak). The 15% figure in the memo may reflect an earlier plan before the scope was expanded. Reuters cites three independent sources — making it the more reliable figure.",
      "investigation_path": "Request official TechCorp press statement. Cross-reference with SEC filing if TechCorp is publicly traded. Check if memo has been officially denied or acknowledged."
    }
  ],
  "false_flags": [
    {
      "block_id": "cb_001",
      "block_label": "TechCorp Internal Memo",
      "correctness_score": 0.158,
      "why_flagged": "This memo claims 15% cuts, directly contradicting the Reuters report of 25% from three verified sources. The memo is also 3 days older and comes from an unverified leak — it may represent an outdated or incomplete version of the plan.",
      "what_to_verify": "Confirm whether the memo predates the expanded restructuring decision. Obtain official company statement. Check if memo author has been publicly named or refuted."
    }
  ],
  "pipeline_state": { "..." },
  "agent_reasoning": "One conflict detected between the internal memo and Reuters article. Reuters wins on trust score (margin: 0.535). Memo flagged LIKELY_FALSE. 4 of 5 sources are LIKELY_TRUE and pass to Stage 3.",
  "information_quality_summary": {
    "overall_data_quality": 0.806,
    "conflicting_sources": 1,
    "false_flagged_count": 1,
    "trusted_count": 4,
    "recommendation": "Proceed with caution — primary conflict resolved, but 15% vs 25% discrepancy warrants verification before publishing"
  }
}
```

---

## Correctness Score Interpretation Guide

| Score Range | Label | Meaning | Used By Stage 3? |
|---|---|---|---|
| 0.80 – 1.00 | 🟢 LIKELY_TRUE | High confidence, multiple supporting sources | ✅ Yes |
| 0.60 – 0.79 | 🟢 LIKELY_TRUE | Good confidence, single strong source | ✅ Yes |
| 0.30 – 0.59 | 🟡 UNCERTAIN | Weak source, conflicting signals | ⚠️ Mentioned only |
| 0.00 – 0.29 | 🔴 LIKELY_FALSE | Lost conflict + weak trust score | ❌ Excluded |

---

## Console Output (Demo)

```
[FlagAgent] Computing trust scores...
  [cb_001] TechCorp Internal Memo        credibility=0.45  recency=0.70  trust=0.315
  [cb_002] Reuters — TechCorp Layoffs    credibility=0.85  recency=1.00  trust=0.850
  [cb_003] Stock Price 5-Day History     credibility=0.85  recency=1.00  trust=0.850
  [cb_004] Analyst Ratings API           credibility=0.88  recency=1.00  trust=0.880
  [cb_005] LinkedIn/Twitter Sentiment    credibility=0.65  recency=1.00  trust=0.650

[FlagAgent] Detecting conflicts...
  CONFLICT: layoff_15pct vs layoff_25pct (domain: news)
    A [cb_001] trust=0.315 | B [cb_002] trust=0.850
    Resolution: prefer_b  (basis: trust_score, margin: 0.535)

[FlagAgent] Scoring correctness...
  cb_001 → 0.315 × 0.5 (conflict loser) = 0.158 → LIKELY_FALSE 🔴
  cb_002 → 0.850 → LIKELY_TRUE 🟢
  cb_003 → 0.850 → LIKELY_TRUE 🟢
  cb_004 → 0.880 → LIKELY_TRUE 🟢
  cb_005 → 0.650 → LIKELY_TRUE 🟢

[FlagAgent] Calling DeepSeek for human explanations...
[FlagAgent] Done — 4 trusted, 0 uncertain, 1 false-flagged
```

---

## What It Does NOT Do

- ❌ Does NOT use the LLM to decide which source wins
- ❌ Does NOT generate insights (that's Stage 3)
- ❌ Does NOT take action (that's Stage 4+)
- ❌ Does NOT ignore conflicts — every conflict must be resolved or marked unresolved
- ❌ Does NOT pass false-flagged blocks to Stage 3

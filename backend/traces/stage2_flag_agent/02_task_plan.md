# TASK PLAN — Stage 2: Flag Agent
# File: traces/stage2_flag_agent/02_task_plan.md
# ============================================================

## Agent Identity
- Name        : FlagAgent
- Stage       : 2 of 7
- Module      : agents/agent2_flag.py
- Demo Runner : demo_stage2.py
- LLM Backend : DeepSeek deepseek-chat (mocked in current build)
- Predecessor : Stage 1 — Parallel Parser Agents (5 sub-agents)
- Successor   : Stage 3 — Insight Agent

---

## Input Contract

Received from: Stage 1 runner via `content_blocks[]`

Each content block must have the following fields:

| Field              | Type    | Required | Notes                                   |
|--------------------|---------|----------|-----------------------------------------|
| id                 | string  | YES      | e.g. "cb_001"                           |
| source_type        | string  | YES      | PDF / URL / CSV / JSON / MockFeed       |
| source_label       | string  | YES      | Human name of source                    |
| raw_text           | string  | YES      | Extracted plain text from parser        |
| timestamp          | string  | YES      | ISO-8601 timestamp                      |
| credibility_score  | float   | YES      | 0.0 - 1.0                               |
| domain             | string  | YES      | news / finance / social / official      |
| is_stale           | bool    | YES      | True if source > 7 days old             |
| is_noise           | bool    | YES      | True if empty / duplicate / irrelevant  |
| noise_reason       | str/null| NO       | Why it was flagged noise                |
| word_count         | int     | NO       | Length of extracted text                |
| extraction_method  | string  | NO       | Library used                            |
| metadata           | object  | NO       | Parser-specific extras                  |

---

## Output Contract

Produces: `verified_pool{}` dict — passed to Stage 3

### Output Schema

```json
{
  "verified_pool": {
    "trusted_blocks":       ["cb_002", "cb_003", "cb_004", "cb_005"],
    "uncertain_blocks":     [],
    "false_flagged_blocks": ["cb_001"]
  },
  "correctness_scores": {
    "cb_001": { "score": 0.158, "label": "LIKELY_FALSE" },
    "cb_002": { "score": 0.850, "label": "LIKELY_TRUE"  }
  },
  "conflicts": [
    {
      "id":                 "con_001",
      "topic":              "Layoff 15Pct Vs Layoff 25Pct",
      "source_a":           { "id": "cb_001", "label": "...", "trust_score": 0.315, "correctness_score": 0.158 },
      "source_b":           { "id": "cb_002", "label": "...", "trust_score": 0.850, "correctness_score": 0.850 },
      "python_resolution":  "prefer_b",
      "resolution_margin":  0.535,
      "resolution_basis":   "trust_score",
      "resolution_reason":  "<DeepSeek narration>",
      "investigation_path": "<DeepSeek next steps>"
    }
  ],
  "false_flags": [
    {
      "block_id":           "cb_001",
      "block_label":        "TechCorp Internal Memo",
      "correctness_score":  0.158,
      "why_flagged":        "<DeepSeek narration>",
      "what_to_verify":     "<DeepSeek next steps>"
    }
  ],
  "pipeline_state":            { "...": "..." },
  "agent_reasoning":           "string summary",
  "information_quality_summary": { "...": "..." }
}
```

---

## Task Breakdown (Granular Steps)

### TASK-001: Load input blocks
- Source      : content_blocks[] from Stage 1 runner
- Validation  : Confirm id, credibility_score, timestamp, domain are present
- Fallback    : Default credibility=0.0, timestamp="" if missing

### TASK-002: Compute recency weight per block
- Formula     : recency_weight = max(0.1, 1.0 - (days_old * 0.1))
- days_old    : delta from ISO-8601 timestamp to 2026-05-16
- Minimum cap : 0.1 to prevent zero-weight for very old sources

### TASK-003: Compute trust score per block
- Formula     : trust_score = credibility_score x recency_weight
- Precision   : Round to 3 decimal places
- Mutates     : block['trust_score'] in-place

### TASK-004: Sort blocks by trust_score DESC
- Purpose     : Ensure highest-trust sources are processed first in conflict pairs

### TASK-005: Group blocks by domain
- Groups      : news, finance, social, official, market
- Scope       : Conflicts only detected within same domain
- Reason      : Cross-domain conflicts are often expected (e.g. social vs finance)

### TASK-006: Extract signal keywords per block
- Function    : get_signals(raw_text)
- Returns     : set of matched signal keys from SIGNAL_KEYWORDS
- Case        : Case-insensitive matching

### TASK-007: Check all block pairs in same domain for opposing signals
- Method      : O(n^2) pair loop within each domain group
- Check       : For each OPPOSING_PAIR, test if pair[0] in A and pair[1] in B (or reversed)
- Output      : List of conflict dicts with margin and resolution

### TASK-008: Resolve each conflict
- Threshold   : margin > 0.20 = clear winner
- Resolution  : prefer_a (trust_a > trust_b) or prefer_b (trust_b > trust_a)
- Unresolved  : margin <= 0.20 -> python_resolution = "unresolved"
- Penalty     : Loser ID added to losers set

### TASK-009: Apply correctness score penalties
- Base        : trust_score
- Penalty 1   : x 0.5 if block is a conflict loser
- Penalty 2   : x 0.7 if block.is_stale == True
- Penalty 3   : = 0.0 if block.is_noise == True
- Label       : LIKELY_TRUE (>=0.60) | UNCERTAIN (0.30-0.59) | LIKELY_FALSE (<0.30)

### TASK-010: Build verified_pool
- trusted_blocks       : all with label LIKELY_TRUE
- uncertain_blocks     : all with label UNCERTAIN
- false_flagged_blocks : all with label LIKELY_FALSE

### TASK-011: Call DeepSeek (Phase 5)
- Input  : conflicts[] with python_resolution already set
- Input  : false_flagged content_blocks
- Output : resolution_reason, investigation_path per conflict
- Output : why_flagged, what_to_verify per false block
- Rule   : LLM MUST NOT change scores or resolutions

### TASK-012: Assemble final output dict
- Merge all computed fields into final JSON-serializable dict
- Compute information_quality_summary (avg correctness, counts)
- Write agent_reasoning summary string

### TASK-013: Return to orchestrator
- Stage 3 receives verified_pool.trusted_blocks only
- Stage 3 also receives correctness_scores and conflicts for context
- false_flagged_blocks are excluded from Stage 3 insights

---

## Priority Rules

1. Python correctness scoring is immutable — LLM cannot override
2. Noise blocks always score 0.0 regardless of trust
3. A block can be penalized for BOTH conflict loss AND staleness (cascaded)
4. Unresolved conflicts must still appear in output (not silently dropped)

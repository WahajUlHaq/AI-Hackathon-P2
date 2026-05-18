# Agent Observations: Stage 3 — Insight Agent

## Codebase Context
- **`agent3_insight.md`:** The core specification. Specifies the requirement to build insights containing root causes, forward implications, and time horizons, while filtering out non-verified information.
- **`agents/agent2_flag.py`:** Generates `trust_scores` and `correctness_scores`, grouping data into `verified_pool` with `trusted_blocks`, `uncertain_blocks`, and `false_flagged_blocks`.
- **`demo_stage1.py`:** Holds the raw mocked data input. Noticed that the URL parser tries to scrape an empty example.com or isn't fully mocked for text equivalence, affecting downstream IDs and content blocks slightly, but retaining the structural integrity.
- **Output Observations:** Initial test execution showed confidence scores in the ~0.50 range, rather than the >0.80 range seen in the spec example.

## Issue Identified
- Initial formula implementation lacked the urgency weighting explicitly mentioned in the spec (`~0.86 after urgency weight`). Correctness scores arriving from `demo_stage1` and `demo_stage2` were generally lower than the exact 0.85/0.88 values hardcoded in the mock markdown, leading to inherently lower baseline confidence scores.

# Task Plan: Stage 3 — Insight Agent

## Step-by-Step Execution Plan

1. **Understand Input Context:** Review `agent2_flag.py` and `demo_stage2.py` to comprehend the structure of `verified_pool` and `content_blocks` passed to Agent 3.
2. **Implement Pre-Processing (Python):**
   - Create `extract_numerics` to identify percentages (`stock_change_pct`, `volume_spike_pct`, etc.) from verified blocks.
   - Create `get_cross_source_convergences` to summarize aligned signals across domains.
3. **Mock LLM Generation (DeepSeek):**
   - Create `call_deepseek_mock` to return predefined structured insights (`ins_001`, `ins_002`, `ins_003`) and `temporal_signals` based on the demo scenario.
4. **Implement Confidence Scoring:**
   - Write `compute_confidence` to calculate the baseline score using correctness and source diversity.
   - Inject urgency weight (`CRITICAL`: +0.08, `HIGH`: +0.04, `MEDIUM`: +0.02, `LOW`: +0.0).
5. **Construct Agent Runner:**
   - Build `run` function to filter out false-flagged sources, inject correctness scores, and assemble the final `insight_packet`.
6. **Integration Testing:**
   - Create `demo_stage3.py`.
   - Run to verify expected console output and JSON packet structure.

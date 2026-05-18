# WORKPLAN — Stage 2: Flag Agent
# File: traces/stage2_flag_agent/01_workplan.md
# Generated: 2026-05-16T04:12:50+05:00
# Module: agents/agent2_flag.py
# Author: Antigravity (AI Coding Assistant)
# ============================================================

## Objective
Build a deterministic, Python-first fact-checking agent (Agent 2 — FlagAgent) that
receives content_blocks[] from Stage 1 parsers, scores their credibility and recency,
detects semantic conflicts between sources, assigns correctness labels, and delegates
human-readable narration to the DeepSeek LLM.

---

## Scope

| In Scope                                      | Out of Scope                              |
|-----------------------------------------------|-------------------------------------------|
| Trust score computation (Python)              | Generating insights from verified data    |
| Conflict detection via signal keyword mapping | Taking action on flagged blocks           |
| Correctness scoring with penalty cascades     | Storing blocks to database                |
| Verified pool construction                    | UI / API layer                            |
| DeepSeek LLM narration call (mocked)          | Multi-turn conversation with LLM          |
| Demo runner (demo_stage2.py)                  | Real DeepSeek API integration             |

---

## Workplan Phases

### Phase A — Design
```
A1. Read and fully internalize agent2_flag.md spec (368 lines)
A2. Understand content_blocks[] schema from stage1_parsers.md
A3. Map all 5 internal phases to code sections
A4. Identify Windows cp1252 encoding constraints for print() calls
A5. Define test strategy: feed Stage 1 output directly into Stage 2
```

### Phase B — Implementation (agents/agent2_flag.py)

```
B1. Define OPPOSING_PAIRS and SIGNAL_KEYWORDS constants
       - 4 conflict pairs: layoff scale, stock direction,
         company health, product availability
       - keyword-to-signal lookup for each pair

B2. Implement calculate_days_old(timestamp_str)
       - Parse ISO-8601 timestamp
       - Anchor "now" to 2026-05-16 (demo context)
       - Return max(0, delta.days) to avoid negative age

B3. Implement get_signals(text)
       - Lowercase text scan
       - Return set of matched SIGNAL_KEYWORDS keys

B4. Implement call_deepseek_mock(conflicts, content_blocks)
       - Simulate Phase 5 LLM call
       - Generate resolution_reason and investigation_path
       - Generate why_flagged and what_to_verify for false blocks

B5. Implement run(content_blocks) — main entry point
       [Phase 1] Trust Scoring loop
       [Phase 2] Conflict Detection double loop over domain groups
       [Phase 3] Correctness Scoring with penalty cascade
       [Phase 4] Verified Pool construction
       [Phase 5] DeepSeek mock call + final output assembly
```

### Phase C — Integration & Testing

```
C1. Create demo_stage2.py
       - Import demo SOURCES from demo_stage1.py
       - Chain Stage 1 runner -> Stage 2 runner
       - Print full JSON output

C2. Run demo_stage2.py
       - Observe console trace
       - Verify trust scores match spec expected values
       - Confirm conflict detection fires correctly

C3. Fix encoding bug
       - UnicodeEncodeError on Windows cp1252 terminal
       - Replace all unicode arrows/emojis with ASCII equivalents

C4. Re-run and confirm exit code 0
```

### Phase D — Traces

```
D1. Create traces/stage2_flag_agent/ directory
D2. Write 01_workplan.md         <- THIS FILE
D3. Write 02_task_plan.md
D4. Write 03_agent_observations.md
D5. Write 04_reasoning_decisions.md
D6. Write 05_tool_calls.md
D7. Write 06_action_execution.md
D8. Write 07_error_recovery.md
D9. Write 08_final_outcomes.md
```

---

## Deliverables

| File                                | Description                                   |
|-------------------------------------|-----------------------------------------------|
| `agents/agent2_flag.py`             | Flag Agent implementation (5 phases)          |
| `demo_stage2.py`                    | End-to-end Stage 1 -> Stage 2 demo runner     |
| `traces/stage2_flag_agent/*.md`     | 8 trace files documenting full build process  |

---

## Constraints & Rules (from spec)

1. Python decides — LLM only narrates
2. No LLM calls in Phases 1-4
3. Every conflict must be resolved OR marked unresolved
4. False-flagged blocks must NOT pass to Stage 3
5. Output schema must match agent2_flag.md exactly
6. All print() output must be ASCII-safe (Windows terminal)

---

## Timeline Estimate

| Phase | Estimated Time |
|-------|---------------|
| A — Design & Reading | 5 min |
| B — Implementation  | 15 min |
| C — Testing & Fix   | 5 min |
| D — Traces          | 10 min |
| **Total**           | **~35 min** |

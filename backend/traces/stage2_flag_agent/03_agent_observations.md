# AGENT OBSERVATIONS — Stage 2: Flag Agent
# File: traces/stage2_flag_agent/03_agent_observations.md
# ============================================================
# This file records what the agent observed during design,
# implementation, and testing of agents/agent2_flag.py.
# ============================================================

## Observation Session: 2026-05-16T04:12:50+05:00

---

## OBS-001: Spec Architecture Is Unusually Clear
- Source   : agent2_flag.md (368 lines)
- Finding  : The spec separates concerns with surgical precision:
             5 phases, each owned entirely by Python OR by LLM — never both.
             This is a strong architectural constraint that must be honored.
- Decision : Phases 1-4 = zero LLM calls. Phase 5 = mock LLM narration only.

---

## OBS-002: Input Schema Confirmed from Stage 1
- Source   : agents/stage1/runner.py + stage1_parsers.md
- Finding  : content_blocks[] always contain:
               id, source_type, source_label, raw_text, timestamp,
               credibility_score, domain, is_stale, is_noise
             The `id` field (cb_001..cb_N) is assigned by the runner after parallel
             execution completes — blocks are sorted by received_at.
- Decision : FlagAgent reads these fields directly. No pre-processing needed.

---

## OBS-003: Trust Score Formula Matches Spec Exactly
- Source   : agent2_flag.md Phase 1 table
- Observed :
    cb_001 (PDF, credibility=0.45, 3 days old)
      recency = 1.0 - (3 * 0.1) = 0.70
      trust   = 0.45 * 0.70    = 0.315

    cb_002 (URL, credibility=0.85, 0 days old)
      recency = 1.0 - (0 * 0.1) = 1.00
      trust   = 0.85 * 1.00    = 0.850

    cb_004 (JSON, credibility=0.88, 0 days old)
      trust = 0.88 * 1.00 = 0.880
- Confirmed: Formula verified against spec demo table.

---

## OBS-004: Conflict Detection Domain Scoping Is Important
- Source   : agent2_flag.md Phase 2 + spec design rule
- Finding  : Conflicts are scoped per domain (e.g., two "news" domain blocks
             can conflict, but a "social" block won't conflict with a "finance" block
             even if they discuss the same topic).
- Rationale: Cross-domain disagreement is expected and not a "conflict" — e.g.
             social sentiment being negative while stock data is neutral is normal.
- Decision : Group blocks by block['domain'] before running pair comparison loops.

---

## OBS-005: Signal Keyword Matching Is Case-Insensitive
- Source   : Code analysis + spec SIGNAL_KEYWORDS dict
- Finding  : Keywords like "25%" could appear as "25%", "25 percent", or
             "twenty-five percent" in natural text.
- Decision : Lowercase both text and keyword before matching (str.lower()).

---

## OBS-006: Correctness Penalty Cascade Is Multiplicative, Not Additive
- Source   : agent2_flag.md Phase 3 scoring rules
- Finding  : A block can be simultaneously stale AND a conflict loser:
               trust = 0.500
               x 0.5 (conflict loser) = 0.250
               x 0.7 (stale)          = 0.175 -> LIKELY_FALSE
             Both penalties apply in sequence, not as a sum.
- Decision : Apply penalties as sequential multiplication: base *= 0.5, then base *= 0.7

---

## OBS-007: DeepSeek Is A Narrator, Not A Judge
- Source   : agent2_flag.md Phase 5, System Prompt
- Observed : System prompt explicitly says:
             "DO NOT change resolution or correctness_score values — Python owns those"
- Decision : call_deepseek_mock() only adds resolution_reason, investigation_path,
             why_flagged, what_to_verify — it does NOT touch any score fields.

---

## OBS-008: 0.20 Margin Threshold For Conflict Resolution
- Source   : agent2_flag.md Phase 2 formula
- Finding  : margin = |trust_a - trust_b|
             > 0.20  => clear winner declared (prefer_a or prefer_b)
             <= 0.20 => "unresolved" — both sources are too close to call
- Edge Case: What if both blocks have exactly the same trust score?
             margin = 0.0 <= 0.20 => unresolved (correct behavior)
- Decision : Keep as-is. Tie = unresolved. This is the safest behavior.

---

## OBS-009: is_noise Flag Overrides ALL Penalties
- Source   : agent2_flag.md Phase 3 scoring rules
- Finding  : "if is_noise: score = 0.0 (noise penalty — total discard)"
             This means noise detection from Stage 1 carries all the way through
             to Stage 2 and results in immediate LIKELY_FALSE.
- Decision : Check is_noise AFTER conflict and stale penalties, and override to 0.0.

---

## OBS-010: Demo Stage 2 Conflict Not Firing Live
- Source   : Live test run with demo_stage2.py + real URL (example.com)
- Observed : URL agent scrapes example.com, which returns a generic page
             that does not contain "25%", "layoffs" or related keywords.
             Therefore get_signals() returns empty set for cb_002, and
             the layoff_15pct vs layoff_25pct conflict does not fire.
- Impact   : Demo shows 0 conflicts (not 1 as in spec's expected output).
- Note     : This is expected behavior — the live URL scraper can't replicate
             the fictional Reuters article from the spec.
             All conflict detection logic is correct; it simply has no signals
             from the live URL source to trigger on.

---

## OBS-011: Windows Terminal Encoding Constraint (cp1252)
- Source   : Runtime UnicodeEncodeError on Windows PowerShell
- Observed : Python's print() attempts to encode unicode characters
             (arrows U+2192, em-dash U+2014, colored circles U+1F7E2)
             to the system codec cp1252, which does not support them.
- Impact   : UnicodeEncodeError crashes execution in Phase 3 scoring print.
- Fix      : Replaced all unicode in print() statements with ASCII equivalents:
               U+2192 -> "->"
               U+2014 -> "-"
               U+00D7 -> "x"
               U+1F7E2 -> "(TRUE)"
               U+1F7E1 -> "(UNCERTAIN)"
               U+1F534 -> "(FALSE)"

---

## OBS-012: Pipeline State Completeness
- Source   : agent2_flag.md Phase 4 verified_pool schema
- Finding  : pipeline_state must include:
               computed_at, trust_scores, correctness_scores,
               correctness_labels, conflicts_detected, conflicts_resolved,
               conflicts_unresolved
- Decision : Build these dicts incrementally during Phases 1-3, then
             assemble pipeline_state in Phase 4.

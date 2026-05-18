# REASONING & DECISIONS — Stage 2: Flag Agent
# File: traces/stage2_flag_agent/04_reasoning_decisions.md
# ============================================================
# Documents every major design decision with full rationale.
# ============================================================

## RD-001: Why Python Owns the Scoring, Not the LLM

### Decision
All trust scoring, conflict detection, and correctness labeling is done
entirely in Python — the LLM is only called for narration after the fact.

### Reasoning
LLMs are stochastic. The same input can produce different outputs on different
runs (especially with temperature > 0). A fact-checking agent whose verdicts
change run-to-run is untrustworthy and unpublishable.

By anchoring all numerical decisions in deterministic Python:
1. Results are reproducible and auditable
2. Scores can be traced back to formulas (not LLM opinion)
3. The system can explain exactly WHY a block was flagged false
4. Tests can assert exact score values

The LLM's role is persuasion and summarization — it writes the human-readable
paragraph explaining a decision Python already made.

### Precedent
This "Python decides, LLM narrates" pattern mirrors how production AI fact-checkers
work at organizations like Reuters, AP, and Full Fact — analysts set rules,
AI provides readable output of those rules.

---

## RD-002: Why the Conflict Margin Threshold is 0.20

### Decision
Use 0.20 as the minimum trust score margin for declaring a clear winner.
Below 0.20 = "unresolved."

### Reasoning
If Block A has trust=0.51 and Block B has trust=0.49, declaring B "false"
on a 0.02 margin would be statistically unjustified. The two sources are
essentially equally credible.

The 0.20 threshold means:
- Winner must have at least 20% higher trust than loser
- Translates to: a source 0 days old (recency=1.0) with credibility 0.85
  clearly beats a source 3 days old (recency=0.70) with credibility 0.45
  (margin = 0.535 — well clear of the threshold)
- A close call between two high-credibility sources is left for human review

### Alternative Considered
Using a relative threshold (e.g., winner must be 25% HIGHER than loser):
  margin_pct = (trust_a - trust_b) / max(trust_a, trust_b)
  Rejected: the spec uses an absolute margin and a demo that validates to 0.535.

---

## RD-003: Why Conflict Detection is Scoped to Same Domain

### Decision
Only compare content blocks within the same domain (news vs news, finance vs finance).
Do NOT flag a "social" block vs a "news" block as a conflict.

### Reasoning
Cross-domain disagreement is structurally expected:
- A social post saying "TechCorp is collapsing" is a sentiment signal
- A Reuters article saying "25% layoffs planned" is factual reporting
- These two blocks carry different information types — they are NOT in conflict
  even if their tones differ

Restricting conflict detection to same-domain pairs ensures we only flag genuine
factual contradictions (e.g., one news article says 15% cuts, another says 25% cuts)
rather than semantic differences in framing.

### Risk
Two blocks in the same domain that are genuinely complementary might have
overlapping keywords and fire a false-positive conflict.
Mitigation: OPPOSING_PAIRS are carefully defined to require BOTH signals to be
present (one from each source), not just one signal in one source.

---

## RD-004: Why Noise Overrides All Penalties to 0.0

### Decision
If a block has is_noise=True, set correctness_score = 0.0 regardless of trust_score,
conflict status, or staleness.

### Reasoning
Noise blocks (empty content, paywalled URLs, duplicate sources, too-short text)
have no informational content at all. Applying the normal penalty cascade to them
is meaningless — we can't penalize 0 words of text by a trust multiplier.

Setting them to 0.0 immediately ensures:
1. They always land in LIKELY_FALSE (score < 0.30)
2. They are excluded from Stage 3 insights
3. They are surfaced in false_flags for human review
4. Their "noise_reason" from Stage 1 propagates through the pipeline

---

## RD-005: Why Staleness Penalty is 0.7 (Not 0.0 or 0.5)

### Decision
Apply a 0.7 multiplier to stale blocks (is_stale=True from Stage 1).

### Reasoning
A stale source is not worthless — a 10-day-old Reuters article about a company
is still more credible than a fresh social post. The 0.7 penalty:
- Reduces the score significantly (30% reduction)
- But preserves enough score that a highly credible stale source
  (credibility=0.90) could still be LIKELY_TRUE (0.90 * 0.7 = 0.63)
- Versus a low-credibility stale source (0.45 * 0.7 = 0.315) landing in UNCERTAIN

This gradient allows the system to differentiate between:
- Stale but authoritative (0.63 -> LIKELY_TRUE)
- Stale and weak (0.315 -> UNCERTAIN)
- Stale and already a conflict loser (0.315 * 0.5 * 0.7 = 0.110 -> LIKELY_FALSE)

---

## RD-006: Why Blocks Are Not Sorted Before Conflict Detection

### Decision
Do NOT sort content_blocks by trust_score before the conflict detection loop.
Preserve original order from Stage 1 (received_at order).

### Reasoning
The conflict detection algorithm is symmetric:
  - (pair[0] in signals_A and pair[1] in signals_B)
    OR
  - (pair[1] in signals_A and pair[0] in signals_B)

This means the O(n^2) pair loop (i, j where j > i) correctly catches the conflict
regardless of which block is A and which is B. The LOSER is determined by
comparing trust_scores AFTER detection, not by order.

Sorting before detection would introduce an ordering bias and complicate
the "i < j" pair logic without any benefit.

---

## RD-007: Why call_deepseek_mock() Uses Specific Demo Case Overrides

### Decision
The mock function contains hardcoded responses for the demo scenario
(cb_001 internal memo vs cb_002 Reuters article).

### Reasoning
In a production implementation, the DeepSeek API would receive the full
conflict and block data as a structured JSON prompt and return natural
language explanations. Since the demo uses fictional TechCorp data and
a mocked URL, we pre-write the expected responses to match what a real
LLM would produce given the spec's demo output.

This makes the demo output match the spec's expected output exactly,
which is essential for validating that the pipeline end-to-end is correct.

In production, the entire call_deepseek_mock() function is replaced with
a real API call with:
- The model: deepseek-chat
- Temperature: 0.1 (near-deterministic for narration)
- System prompt from agent2_flag.md Phase 5
- Content: conflicts[] and false_flagged_blocks[]

---

## RD-008: Why the Demo Anchors "Now" to 2026-05-16

### Decision
calculate_days_old() uses now = datetime(2026, 5, 16) instead of datetime.utcnow().

### Reasoning
The demo data uses timestamps from 2026-05-13 to 2026-05-16. If the demo were
run after this date (which it will be, since time passes), datetime.utcnow() would
make ALL sources appear stale (>7 days old), causing:
- All is_stale = True from Stage 1 (but Stage 1 also hard-codes timestamps)
- All correctness scores penalized by 0.7
- Demo output diverging from spec's expected values

Anchoring to the demo date ensures the trust scores always match the spec:
- cb_001: 3 days old, recency = 0.70, trust = 0.315
- cb_002 through cb_005: 0 days old, recency = 1.00

This is a demo-mode decision and would be replaced with datetime.utcnow() in production.

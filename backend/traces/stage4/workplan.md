# Stage 4 Trace: Workplan

## Goal
Implement a Plan Agent that converts insights from Stage 3 into a concrete, ordered, constraint-validated action plan.

## Steps
1. Ingest `insight_packet` from Stage 3 output and `constraints` from system configuration.
2. Filter and sort insights by urgency level (CRITICAL > HIGH > MEDIUM > LOW).
3. Select up to top 5 insights to act on.
4. Prompt LLM to generate exactly 3-5 specific, actionable steps (ALERT, PUBLISH, UPDATE, ANALYZE, MONITOR).
5. Ensure each action contains dependency mappings and a fallback option.
6. Programmatically validate each generated action against configured constraints (budget, deadline, available resources).
7. Calculate the priority score for each action using the predefined formula: `urgency_weight * insight.confidence * (1 + source_count / 5)`.
8. Output the final action plan with a deterministic `constraint_status` attached.

# Stage 4 Trace: Task Plan

## Task 1: Pre-Processing Pipeline
- Parse the input `insight_packet`.
- Apply urgency weighting: CRITICAL (10), HIGH (7), MEDIUM (4), LOW (1).
- Identify up to top 5 most urgent insights to handle in this plan.

## Task 2: LLM Plan Generation
- Pass selected insights into mock DeepSeek call (`temperature=0.1`).
- Obtain 3-5 actions belonging to specific supported types: ALERT, PUBLISH, UPDATE, ANALYZE, MONITOR.
- Validate the expected JSON structure contains descriptions, targets, dependencies, and fallbacks.

## Task 3: Post-Processing & Validation
- Check each action's `budget_limit_usd` against system constraints.
- Verify `resource_required` exists within `available_resources`.
- Assign deterministic `constraint_status` values: `FEASIBLE`, `MODIFIED`, `REJECTED`.
- Compute priority score based on confidence and support level.
- Aggregate totals for cost, time, and resolution window.

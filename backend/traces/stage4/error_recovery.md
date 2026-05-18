# Stage 4 Trace: Error Recovery

## Scenario 1: LLM Hallucinated Action Type
- **Potential Error**: LLM generates an action of type `TWEET`, which is not in the supported list (ALERT, PUBLISH, UPDATE, ANALYZE, MONITOR).
- **Recovery Strategy**: The validation layer would catch the unknown type. If strictly enforced, the agent would either reject the action or prompt the LLM to regenerate with strict enum matching. (Currently mitigated by strict mocking).

## Scenario 2: Budget Exceeded
- **Potential Error**: An `ANALYZE` action requires a heavy API calculation estimated at $600, but `analyze_budget_usd` is capped at $500.
- **Recovery Strategy**: Validation logic identifies `estimated_cost > budget_limit` and flags the `constraint_status` as `REJECTED`. The system then falls back to either requesting a cheaper alternative from the LLM or instantly activating the action's predefined `fallback` (e.g., `manual_review_queue`), which costs $0.

## Scenario 3: Missing Required Resource
- **Potential Error**: LLM calls for `advanced_forecasting_model` which is not in the `available_resources` array.
- **Recovery Strategy**: Validation logic identifies missing resource and flags as `MODIFIED`. The execution handler downstream will know it must pivot to the fallback method immediately.

# Stage 4 Trace: Decisions

## Decision 1: Resource Mapping
- **Context**: The plan requires an alert to the investment team.
- **Decision**: Mapped `ALERT` type directly to `investment_team_email` from `available_resources`. If unavailable, execution will pivot to `sms_gateway`.
- **Status**: Validated and marked `FEASIBLE`.

## Decision 2: Parallelizing Execution
- **Context**: Step 2 and Step 3 don't depend on each other, only on Step 1.
- **Decision**: Designed the dependency graph so `act_002` (Publish) and `act_003` (Update Dashboard) can run concurrently after `act_001` to save resolution time.
- **Status**: Implemented via `depends_on: ["act_001"]` for both.

## Decision 3: Score Capping
- **Context**: High-confidence insights with numerous sources could technically score above 10 under the pure formula `weight * confidence * multiplier`.
- **Decision**: Enforced a strict programmatic cap of 10.0 on `priority_score` to maintain normalized scaling for the Stage 5 Execution Agent.
- **Status**: Implemented via `min(round(score, 1), 10.0)`.

# Decisions

- **DECISION 1**: Simulated `ALERT` via email.
  - *Rationale*: Primary dependency for subsequent actions; must succeed to test downstream failures.
- **DECISION 2**: Triggered forced failure on `PUBLISH` action (`act_002`).
  - *Rationale*: System required to demonstrate fault tolerance and Stage 6 recovery workflow. Timeout simulated at 5020ms.
- **DECISION 3**: Skipped `ANALYZE` action (`act_004`).
  - *Rationale*: Dependency requirement not met. Action marked as `SKIPPED` rather than `FAILED` since the error is upstream.
- **DECISION 4**: Allowed `MONITOR` action (`act_005`) to proceed.
  - *Rationale*: Unaffected by the failed `PUBLISH` action. Demonstrates isolated fault domains.

# Reasoning

- **Sequential Execution**: Actions are executed sequentially based on `step`. A failure in a parent node in the dependency graph must pause or skip all dependent child nodes to prevent inconsistent system states.
- **Failure Injection Strategy**: By failing the first `PUBLISH` task with an `API_TIMEOUT`, the system forces the execution of the `requires_recovery` flag, allowing Stage 6 to demonstrate its fallback mechanism capabilities.
- **State Snapshots**: Providing `before_state` and `after_state` creates a clear, auditable timeline of events, essential for the final investigative report in Stage 7.
- **Dependency Blocking**: Action `act_004` cannot proceed without `act_002` completing successfully. Proceeding without the published brief could cause the analytics engine to report false negatives or analyze incomplete data sets.

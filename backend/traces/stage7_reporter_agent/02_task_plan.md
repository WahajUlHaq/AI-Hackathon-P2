# Stage 7 Task Plan

1. **Task 1: Pre-process State Data**
   - Aggregate execution_log from Stage 5 and post_recovery_log from Stage 6.
   - Map systems touched to their initial and final states.

2. **Task 2: Build Before/After Diff**
   - Iterate over affected systems (e.g., Investor Portal, Analytics Engine).
   - Generate `before` and `after` string descriptions.
   - Tag with `change_type` (POSITIVE, PARTIAL, NEGATIVE).

3. **Task 3: Build Action Timeline**
   - Combine actions and sort by `executed_at`.
   - Mark final statuses (`SUCCESS`, `RECOVERED`, `UNBLOCKED_AND_SUCCEEDED`).
   - Append duration notes.

4. **Task 4: Calculate Projected Impact**
   - Tally total verified sources, notifications, and identified false claims.
   - Populate quantitative impact metrics.

5. **Task 5: Export Antigravity Trace**
   - Extract raw pipeline stats: `workplan`, `task_plan`, `reasoning_steps`, `tool_calls`, `failures_and_recovery`.
   - Produce the `final_outcome` summary text.
   - Serialize and flush to disk.

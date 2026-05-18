# Task Plan

1. **Failure Identification:**
   - Scan the `execution_log` for any action where `requires_recovery` is `True`.
   
2. **Fallback Retrieval:**
   - Cross-reference the failed `action_id` with the original `action_plan` to extract the `fallback` object.
   
3. **Fallback Simulation:**
   - Execute the fallback step. For example, if `PUBLISH` to `investor_portal_api` failed, use `email_draft`.
   - Record the `recovery_output` and duration.
   
4. **Dependency Resolution:**
   - Find all actions in the log marked as `SKIPPED` due to the failed upstream dependency.
   - Mark them as `UNBLOCKED` so they can be processed in a subsequent pass if needed.
   
5. **Finalization:**
   - Generate a `recovery_summary` detailing which actions were successfully recovered.

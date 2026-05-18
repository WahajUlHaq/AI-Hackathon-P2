import os

traces_dir = "traces/stage6_recovery_agent"
os.makedirs(traces_dir, exist_ok=True)

traces = {
    "01_workplan.md": """# Workplan: Recovery Agent (Stage 6)

## Objective
Detect failed actions from the Stage 5 Execution Log, retrieve pre-planned fallback strategies from the Stage 4 Action Plan, execute these fallbacks to recover the system state, and unblock any dependent downstream actions.

## Scope
1. Ingest `execution_log[]` from Stage 5 and `action_plan[]` from Stage 4.
2. Identify actions flagged with `status="FAILED"` and `requires_recovery=true`.
3. Extract the `fallback` mechanism for each failed action.
4. Simulate the fallback execution.
5. Identify and unblock previously skipped dependent actions.

## Timeline
- `T+0`: Parse execution log for failures.
- `T+1`: Match failed actions with fallback plans.
- `T+2`: Execute fallback actions.
- `T+3`: Update system state and unblock dependent tasks.
""",
    "02_task_plan.md": """# Task Plan

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
""",
    "03_agent_observations.md": """# Agent Observations

### Input Analysis
- Detected 1 failed action: `act_002` (Publish Investor Brief).
- Detected 1 skipped action: `act_004` (Trigger Deep Due Diligence Analysis) which was blocked by `act_002`.

### Fallback Analysis
- Original failure reason: `API_TIMEOUT` on `investor_portal_api`.
- Fallback route identified: `email_draft` (Send as formatted email attachment to distribution list).

### Execution Observations
- The fallback execution for `act_002` was successful. The simulated email draft was created and queued for the distribution list.
- With `act_002` recovered, `act_004` no longer has a failed dependency.
""",
    "04_reasoning.md": """# Reasoning

- **Fallback Execution**: When the primary mechanism (`investor_portal_api`) fails due to a timeout, a resilient system must rely on a secondary mechanism to fulfill the action's intent. Sending an email draft fulfills the `PUBLISH` intent, albeit via a different medium.
- **State Reconciliation**: Recovering an action means we must also update the state of dependent actions. `act_004` was correctly skipped in Stage 5, but its blockage is removed once the recovery logic satisfies the dependency requirement.
- **Auditability**: We explicitly log the `fallback_used` and the result to ensure full transparency of the system's fault-tolerance mechanisms, proving to auditors that the failure was gracefully handled.
""",
    "05_decisions.md": """# Decisions

- **DECISION 1**: Triggered fallback logic for `act_002`.
  - *Rationale*: Stage 5 explicitly flagged this action with `requires_recovery=True`.
- **DECISION 2**: Used `email_draft` as the target system instead of retrying `investor_portal_api`.
  - *Rationale*: A timeout on the portal API suggests an infrastructure issue. Retries might exacerbate the problem, so switching to an entirely different delivery mechanism (email) is the safest fallback.
- **DECISION 3**: Flagged `act_004` as `UNBLOCKED`.
  - *Rationale*: Since the brief content was successfully delivered via the fallback, the analytical system can now proceed with its deep due diligence using the distributed brief.
""",
    "06_tool_calls.md": """# Tool Calls

```json
[
  {
    "tool": "POST_API",
    "target": "/email/drafts",
    "payload": {
      "subject": "TechCorp Confidence Crisis — Verified Analysis",
      "body": "Full brief content (Fallback Delivery)...",
      "distribution_list": "investors@firm.com"
    },
    "result": "SUCCESS",
    "duration_ms": 320
  }
]
```
""",
    "07_action_execution.md": """# Action Execution

### Recovery Action 1 (`act_002`): PUBLISH (Fallback)
- **Target System**: `email_draft`
- **Execution**: Mock POST request to `/email/drafts`
- **Result**: Success. Email drafted successfully and sent to distribution list.
- **Duration**: 320ms.

### Dependency Update (`act_004`)
- **Action Status Update**: Blocked -> Unblocked.
- **Result**: The system recognizes that the dependency constraint for `act_004` has now been fulfilled by the recovery of `act_002`.
""",
    "08_error_recovery.md": """# Error Recovery

### Recovery Summary
- **Primary Failure**: `API_TIMEOUT` on `act_002` (`investor_portal_api`).
- **Recovery Strategy**: Execution of pre-defined fallback from Stage 4.
- **Outcome**: The `PUBLISH` intent was successfully recovered using the secondary communication channel (`email_draft`).

### Resiliency Impact
- The system demonstrated its ability to handle external service outages without human intervention.
- The workflow integrity was preserved, preventing a complete pipeline halt and ensuring critical information was still disseminated.
""",
    "09_final_outcomes.md": """# Final Outcomes

## Recovery Execution Summary

- **Total Actions Recovered**: 1 (`act_002`)
- **Total Actions Unblocked**: 1 (`act_004`)
- **Recovery Status**: SUCCESS
- **System State**: The investment brief was successfully distributed despite the primary API failure. The downstream analytics job is clear to run.

## Hand-off to Stage 7
- The combined logs of Stage 5 (Execution) and Stage 6 (Recovery) will now be passed to Stage 7 (Reporting Agent) to compile the final comprehensive audit report.
"""
}

for filename, content in traces.items():
    filepath = os.path.join(traces_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Created {filepath}")

print("Stage 6 traces created successfully.")

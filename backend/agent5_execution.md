# ⚡ Stage 5 — Execution Agent

## Overview

| Property | Value |
|---|---|
| **File** | `agents/agent5_executor.py` |
| **Role** | Simulate step-by-step action execution with deep before/after comparison per step |
| **LLM** | ✅ DeepSeek `deepseek-chat` · temperature=`0.1` |
| **Input** | `action_plan[]` from Stage 4 |
| **Output** | `execution_log[]` — full execution trace with comparison, before/after, side effects |
| **Failure Injection** | First `PUBLISH` action fails with `API_TIMEOUT` (deliberate, for demo) |
| **Feeds Into** | Stage 6 (failures) + Stage 7 (report) |

---

## Responsibility

The Execution Agent walks through the action plan **one step at a time**, simulating each action with:

1. **Before State** — snapshot of the target system before this action runs
2. **Mock Execution** — simulated API call with realistic response
3. **After State** — snapshot of the target system after this action
4. **Comparison Report** — explicit diff between before and after
5. **Side Effects** — what this action changed in OTHER systems
6. **Failure Injection** — first PUBLISH action deliberately fails to trigger Stage 6

This is the "show your work" agent. Judges see exactly what changed, when, and why.

---

## Architecture

```
action_plan[] (5 actions, ordered by step + depends_on)
│
├── STEP SEQUENCER:
│     Process actions in step order
│     If action.depends_on[] are not ALL completed → skip or wait
│     If dependency FAILED → status = SKIPPED
│
├── For each action:
│     │
│     ├── SNAPSHOT before_state of target_system
│     │
│     ├── FAILURE INJECTION CHECK:
│     │     if action.type == "PUBLISH" and first_publish_not_yet_injected:
│     │         → inject API_TIMEOUT failure
│     │         → set requires_recovery = True
│     │     else:
│     │         → execute normally
│     │
│     ├── MOCK API CALL (by action type):
│     │     ALERT    → POST /notifications/{email|sms}
│     │     PUBLISH  → POST /investor-portal/briefs
│     │     UPDATE   → PATCH /portfolio/flags
│     │     ANALYZE  → POST /analytics/jobs
│     │     MONITOR  → POST /scheduler/jobs
│     │
│     ├── SNAPSHOT after_state of target_system
│     │
│     ├── BUILD COMPARISON REPORT:
│     │     explicit field-by-field diff
│     │     what changed, what did not change
│     │     magnitude of change
│     │
│     └── DETECT SIDE EFFECTS:
│           What other systems/actions were affected by this action?
│
└── DeepSeek assembles: execution_log[] + execution_summary
```

---

## Mock API Reference

| Action Type | Endpoint | Method | Success Response | Simulated Time |
|---|---|---|---|---|
| `ALERT` (email) | `/notifications/email` | POST | `{message_id, sent_to, status}` | 250ms |
| `ALERT` (SMS) | `/notifications/sms` | POST | `{message_id, phone_count}` | 180ms |
| `PUBLISH` | `/investor-portal/briefs` | POST | `{brief_id, url, published_at}` | **FAILS (timeout)** |
| `UPDATE` | `/portfolio/flags` | PATCH | `{records_updated, new_flag}` | 340ms |
| `ANALYZE` | `/analytics/jobs` | POST | `{job_id, estimated_minutes}` | 420ms |
| `MONITOR` | `/scheduler/jobs` | POST | `{job_id, next_run, interval}` | 90ms |

---

## Execution Log Entry — SUCCESS (act_001)

```json
{
  "action_id": "act_001",
  "step": 1,
  "title": "CRITICAL ALERT — Investment Team Notification",
  "type": "ALERT",
  "executed_at": "2026-05-16T08:52:00Z",
  "duration_ms": 250,
  "status": "SUCCESS",
  "error": null,
  "requires_recovery": false,
  "before_state": {
    "system": "investment_team_email",
    "investment_team_alerted": false,
    "last_techcorp_alert": "2026-04-10T14:00:00Z",
    "pending_alerts": 0
  },
  "after_state": {
    "system": "investment_team_email",
    "investment_team_alerted": true,
    "last_techcorp_alert": "2026-05-16T08:52:00Z",
    "pending_alerts": 0,
    "message_id": "alert_7741",
    "recipients": 8
  },
  "comparison": {
    "fields_changed": ["investment_team_alerted", "last_techcorp_alert"],
    "fields_unchanged": ["pending_alerts"],
    "change_summary": "Alert status: false → true. Last alert date updated. 8 recipients notified.",
    "impact_magnitude": "HIGH — team now aware of crisis, can begin response"
  },
  "simulation_output": {
    "api_endpoint": "POST /notifications/email",
    "request_payload": {
      "to": "investment-team@firm.com",
      "subject": "CRITICAL: TechCorp Confidence Crisis — Action Required",
      "body_summary": "25% layoffs confirmed (Reuters), stock -17.9%, 3 analyst downgrades, employee morale collapse. Full brief being published. Confidence: 86%.",
      "sensitivity": "CONFIDENTIAL",
      "priority": "URGENT"
    },
    "response": {
      "message_id": "alert_7741",
      "status": "delivered",
      "recipients": 8
    }
  },
  "side_effects": [
    "Investment team now expects investor brief (act_002) to follow within 30 minutes",
    "Alert logged in audit trail for compliance record"
  ]
}
```

---

## Execution Log Entry — FAILED — Injected (act_002)

```json
{
  "action_id": "act_002",
  "step": 2,
  "title": "Publish Investor Brief — TechCorp Crisis Analysis",
  "type": "PUBLISH",
  "executed_at": "2026-05-16T08:52:15Z",
  "duration_ms": 5020,
  "status": "FAILED",
  "error": "API_TIMEOUT: investor_portal_api did not respond within 5000ms",
  "requires_recovery": true,
  "before_state": {
    "system": "investor_portal_api",
    "techcorp_brief_published": false,
    "portal_status": "unknown",
    "last_successful_publish": "2026-05-15T14:00:00Z"
  },
  "after_state": {
    "system": "investor_portal_api",
    "techcorp_brief_published": false,
    "portal_status": "timeout",
    "last_successful_publish": "2026-05-15T14:00:00Z"
  },
  "comparison": {
    "fields_changed": ["portal_status"],
    "fields_unchanged": ["techcorp_brief_published", "last_successful_publish"],
    "change_summary": "Portal status changed from unknown → timeout. Brief NOT published. No content change.",
    "impact_magnitude": "CRITICAL — investment team alerted but brief not yet available"
  },
  "simulation_output": {
    "api_endpoint": "POST /investor-portal/briefs",
    "request_payload": {
      "title": "TechCorp Confidence Crisis — Verified Analysis",
      "body": "Full brief content...",
      "sensitivity": "CONFIDENTIAL"
    },
    "response": "TIMEOUT after 5020ms — no response received"
  },
  "side_effects": [
    "act_004 (ANALYZE) is now BLOCKED — depends on act_002 completion",
    "Investment team has been alerted but cannot access brief yet — creates expectation gap",
    "Brief content was prepared but not delivered — needs fallback route"
  ]
}
```

---

## Execution Log Entry — SKIPPED (act_004)

```json
{
  "action_id": "act_004",
  "step": 4,
  "title": "Trigger Deep Due Diligence Analysis",
  "type": "ANALYZE",
  "executed_at": null,
  "duration_ms": null,
  "status": "SKIPPED",
  "error": "Blocked — act_002 (PUBLISH) failed. depends_on not satisfied.",
  "requires_recovery": false,
  "before_state": {},
  "after_state": {},
  "comparison": {
    "fields_changed": [],
    "change_summary": "No execution — blocked by upstream failure. Analysis not triggered.",
    "impact_magnitude": "MEDIUM — deep analysis delayed but not permanently lost"
  },
  "side_effects": [
    "Deep due diligence report will be delayed until act_002 is recovered"
  ]
}
```

---

## Comparison Report — The Key Feature

Every execution entry includes an explicit `comparison` block that shows the before→after diff:

```
BEFORE                              AFTER
──────────────────────────────────────────────────────────────
investment_team_alerted: false  →  investment_team_alerted: true      ✅ CHANGED
last_techcorp_alert: 2026-04-10 →  last_techcorp_alert: 2026-05-16   ✅ CHANGED
pending_alerts: 0               →  pending_alerts: 0                  ─ UNCHANGED
──────────────────────────────────────────────────────────────
Summary: Alert sent. 8 recipients. Team now aware of TechCorp crisis.
Impact:  HIGH — unblocks investment team response decision-making.
```

---

## Failure Injection Logic

```
RULE: The FIRST action of type "PUBLISH" is deliberately failed.

Why:
  - Demonstrates recovery system is real and works
  - Shows before/after state captures the failure clearly
  - Creates a downstream blocker (act_004 depends on act_002)
  - Proves fallback path (email draft instead of portal)
  - Required by challenge brief: at least one action must fail and be recovered

Injection Code (pseudocode):
  for action in action_plan:
      if action.type == "PUBLISH" and not first_publish_injected:
          → status = FAILED
          → error = "API_TIMEOUT: investor_portal_api did not respond within 5000ms"
          → duration_ms = 5020
          → requires_recovery = True
          first_publish_injected = True
      else:
          → execute normally → status = SUCCESS
```

---

## Execution Summary

```json
{
  "total_actions": 5,
  "succeeded": 3,
  "failed": 1,
  "skipped": 1,
  "failed_action_ids": ["act_002"],
  "skipped_action_ids": ["act_004"],
  "execution_start": "2026-05-16T08:52:00Z",
  "execution_end": "2026-05-16T08:52:30Z",
  "total_duration_ms": 6080,
  "failure_reason": "act_002 — investor_portal_api timeout",
  "recovery_needed": true
}
```

---

## System State After Stage 5

```
act_001 (ALERT)   → ✅ SUCCESS  — Investment team notified
act_002 (PUBLISH) → ❌ FAILED   — Brief not published (portal timeout)
act_003 (UPDATE)  → ✅ SUCCESS  — Portfolio dashboard flagged
act_004 (ANALYZE) → ⏭ SKIPPED  — Blocked by act_002 failure
act_005 (MONITOR) → ✅ SUCCESS  — Hourly monitoring scheduled
```

---

## Console Output (Demo)

```
[ExecutorAgent] Simulating 5 actions...

Step 1: ALERT — Investment Team Email
  Before: alerted=false, last_alert=2026-04-10
  Executing POST /notifications/email... (250ms)
  After:  alerted=true, message_id=alert_7741, recipients=8
  Change: alert sent to 8 team members ✅

Step 2: PUBLISH — Investor Portal Brief
  Before: brief_published=false, portal_status=unknown
  Executing POST /investor-portal/briefs... (5020ms)
  ⚠ TIMEOUT — API did not respond after 5000ms
  After:  brief_published=false, portal_status=timeout
  Change: portal_status unknown → timeout. Brief NOT sent ❌
  Side effect: act_004 is now BLOCKED

Step 3: UPDATE — Portfolio Dashboard
  Before: techcorp_flag=none, risk_level=normal
  Executing PATCH /portfolio/flags... (340ms)
  After:  techcorp_flag=CRISIS_WATCH, risk_level=HIGH
  Change: 1 record updated ✅

Step 4: ANALYZE — Deep Due Diligence
  SKIPPED — blocked by act_002 failure ⏭

Step 5: MONITOR — Hourly Monitoring Schedule
  Before: job=null
  Executing POST /scheduler/jobs... (90ms)
  After:  job_id=job_8821, interval=1h, next_run=2026-05-16T09:52:00Z
  Change: monitoring job created ✅

[ExecutorAgent] Done — 3 succeeded, 1 failed, 1 skipped (6080ms total)
```

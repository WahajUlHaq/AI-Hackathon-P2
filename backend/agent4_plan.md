# 📋 Stage 4 — Plan Agent

## Overview

| Property | Value |
|---|---|
| **File** | `agents/agent4_plan.py` |
| **Role** | Generate 3–5 constrained, ordered, interconnected actions with fallbacks |
| **LLM** | ✅ DeepSeek `deepseek-chat` · temperature=`0.1` |
| **Input** | `insight_packet{}` from Stage 3 + `constraints{}` |
| **Output** | `action_plan[]` — validated, prioritized action chain |
| **Feeds Into** | Stage 5 — Execution Agent |

---

## Responsibility

The Plan Agent converts "what is wrong and why it matters" into a **concrete, constraint-validated, step-ordered plan of action**. Every action must:

- Be specific (not vague like "investigate further")
- Respect real constraints (budget, deadline, available resources)
- Have a stated dependency (which other actions must complete first)
- Have a pre-designed fallback (what to do if this action fails)
- Have a priority score (so Stage 5 knows what matters most)

---

## Architecture

```
insight_packet{} + constraints{}
│
├── PRE-PROCESSING (Python, before LLM):
│     │
│     ├── Sort insights by urgency weight:
│     │     CRITICAL → 10, HIGH → 7, MEDIUM → 4, LOW → 1
│     │
│     ├── Identify constraint limits:
│     │     budget_pkr, deadline_hours, available_resources
│     │
│     └── Select top N insights to act on (max 5)
│
├── DEEPSEEK CALL (temp=0.1):
│     │
│     ├── Generate EXACTLY 3–5 actions
│     ├── Each action must be one of: ALERT, PUBLISH, UPDATE, ANALYZE, MONITOR
│     ├── Validate each against constraints → FEASIBLE / MODIFIED / REJECTED
│     ├── Map depends_on[] for each action (dependency chain)
│     ├── Design fallback for each action
│     └── Assign priority_score 0.0–10.0
│
└── Output: action_plan[]
```

---

## Action Types

| Type | What It Means | Target System Examples |
|---|---|---|
| `ALERT` | Send urgent notification to stakeholder | email, sms, Slack, dashboard |
| `PUBLISH` | Create and push a document/report/brief | CMS, email list, investor portal |
| `UPDATE` | Modify a record or status in a system | CRM, portfolio dashboard, watchlist |
| `ANALYZE` | Trigger deeper automated analysis | analytics system, report generator |
| `MONITOR` | Schedule automated repeated recheck | monitoring scheduler, cron job |

---

## Constraints Object

```json
{
  "alert_budget_usd": 0,
  "publish_deadline_hours": 4,
  "analyze_budget_usd": 500,
  "available_resources": [
    "investment_team_email",
    "investor_portal_api",
    "portfolio_dashboard",
    "analytics_engine",
    "monitoring_scheduler"
  ],
  "api_rate_limits": {
    "investor_portal_api": "10 calls/hour",
    "analytics_engine": "5 calls/hour"
  },
  "output_language": "English",
  "sensitivity_level": "CONFIDENTIAL"
}
```

---

## Constraint Validation Logic

```
For each action:
  if estimated_cost > budget_limit:
    constraint_status = "REJECTED"
    → generate cheaper alternative action

  elif deadline < now + estimated_time:
    constraint_status = "MODIFIED"
    → reduce scope to fit deadline

  elif resource_required NOT IN available_resources:
    constraint_status = "MODIFIED"
    → substitute nearest available resource

  else:
    constraint_status = "FEASIBLE"
```

---

## Priority Scoring Formula

```
urgency_weight = {CRITICAL: 10, HIGH: 7, MEDIUM: 4, LOW: 1}

priority_score = urgency_weight[insight.urgency]
               × insight.confidence
               × (1 + source_count / 5)   ← bonus for multi-source support

Capped at 10.0
```

---

## Full Output Schema

### Single Action Object

```json
{
  "action_id": "act_001",
  "step": 1,
  "title": "CRITICAL ALERT — Investment Team Notification",
  "type": "ALERT",
  "description": "Send immediate alert to investment team with verified summary: TechCorp cutting 25% workforce (Reuters confirmed), stock -17.9%, 3 analyst downgrades, abnormal volume spike. Attach confidence score and source breakdown. Flag as CONFIDENTIAL.",
  "target_system": "investment_team_email",
  "stakeholder": "investment_team",
  "triggered_by_insight": "ins_001",
  "constraints": {
    "budget_limit_usd": 0,
    "deadline": "2026-05-16T10:30:00Z",
    "resource_required": "investment_team_email",
    "sensitivity": "CONFIDENTIAL"
  },
  "constraint_status": "FEASIBLE",
  "constraint_notes": null,
  "priority_score": 9.5,
  "depends_on": [],
  "estimated_duration_minutes": 2,
  "fallback": {
    "title": "Send via SMS gateway if email fails",
    "type": "ALERT",
    "target_system": "sms_gateway",
    "description": "If email delivery fails, send compressed 160-char SMS alert to investment team leads directly."
  }
}
```

### Full Action Plan Output

```json
{
  "action_plan": [
    {
      "action_id": "act_001",
      "step": 1,
      "title": "CRITICAL ALERT — Investment Team",
      "type": "ALERT",
      "target_system": "investment_team_email",
      "priority_score": 9.5,
      "depends_on": [],
      "constraint_status": "FEASIBLE",
      "fallback": { "type": "ALERT", "target_system": "sms_gateway" }
    },
    {
      "action_id": "act_002",
      "step": 2,
      "title": "Publish Investor Brief — TechCorp Crisis Analysis",
      "type": "PUBLISH",
      "target_system": "investor_portal_api",
      "priority_score": 8.8,
      "depends_on": ["act_001"],
      "constraint_status": "FEASIBLE",
      "fallback": { "type": "PUBLISH", "target_system": "email_draft", "description": "If portal API unavailable, send as formatted email attachment to distribution list" }
    },
    {
      "action_id": "act_003",
      "step": 3,
      "title": "Flag TechCorp in Portfolio Dashboard",
      "type": "UPDATE",
      "target_system": "portfolio_dashboard",
      "priority_score": 7.2,
      "depends_on": ["act_001"],
      "constraint_status": "FEASIBLE",
      "fallback": { "type": "UPDATE", "target_system": "spreadsheet_export" }
    },
    {
      "action_id": "act_004",
      "step": 4,
      "title": "Trigger Deep Due Diligence Analysis",
      "type": "ANALYZE",
      "target_system": "analytics_engine",
      "priority_score": 6.8,
      "depends_on": ["act_002", "act_003"],
      "constraint_status": "FEASIBLE",
      "fallback": { "type": "ANALYZE", "target_system": "manual_review_queue" }
    },
    {
      "action_id": "act_005",
      "step": 5,
      "title": "Schedule Hourly TechCorp Monitoring (24h)",
      "type": "MONITOR",
      "target_system": "monitoring_scheduler",
      "priority_score": 5.5,
      "depends_on": ["act_003"],
      "constraint_status": "FEASIBLE",
      "fallback": { "type": "MONITOR", "target_system": "manual_reminder" }
    }
  ],
  "plan_summary": "Alert investment team → publish investor brief → update dashboard → trigger deep analysis → monitor 24h",
  "total_estimated_cost_usd": 0,
  "estimated_resolution_hours": 4,
  "actions_total": 5,
  "actions_feasible": 5,
  "actions_modified": 0,
  "actions_rejected": 0,
  "agent_reasoning": "All three CRITICAL/HIGH insights (confidence crisis, volume anomaly, morale collapse) require immediate investment team awareness. Publishing a verified brief before the rumor spreads further is the highest-leverage action. Dashboard flagging ensures ongoing portfolio risk visibility."
}
```

---

## Dependency Graph

```
act_001 (ALERT) ──────────────────────────────┐
                                              ├──▶ act_002 (PUBLISH) ──▶ act_004 (ANALYZE)
                                              └──▶ act_003 (UPDATE)  ──▶ act_005 (MONITOR)

Execution order:
  Step 1: act_001 (no dependencies — run immediately)
  Step 2: act_002 + act_003 (both depend only on act_001 — run in parallel after step 1)
  Step 3: act_004 (depends on act_002 + act_003)
          act_005 (depends on act_003 only — could run earlier)
```

---

## Console Output (Demo)

```
[PlanAgent] Generating action plan from 3 insights...
[PlanAgent] Top insight: ins_001 (CRITICAL, confidence=0.86)
[PlanAgent] Constraint check:
  act_001 ALERT  → FEASIBLE   (email, $0, 2min)
  act_002 PUBLISH→ FEASIBLE   (portal API, $0, 30min)
  act_003 UPDATE → FEASIBLE   (dashboard, $0, 5min)
  act_004 ANALYZE→ FEASIBLE   (analytics engine, $0, 60min)
  act_005 MONITOR→ FEASIBLE   (scheduler, $0, 1min)
[PlanAgent] Done — 5 actions, $0 cost, ~4 hour resolution window
```

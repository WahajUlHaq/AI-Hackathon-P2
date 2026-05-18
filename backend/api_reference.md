# 🌐 API Reference — Autonomous Content-to-Action Agent

## Overview

| Property | Value |
|---|---|
| **Framework** | FastAPI |
| **Server** | Uvicorn |
| **Base URL** | `http://localhost:8000` |
| **API Prefix** | `/api/v1` |
| **Format** | JSON (REST) · `text/event-stream` (SSE stream) |
| **Auth** | None (local dev) |
| **Docs UI** | `http://localhost:8000/docs` (Swagger UI) |

---

## Starting the API Server

```bash
# Install dependencies
pip install fastapi uvicorn python-multipart

# Run the server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Endpoint Summary

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/run` | Submit sources → start pipeline |
| `GET` | `/api/v1/status/{job_id}` | Poll pipeline status |
| `GET` | `/api/v1/result/{job_id}` | Get full pipeline result |
| `GET` | `/api/v1/trace/{job_id}` | Get Antigravity trace only |
| `GET` | `/api/v1/report/{job_id}` | Get final report only |
| `GET` | `/api/v1/stream/{job_id}` | **Live thinking stream (SSE)** |
| `POST` | `/api/v1/run/sync` | Run pipeline synchronously (wait for result) |
| `GET` | `/api/v1/health` | Health check |

---

## `POST /api/v1/run`

### Description
Submit raw content sources and constraints to start the 7-agent pipeline. Returns a `job_id` immediately. Use `/status/{job_id}` to poll for completion.

### Request Body

```json
{
  "sources": [
    {
      "label": "Warehouse Inventory Report",
      "type": "PDF",
      "content": "Current stock levels: Item A=500 units, Item B=120 units. Last updated: 2026-05-07",
      "received_at": "2026-05-07T08:00:00Z"
    },
    {
      "label": "News Article — Transport Strike",
      "type": "URL",
      "content": "A major transport strike is disrupting supply chains. Deliveries delayed 5-7 days.",
      "received_at": "2026-05-15T08:30:00Z"
    },
    {
      "label": "Sales Dashboard Export",
      "type": "CSV",
      "content": "Week,Orders\n2026-W17,980\n2026-W18,1200\n2026-W19,1620",
      "received_at": "2026-05-15T09:00:00Z"
    },
    {
      "label": "Supplier API Response",
      "type": "JSON",
      "content": "{\"supplier\":\"FastSupply\",\"stock_available\":false,\"lead_time_days\":9}",
      "received_at": "2026-05-15T09:45:00Z"
    },
    {
      "label": "Customer Complaints Feed",
      "type": "MockFeed",
      "content": "15 complaints in 2 hours: item not available, out of stock error",
      "received_at": "2026-05-15T10:05:00Z"
    }
  ],
  "constraints": {
    "emergency_order_budget_pkr": 500000,
    "notification_deadline_hours": 2,
    "available_resources": [
      "procurement_manager",
      "customer_service_bot",
      "warehouse_api",
      "monitoring_scheduler"
    ],
    "api_rate_limits": {
      "warehouse_api": "10 calls/min",
      "sms_gateway": "5 calls/min"
    }
  },
  "use_demo": false
}
```

### Request Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `sources` | `array` | Yes (unless `use_demo=true`) | List of raw content sources |
| `sources[].label` | `string` | Yes | Human-readable source name |
| `sources[].type` | `string` | Yes | `PDF`, `URL`, `CSV`, `JSON`, `MockFeed` |
| `sources[].content` | `string` | Yes | Raw text content of the source |
| `sources[].received_at` | `string` | Yes | ISO8601 timestamp of source data |
| `constraints` | `object` | No | System limits. Defaults used if omitted |
| `constraints.emergency_order_budget_pkr` | `number` | No | Max PKR for emergency order (default: 500000) |
| `constraints.notification_deadline_hours` | `number` | No | Hours to notify stakeholders (default: 2) |
| `constraints.available_resources` | `array[string]` | No | Available roles/systems |
| `constraints.api_rate_limits` | `object` | No | Rate limits per system |
| `use_demo` | `boolean` | No | If `true`, ignores `sources` and uses built-in demo scenario |

### Response — `202 Accepted`

```json
{
  "job_id": "job_a3f92b1c",
  "status": "queued",
  "message": "Pipeline started. Poll /api/v1/status/job_a3f92b1c for updates.",
  "estimated_duration_seconds": 45,
  "submitted_at": "2026-05-15T10:15:00Z"
}
```

### Response Fields

| Field | Type | Description |
|---|---|---|
| `job_id` | `string` | Unique ID for this pipeline run |
| `status` | `string` | `queued` — pipeline is starting |
| `message` | `string` | Human-readable status |
| `estimated_duration_seconds` | `number` | Expected completion time |
| `submitted_at` | `string` | ISO8601 timestamp |

### Error Responses

| Code | Reason | Body |
|---|---|---|
| `422` | Missing required fields | `{"detail": [{"loc": ["body","sources"], "msg": "field required"}]}` |
| `500` | DeepSeek API key not configured | `{"error": "DEEPSEEK_API_KEY not set"}` |

---

## `GET /api/v1/status/{job_id}`

### Description
Poll the status of a running pipeline job.

### Path Parameters

| Parameter | Type | Description |
|---|---|---|
| `job_id` | `string` | Job ID from `/run` response |

### Response — `200 OK`

**While running:**
```json
{
  "job_id": "job_a3f92b1c",
  "status": "running",
  "current_step": 3,
  "current_agent": "ImpactAnalyzer",
  "steps_completed": 2,
  "steps_total": 7,
  "progress_percent": 28,
  "started_at": "2026-05-15T10:15:00Z",
  "elapsed_seconds": 18
}
```

**When complete:**
```json
{
  "job_id": "job_a3f92b1c",
  "status": "completed",
  "current_step": 7,
  "current_agent": "ReporterAgent",
  "steps_completed": 7,
  "steps_total": 7,
  "progress_percent": 100,
  "started_at": "2026-05-15T10:15:00Z",
  "completed_at": "2026-05-15T10:15:45Z",
  "elapsed_seconds": 45,
  "result_url": "/api/v1/result/job_a3f92b1c"
}
```

**On failure:**
```json
{
  "job_id": "job_a3f92b1c",
  "status": "failed",
  "failed_at_step": 2,
  "failed_agent": "InsightAgent",
  "error": "DeepSeek API returned 429 Too Many Requests",
  "elapsed_seconds": 12
}
```

### Status Values

| Status | Meaning |
|---|---|
| `queued` | Waiting to start |
| `running` | Pipeline executing |
| `completed` | All 7 agents finished successfully |
| `failed` | Pipeline stopped due to unrecoverable error |

### Error Responses

| Code | Reason |
|---|---|
| `404` | `job_id` not found |

---

## `GET /api/v1/result/{job_id}`

### Description
Retrieve the complete pipeline result after status is `completed`.

### Path Parameters

| Parameter | Type | Description |
|---|---|---|
| `job_id` | `string` | Job ID from `/run` response |

### Response — `200 OK`

```json
{
  "job_id": "job_a3f92b1c",
  "status": "completed",
  "pipeline_duration_ms": 45200,
  "ingestion": {
    "content_blocks": [
      {
        "id": "cb_001",
        "source_type": "PDF",
        "source_label": "Warehouse Inventory Report",
        "raw_text": "Current stock levels: Item A=500 units...",
        "timestamp": "2026-05-07T00:00:00Z",
        "credibility_score": 0.3,
        "domain": "inventory",
        "is_stale": true,
        "is_noise": false
      }
    ],
    "ingestion_summary": {
      "total_sources": 5,
      "noise_filtered": 0,
      "stale_flagged": 1,
      "domains_detected": ["inventory", "logistics", "customer"]
    }
  },
  "insights": {
    "insights": [
      {
        "id": "ins_001",
        "title": "Inventory Shortage Risk",
        "description": "...",
        "signal_type": "risk",
        "confidence": 0.87,
        "urgency": "CRITICAL"
      }
    ],
    "contradictions": [
      {
        "id": "con_001",
        "topic": "Current stock level",
        "resolution": "prefer_source_b",
        "resolution_reason": "Supplier API is 8 days newer with 3x higher credibility"
      }
    ],
    "overall_confidence": 0.82
  },
  "impact": {
    "impact_reports": [
      {
        "insight_id": "ins_001",
        "financial_impact": {
          "type": "loss",
          "estimated_amount_pkr": "PKR 2,430,000"
        },
        "urgency": "CRITICAL",
        "action_window": "2 hours"
      }
    ],
    "combined_risk_score": 8.7
  },
  "action_plan": {
    "action_plan": [
      {
        "action_id": "act_001",
        "step": 1,
        "title": "Validate Real-Time Stock",
        "type": "VALIDATE",
        "constraint_status": "FEASIBLE",
        "priority_score": 9.8
      }
    ],
    "total_estimated_cost_pkr": 420000,
    "estimated_resolution_time": "9-10 hours"
  },
  "execution": {
    "execution_log": [
      {
        "action_id": "act_001",
        "status": "SUCCESS",
        "duration_ms": 340,
        "before_state": {},
        "after_state": {}
      },
      {
        "action_id": "act_003",
        "status": "FAILED",
        "error": "API_TIMEOUT",
        "requires_recovery": true
      }
    ],
    "execution_summary": {
      "total_actions": 5,
      "succeeded": 3,
      "failed": 1,
      "skipped": 1
    }
  },
  "recovery": {
    "recovery_actions": [
      {
        "failed_action_id": "act_003",
        "strategy": "RETRY",
        "recovery_status": "RECOVERED",
        "fallback_details": {
          "order_id": "ALT_ORD_9921",
          "cost_pkr": 465000
        }
      }
    ],
    "recovery_summary": {
      "total_failures": 1,
      "recovered": 1,
      "escalated": 0
    }
  },
  "final_report": {
    "before_after": [
      {
        "system": "Warehouse Stock Data",
        "metric": "Source of Truth",
        "before": "Stale PDF — Item A: 500 units",
        "after": "Live API — Item A: 47 units (critical_low)"
      }
    ],
    "cost_analysis": {
      "total_cost_pkr": 465000,
      "total_latency_ms": 18900
    },
    "projected_impact": {
      "stockout_risk_reduction_percent": 68,
      "revenue_protected_pkr": "PKR 2,430,000",
      "customers_notified": 1620
    },
    "antigravity_trace": {
      "workplan": "5-step: validate → notify → order → update → monitor",
      "final_outcome": "All 5 actions completed (1 via fallback). 68% risk reduction."
    }
  }
}
```

### Error Responses

| Code | Reason |
|---|---|
| `404` | `job_id` not found |
| `409` | Pipeline still running — use `/status` first |

---

## `GET /api/v1/trace/{job_id}`

### Description
Retrieve only the Antigravity trace — the official submission document.

### Response — `200 OK`

```json
{
  "job_id": "job_a3f92b1c",
  "antigravity_trace": {
    "workplan": "5-step action chain: validate stock → notify procurement → emergency order → update customers → monitor 24h",
    "task_plan": [
      "Step 1: Ingest 5 sources (1 stale, 0 noise) — SUCCESS",
      "Step 2: Extract 3 insights, 1 contradiction resolved — SUCCESS",
      "Step 3: Impact scored 8.7/10, CRITICAL urgency — SUCCESS",
      "Step 4: 5-action plan generated, PKR 420,000 budget — SUCCESS",
      "Step 5: 3 succeeded, 1 FAILED (API_TIMEOUT), 1 SKIPPED — PARTIAL",
      "Step 6: Retry×2 → Fallback AlternateSupply → RECOVERED — SUCCESS",
      "Step 7: Final report compiled, trace exported — SUCCESS"
    ],
    "reasoning_steps": [
      "Agent 2: Warehouse PDF (8 days old, credibility 0.3) flagged stale — down-ranked",
      "Agent 2: Supplier API (credibility 0.9, today) preferred — contradiction resolved: prefer_source_b",
      "Agent 3: 1620 unfulfilled orders × PKR 1,500 = PKR 2,430,000 at risk — CRITICAL",
      "Agent 4: Emergency order cost PKR 420,000 < budget PKR 500,000 — FEASIBLE",
      "Agent 6: FastSupply timed out twice — activated AlternateSupply fallback",
      "Agent 6: act_004 unblocked after fallback confirmed at 7-day lead time"
    ],
    "tool_calls": [
      "GET /warehouse/stock?items=ItemA,ItemB → SUCCESS (340ms) {Item_A:47, Item_B:12}",
      "POST /notifications/email+sms → SUCCESS (210ms) {message_id:msg_8821}",
      "POST /procurement/emergency-order [FastSupply] → TIMEOUT (5020ms)",
      "POST /procurement/emergency-order [FastSupply] retry 1 → TIMEOUT (5010ms)",
      "POST /procurement/emergency-order [FastSupply] retry 2 → TIMEOUT (5080ms)",
      "POST /procurement/emergency-order [AlternateSupply] → SUCCESS (3200ms) {order_id:ALT_ORD_9921}",
      "PATCH /crm/delivery-estimates → SUCCESS (980ms) {records_updated:1620}",
      "POST /scheduler/jobs → SUCCESS (120ms) {job_id:job_4422}"
    ],
    "failures_and_recovery": [
      "act_003 FAILED: API_TIMEOUT × 2 → Fallback: AlternateSupply order ALT_ORD_9921 confirmed → RECOVERED"
    ],
    "final_outcome": "All 5 actions completed (1 via fallback). Stockout risk reduced 68%. PKR 2.43M revenue protected. 1620 customers notified with 7-9 day delivery estimate. 24-hour monitoring active."
  }
}
```

---

## `GET /api/v1/report/{job_id}`

### Description
Retrieve only the final report section — optimized for UI rendering.

### Response — `200 OK`

```json
{
  "job_id": "job_a3f92b1c",
  "report": {
    "before_after": [
      {
        "system": "Warehouse Stock Data",
        "metric": "Source of Truth",
        "before": "Stale PDF — Item A: 500 units (8 days old)",
        "after": "Live Warehouse API — Item A: 47 units, Item B: 12 units",
        "change_description": "Contradiction resolved. Real-time data confirmed critical_low."
      },
      {
        "system": "Procurement",
        "metric": "Emergency Order",
        "before": "No order placed",
        "after": "ALT_ORD_9921 confirmed via AlternateSupply — 2800 units, PKR 465,000"
      },
      {
        "system": "Customer Portal",
        "metric": "Delivery Estimate",
        "before": "2-3 days",
        "after": "7-9 days (updated, auto-reply active)"
      },
      {
        "system": "Notifications",
        "metric": "Procurement Manager Alert",
        "before": "Not notified",
        "after": "Email + SMS sent (msg_8821)"
      },
      {
        "system": "Monitoring",
        "metric": "Automated Recheck",
        "before": "None",
        "after": "job_4422 — every 6 hours for 24 hours"
      }
    ],
    "action_timeline": [
      { "step": 1, "title": "Validate Stock", "status": "SUCCESS", "duration_ms": 340, "cost_pkr": 0 },
      { "step": 2, "title": "Alert Procurement Manager", "status": "SUCCESS", "duration_ms": 210, "cost_pkr": 0 },
      { "step": 3, "title": "Emergency Order", "status": "RECOVERED", "duration_ms": 15110, "cost_pkr": 465000 },
      { "step": 4, "title": "Update Customer Estimates", "status": "SUCCESS", "duration_ms": 980, "cost_pkr": 0 },
      { "step": 5, "title": "Schedule Monitoring", "status": "SUCCESS", "duration_ms": 120, "cost_pkr": 0 }
    ],
    "cost_analysis": {
      "total_cost_pkr": 465000,
      "total_latency_ms": 18900
    },
    "projected_impact": {
      "stockout_risk_reduction_percent": 68,
      "revenue_protected_pkr": "PKR 2,430,000",
      "customers_notified": 1620,
      "monitoring_active": true
    }
  }
}
```

---

## `GET /api/v1/stream/{job_id}`

### Description

Opens a **Server-Sent Events (SSE)** connection that streams the pipeline's live "thinking" in human language. The stream stays open for the entire duration of the pipeline and pushes a new thought event every time an agent makes an observation, decision, warning, or completes a step.

This is the **most powerful UX feature** — it lets users watch the AI reason through the problem in real time, in plain English. Not logs. Not JSON. Natural narrative thinking.

> Works with `EventSource` in browsers and `expo-event-source` in React Native.

### Path Parameters

| Parameter | Type | Description |
|---|---|---|
| `job_id` | `string` | Job ID returned from `POST /api/v1/run` |

### Request Headers

```
Accept: text/event-stream
Cache-Control: no-cache
```

### Response — `200 OK` (SSE stream)

**Content-Type:** `text/event-stream`  
**Connection:** kept open until pipeline completes

Each event is sent as:

```
data: {JSON thought object}\n\n
```

---

### SSE Event Format

Every event pushed to the stream follows this JSON structure:

```json
{
  "job_id": "job_a3f92b1c",
  "step": 2,
  "agent": "InsightAgent",
  "type": "observation",
  "thought": "Something doesn't add up — two sources are saying completely different things about stock levels.",
  "emoji": "💭",
  "timestamp": "2026-05-15T10:15:08Z"
}
```

### Event Fields

| Field | Type | Description |
|---|---|---|
| `job_id` | `string` | The pipeline job this thought belongs to |
| `step` | `number` | Which agent step (1–7) emitted this thought |
| `agent` | `string` | Agent name: `IngestionAgent`, `InsightAgent`, etc. |
| `type` | `string` | Type of thought (see table below) |
| `thought` | `string` | Human-language narrative — what the agent is thinking |
| `emoji` | `string` | Visual indicator matching the thought type |
| `timestamp` | `string` | ISO8601 time this thought was emitted |

### Thought Types

| Type | Emoji | When Emitted | Human Language Feel |
|---|---|---|---|
| `start` | 🔍 | Agent begins processing | "Let me go through each of the 5 sources..." |
| `observation` | 💭 | Agent notices something in the data | "This PDF is 8 days old — that's suspicious." |
| `decision` | ✅ | Agent makes a confirmed choice | "I'm going to trust the API over the PDF." |
| `conflict` | ⚡ | Contradiction found between sources | "Wait — these two sources directly disagree." |
| `action` | 🚀 | Simulating an action step | "Sending emergency alert to procurement manager now." |
| `warning` | ⚠️ | Something went wrong or looks bad | "FastSupply didn't respond. Timed out after 5 seconds." |
| `recovery` | 🔄 | Recovering from a failure | "Switching to AlternateSupply — order confirmed." |
| `result` | ✅ | Step or sub-task complete | "Stock confirmed: 47 units of Item A. Critically low." |
| `done` | 🎯 | Entire pipeline finished | "All done. PKR 2.43M protected. 1,620 customers notified." |

---

### Full Example Stream (Demo Scenario)

The following is the complete sequence of SSE events for the inventory shortage demo:

```
data: {"step":1,"agent":"IngestionAgent","type":"start","emoji":"🔍","thought":"Let me go through each of the 5 sources you gave me, one by one."}

data: {"step":1,"agent":"IngestionAgent","type":"observation","emoji":"💭","thought":"First up: a warehouse PDF from May 7th. That's 8 days ago — I'll flag this as stale."}

data: {"step":1,"agent":"IngestionAgent","type":"observation","emoji":"💭","thought":"News article from this morning about a transport strike. Recent and credible — score: 0.75."}

data: {"step":1,"agent":"IngestionAgent","type":"observation","emoji":"💭","thought":"Sales CSV shows orders jumped from 1,200 to 1,620 this week. That's a 35% spike worth flagging."}

data: {"step":1,"agent":"IngestionAgent","type":"observation","emoji":"💭","thought":"Supplier API response — fresh from 30 minutes ago. Stock unavailable, 9-day lead time. That's concerning."}

data: {"step":1,"agent":"IngestionAgent","type":"observation","emoji":"💭","thought":"Customer feed: 15 complaints in just 2 hours about items being out of stock. Alarm bells ringing."}

data: {"step":1,"agent":"IngestionAgent","type":"result","emoji":"✅","thought":"Done reading. 5 sources processed. 1 is stale (the PDF). None are noise."}

data: {"step":2,"agent":"InsightAgent","type":"start","emoji":"🔍","thought":"Now I need to find the real signals here — not just summarize, but find what actually matters."}

data: {"step":2,"agent":"InsightAgent","type":"conflict","emoji":"⚡","thought":"Hold on — the warehouse PDF says 500 units are available. But the supplier API says stock is completely gone. These two sources are directly contradicting each other."}

data: {"step":2,"agent":"InsightAgent","type":"decision","emoji":"✅","thought":"Comparing them: the PDF is 8 days old with credibility 0.3. The supplier API is from today with credibility 0.9. The API wins. The PDF was written before the transport strike hit."}

data: {"step":2,"agent":"InsightAgent","type":"observation","emoji":"💭","thought":"Orders up 35% this week, going INTO a confirmed stock shortage. That's not just a risk — that's a crisis in motion."}

data: {"step":2,"agent":"InsightAgent","type":"observation","emoji":"💭","thought":"The customer complaint spike — 400% above average — confirms customers are already hitting this problem right now."}

data: {"step":2,"agent":"InsightAgent","type":"result","emoji":"✅","thought":"3 signals found: inventory shortage risk (CRITICAL), demand surge (HIGH), and one contradiction resolved. Overall confidence: 82%."}

data: {"step":3,"agent":"ImpactAnalyzer","type":"start","emoji":"🔍","thought":"Now I need to understand what this actually means in business terms — not just what's wrong, but how bad it is."}

data: {"step":3,"agent":"ImpactAnalyzer","type":"observation","emoji":"💭","thought":"1,620 orders this week. If we can't fulfill them, that's 1,620 unhappy customers. At PKR 1,500 average order value — that's PKR 2.43 million at risk."}

data: {"step":3,"agent":"ImpactAnalyzer","type":"observation","emoji":"💭","thought":"The procurement manager needs to know right now. Customer service too — complaints are already flooding in."}

data: {"step":3,"agent":"ImpactAnalyzer","type":"result","emoji":"✅","thought":"Risk score: 8.7 out of 10. This is CRITICAL. We have a 2-hour window to act before things get significantly worse."}

data: {"step":4,"agent":"ActionPlannerAgent","type":"start","emoji":"🔍","thought":"Time to build a plan. I need to move fast but I also need to stay within the constraints."}

data: {"step":4,"agent":"ActionPlannerAgent","type":"decision","emoji":"✅","thought":"First action: verify the real stock count live from the warehouse system. I don't trust the PDF anymore."}

data: {"step":4,"agent":"ActionPlannerAgent","type":"decision","emoji":"✅","thought":"After confirming stock, we immediately notify the procurement manager — email and SMS. They need to authorize an emergency order."}

data: {"step":4,"agent":"ActionPlannerAgent","type":"observation","emoji":"💭","thought":"Emergency order budget is PKR 500,000. My estimate is PKR 420,000 — we're within limits. Marking this as FEASIBLE."}

data: {"step":4,"agent":"ActionPlannerAgent","type":"decision","emoji":"✅","thought":"After the order is placed, we update the customer portal. Telling people '2-3 days' when it'll actually take 9 is dishonest and will make complaints worse."}

data: {"step":4,"agent":"ActionPlannerAgent","type":"result","emoji":"✅","thought":"Plan ready: 5 actions, estimated PKR 420,000, resolution window ~10 hours. Each action has a fallback in case something goes wrong."}

data: {"step":5,"agent":"ExecutorAgent","type":"start","emoji":"🔍","thought":"Executing the plan now, step by step."}

data: {"step":5,"agent":"ExecutorAgent","type":"action","emoji":"🚀","thought":"Step 1: Calling the warehouse API to get real-time stock numbers..."}

data: {"step":5,"agent":"ExecutorAgent","type":"result","emoji":"✅","thought":"Got it. Item A: only 47 units remaining. Item B: 12 units. Status: critical_low. The old PDF was completely wrong."}

data: {"step":5,"agent":"ExecutorAgent","type":"action","emoji":"🚀","thought":"Step 2: Sending urgent email and SMS to the procurement manager..."}

data: {"step":5,"agent":"ExecutorAgent","type":"result","emoji":"✅","thought":"Sent. Message ID msg_8821. The procurement manager has been alerted with full shortage details."}

data: {"step":5,"agent":"ExecutorAgent","type":"action","emoji":"🚀","thought":"Step 3: Placing emergency order with FastSupply — 2,000 units of Item A and 800 of Item B..."}

data: {"step":5,"agent":"ExecutorAgent","type":"warning","emoji":"⚠️","thought":"FastSupply isn't responding. The API timed out after 5 seconds. This is a problem."}

data: {"step":5,"agent":"ExecutorAgent","type":"observation","emoji":"💭","thought":"Steps 4 and 5 are now blocked — I can't update delivery estimates without a confirmed order. Passing to Recovery."}

data: {"step":6,"agent":"RecoveryAgent","type":"start","emoji":"🔍","thought":"I see a failure. FastSupply timed out. Let me figure out the best way to recover."}

data: {"step":6,"agent":"RecoveryAgent","type":"decision","emoji":"✅","thought":"This looks like a transient network issue. Worth retrying before giving up."}

data: {"step":6,"agent":"RecoveryAgent","type":"warning","emoji":"⚠️","thought":"Retry 1 failed. Still timing out. Trying one more time..."}

data: {"step":6,"agent":"RecoveryAgent","type":"warning","emoji":"⚠️","thought":"Retry 2 also failed. FastSupply is definitely down. Activating the fallback plan."}

data: {"step":6,"agent":"RecoveryAgent","type":"recovery","emoji":"🔄","thought":"Switching to AlternateSupply. Placing the same order — 2,800 units total."}

data: {"step":6,"agent":"RecoveryAgent","type":"result","emoji":"✅","thought":"AlternateSupply confirmed: order ALT_ORD_9921. Cost PKR 465,000 — within our PKR 500,000 budget. Lead time: 7 days — actually better than FastSupply's 9 days."}

data: {"step":6,"agent":"RecoveryAgent","type":"action","emoji":"🚀","thought":"Unblocking step 4. Updating customer delivery estimates with the 7-day lead time from AlternateSupply."}

data: {"step":6,"agent":"RecoveryAgent","type":"result","emoji":"✅","thought":"1,620 customer records updated. Auto-reply drafted. Fully recovered."}

data: {"step":7,"agent":"ReporterAgent","type":"start","emoji":"🔍","thought":"Compiling the final report. Let me put together everything that happened."}

data: {"step":7,"agent":"ReporterAgent","type":"observation","emoji":"💭","thought":"Before: stale PDF said stock was fine. After: live data confirmed critically low — 47 units. The contradiction was real and mattered."}

data: {"step":7,"agent":"ReporterAgent","type":"observation","emoji":"💭","thought":"Emergency order placed — not with our first choice, but AlternateSupply came through. PKR 465,000 spent, within budget."}

data: {"step":7,"agent":"ReporterAgent","type":"done","emoji":"🎯","thought":"All 5 actions completed. PKR 2.43 million in revenue protected. Stockout risk reduced by 68%. 1,620 customers notified with honest 7-9 day estimates. 24-hour monitoring is now active."}

event: done
data: {"job_id": "job_a3f92b1c", "status": "completed"}
```

---

### Connection Lifecycle

```
1. Client connects → GET /api/v1/stream/{job_id}
2. Server opens SSE connection (HTTP 200, keep-alive)
3. Server waits for thoughts from async queue
4. As each agent runs:
     agent emits thought → queue → SSE endpoint → client
5. When pipeline finishes:
     server emits: event: done
     server closes connection
6. Client receives 'done' event → stop listening
```

---

### Integration Code

**React Native (Expo) — using `EventSource`:**

```javascript
import EventSource from 'react-native-event-source';

const subscribeToStream = (jobId, onThought, onDone) => {
  const es = new EventSource(
    `http://localhost:8000/api/v1/stream/${jobId}`
  );

  es.onmessage = (event) => {
    const thought = JSON.parse(event.data);
    // thought = { step, agent, type, emoji, thought, timestamp }
    onThought(thought);
  };

  es.addEventListener('done', (event) => {
    onDone(JSON.parse(event.data));
    es.close();
  });

  es.onerror = (err) => {
    console.error('Stream error:', err);
    es.close();
  };

  return es;  // call es.close() to disconnect early
};

// Usage in component:
const stream = subscribeToStream(
  jobId,
  (thought) => setThoughts(prev => [...prev, thought]),
  (result) => console.log('Pipeline done:', result)
);
```

**Web (JavaScript) — native `EventSource`:**

```javascript
const es = new EventSource(
  `http://localhost:8000/api/v1/stream/${jobId}`
);

es.onmessage = (event) => {
  const thought = JSON.parse(event.data);
  appendToThinkingFeed(thought.emoji, thought.thought, thought.agent);
};

es.addEventListener('done', () => {
  markPipelineComplete();
  es.close();
});
```

---

### Rendering Thoughts in UI

Recommended display format for the thinking feed:

```
┌─────────────────────────────────────────────────────────┐
│ 🤖 Agent Thinking Stream                                 │
├─────────────────────────────────────────────────────────┤
│ Step 1 · IngestionAgent                                  │
│ 🔍  Let me go through each of the 5 sources...          │
│ 💭  First up: a warehouse PDF from May 7th. 8 days old.  │
│ 💭  Supplier API — stock unavailable. 9-day lead time.   │
│ ✅  Done. 5 sources processed. 1 stale. 0 noise.         │
│                                                          │
│ Step 2 · InsightAgent                                    │
│ 🔍  Finding the real signals...                          │
│ ⚡  Two sources disagree on stock levels!                │
│ ✅  API wins over PDF. Contradiction resolved.           │
│                                                          │
│ Step 5 · ExecutorAgent                                   │
│ 🚀  Placing emergency order with FastSupply...           │
│ ⚠️   FastSupply timed out. Problem.                      │
│                                                          │
│ Step 6 · RecoveryAgent                                   │
│ 🔄  Switching to AlternateSupply...                      │
│ ✅  Order ALT_ORD_9921 confirmed. Recovered.             │
│                                                          │
│ Step 7 · ReporterAgent                                   │
│ 🎯  All done. PKR 2.43M protected. 68% risk reduction.  │
└─────────────────────────────────────────────────────────┘
```

---

### Error Responses

| Code | Reason |
|---|---|
| `404` | `job_id` not found |
| `409` | Pipeline already completed — stream is no longer available |

---

### Description
Run the full pipeline **synchronously** — waits for all 7 agents to complete and returns the full result in one response. Useful for testing and mobile app direct calls.

> ⚠️ This will block for ~30–50 seconds. Recommended only for demos or when async polling is not feasible.

### Request Body
Same as `POST /api/v1/run`

### Response — `200 OK`
Same as `GET /api/v1/result/{job_id}` — the complete pipeline result, returned directly.

---

## `GET /api/v1/health`

### Description
Health check endpoint. Returns server status and configuration validity.

### Response — `200 OK`

```json
{
  "status": "ok",
  "api_version": "1.0.0",
  "deepseek_key_configured": true,
  "agents_loaded": 7,
  "uptime_seconds": 3600
}
```

---

## Request/Response Flow Diagram

```
CLIENT                         API SERVER                      AGENTS
  │                                │                              │
  │ POST /api/v1/run               │                              │
  │ {sources[], constraints}       │                              │
  │──────────────────────────────▶│                              │
  │                                │ validate input               │
  │                                │ create job_id                │
  │ 202 Accepted                   │ launch pipeline async        │
  │ {job_id, status:"queued"}      │──────────────────────────────▶
  │◀──────────────────────────────│                              │
  │                                │                    Agent 1   │
  │                                │                    Agent 2   │
  │ GET /api/v1/status/{job_id}   │                    Agent 3   │
  │──────────────────────────────▶│                    ...       │
  │ 200 {status:"running", step:3} │                              │
  │◀──────────────────────────────│                              │
  │                                │                    Agent 7   │
  │ (polling every 5 seconds)      │                    Done ✅   │
  │                                │◀─────────────────────────────
  │ GET /api/v1/status/{job_id}   │                              │
  │──────────────────────────────▶│                              │
  │ 200 {status:"completed"}       │                              │
  │◀──────────────────────────────│                              │
  │                                │                              │
  │ GET /api/v1/result/{job_id}   │                              │
  │──────────────────────────────▶│                              │
  │ 200 {full pipeline result}     │                              │
  │◀──────────────────────────────│                              │
```

---

## Mobile App Integration (React Native)

```javascript
// 1. Submit pipeline job
const submitPipeline = async (sources, constraints) => {
  const response = await fetch('http://localhost:8000/api/v1/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sources, constraints })
  });
  const { job_id } = await response.json();
  return job_id;
};

// 2. Poll for status
const pollStatus = async (jobId) => {
  while (true) {
    const res = await fetch(`http://localhost:8000/api/v1/status/${jobId}`);
    const data = await res.json();

    if (data.status === 'completed') return data;
    if (data.status === 'failed') throw new Error(data.error);

    await new Promise(resolve => setTimeout(resolve, 5000)); // wait 5s
  }
};

// 3. Get result
const getResult = async (jobId) => {
  const res = await fetch(`http://localhost:8000/api/v1/result/${jobId}`);
  return await res.json();
};

// 4. Full flow
const runPipeline = async () => {
  const jobId = await submitPipeline(SOURCES, CONSTRAINTS);
  await pollStatus(jobId);
  const result = await getResult(jobId);
  console.log(result.final_report.projected_impact);
};
```

---

## Error Response Format (Standard)

All errors follow this format:

```json
{
  "error": "error_type",
  "message": "human readable description",
  "detail": "optional technical detail",
  "job_id": "job_a3f92b1c",
  "timestamp": "2026-05-15T10:15:00Z"
}
```

### Error Types

| Error Type | HTTP Code | When It Happens |
|---|---|---|
| `validation_error` | 422 | Missing or invalid request fields |
| `job_not_found` | 404 | `job_id` doesn't exist |
| `job_still_running` | 409 | Tried to get result before completion |
| `pipeline_failed` | 500 | Unrecoverable agent failure |
| `api_key_missing` | 500 | `DEEPSEEK_API_KEY` not in `.env` |
| `deepseek_error` | 502 | DeepSeek API returned an error |
| `timeout` | 504 | Pipeline exceeded max duration |

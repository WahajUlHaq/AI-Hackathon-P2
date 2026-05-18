# ChainSight — Gemini Antigravity Orchestration Traces

This document shows exactly how ChainSight uses **Google Gemini function-calling (Antigravity-style)** to orchestrate the entire supply chain analysis pipeline autonomously, and what the full SSE event trace looks like from start to finish.

---

## What is the Antigravity Pattern?

Google Antigravity is the model-driven orchestration approach where **the LLM itself decides** which tools to call, in what order, and what to do with each result — rather than a hardcoded Python script calling agents sequentially.

In ChainSight:
- `POST /api/analyze` triggers the orchestrator
- Gemini 2.5-Flash-Lite is given **14 MCP tools as function declarations**
- Gemini reads each tool result before deciding its next call
- Every call and result is broadcast as a **Server-Sent Event (SSE)** in real time
- If Gemini quota is exhausted → **DeepSeek** takes over with the same tools
- If DeepSeek also fails → **Python direct fallback** runs the fixed pipeline

```
Client ──POST /api/analyze──► FastAPI
         ◄──SSE stream───────  GET /api/stream/{session_id}

FastAPI ──► Gemini (function-calling loop)
              │  parse_sources()       ← Gemini calls this
              │  ◄ result              ← Gemini reads the result
              │  extract_insights()    ← Gemini calls next
              │  ◄ result
              │  plan_actions()        ← Gemini calls next
              │  ◄ result
              │  execute_action()      ← Gemini calls with primary_action_id
              │  ◄ result
              └─ STOP + return summary
```

---

## SSE Event Stream Format

Every event is a `text/event-stream` message with `event:` and `data:` (JSON).

| Event Type | When Emitted | Key Fields |
|---|---|---|
| `orchestrator_start` | Pipeline begins | `session_id`, `sources_count` |
| `tool_call` | Gemini calls a tool | `tool`, `args`, `call_number` |
| `tool_result` | Tool returns result | `tool`, `call_number`, `success`, `result` |
| `orchestrator_done` | Gemini finishes loop | `message`, `tool_calls_total`, `summary` |
| `pipeline_done` | Full result ready | Complete `AnalyzeResponse` JSON |
| `pipeline_error` | Unrecoverable failure | `error` string |

---

## Full Trace — Port Strike Scenario (Gemini Primary)

**Input:**
```
POST /api/analyze
{
  "content": "Port of Karachi dock-worker strike, day 3. 847 pallets of SKU-A001
  stranded. 40% backlog. Lahore DC has 2.3 days of supply remaining..."
}
```

**SSE Stream (real captured output):**

```
event: orchestrator_start
data: {
  "message": "Gemini orchestrator started",
  "session_id": "session-1747123456789",
  "sources_count": 1
}

event: tool_call
data: {
  "tool": "parse_sources",
  "args": { "session_id": "session-1747123456789" },
  "call_number": 1
}

event: tool_result
data: {
  "tool": "parse_sources",
  "call_number": 1,
  "success": true,
  "result": {
    "session_id": "session-1747123456789",
    "sources_parsed": 1,
    "noise_filtered": 0,
    "entities_found": 1,
    "credibility_scores": { "src-1": 0.80 },
    "key_metrics": {
      "backlog_pct": 40,
      "affected_shipments": 847,
      "delay_days": 5,
      "revenue_at_risk_usd": 127050,
      "days_of_supply_remaining": 2.3,
      "supplier_reliability_pct": null
    },
    "time_horizon": "72 hours",
    "entities": [
      {
        "disruption_type": "port_strike",
        "location": "Port of Karachi",
        "affected_region": "Lahore Distribution Center",
        "duration_days": 3,
        "severity": "critical",
        "raw_facts": [
          "847 pallets of SKU-A001 stranded at port holding areas",
          "40% shipment backlog accumulated across inbound logistics",
          "Lahore DC inventory covers only 2.3 days of demand"
        ]
      }
    ],
    "next_step": "Call extract_insights with this session_id"
  }
}

event: tool_call
data: {
  "tool": "extract_insights",
  "args": { "session_id": "session-1747123456789" },
  "call_number": 2
}

event: tool_result
data: {
  "tool": "extract_insights",
  "call_number": 2,
  "success": true,
  "result": {
    "session_id": "session-1747123456789",
    "title": "Port of Karachi Strike — Critical Stockout & SLA Breach Risk",
    "urgency": "immediate",
    "total_exposure_usd": 127050,
    "affected_skus": ["SKU-A001", "SKU-B042", "SKU-C118"],
    "key_risks": [
      "Lahore DC stockout in 2.3 days without rerouting",
      "SLA breach for 23 retail partners within 48 hours",
      "15% probability of additional road disruption due to monsoon forecast"
    ],
    "causal_chains": [
      {
        "cause": "Port of Karachi dock-worker strike (day 3, indefinite)",
        "immediate_effect": "847 pallets stranded; all container handling suspended",
        "downstream_effect": "Lahore DC stockout in 2.3 days; SLA penalties for 23 retailers",
        "financial_impact_usd": 127050,
        "probability_pct": 85
      }
    ],
    "next_step": "Call plan_actions with this session_id"
  }
}

event: tool_call
data: {
  "tool": "plan_actions",
  "args": { "session_id": "session-1747123456789" },
  "call_number": 3
}

event: tool_result
data: {
  "tool": "plan_actions",
  "call_number": 3,
  "success": true,
  "result": {
    "session_id": "session-1747123456789",
    "primary_action_id": "ACT-001",
    "total_budget_usd": 500,
    "rationale": "ACT-001 reroutes via Gwadar to unblock stranded pallets — highest savings at $99,960. ACT-002 activates Lahore DC safety stock as bridge. ACT-003 notifies retail partners of delay to manage SLA. ACT-004 adjusts Lahore pricing to reduce demand pressure.",
    "ranked_actions": [
      {
        "action_id": "ACT-001",
        "action_type": "reroute_shipment",
        "title": "Reroute 847 Pallets via Gwadar Port",
        "confidence_pct": 85,
        "estimated_savings_usd": 99960,
        "feasibility_status": "feasible",
        "parameters": {
          "route_id": "KHI-LHE-001",
          "reason": "port_strike",
          "new_waypoints": ["Gwadar", "N-55 Highway", "Lahore DC"]
        }
      },
      {
        "action_id": "ACT-002",
        "action_type": "activate_safety_stock",
        "title": "Activate Safety Stock at Lahore DC",
        "confidence_pct": 90,
        "estimated_savings_usd": 22500,
        "feasibility_status": "feasible",
        "parameters": { "dc": "lahore_dc" }
      },
      {
        "action_id": "ACT-003",
        "action_type": "send_notification",
        "title": "Alert 23 Retail Partners of Delay",
        "confidence_pct": 95,
        "estimated_savings_usd": 4590,
        "feasibility_status": "feasible",
        "parameters": {
          "notification_type": "alert",
          "recipients": ["ops@chainsight.io", "logistics@partner.com"],
          "subject": "Port of Karachi Strike — Delivery Delay Notice",
          "body": "Critical: Port of Karachi strike (day 3) is causing 4-7 day delays. Reroute via Gwadar initiated. Updated ETA to follow.",
          "priority": "high"
        }
      }
    ],
    "next_step": "Call execute_action with this session_id"
  }
}

event: tool_call
data: {
  "tool": "execute_action",
  "args": {
    "session_id": "session-1747123456789",
    "action_id": "ACT-001"
  },
  "call_number": 4
}

event: tool_result
data: {
  "tool": "execute_action",
  "call_number": 4,
  "success": true,
  "result": {
    "session_id": "session-1747123456789",
    "action_id": "ACT-001",
    "action_type": "reroute_shipment",
    "title": "Reroute 847 Pallets via Gwadar Port",
    "status": "success",
    "attempt": 1,
    "latency_ms": 187,
    "api_calls_total": 1,
    "api_calls_succeeded": 1,
    "state_before": {
      "penalty_exposure_usd": 320000,
      "notifications_count": 2
    },
    "state_after": {
      "penalty_exposure_usd": 220040,
      "notifications_count": 2
    },
    "penalty_delta_usd": -99960,
    "completed_actions_so_far": ["ACT-001"]
  }
}

event: orchestrator_done
data: {
  "message": "Gemini orchestrator completed",
  "tool_calls_total": 4,
  "summary": "Pipeline complete. Rerouted 847 pallets via Gwadar, activated Lahore safety stock, and notified 23 retail partners. Penalty exposure reduced by $99,960."
}

event: pipeline_done
data: {
  "session_id": "session-1747123456789",
  "parsed": { ... },
  "insight": { ... },
  "plan": { ... },
  "execution": {
    "total_actions_attempted": 1,
    "total_actions_succeeded": 1,
    "penalty_reduction_usd": 99960,
    "eta_improvement_days": 0.0,
    "total_latency_ms": 187,
    "outcome_summary": "Orchestrated by Gemini via function calling."
  }
}
```

---

## Trace — DeepSeek Fallback (Gemini Quota Exhausted)

When Gemini hits its daily quota (429 RPD), the orchestrator transparently switches to DeepSeek Chat using the **OpenAI tool-calling format** with the same 14 tools.

```
event: orchestrator_start
data: {
  "message": "Gemini quota exhausted — switching to DeepSeek orchestrator",
  "tool_calls_total": 0
}

event: tool_call
data: { "tool": "parse_sources", "args": { "session_id": "..." }, "call_number": 1 }

event: tool_result
data: { "tool": "parse_sources", "call_number": 1, "success": true, "result": { ... } }

event: tool_call
data: { "tool": "extract_insights", "args": { "session_id": "..." }, "call_number": 2 }

... (identical pipeline, different orchestrator)

event: orchestrator_done
data: {
  "message": "DeepSeek orchestrator completed",
  "tool_calls_total": 0,
  "summary": ""
}
```

The DeepSeek fallback uses `run_agentic_loop` in `backend/deepseek_client.py` — an OpenAI-compatible tool-calling loop that mirrors the Gemini Antigravity pattern.

---

## Trace — Multi-Source with Contradiction Detection

**Input (5 sources with contradicting backlog figures):**
```
POST /api/analyze
{
  "sources": [
    { "source_id": "src-1", "source_type": "realtime_feed",
      "content": "Karachi port backlog at 40%...", "timestamp_utc": "2026-05-13T06:00:00Z" },
    { "source_id": "src-2", "source_type": "news_article",
      "content": "Port backlog reportedly at 65%...", "timestamp_utc": "2026-05-12T18:00:00Z" },
    { "source_id": "src-3", "source_type": "dashboard",
      "content": "Current inventory: Lahore DC 2.3 days...", "timestamp_utc": "2026-05-13T05:30:00Z" },
    { "source_id": "src-4", "source_type": "pdf_report",
      "content": "SLA penalty clause: PKR 150/pallet/day...", "timestamp_utc": "2026-05-10T00:00:00Z" },
    { "source_id": "src-5", "source_type": "csv_json",
      "content": "[{\"sku\":\"SKU-A001\",\"pallets_at_risk\":847}]", "timestamp_utc": "2026-05-13T06:00:00Z" }
  ]
}
```

**parse_sources result (contradiction detected + resolved):**
```json
{
  "sources_parsed": 5,
  "noise_filtered": 0,
  "entities_found": 1,
  "contradictions_detected": 1,
  "credibility_scores": {
    "src-1": 0.92,
    "src-2": 0.64,
    "src-3": 0.85,
    "src-4": 0.55,
    "src-5": 0.70
  },
  "contradictions": [
    {
      "metric": "backlog_pct",
      "source_a_id": "src-1",
      "source_a_claim": "40%",
      "source_b_id": "src-2",
      "source_b_claim": "65%",
      "resolution": "source_a_preferred",
      "resolution_reason": "src-1 is realtime_feed (credibility 0.92) and 12 hours more recent than src-2 (news_article, credibility 0.64)"
    }
  ],
  "temporal_signals": [
    {
      "metric": "backlog_pct",
      "trend": "rising",
      "change_pct": 62.5,
      "observation": "backlog grew from ~25% baseline to 40% confirmed over 24 hours"
    }
  ]
}
```

---

## Gemini Function Declarations (Tool Schema)

The orchestrator registers all 14 MCP tools as Gemini `FunctionDeclaration` objects. Here are the key pipeline tools:

```python
# Simplified — see backend/orchestrator.py _to_gemini_tools()

parse_sources(session_id: str)
# Parses all pre-loaded sources, returns entities + metrics + contradictions

extract_insights(session_id: str)
# Builds causal chains (cause → effect → $-impact) from parsed data

plan_actions(session_id: str)
# Ranks actions by savings, feasibility, confidence — returns primary_action_id

execute_action(session_id: str, action_id: str)
# Calls mock API (routing/inventory/pricing/notifications), captures before/after state

get_system_state()
# Returns live snapshot of all 3 DCs, routes, pricing, notifications

reset_state()
# Resets all mock API state to baseline (demo use)
```

---

## System Instruction (Gemini Prompt)

```
You are ChainSight Orchestrator — an autonomous supply chain intelligence agent.

Your job: orchestrate the full analysis pipeline by calling tools in strict order.

PIPELINE — follow exactly:
1. parse_sources(session_id)               ← call with ONLY session_id
2. extract_insights(session_id)            ← causal chains + dollar exposure
3. plan_actions(session_id)               ← ranked action plan
4. execute_action(session_id, action_id)  ← call once with primary_action_id from step 3
5. Stop and return your final summary.

IMPORTANT RULES:
- Do NOT pass a 'sources' list to parse_sources — just session_id. Sources are pre-loaded.
- Pass the SAME session_id to every tool call.
- After parse_sources succeeds, IMMEDIATELY call extract_insights — do not stop.
- After extract_insights succeeds, IMMEDIATELY call plan_actions — do not stop.
- After plan_actions succeeds, IMMEDIATELY call execute_action with primary_action_id.
- After execute_action, STOP calling tools and return your summary.
- Never repeat a tool call that already succeeded.
- Never ask clarifying questions — just execute the pipeline.
```

---

## Orchestration Architecture

```
POST /api/analyze
        │
        ▼
  Input Validation  ──── not supply-chain? ──► 422 irrelevant_input
        │
        ▼
  _run_pipeline()
        │
        ├─── Gemini 2.5-Flash-Lite (Antigravity function-calling loop)
        │         │
        │    ┌────▼─────────────────────────────────┐
        │    │  Multi-turn conversation              │
        │    │  contents = [user_msg]                │
        │    │                                       │
        │    │  while tool_calls < 30:               │
        │    │    response = gemini.generate(...)    │
        │    │    for fc in function_calls:          │
        │    │      emit SSE "tool_call"             │
        │    │      result = _handle_tool_call(...)  │
        │    │      emit SSE "tool_result"           │
        │    │    contents.append(tool_results)      │
        │    │    if no more function_calls: STOP    │
        │    └───────────────────────────────────────┘
        │
        ├─── On Gemini 429 → DeepSeek agentic loop (OpenAI tool-calling)
        │
        └─── On any failure → Python direct fallback (hardcoded sequence)
                  parse_sources → extract_insights → plan_actions → execute_action
```

---

## Key Implementation Files

| File | Role |
|---|---|
| [backend/orchestrator.py](backend/orchestrator.py) | Gemini Antigravity loop + DeepSeek fallback |
| [backend/deepseek_client.py](backend/deepseek_client.py) | DeepSeek agentic loop (`run_agentic_loop`) |
| [backend/mcp_server.py](backend/mcp_server.py) | 14 MCP tools + `_handle_tool_call` dispatcher |
| [backend/main.py](backend/main.py) | FastAPI endpoints, SSE queue, input validation |
| [backend/agents/parser_agent.py](backend/agents/parser_agent.py) | Multi-source parser (DeepSeek-powered) |
| [backend/agents/insight_agent.py](backend/agents/insight_agent.py) | Causal chain extractor (DeepSeek-powered) |
| [backend/agents/planner_agent.py](backend/agents/planner_agent.py) | Action ranker (DeepSeek-powered) |
| [backend/agents/executor_agent.py](backend/agents/executor_agent.py) | Mock API executor (no LLM) |
| [backend/contract.py](backend/contract.py) | JSON contract validator — PASS/WARN/REJECT |
| [mcp_config.json](mcp_config.json) | Google Antigravity MCP server config |

---

## Live Stream — How to Watch in Real Time

```bash
# 1. Open the SSE stream FIRST (use a fixed session ID)
curl -N "http://localhost:8000/api/stream/my-session-001"

# 2. In a second terminal, trigger the analysis
curl -X POST "http://localhost:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "my-session-001",
    "content": "Port of Karachi strike day 3. 847 pallets stranded. Lahore DC stockout in 2.3 days."
  }'
```

You will see each `tool_call` and `tool_result` event appear in terminal 1 as Gemini calls each tool — this is the Antigravity trace in action.

---

## Input Validation

ChainSight rejects non-supply-chain content before consuming any API quota:

```
POST /api/analyze  { "content": "hello world" }

→ 422 Unprocessable Entity
{
  "error": "irrelevant_input",
  "message": "ChainSight only analyses supply chain events. Please provide
              content about disruptions, shipments, logistics, inventory,
              or related topics."
}
```

The guard checks for at least **2 supply-chain keywords** (port, strike, shipment, cargo, logistics, inventory, pallet, route, delay, stockout, sku, dc, etc.) before admitting the request to the pipeline.

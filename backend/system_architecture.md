# 🏗️ System Architecture — Autonomous Content-to-Action Agent

## Document Purpose

This document describes the complete system architecture of the Autonomous Content-to-Action Agent — how it is structured, how agents are orchestrated, how data flows through the pipeline, and how Google Antigravity sits at the center of all orchestration.

---

## 1. High-Level System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                                      │
│         Mobile App (React Native)  ·  Web Dashboard (Next.js)       │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP REST
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    API LAYER                                         │
│              FastAPI  ·  Uvicorn  ·  REST + SSE Endpoints           │
│   POST /run · GET /status · GET /result · GET /stream/{job_id}      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ calls
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│              GOOGLE ANTIGRAVITY — ORCHESTRATION CORE                 │
│                     orchestrator.py                                  │
│                                                                      │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐       │
│   │ Agent 1  │──▶│ Agent 2  │──▶│ Agent 3  │──▶│ Agent 4  │       │
│   │Ingestion │   │ Insight  │   │ Impact   │   │ Planner  │       │
│   └──────────┘   └──────────┘   └──────────┘   └────┬─────┘       │
│                                                       │             │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐         │             │
│   │ Agent 7  │◀──│ Agent 6  │◀──│ Agent 5  │◀────────┘             │
│   │ Reporter │   │Recovery  │   │Executor  │                        │
│   └──────────┘   └──────────┘   └──────────┘                       │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ all agents call
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    LLM LAYER                                         │
│                  DeepSeek API  (deepseek-chat)                      │
│              llm_client.py  ·  json_object mode                     │
└─────────────────────────────────────────────────────────────────────┘
                           │ results stored
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PERSISTENCE LAYER                                 │
│              output/pipeline_result.json                             │
│              (full pipeline output — all 7 agent outputs)           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Architectural Layers

### Layer 1: Client Layer
- **Mobile App** (React Native / Expo) — mandatory deliverable
- **Web Dashboard** (Next.js) — optional
- Clients submit raw source content and receive the final report
- All communication via HTTP REST to the API Layer

### Layer 2: API Layer
- **FastAPI** framework on **Uvicorn** server
- Receives `POST /api/v1/run` with sources and constraints
- Returns job ID immediately (async pipeline)
- Client polls `GET /api/v1/status/{job_id}` for completion
- Final result retrieved via `GET /api/v1/result/{job_id}`
- **Live thinking stream** via `GET /api/v1/stream/{job_id}` (SSE)

### Layer 3: Google Antigravity — Orchestration Core
- `orchestrator.py` is the **Antigravity workplan executor**
- Chains all 7 agents in strict sequence
- Holds all intermediate state between agent calls
- Logs every step (printed + saved to JSON)
- This layer IS what Antigravity runs and traces

### Layer 4: LLM Layer
- All 7 agents call `llm_client.py → call_deepseek()`
- Single shared gateway to DeepSeek API
- Model: `deepseek-chat`, mode: `json_object`
- Temperature per agent: 0.1 (strict) to 0.2 (slight flexibility)

### Layer 5: Persistence Layer
- `output/pipeline_result.json` — complete structured output
- Contains all 7 agent outputs + final report + Antigravity trace
- This file is the submission artifact

---

## 3. Agent Orchestration — Detailed Sequence

```
orchestrator.run_pipeline(sources, constraints)
│
│  ┌─────────────────────────────────────────────────────┐
│  │ STEP 1 — IngestionAgent                             │
│  │  Input : sources[] (5 raw items)                    │
│  │  Output: content_blocks[] + ingestion_summary       │
│  │  Role  : Parse, score, flag, normalize              │
│  └─────────────────────────┬───────────────────────────┘
│                            │ content_blocks[]
│  ┌─────────────────────────▼───────────────────────────┐
│  │ STEP 2 — InsightAgent                               │
│  │  Input : content_blocks[]                           │
│  │  Output: insights[] + contradictions[]              │
│  │  Role  : Extract signals, resolve contradictions    │
│  └─────────────────────────┬───────────────────────────┘
│                            │ insights[]
│  ┌─────────────────────────▼───────────────────────────┐
│  │ STEP 3 — ImpactAnalyzer                             │
│  │  Input : insights[]                                 │
│  │  Output: impact_reports[] + risk_score              │
│  │  Role  : Quantify consequences, assign urgency      │
│  └─────────────────────────┬───────────────────────────┘
│                            │ impact_reports[] + constraints
│  ┌─────────────────────────▼───────────────────────────┐
│  │ STEP 4 — ActionPlannerAgent                         │
│  │  Input : impact_reports[] + constraints{}           │
│  │  Output: action_plan[] (3-5 actions with fallbacks) │
│  │  Role  : Generate + validate constrained actions    │
│  └─────────────────────────┬───────────────────────────┘
│                            │ action_plan[]
│  ┌─────────────────────────▼───────────────────────────┐
│  │ STEP 5 — ExecutorAgent                              │
│  │  Input : action_plan[]                              │
│  │  Output: execution_log[] + summary                  │
│  │  Role  : Simulate execution, inject failure         │
│  └─────────────────────────┬───────────────────────────┘
│                            │ execution_log[] + action_plan[]
│  ┌─────────────────────────▼───────────────────────────┐
│  │ STEP 6 — RecoveryAgent                              │
│  │  Input : execution_log[] + action_plan[]            │
│  │  Output: recovery_actions[] + post_recovery_log[]   │
│  │  Role  : Retry, fallback, rollback failed actions   │
│  └─────────────────────────┬───────────────────────────┘
│                            │ all outputs merged
│  ┌─────────────────────────▼───────────────────────────┐
│  │ STEP 7 — ReporterAgent                              │
│  │  Input : ALL previous outputs (dict of dicts)       │
│  │  Output: final_report + antigravity_trace           │
│  │  Role  : Compile results, generate trace            │
│  └─────────────────────────┬───────────────────────────┘
│                            │ full output
│  ┌─────────────────────────▼───────────────────────────┐
│  │ SAVE output/pipeline_result.json                    │
│  └─────────────────────────────────────────────────────┘
```

---

## 4. Live Thinking Stream — Architecture

### What It Is

The Thinking Stream is a **Server-Sent Events (SSE)** channel that runs in parallel to the main pipeline. As each agent processes its data, it emits human-language "thoughts" in real time — exactly like how a human expert would talk through their reasoning out loud.

This is not logs. It is **narrative thinking** — written as if the AI is explaining itself to a human:

```
"I'm reading the warehouse PDF... it says 500 units but wait —
 this was written 8 days ago. That's stale. I'm not going to 
 trust this over the supplier API."
```

### Stream Architecture

```
CLIENT (Mobile / Web)
  │
  │  GET /api/v1/stream/{job_id}
  │  Accept: text/event-stream
  │──────────────────────────────────────────────────────▶
  │                                                      │
  │◀── SSE: data: {thought, agent, step, type} ─────────│
  │◀── SSE: data: {thought, agent, step, type} ─────────│
  │◀── SSE: data: {thought, agent, step, type} ─────────│
  │   (stream stays open until pipeline completes)       │
  │◀── SSE: event: done ────────────────────────────────│
  │                                                      │
  │  Connection closed                                   │
```

### Thought Emitter Pattern

Each agent has a **thought emitter** — a function that pushes human-language thought events into an async queue. The SSE endpoint reads from this queue and sends events to the client.

```python
# Inside each agent, before/during/after key decisions:
await thought_queue.put({
    "agent": "InsightAgent",
    "step": 2,
    "type": "observation",
    "thought": "I found something interesting — two sources are "
                "saying completely different things about stock levels."
})
```

### Thought Event Types

| Type | When Used | Example |
|---|---|---|
| `start` | Agent begins | "I'm now reading all 5 sources you gave me..." |
| `observation` | Agent notices something | "This PDF is 8 days old — that's suspicious." |
| `decision` | Agent makes a choice | "I'm going to trust the API over the PDF." |
| `conflict` | Contradiction found | "Wait — these two sources disagree. Let me figure out which one is right." |
| `action` | Action being taken | "Sending an emergency alert to the procurement manager now." |
| `warning` | Something concerning | "The supplier timed out. I'll try again before giving up." |
| `recovery` | Recovering from failure | "FastSupply failed twice. Switching to AlternateSupply — they can do it in 7 days." |
| `result` | Step complete | "Done. Stock is critically low — only 47 units of Item A remain." |
| `done` | Entire pipeline finished | "All done. I've protected PKR 2.43M and notified 1,620 customers." |

### Full Thought Timeline (Demo Scenario)

```
[Agent 1 — Ingestion]
  💭 "Let me go through each of the 5 sources you gave me, one by one."
  💭 "First up: a warehouse PDF from May 7th. That's 8 days ago — I'll flag this as stale."
  💭 "Next: a news article from this morning about a transport strike. This looks credible."
  💭 "The sales CSV shows orders jumped from 1,200 to 1,620 this week. That's a 35% spike."
  💭 "Supplier API is fresh — just 30 minutes old. Stock unavailable, 9-day lead time. That's bad."
  💭 "Customer feed: 15 complaints in 2 hours about items being out of stock. Alarm bells ringing."
  ✅ "Done reading. 5 sources processed. 1 is stale. None are noise."

[Agent 2 — Insight]
  💭 "Something doesn't add up. The old PDF says there's 500 units — but the supplier API says stock is gone."
  💭 "These two sources are contradicting each other directly."
  💭 "Let me compare them: the PDF is 8 days old with a credibility score of 0.3... the API is from today with 0.9."
  💭 "Easy call. The API wins. The PDF was written before the strike hit. I'll mark it as outdated."
  💭 "Now looking at the trend: orders up 35% this week, INTO a confirmed stock shortage. That's a crisis."
  💭 "The complaint spike — 400% above average — confirms customers are already feeling it."
  ✅ "I see 3 meaningful signals: inventory risk (CRITICAL), demand surge (HIGH), and a resolved contradiction."

[Agent 3 — Impact]
  💭 "1,620 orders this week. If stock runs out, that's 1,620 unfulfilled orders."
  💭 "Average order value is PKR 1,500. So we're looking at roughly PKR 2.43 million in potential lost revenue."
  💭 "The procurement manager needs to know immediately. Customer service too — complaints are already coming in."
  💭 "This is CRITICAL. We have maybe 2 hours before this gets worse."
  ✅ "Risk score: 8.7 out of 10. Top priority: the inventory shortage."

[Agent 4 — Planner]
  💭 "We need to act fast. First thing — verify the real stock count directly from the warehouse system."
  💭 "The old PDF said 500 units, but I don't believe that anymore. I need the real number."
  💭 "After confirming, we alert the procurement manager — they need to authorize an emergency order."
  💭 "Emergency order budget is PKR 500,000. I'm estimating the order at PKR 420,000 — that fits."
  💭 "And after the order, we update the customer portal. No point promising 2-3 days when it'll take 9."
  💭 "I'll also schedule a recheck every 6 hours for 24 hours to make sure things don't slip again."
  ✅ "Plan ready: 5 actions, PKR 420,000 estimated cost, ~10 hour resolution window."

[Agent 5 — Executor]
  💭 "Running step 1: Calling the warehouse API to get real stock numbers..."
  💭 "Got it — Item A: only 47 units. Item B: 12 units. That's critically low. The PDF was completely wrong."
  💭 "Step 2: Sending urgent email and SMS to the procurement manager now..."
  💭 "Sent. Message ID msg_8821. They've been notified."
  💭 "Step 3: Placing emergency order with FastSupply for 2,800 units..."
  ⚠️  "Hmm. FastSupply isn't responding. The request timed out after 5 seconds."
  💭 "Step 4 and 5 are blocked — I can't update delivery estimates without a confirmed order."
  ✅ "3 steps done, 1 failed, 1 blocked. Handing over to recovery."

[Agent 6 — Recovery]
  💭 "FastSupply timed out. This looks like a transient network issue — worth retrying."
  💭 "Retry 1... still timing out. Retry 2... still nothing."
  ⚠️  "FastSupply is definitely down. But we have a fallback: AlternateSupply."
  💭 "Switching to AlternateSupply now. Placing the same order — 2,800 units."
  💭 "AlternateSupply confirmed: order ALT_ORD_9921. Cost PKR 465,000 — still within our budget."
  💭 "Lead time is 7 days instead of 9. Actually slightly better."
  💭 "Now unblocking step 4 — we can update the delivery estimate using the 7-day lead time."
  ✅ "Fully recovered. Order confirmed. Step 4 completed successfully."

[Agent 7 — Reporter]
  💭 "Pulling everything together for the final report..."
  💭 "Before: we had a stale PDF saying stock was fine. After: real data shows critically low stock."
  💭 "An emergency order was placed — not with our first choice, but the fallback worked."
  💭 "1,620 customers have been notified with honest delivery estimates."
  💭 "PKR 2.43 million in revenue protected. Stockout risk reduced by 68%."
  ✅ "All done. Full Antigravity trace compiled and ready for submission."
```

### Queue-Based Implementation

```
Orchestrator starts pipeline
         │
         │ creates shared AsyncQueue
         │ passes queue to all agents
         │
         ├── Pipeline runs agents 1→7 sequentially
         │     Each agent.run() calls emit_thought(queue, ...)
         │
         └── SSE endpoint reads queue
               yields SSE events to client in real time
               closes stream when pipeline.done = True
```

---

## 5. Google Antigravity — Orchestration Role

Antigravity is the environment in which this entire system runs. It is responsible for:

| Antigravity Function | How It's Implemented |
|---|---|
| **Workplan generation** | `orchestrator.py` creates a 7-step workplan at startup |
| **Task planning** | Each agent call = one task in the plan |
| **Reasoning trace** | Each agent's `agent_reasoning` field + print logs |
| **Tool/API integration** | `llm_client.py` manages all DeepSeek calls as tools |
| **Action execution** | Agent 5 simulates all action executions |
| **Failure recovery** | Agent 6 handles all retry/fallback/rollback decisions |
| **Trace export** | `antigravity_trace` in the final report = submission log |
| **Decision flow** | Every agent outputs `agent_reasoning` explaining its decisions |

### What Antigravity Traces

```json
{
  "antigravity_trace": {
    "workplan": "Validate → Notify → Order → Update → Monitor",
    "task_plan": [
      "Task 1: Ingest 5 sources (1 stale, 0 noise)",
      "Task 2: Extract 3 insights, 1 contradiction resolved",
      "Task 3: Impact scored 8.7/10 — CRITICAL urgency",
      "Task 4: 5-action plan generated — PKR 420,000 budget",
      "Task 5: 3 succeeded, 1 FAILED (API timeout), 1 skipped",
      "Task 6: Fallback to AlternateSupply — RECOVERED",
      "Task 7: Final report compiled — 68% risk reduction"
    ],
    "reasoning_steps": ["..."],
    "tool_calls": ["..."],
    "failures_and_recovery": ["..."],
    "final_outcome": "All 5 actions completed. PKR 2.43M protected."
  }
}
```

---

## 5. Data Flow Diagram (Full)

```
[Raw Source 1: PDF]  ──────────────────────────────────────┐
[Raw Source 2: URL]  ──────────────────────────────────────┤
[Raw Source 3: CSV]  ──────── Agent 1 (Ingestion) ─────────┤
[Raw Source 4: JSON] ──────────────────────────────────────┤
[Raw Source 5: Feed] ──────────────────────────────────────┘
                                     │
                             content_blocks[]
                             (id, raw_text,
                              credibility,
                              is_stale,
                              domain)
                                     │
                                     ▼
                          Agent 2 (Insight)
                                     │
                        InsightPacket {
                          insights[],
                          contradictions[],
                          temporal_signals[],
                          overall_confidence
                        }
                                     │
                                     ▼
                          Agent 3 (Impact)
                                     │
                        ImpactReport {
                          financial_impact,
                          operational_impact,
                          customer_impact,
                          stakeholders,
                          urgency,
                          risk_score
                        }
                                     │
                               + constraints{}
                                     │
                                     ▼
                          Agent 4 (Planner)
                                     │
                        ActionPlan [
                          {VALIDATE, depends_on:[]},
                          {NOTIFY,   depends_on:[act_001]},
                          {ORDER,    depends_on:[act_001,act_002]},
                          {UPDATE,   depends_on:[act_003]},
                          {MONITOR,  depends_on:[act_003]}
                        ]
                                     │
                                     ▼
                          Agent 5 (Executor)
                                     │
                        ExecutionLog [
                          act_001: SUCCESS ✅
                          act_002: SUCCESS ✅
                          act_003: FAILED  ❌ (API_TIMEOUT)
                          act_004: SKIPPED ⏭
                          act_005: SUCCESS ✅
                        ]
                                     │
                          ┌──────────┘
                          │ FAILED: act_003
                          ▼
                 Agent 6 (Recovery)
                          │
                 RecoveryLog {
                   act_003: RETRY×2→FALLBACK→RECOVERED
                   act_004: UNBLOCKED→SUCCESS
                 }
                          │
                 merged: full_log[]
                          │
                          ▼
                 Agent 7 (Reporter)
                          │
                 FinalReport {
                   before_after[],
                   timeline[],
                   cost_analysis,
                   projected_impact,
                   antigravity_trace
                 }
                          │
                          ▼
              output/pipeline_result.json
```

---

## 6. File Structure

```

│
├── orchestrator.py              ← Antigravity entry point
├── requirements.txt             ← Python dependencies
├── .env                         ← DEEPSEEK_API_KEY
│
├── agents/
│   ├── __init__.py
│   ├── llm_client.py            ← Shared DeepSeek gateway
│   ├── agent1_ingestion.py      ← Step 1
│   ├── agent2_insight.py        ← Step 2
│   ├── agent3_impact.py         ← Step 3
│   ├── agent4_planner.py        ← Step 4
│   ├── agent5_executor.py       ← Step 5
│   ├── agent6_recovery.py       ← Step 6
│   └── agent7_reporter.py       ← Step 7
│
├── api/
│   ├── __init__.py
│   ├── main.py                  ← FastAPI app + all routes
│   ├── models.py                ← Pydantic request/response models
│   └── stream.py                ← SSE thinking stream + thought emitter
│
├── output/
│   └── pipeline_result.json     ← Auto-generated on each run
│
└── docs/
    ├── system_architecture.md   ← THIS FILE
    ├── api_reference.md         ← HTTP API documentation
    ├── module_llm_client.md
    ├── module_orchestrator.md
    ├── agent1_ingestion.md
    ├── agent2_insight.md
    ├── agent3_impact.md
    ├── agent4_planner.md
    ├── agent5_executor.md
    ├── agent6_recovery.md
    └── agent7_reporter.md
```

---

## 7. Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Orchestration Platform | Google Antigravity | Core agent runtime, trace, workplan |
| LLM Provider | DeepSeek (`deepseek-chat`) | All agent reasoning and JSON generation |
| LLM Client | `requests` + `python-dotenv` | HTTP calls to DeepSeek API |
| API Server | FastAPI + Uvicorn | REST API for frontend integration |
| Live Stream | SSE (Server-Sent Events) | Real-time thinking stream per pipeline run |
| Async Queue | `asyncio.Queue` | Bridges agent thought emitters to SSE endpoint |
| Mobile App | React Native (Expo) | Mandatory deliverable |
| Web Dashboard | Next.js | Optional UI |
| PDF Parsing | PyPDF2 | Extract text from PDF sources |
| Web Scraping | BeautifulSoup4 | Extract text from URL sources |
| Data Persistence | JSON file | `output/pipeline_result.json` |
| Environment Config | `.env` + `python-dotenv` | Secrets management |

---

## 8. Agent Responsibility Matrix

| Agent | Reads From | Writes To | DeepSeek Call | Can Skip? |
|---|---|---|---|---|
| Agent 1 — Ingestion | `sources[]` (raw input) | `content_blocks[]` | ✅ Always | ❌ No |
| Agent 2 — Insight | `content_blocks[]` | `insights[]`, `contradictions[]` | ✅ Always | ❌ No |
| Agent 3 — Impact | `insights[]` | `impact_reports[]` | ✅ Always | ❌ No |
| Agent 4 — Planner | `impact_reports[]` + `constraints` | `action_plan[]` | ✅ Always | ❌ No |
| Agent 5 — Executor | `action_plan[]` | `execution_log[]` | ✅ Always | ❌ No |
| Agent 6 — Recovery | `execution_log[]` + `action_plan[]` | `recovery_actions[]` | ✅ Only if failures | ✅ Yes (if no failures) |
| Agent 7 — Reporter | All previous outputs | `final_report` | ✅ Always | ❌ No |

---

## 9. Error Handling Architecture

```
Level 1: LLM Client (llm_client.py)
  - HTTPError   → raised to caller agent
  - JSONDecodeError → raised to caller agent
  - ValueError (no API key) → raised immediately

Level 2: Agent Level
  - LLM errors → logged + re-raised to orchestrator
  - Empty/null response → fallback to default empty schema

Level 3: Orchestrator Level
  - Agent failure → log + continue pipeline where possible
  - Critical agent failure → stop pipeline, save partial result

Level 4: Recovery Agent
  - Execution failures → retry / fallback / rollback
  - Recovery failure → escalate to human operator

Level 5: API Layer
  - Pipeline error → HTTP 500 with error detail
  - Invalid input → HTTP 422 with validation error
  - Timeout → HTTP 504 with partial result link
```

---

## 10. Cost & Scalability Analysis

### Per-Run Cost Estimate

| Component | Tokens (Input) | Tokens (Output) | Cost (USD) |
|---|---|---|---|
| Agent 1 — Ingestion | ~2,000 | ~1,500 | ~$0.002 |
| Agent 2 — Insight | ~3,000 | ~2,000 | ~$0.003 |
| Agent 3 — Impact | ~2,500 | ~1,500 | ~$0.002 |
| Agent 4 — Planner | ~4,000 | ~3,000 | ~$0.004 |
| Agent 5 — Executor | ~5,000 | ~4,000 | ~$0.006 |
| Agent 6 — Recovery | ~6,000 | ~3,000 | ~$0.006 |
| Agent 7 — Reporter | ~8,000 | ~5,000 | ~$0.009 |
| **TOTAL** | ~30,500 | ~20,000 | **~$0.032** |

### Latency Estimate

| Agent | Typical Latency |
|---|---|
| Agent 1 | 3–5 seconds |
| Agent 2 | 4–7 seconds |
| Agent 3 | 3–5 seconds |
| Agent 4 | 4–6 seconds |
| Agent 5 | 5–8 seconds |
| Agent 6 | 5–8 seconds |
| Agent 7 | 6–10 seconds |
| **Total** | **30–50 seconds** |

### Scaling

| Scale | Approach | Notes |
|---|---|---|
| 1 run | Sequential (current) | ~$0.03, ~40s |
| 10x runs | Async + `asyncio.gather` | Parallel agents where no dependency |
| 100x runs | FastAPI + Celery + Redis queue | Distribute across workers |
| 1000x runs | Kubernetes + horizontal scaling | Multiple API instances |

---

## 11. Baseline Comparison

| Metric | Simple Rule-Based System | This Agentic System |
|---|---|---|
| Source types handled | 1 (fixed format) | 5+ (adaptive) |
| Contradiction handling | ❌ None — takes first value | ✅ Credibility + recency scoring |
| Action chain | ❌ Single hardcoded alert | ✅ 3–5 contextual, constrained actions |
| Failure recovery | ❌ Pipeline crashes | ✅ Retry → fallback → rollback |
| Insight quality | ❌ Keyword match / threshold alert | ✅ LLM reasoning over full context |
| Constraint awareness | ❌ None | ✅ Budget, time, resource validation |
| Trace / audit log | ❌ None | ✅ Full Antigravity trace |
| Cost per run | ~$0.001 (rule engine) | ~$0.032 (LLM powered) |
| Reasoning quality | ❌ Binary rules | ✅ Multi-step contextual reasoning |

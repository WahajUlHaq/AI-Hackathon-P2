# ChainSight — Architecture Diagram

```mermaid
graph TB
    %% ─── CLIENT LAYER ───────────────────────────────────────────────────
    subgraph CLIENTS["🖥️  CLIENT LAYER"]
        MA["📱 Mobile App\nReact Native Expo\nSSE consumer + REST"]
        PM["📬 Postman / REST\nDirect HTTP calls"]
        GA["🤖 Google Antigravity\nAgent Runtime\n(reads mcp_config.json)"]
    end

    %% ─── FASTAPI BACKEND ─────────────────────────────────────────────────
    subgraph API["⚡ FastAPI Backend — localhost:8000"]
        EP1["POST /api/analyze\n(main entry point)"]
        EP2["GET /api/stream/{session_id}\nSSE — live events"]
        EP3["GET/POST /api/state\nPOST /api/state/reset"]
        MCP_EP["POST /mcp/\nMCP Streamable HTTP\nJSON-RPC 2.0"]
    end

    %% ─── SSE BUS ────────────────────────────────────────────────────────
    subgraph SSE_BUS["📡 SSE Event Bus"]
        SSE["orchestrator_start\ntool_call  ·  tool_result\norchestrator_done\npipeline_done  ·  pipeline_error"]
    end

    %% ─── ORCHESTRATION LAYER ─────────────────────────────────────────────
    subgraph ORCH["🧠 Orchestration Layer"]
        GEM["🔮 Gemini 2.5-Flash-Lite\nPrimary Orchestrator\nNative function-calling loop\n↓ quota exhausted?"]
        DS_ORCH["⚡ DeepSeek Chat\nFallback Orchestrator\nOpenAI tool-calling loop\n↓ also fails?"]
        PY_FB["🐍 Python Direct Fallback\nHardcoded pipeline\nno LLM orchestration"]
        GEM -->|"429 RPD / quota"| DS_ORCH
        DS_ORCH -->|"error"| PY_FB
    end

    %% ─── MCP SERVER ─────────────────────────────────────────────────────
    subgraph MCP_SRV["🔧 MCP Server — 14 Tools"]
        direction LR
        subgraph PARSE_TOOLS["Parse Tools"]
            T_PS["parse_sources\n(multi-source)"]
            T_PT["parse_csv_source\nparse_pdf_source\nparse_news_source\nparse_dashboard_source\nparse_realtime_source"]
        end
        subgraph CHAIN_TOOLS["Pipeline Tools"]
            T_EI["extract_insights"]
            T_PA["plan_actions"]
            T_EA["execute_action"]
        end
        subgraph STATE_TOOLS["State / Query Tools"]
            T_SS["get_system_state\nreset_state\nget_inventory\nget_routes\nsend_notification"]
        end
    end

    %% ─── CONTENT FETCHER ────────────────────────────────────────────────
    CF["🌐 Content Fetcher\nresolve_content(text)\nURL → HTML strip (12 k chars)\nURL → PDF extract (pypdf)\nplain text → pass-through"]

    %% ─── AGENT PIPELINE ─────────────────────────────────────────────────
    subgraph AGENTS["🤖 Agent Pipeline  (DeepSeek-powered)"]
        direction LR
        AG1["🔵 Parser Agent\nAgent 1 — parse_sources\n5 source types\ncredibility scoring\nconflict detection\ndeepseek-chat T=0.1"]
        AG2["🟡 Insight Agent\nAgent 2 — extract_insights\nCause → Effect → $-impact\ncausal chains\ndeepseek-chat T=0.2"]
        AG3["🟠 Planner Agent\nAgent 3 — plan_actions\nRanked actions\nexact API parameters\ndeepseek-chat T=0.15"]
        AG4["🔴 Executor Agent\nAgent 4 — execute_action\nMock API calls\nbefore/after state snapshot\n(no LLM)"]
        AG1 -->|"parsed"| AG2
        AG2 -->|"insights"| AG3
        AG3 -->|"plan"| AG4
    end

    %% ─── CONTRACT ENFORCEMENT ───────────────────────────────────────────
    subgraph CONTRACT["📋 Contract Enforcement"]
        CE["check_parsed()  ·  check_insight()  ·  check_plan()\nPASS ✅  →  continue\nWARN ⚠️  →  log + continue\nREJECT ❌  →  inject correction_hint + retry (max 3×)"]
    end

    %% ─── MOCK APIs ──────────────────────────────────────────────────────
    subgraph MOCKS["🏭 Mock APIs"]
        INV["📦 Inventory API\n3 DCs (Karachi/Lahore/Islamabad)\nSKU lookup · safety stock\nexposure calculation"]
        RTE["🚚 Routing API\n5 active routes\nreroute optimizer\ncost + ETA delta"]
        PRC["💰 Pricing API\nbase + surge pricing\n±25% surge adjustment\nper-SKU override"]
        NTF["🔔 Notifications API\nEmail / WhatsApp\naudit log\nbatch send"]
    end

    %% ─── STATE MANAGEMENT ───────────────────────────────────────────────
    subgraph STATE["💾 State Management"]
        ST["in-memory supply-chain state\nsnapshot()  →  before_state\nrestore()   ←  rollback\nreset()     fresh start\nafter_state diff returned"]
    end

    %% ─── GOOGLE ANTIGRAVITY SKILLS ──────────────────────────────────────
    subgraph AG_SKILLS["🚀 Google Antigravity Skills"]
        direction LR
        SK1["content-parser\nSKILL.md"]
        SK2["insight-extractor\nSKILL.md"]
        SK3["action-planner\nSKILL.md"]
        SK4["action-executor\nSKILL.md"]
        WF["analyze-supply-chain\nWORKFLOW RULE"]
    end

    %% ─── EDGES ──────────────────────────────────────────────────────────

    %% Clients → API
    MA -->|"POST /api/analyze\nGET /api/stream"| EP1
    MA --> EP2
    PM --> EP1
    GA -->|"JSON-RPC tool calls"| MCP_EP

    %% Antigravity reads skills
    GA -.->|"reads"| AG_SKILLS
    AG_SKILLS -.->|"guides tool selection"| MCP_EP

    %% API → internal
    EP1 --> ORCH
    EP2 --> SSE_BUS
    MCP_EP --> MCP_SRV

    %% Orchestrator → tools
    ORCH -->|"calls MCP tools\nvia _handle_tool_call()"| MCP_SRV
    ORCH -->|"emits events"| SSE_BUS

    %% MCP tools → Content Fetcher
    T_PS -->|"resolve_content()"| CF
    T_PT -->|"resolve_content()"| CF

    %% MCP tools → Agents
    T_PS --> AG1
    T_PT --> AG1
    T_EI --> AG2
    T_PA --> AG3
    T_EA --> AG4

    %% Contract wraps agents
    AG1 <-->|"PASS/WARN/REJECT\nretry loop"| CONTRACT
    AG2 <-->|"PASS/WARN/REJECT\nretry loop"| CONTRACT
    AG3 <-->|"PASS/WARN/REJECT\nretry loop"| CONTRACT

    %% Agents → Mock APIs + State
    AG4 --> MOCKS
    AG4 --> STATE

    %% State → API response
    STATE -->|"before_state\nafter_state"| EP1

    %% SSE to mobile
    SSE_BUS -->|"text/event-stream"| MA

    %% Styling
    classDef client fill:#1a1a2e,stroke:#e94560,color:#fff
    classDef api fill:#16213e,stroke:#0f3460,color:#fff
    classDef orch fill:#0f3460,stroke:#533483,color:#fff
    classDef agent fill:#533483,stroke:#e94560,color:#fff
    classDef mock fill:#1a472a,stroke:#2d6a4f,color:#fff
    classDef state fill:#1b4332,stroke:#40916c,color:#fff
    classDef contract fill:#7b2d00,stroke:#d4551a,color:#fff
    classDef skill fill:#3d1a78,stroke:#9b59b6,color:#fff

    class MA,PM,GA client
    class EP1,EP2,EP3,MCP_EP api
    class GEM,DS_ORCH,PY_FB orch
    class AG1,AG2,AG3,AG4 agent
    class INV,RTE,PRC,NTF mock
    class ST state
    class CE contract
    class SK1,SK2,SK3,SK4,WF skill
```

---

## Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                     TWO ENTRY PATHS                                 │
│                                                                     │
│  PATH A — Direct API (Postman / Mobile App)                        │
│  POST /api/analyze  →  Orchestrator  →  MCP Tool calls  →  Agents  │
│                                                                     │
│  PATH B — Google Antigravity (MCP)                                 │
│  Antigravity reads Skills  →  POST /mcp/  →  Agents               │
└─────────────────────────────────────────────────────────────────────┘

ORCHESTRATION PRIORITY:
  1. Gemini 2.5-Flash-Lite  (native function calling)
     └─ quota exhausted (429 RPD) ──►
  2. DeepSeek Chat  (OpenAI-compat tool calling)
     └─ error ──►
  3. Python hardcoded fallback  (no LLM)

SERIAL EXECUTION CHAIN (enforced by orchestrator):
  parse_sources  ──►  extract_insights  ──►  plan_actions  ──►  execute_action

PARALLEL CONTENT TYPES (within parse_sources):
  csv_json  |  pdf_report  |  news_article  |  dashboard  |  realtime_feed

CONFLICT RESOLUTION (within Parser Agent):
  credibility: realtime(0.92) > dashboard(0.85) > news(0.80) > pdf(0.75) > csv(0.70)
  age penalty: −0.20 if source > 24h old
  resolution logged in parsed.contradictions[]

CONTRACT ENFORCEMENT per agent:
  PASS  → continue
  WARN  → log warning, continue
  REJECT → inject correction_hint, retry (max 3 iterations)

STATE MANAGEMENT:
  before_state snapshot taken before execute_action
  after_state diff returned in AnalyzeResponse.execution
  rollback available via POST /api/state/reset
```

---

## File Structure

```
Hackathon--AI-Seekho/
├── backend/
│   ├── main.py                  FastAPI app, endpoints
│   ├── orchestrator.py          Gemini → DeepSeek → Python fallback
│   ├── gemini_client.py         Gemini API wrapper, model fallback chain
│   ├── deepseek_client.py       DeepSeek API wrapper, agentic loop
│   ├── mcp_server.py            MCP Streamable HTTP, 14 tools
│   ├── content_fetcher.py       URL/PDF auto-fetch
│   ├── contract.py              PASS/WARN/REJECT enforcement
│   ├── state.py                 In-memory supply-chain state
│   ├── models.py                All Pydantic schemas
│   ├── agents/
│   │   ├── parser_agent.py      Agent 1 — multi-source parser (DeepSeek)
│   │   ├── insight_agent.py     Agent 2 — causal chains (DeepSeek)
│   │   ├── planner_agent.py     Agent 3 — action planner (DeepSeek)
│   │   └── executor_agent.py    Agent 4 — mock API executor
│   └── mock_apis/
│       ├── inventory.py         3 distribution centers, SKU lookup
│       ├── routing.py           5 routes, reroute optimizer
│       ├── pricing.py           Base + surge pricing
│       └── notifications.py     Email/WhatsApp + audit log
├── .agents/
│   ├── rules/
│   │   └── analyze-supply-chain.md   Antigravity workflow
│   └── skills/
│       ├── content-parser/SKILL.md
│       ├── insight-extractor/SKILL.md
│       ├── action-planner/SKILL.md
│       └── action-executor/SKILL.md
├── mcp_config.json              Points Antigravity → localhost:8000/mcp/
├── ChainSighst.postman_collection.json
└── ARCHITECTURE.md              ← this file
```

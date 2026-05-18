# 🏗️ NEW SYSTEM ARCHITECTURE
## Autonomous Content-to-Action Agent — News Analysis Domain

---

## 🎯 Chosen Domain: News Analysis

**Scenario:** Multiple sources report that **TechCorp** is planning a major round of layoffs.
Sources conflict on the scale, timing, and executive statements.
The system must determine what is actually true, extract real insights, and generate actions.

**Why News Analysis?**
- 5 source types map perfectly (PDF memo, news URL, stock CSV, analyst JSON, social feed)
- Natural contradiction: leaked memo says 15% cuts, news article says 25%
- Clear temporal signals: stock declining over 5 days
- Realistic actionable outputs: alerts, reports, notifications

---

## 🗺️ Full System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                         │
│              Mobile App (React Native)  ·  Web Dashboard                    │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │ HTTP REST + SSE Stream
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API LAYER (FastAPI + Uvicorn)                        │
│   POST /run  ·  GET /status  ·  GET /result  ·  GET /stream/{job_id}        │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              GOOGLE ANTIGRAVITY — ORCHESTRATOR                               │
│                        orchestrator.py                                       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STAGE 1 — PARALLEL PARSER AGENTS  (run simultaneously)             │   │
│  │                                                                      │   │
│  │  [1a: PDF Parser] [1b: URL Scraper] [1c: CSV Parser]                │   │
│  │  [1d: JSON Parser]                 [1e: Feed Parser]                │   │
│  │                                                                      │   │
│  │  All output → ContentBlock[] → merged into unified pool             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                             │                                                │
│                             ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STAGE 2 — FLAG AGENT (Truth/False Detection)                        │   │
│  │  • Python: compute trust_score per block                             │   │
│  │  • Python: detect conflicts between blocks                           │   │
│  │  • Python: resolve conflicts deterministically                       │   │
│  │  • DeepSeek: explain, score correctness, flag false info             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                             │                                                │
│                             ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STAGE 3 — INSIGHT AGENT                                             │   │
│  │  • Extract deep, non-trivial signals from VERIFIED info only         │   │
│  │  • Temporal analysis, trend detection, anomaly spotting              │   │
│  │  • Confidence-scored, urgency-ranked insight packets                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                             │                                                │
│                             ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STAGE 4 — PLAN AGENT                                                │   │
│  │  • 3-5 constrained, interconnected actions                           │   │
│  │  • Each action validated against budget/time/resource                │   │
│  │  • Fallback defined per action                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                             │                                                │
│                             ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STAGE 5 — EXECUTION AGENT                                           │   │
│  │  • Simulate actions step-by-step                                     │   │
│  │  • Before vs after state per action                                  │   │
│  │  • In-depth comparison report per step                               │   │
│  │  • Injects 1 deliberate failure (ORDER/PUBLISH type)                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                             │                                                │
│                             ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STAGE 6 — RECOVERY AGENT                                            │   │
│  │  • Detect failed actions, retry/fallback/rollback                    │   │
│  │  • Re-execute blocked downstream actions                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                             │                                                │
│                             ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STAGE 7 — REPORTER AGENT                                            │   │
│  │  • Before/after diff for every system                                │   │
│  │  • Full Antigravity trace (workplan, reasoning, tool calls)          │   │
│  │  • Cost + latency breakdown                                          │   │
│  │  • Projected impact metrics                                          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ══════════════════ THINKING STREAM (runs in parallel) ═══════════════════  │
│   asyncio.Queue ← agents emit thoughts → SSE → client in real time          │
└─────────────────────────────────────────────────────────────────────────────┘
                             │ all agents call
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LLM LAYER — DeepSeek API (deepseek-chat)                  │
│                         llm_client.py · json_object mode                    │
└─────────────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    output/pipeline_result.json                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗂️ File Structure

```
│
├── orchestrator.py                ← Antigravity entry point (chains all stages)
├── requirements.txt
├── .env                           ← DEEPSEEK_API_KEY
│
├── agents/
│   ├── __init__.py
│   ├── llm_client.py              ← Shared DeepSeek gateway
│   │
│   ├── stage1/                    ← Parallel parser sub-agents
│   │   ├── __init__.py
│   │   ├── agent1a_pdf.py         ← PDF parser (no LLM)
│   │   ├── agent1b_url.py         ← URL scraper (no LLM)
│   │   ├── agent1c_csv.py         ← CSV parser (no LLM)
│   │   ├── agent1d_json.py        ← JSON parser (no LLM)
│   │   ├── agent1e_feed.py        ← Mock feed parser (no LLM)
│   │   └── runner.py              ← Runs 1a–1e in parallel via ThreadPoolExecutor
│   │
│   ├── agent2_flag.py             ← Truth/False detection + conflict resolution
│   ├── agent3_insight.py          ← Deep insight extraction
│   ├── agent4_plan.py             ← Action planning with constraints
│   ├── agent5_executor.py         ← Step-by-step execution simulation
│   ├── agent6_recovery.py         ← Failure recovery
│   └── agent7_reporter.py         ← Final report + Antigravity trace
│
├── api/
│   ├── __init__.py
│   ├── main.py                    ← FastAPI routes
│   ├── models.py                  ← Pydantic schemas
│   └── stream.py                  ← SSE thinking stream
│
├── output/
│   └── pipeline_result.json
│
└── docs/
    ├── NEW_ARCHITECTURE.md        ← THIS FILE
    ├── stage1_parsers.md          ← Agents 1a–1e
    ├── agent2_flag.md             ← Flag Agent
    ├── agent3_insight.md          ← Insight Agent
    ├── agent4_plan.md             ← Plan Agent
    ├── agent5_execution.md        ← Execution Agent
    ├── agent6_recovery.md
    ├── agent7_reporter.md
    ├── orchestrator.md
    ├── stream_thinking.md
    └── api_reference.md
```

---

## 🤖 Agent Model Recommendations

| Agent | Role | LLM Needed? | Recommended Model | Why |
|---|---|---|---|---|
| **1a — PDF Parser** | Extract text from PDF | ❌ No LLM | PyPDF2 / pdfplumber | Rule-based extraction, no reasoning needed |
| **1b — URL Scraper** | Scrape and clean web article | ❌ No LLM | BeautifulSoup4 + requests | Deterministic HTML parsing |
| **1c — CSV Parser** | Parse rows, detect columns | ❌ No LLM | Python csv / pandas | Pure data parsing |
| **1d — JSON Parser** | Parse and flatten JSON | ❌ No LLM | json.loads | Deterministic |
| **1e — Feed Parser** | Extract feed text | ❌ No LLM | String regex / json | Deterministic |
| **2 — Flag Agent** | Truth/false detection, conflict resolution | ✅ DeepSeek Chat | `deepseek-chat` temp=0.1 | Strict logical reasoning, JSON output |
| **3 — Insight Agent** | Deep insight generation | ✅ DeepSeek Chat | `deepseek-chat` temp=0.3 | Needs some creative reasoning for non-trivial signals |
| **4 — Plan Agent** | Constraint-aware planning | ✅ DeepSeek Chat | `deepseek-chat` temp=0.1 | Deterministic planning, no creativity needed |
| **5 — Execution Agent** | Simulate actions + comparison | ✅ DeepSeek Chat | `deepseek-chat` temp=0.1 | Structured simulation output |
| **6 — Recovery Agent** | Retry/fallback decisions | ✅ DeepSeek Chat | `deepseek-chat` temp=0.1 | Strict decision tree |
| **7 — Reporter Agent** | Final report + trace | ✅ DeepSeek Chat | `deepseek-chat` temp=0.1 | Deterministic compilation |
| **Thinking Stream** | Human-language narration | ✅ DeepSeek Chat | `deepseek-chat` temp=0.7 | Needs natural, expressive language |

---

## 📊 Data Contract Between Stages

```
Stage 1 Output  →  content_blocks[]
  Each block: {id, source_type, source_label, raw_text,
               timestamp, credibility_score, domain,
               is_stale, is_noise, metadata}

Stage 2 Output  →  verified_pool{}
  trusted_blocks[], downranked_blocks[], false_flagged_blocks[]
  conflicts[], correctness_scores{}, pipeline_state{}

Stage 3 Output  →  insight_packet{}
  insights[], temporal_signals[], overall_confidence

Stage 4 Output  →  action_plan[]
  Each action: {id, step, type, title, description,
                constraints, constraint_status,
                priority_score, depends_on, fallback}

Stage 5 Output  →  execution_log[]
  Each entry: {action_id, status, before_state,
               after_state, comparison, duration_ms}

Stage 6 Output  →  recovery_log{}
  recovery_actions[], post_recovery_log[], recovery_summary

Stage 7 Output  →  final_report{}
  before_after[], timeline[], cost_analysis,
  projected_impact, antigravity_trace
```

---

## 🎬 Demo Scenario — TechCorp Layoffs

**5 Input Sources:**

| # | Source | Type | Age | Key Claim |
|---|---|---|---|---|
| S1 | TechCorp Leaked Internal Memo | PDF | 3 days old | "15% workforce reduction planned" |
| S2 | Reuters News Article | URL | Today | "TechCorp to cut 25% of staff, sources say" |
| S3 | Stock Price History (5 days) | CSV | Today | TECH stock down 18% over 5 days |
| S4 | Analyst Ratings API | JSON | Today | 3 analysts downgraded, target cut from $180→$120 |
| S5 | LinkedIn/Twitter Sentiment | MockFeed | Today | 400% spike in employee posts about job search |

**Key Conflict:**
- S1 says 15% cuts — S2 says 25% cuts
- Stage 2 resolves: S2 is more recent and higher credibility → prefer S2
- S1 flagged as: conflicting/unverified, correctness_score=0.35

**Action Chain (Stage 4):**
1. `ALERT` — Notify investment team of confirmed layoff signal
2. `PUBLISH` — Draft investor brief with verified facts only
3. `UPDATE` — Flag TechCorp in portfolio monitoring dashboard
4. `ANALYZE` — Trigger deeper due diligence on TechCorp position
5. `MONITOR` — Schedule hourly news monitoring for 24 hours

**Injected Failure:** Step 2 PUBLISH fails (external publishing API timeout)
**Recovery:** Retry ×2 → Fallback to email draft instead

---

## 🌊 Thinking Stream (Human Language)

The stream runs **parallel** to the pipeline via `asyncio.Queue`.
Every agent emits thoughts in real-time. Client receives them via SSE.

Example thoughts from this scenario:

```
🔍 [Stage 1 — Parsers]  "Starting all 5 parsers at the same time..."
💭 [Agent 1a — PDF]     "Reading TechCorp memo... says 15% cuts planned."
💭 [Agent 1b — URL]     "Scraping Reuters article... this says 25% cuts."
💭 [Agent 1c — CSV]     "Stock data shows 18% drop in 5 days. That's significant."
💭 [Agent 1d — JSON]    "3 analyst downgrades. Price target slashed from $180 to $120."
💭 [Agent 1e — Feed]    "Social sentiment: 400% spike in 'job searching' posts from employees."
✅ [Stage 1 Complete]   "5 sources parsed. Ready for fact-checking."

⚡ [Stage 2 — Flag]     "Wait — the memo says 15% and Reuters says 25%. They can't both be right."
💭 [Stage 2 — Flag]     "Memo is 3 days old, credibility 0.45. Reuters is today, credibility 0.82."
✅ [Stage 2 — Flag]     "Reuters wins. Trust score gap is 0.54 — well above threshold."
🚨 [Stage 2 — Flag]     "Flagging memo claim as LIKELY FALSE. Correctness score: 0.35."

💭 [Stage 3 — Insight]  "Verified facts: 25% layoffs confirmed, stock -18%, analysts bearish."
💭 [Stage 3 — Insight]  "This isn't just a layoff story — it's a confidence crisis signal."
✅ [Stage 3 — Insight]  "3 insights extracted. Overall confidence: 0.84."

💭 [Stage 4 — Plan]     "We need to act on 3 fronts: alert team, publish brief, monitor closely."
⚠️ [Stage 5 — Execute]  "Publishing API timed out. Can't push the investor brief."
🔄 [Stage 6 — Recovery] "Retried twice. Switching to email fallback — brief sent."
🎯 [Stage 7 — Report]   "All done. Investment team notified. Dashboard updated."
```

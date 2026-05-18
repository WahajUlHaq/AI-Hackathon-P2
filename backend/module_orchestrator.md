# 🎛️ Orchestrator — Pipeline Runner

## Overview

| Property | Value |
|---|---|
| **File** | `orchestrator.py` |
| **Role** | Chain all 7 stages end-to-end, manage state, emit to thinking stream |
| **Entry Point** | `python orchestrator.py` |
| **Also Used By** | `api/main.py` — calls `run_pipeline()` for HTTP requests |
| **Output** | `output/pipeline_result.json` |

---

## Pipeline Sequence

```
run_pipeline(sources, constraints)
│
├── Stage 1: stage1_runner.run(sources)
│     [parallel] 1a+1b+1c+1d+1e → content_blocks[]
│
├── Stage 2: agent2_flag.run(content_blocks)
│     Python: trust_score, conflict detection, correctness scoring
│     DeepSeek: explanations, false flag narratives
│     → verified_pool{}, pipeline_state{}
│
├── Stage 3: agent3_insight.run(verified_pool)
│     DeepSeek (temp=0.3): deep insights, temporal signals
│     → insight_packet{}
│
├── Stage 4: agent4_plan.run(insight_packet, constraints)
│     DeepSeek (temp=0.1): constrained 5-action plan
│     → action_plan[]
│
├── Stage 5: agent5_executor.run(action_plan)
│     DeepSeek (temp=0.1): step-by-step simulation + comparison
│     → execution_log[]
│
├── Stage 6: agent6_recovery.run(execution_log, action_plan)
│     Python: detect failures, choose strategy
│     DeepSeek (temp=0.1): retry + fallback simulation
│     → recovery_actions[], post_recovery_log[]
│
├── Merge: full_log = execution_log + post_recovery_log
│
├── Stage 7: agent7_reporter.run(all_outputs)
│     DeepSeek (temp=0.1): compile report + Antigravity trace
│     → final_report{}
│
└── Save: output/pipeline_result.json
```

---

## State Flow — What Each Stage Receives and Produces

| Stage | Receives | Produces | State Variable |
|---|---|---|---|
| Stage 1 | `sources[]` (raw) | `content_blocks[]` | `content_blocks` |
| Stage 2 | `content_blocks[]` | `verified_pool{}`, `pipeline_state{}`, `python_conflicts[]` | `verified_pool`, `pipeline_state` |
| Stage 3 | `verified_pool{}` (trusted_blocks only) | `insight_packet{}` | `insight_packet` |
| Stage 4 | `insight_packet{}` + `constraints{}` | `action_plan[]` | `action_plan` |
| Stage 5 | `action_plan[]` | `execution_log[]` | `execution_log` |
| Stage 6 | `execution_log[]` + `action_plan[]` | `recovery_actions[]`, `post_recovery_log[]` | `recovery_result` |
| Stage 7 | All of the above | `final_report{}` | `final_report` |

---

## Demo Input — TechCorp Layoffs Scenario

### 5 Sources

```python
DEMO_SOURCES = [
    {
        "label": "TechCorp Internal Memo",
        "type": "PDF",
        "content": "base64_or_filepath",
        "received_at": "2026-05-13T10:00:00Z"    # 3 days old
    },
    {
        "label": "Reuters — TechCorp Layoffs Report",
        "type": "URL",
        "content": "https://reuters.com/technology/techcorp-layoffs-2026",
        "received_at": "2026-05-16T08:30:00Z"
    },
    {
        "label": "TechCorp Stock Price — 5 Day History",
        "type": "CSV",
        "content": "Date,Close,Volume\n2026-05-12,162.00,8200000\n...",
        "received_at": "2026-05-16T09:00:00Z"
    },
    {
        "label": "Analyst Ratings API",
        "type": "JSON",
        "content": '{"analysts":[{"firm":"Goldman","rating":"SELL","target":120},...]}',
        "received_at": "2026-05-16T09:30:00Z"
    },
    {
        "label": "LinkedIn/Twitter Sentiment Feed",
        "type": "MockFeed",
        "content": "847 posts in 6h. Top: job search (312), layoffs confirmed (289), stock sell (156). Sentiment: -0.78",
        "received_at": "2026-05-16T10:00:00Z"
    }
]
```

### Constraints

```python
CONSTRAINTS = {
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

## Thinking Stream Integration

```python
import asyncio

async def run_pipeline_async(sources, constraints, thought_queue=None):
    """
    thought_queue: asyncio.Queue — if provided, agents emit thoughts to it.
    SSE endpoint reads from this queue and streams to client.
    """

    async def emit(agent, stage, type_, emoji, thought):
        if thought_queue:
            await thought_queue.put({
                "stage":   stage,
                "agent":   agent,
                "type":    type_,
                "emoji":   emoji,
                "thought": thought,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

    await emit("Orchestrator", 0, "start", "🔍",
               "Pipeline starting — reading 5 sources simultaneously.")

    # Stage 1
    content_blocks = await stage1_runner.run_async(sources, emit)

    # Stage 2
    flag_result = await agent2_flag.run_async(content_blocks, emit)

    # ... and so on for each stage
```

---

## Output File Structure

`output/pipeline_result.json`:

```json
{
  "pipeline_duration_ms": 32500,
  "domain": "news_analysis",
  "scenario": "techcorp_layoffs",
  "stage1": {
    "content_blocks": [...],
    "ingestion_summary": {...}
  },
  "stage2": {
    "verified_pool": {...},
    "correctness_scores": {...},
    "conflicts": [...],
    "false_flags": [...],
    "pipeline_state": {...}
  },
  "stage3": {
    "insights": [...],
    "temporal_signals": [...],
    "overall_confidence": 0.82
  },
  "stage4": {
    "action_plan": [...],
    "plan_summary": "..."
  },
  "stage5": {
    "execution_log": [...],
    "execution_summary": {...}
  },
  "stage6": {
    "recovery_actions": [...],
    "post_recovery_execution_log": [...],
    "recovery_summary": {...}
  },
  "final_report": {
    "before_after": [...],
    "action_timeline": [...],
    "projected_impact": {...},
    "antigravity_trace": {...}
  }
}
```

---

## Running the Pipeline

```bash
# Default demo run (TechCorp scenario)
python orchestrator.py

# Custom sources via Python
from orchestrator import run_pipeline
result = run_pipeline(sources=[...], constraints={...})
print(result["final_report"]["antigravity_trace"]["final_outcome"])

# Via API
uvicorn api.main:app --reload --port 8000
# POST http://localhost:8000/api/v1/run
# GET  http://localhost:8000/api/v1/stream/{job_id}
```

---

## Full Console Output (Demo)

```
============================================================
  AUTONOMOUS CONTENT-TO-ACTION AGENT — PIPELINE START
  Domain: News Analysis — TechCorp Layoffs
  2026-05-16T08:50:00Z
============================================================

[STAGE 1/7] Parallel Parser Agents
  [1a-PDF]  TechCorp Internal Memo        → 312 words, credibility=0.45
  [1b-URL]  Reuters — TechCorp Layoffs    → 847 words, credibility=0.85
  [1c-CSV]  Stock Price 5-Day History     → trend=-17.9%, credibility=0.85
  [1d-JSON] Analyst Ratings API           → 3 downgrades, credibility=0.88
  [1e-Feed] LinkedIn/Twitter Sentiment    → sentiment=-0.78, credibility=0.65
  Done — 5 blocks, 0 noise, 0 stale (1520ms parallel)

[STAGE 2/7] Flag Agent
  trust scores: cb_001=0.315, cb_002=0.850, cb_003=0.850, cb_004=0.880, cb_005=0.650
  CONFLICT: layoff_15pct vs layoff_25pct → prefer cb_002 (margin=0.535)
  cb_001 → correctness=0.158 → LIKELY_FALSE
  Done — 4 trusted, 0 uncertain, 1 false-flagged

[STAGE 3/7] Insight Agent
  Using 4 verified blocks (cb_001 excluded: LIKELY_FALSE)
  Done — 3 insights, 4 temporal signals, confidence=0.82

[STAGE 4/7] Plan Agent
  Done — 5 actions planned, all FEASIBLE, $0 cost

[STAGE 5/7] Execution Agent
  act_001 ALERT   → SUCCESS (250ms)
  act_002 PUBLISH → FAILED — API_TIMEOUT (5020ms)
  act_003 UPDATE  → SUCCESS (340ms)
  act_004 ANALYZE → SKIPPED (blocked by act_002)
  act_005 MONITOR → SUCCESS (90ms)
  Done — 3 succeeded, 1 failed, 1 skipped

[STAGE 6/7] Recovery Agent
  Retry 1: still timing out ❌
  Retry 2: still timing out ❌
  Fallback: email brief → SUCCESS (12 recipients) ✅
  Unblocked act_004 → job_9934 triggered ✅
  Done — 1 recovered, 0 escalated

[STAGE 7/7] Reporter Agent
  Done — report compiled, Antigravity trace ready

============================================================
  PIPELINE COMPLETE — 32500ms total
============================================================

[Orchestrator] Saved → output/pipeline_result.json

── ANTIGRAVITY TRACE ──
Workplan     : parallel parse → flag truth/false → insights → plan → execute
Final Outcome: All 5 actions completed (1 via fallback). 20 stakeholders notified.
               1 false claim blocked. Portfolio flagged. Monitoring active.
```

---

## Cost & Latency Summary

| Stage | LLM Call | Tokens (est.) | Duration |
|---|---|---|---|
| Stage 1 | ❌ None | 0 | 1520ms (parallel) |
| Stage 2 | ✅ 1 call | ~3,000 in / ~2,000 out | 4s |
| Stage 3 | ✅ 1 call | ~4,000 in / ~3,000 out | 5s |
| Stage 4 | ✅ 1 call | ~5,000 in / ~3,000 out | 5s |
| Stage 5 | ✅ 1 call | ~6,000 in / ~5,000 out | 7s |
| Stage 6 | ✅ 1 call | ~7,000 in / ~4,000 out | 6s |
| Stage 7 | ✅ 1 call | ~10,000 in / ~6,000 out | 9s |
| **Total** | **6 LLM calls** | **~55,000 tokens** | **~38s** |

Estimated cost per run: **~$0.040 USD**

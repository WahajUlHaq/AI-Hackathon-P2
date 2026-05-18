# ChainSight — DeepSeek Agent Pipeline (Insight → Planner → Executor) Implementation Plan

We are implementing **Agents 2, 3, and 4** of the ChainSight pipeline, all powered by **DeepSeek Chat** (OpenAI-compatible API). We are also implementing the DeepSeek agentic loop that serves as the fallback orchestrator when Gemini quota is exhausted. This gives ChainSight a fully resilient dual-LLM architecture.

## User Review Required

> [!IMPORTANT]
> The Insight Agent must **never** produce generic summaries. Every causal chain must follow the exact structure: `cause → immediate_effect → downstream_effect → financial_impact_usd → probability_pct`. The `financial_impact_usd` must be a specific dollar figure derived from the parsed metrics (e.g., `847 pallets × $45/pallet holding cost + $0.50/pallet/day SLA penalty × 5 days`). The contract will REJECT any chain with `financial_impact_usd = 0` when parsed metrics are present.

> [!IMPORTANT]
> The Planner Agent must validate constraints before marking an action `feasible`. If `region = "unknown"` is passed to `update_pricing`, the action must be marked `infeasible` with a `feasibility_note`. If `dc` is not one of `karachi_dc | lahore_dc | islamabad_dc`, the action must be marked `infeasible`. The contract validates that `primary_action_id` always points to a `feasible` action.

> [!NOTE]
> The Executor Agent does **not** call an LLM. It is a pure Python dispatcher that reads the `action_type` and `parameters` from the plan and calls the corresponding mock API. It captures state before and after each call using `state.get_snapshot()`. Retry logic uses `constraints.max_retries` from the plan.

## Proposed Changes

### [Backend — DeepSeek Client]

#### [NEW] [deepseek_client.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/deepseek_client.py)

**`generate(system_prompt, user_content, json_mode, temperature)`** — Async HTTP call to `https://api.deepseek.com/chat/completions` using `deepseek-chat` model. Handles 429 by parsing `retry_after` from error response and sleeping. Retries up to 3× before raising `RuntimeError`.

**`mcp_tools_to_openai(tools)`** — Converts MCP TOOLS list to OpenAI function format for DeepSeek tool-calling:
```python
{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["inputSchema"]}}
```

**`run_agentic_loop(system_prompt, user_message, tools, tool_executor, sse_emit, max_turns)`** — OpenAI-compatible tool-calling loop for DeepSeek fallback orchestration. Mirrors the Gemini loop but uses `tool_calls` array in the response instead of `function_call` parts.

### [Backend — Agent 2: Insight]

#### [NEW] [agents/insight_agent.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/agents/insight_agent.py)

**`_SYSTEM_PROMPT`** — Instructs DeepSeek at temperature 0.2 to:
- Build causal chains from parsed entities: `cause → immediate_effect → downstream_effect`
- Calculate `financial_impact_usd` from parsed key_metrics (holding cost + SLA penalties)
- Assign `probability_pct` based on severity and credibility scores
- Set `urgency`: `immediate` (<24h), `24h`, `48h`, `week`
- Resolve contradictions into a single coherent narrative

**Output schema:**
```json
{
  "title": "...", "urgency": "immediate|24h|48h|week",
  "total_exposure_usd": 0.0, "affected_skus": [],
  "key_risks": [], "contradiction_resolutions": [],
  "causal_chains": [{
    "cause": "...", "immediate_effect": "...", "downstream_effect": "...",
    "financial_impact_usd": 0.0, "probability_pct": 0
  }]
}
```

### [Backend — Agent 3: Planner]

#### [NEW] [agents/planner_agent.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/agents/planner_agent.py)

**`_SYSTEM_PROMPT`** — Instructs DeepSeek at temperature 0.15 to:
- Generate 3–5 ranked actions ordered by `estimated_savings_usd` descending
- Mark `feasibility_status`: `feasible | modified | infeasible`
- Include exact API parameters ready for the executor
- Validate constraints: `budget_usd`, `deadline_hours`, `max_retries`, `rollback_on_failure`
- Set `primary_action_id` to the highest-confidence feasible action

**Action types available:** `reroute_shipment`, `activate_safety_stock`, `update_inventory`, `update_pricing`, `send_notification`

### [Backend — Agent 4: Executor]

#### [NEW] [agents/executor_agent.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/agents/executor_agent.py)

Pure Python dispatcher (no LLM):
1. Reads `action_type` and `parameters` from plan
2. Captures `state_before = state.get_snapshot()`
3. Calls the corresponding mock API endpoint
4. Captures `state_after = state.get_snapshot()`
5. Computes `penalty_delta_usd = state_after.penalty_exposure_usd - state_before.penalty_exposure_usd`
6. On failure: if `constraints.rollback_on_failure`, calls rollback API; sets `status = "rolled_back"`
7. On retry: re-attempts up to `constraints.max_retries` times; sets `status = "retried_ok"` or `"failed"`

## Verification Plan

### Insight Agent — Financial Calculation
Input: `entities=[port_strike, karachi, 847 pallets, 5 days delay]`, `key_metrics={affected_shipments:847, delay_days:5}`
Expected `financial_impact_usd` ≈ `847 × $45 (holding) + 847 × $0.50 × 5 (SLA penalty)` = **$40,118**

### Planner Agent — Infeasibility Check
Input insight with `affected_region="unknown"`. 
Expected: `update_pricing` action marked `infeasible`, `feasibility_note` present, not selected as `primary_action_id`.

### Executor Agent — Before/After Delta
Run `activate_safety_stock` on `lahore_dc`. State before: `penalty_exposure_usd=320000`. State after: `penalty_exposure_usd=297500`. Expected `penalty_delta_usd=-22500`. ✅

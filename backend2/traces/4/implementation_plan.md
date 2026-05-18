# ChainSight — Gemini Antigravity Orchestration Loop Implementation Plan

We are implementing the **Gemini 2.5-Flash-Lite Antigravity orchestration loop** — the core intelligence engine of ChainSight. Instead of calling agents in a hardcoded Python sequence, Gemini itself decides which MCP tools to call, in what order, and what to do with each result. This is the Google Antigravity pattern applied to supply chain intelligence.

## User Review Required

> [!IMPORTANT]
> Gemini operates as a **multi-turn conversation loop**. Each tool result is fed back to Gemini as a `FunctionResponse` part in the `contents` list. Gemini then reads it and decides the next action. This means the orchestration is non-deterministic — Gemini _may_ deviate from the expected 4-step order if the system prompt is not strict enough. The `_SYSTEM_INSTRUCTION` must explicitly forbid clarifying questions, repeating succeeded tools, and stopping early.

> [!IMPORTANT]
> Gemini's free tier quota (RPD limit) will be hit during heavy testing. We must implement a transparent DeepSeek fallback that activates on `429` and continues the pipeline without the user noticing any interruption. Both orchestrators must use the same `_handle_tool_call` dispatcher so the pipeline output is identical.

> [!NOTE]
> To keep Gemini's context window manageable across 4 tool calls, we use `_compact_tool_result()` to feed Gemini a 200-character summary of each result instead of the full JSON. The full JSON is stored in `_sessions[session_id]` and used to build the final `AnalyzeResponse`.

## Proposed Changes

### [Backend — Orchestrator]

#### [NEW] [orchestrator.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/orchestrator.py)

**`_to_gemini_tools()`** — Converts the MCP `TOOLS` list (JSON Schema) into Gemini `FunctionDeclaration` objects. Handles nested `array` types, `enum` values, and optional descriptions. Called once at module load, result cached in `_GEMINI_TOOLS`.

**`_SYSTEM_INSTRUCTION`** — The Gemini system prompt enforcing:
```
PIPELINE — follow exactly:
1. parse_sources(session_id)
2. extract_insights(session_id)
3. plan_actions(session_id)
4. execute_action(session_id, action_id)  ← use primary_action_id from step 3
5. Stop and return your final summary.
```
Includes hard rules: never ask clarifying questions, never repeat a succeeded tool, always pass same `session_id`.

**`run_orchestrated(req, session_id, sse_emit)`** — The main async entry point:
1. Pre-loads sources into `_sessions[session_id]["pending_sources"]`
2. Builds initial `contents` list with user message containing session_id and source count
3. Enters the Gemini agentic loop (`while tool_call_count < 30`)
4. On each iteration: calls `generate_with_retry()`, extracts `function_calls` from response parts
5. For each function call: emits `tool_call` SSE, calls `_handle_tool_call()`, emits `tool_result` SSE
6. Feeds all results back as `FunctionResponse` parts in a single turn
7. Stops when Gemini returns no function calls (text-only response = done)
8. On `429`: switches to `ds_agentic_loop` (DeepSeek fallback)
9. After loop: runs Python hardcoded fallback for any stages Gemini skipped

**`_compact_tool_result(tool_name, result, is_error)`** — Returns a 200-char summary tailored per tool:
- `parse_sources`: returns `entities_found`, `contradictions_detected`, `next_step`
- `extract_insights`: returns `total_exposure_usd`, `urgency`, `causal_chains count`
- `plan_actions`: returns `primary_action_id`, `total_budget_usd`, `actions count`
- `execute_action`: returns `status`, `penalty_delta_usd`, `latency_ms`

#### [MODIFY] [gemini_client.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/gemini_client.py)
- Implement `generate_with_retry()` with model fallback chain: `gemini-2.5-flash-lite` → `gemini-2.0-flash-lite` → `gemini-1.5-flash-8b`
- Raise on exhaustion so orchestrator can catch and switch to DeepSeek

## Verification Plan

### Gemini Orchestration — Port of Karachi Scenario
```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Port of Karachi strike day 3. 847 pallets stranded. Lahore DC has 2.3 days of supply."
  }'
```
Expected SSE sequence:
1. `orchestrator_start` — Gemini started
2. `tool_call: parse_sources` (call #1)
3. `tool_result: parse_sources` ✓
4. `tool_call: extract_insights` (call #2)
5. `tool_result: extract_insights` ✓
6. `tool_call: plan_actions` (call #3)
7. `tool_result: plan_actions` ✓
8. `tool_call: execute_action` (call #4, with `action_id=ACT-001`)
9. `tool_result: execute_action` ✓
10. `orchestrator_done` — summary text from Gemini

### DeepSeek Fallback
- Remove GEMINI_API_KEY from env temporarily
- Confirm pipeline completes via DeepSeek with identical output schema

### Safety Cap
- Set `MAX_TOOL_CALLS = 5` temporarily and verify Python fallback completes any skipped stages

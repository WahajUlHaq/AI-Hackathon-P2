"""
Gemini Orchestrator — Antigravity-style orchestration for the mobile API path.

When mobile calls POST /api/analyze, this module runs the same pipeline
as Google Antigravity: Gemini uses function calling to decide which MCP
tools to call, in what order, and reads each result before proceeding.

The MCP tools (parse_csv_source, parse_news_source, merge_and_analyze,
extract_insights, plan_actions, execute_action, …) are registered as
Gemini function declarations. Gemini acts as the orchestrator — it calls
each tool explicitly rather than Python running agents in a fixed sequence.

SSE events are emitted after each tool call so the mobile app sees a
real-time trace of every orchestration step.
"""
import asyncio
import json
import os
import uuid

from google import genai
from google.genai import types

import state
from gemini_client import generate_with_retry
from mcp_server import TOOLS, _handle_tool_call, _sessions
from models import AnalyzeRequest, AnalyzeResponse, AgentStep, ExecutionResult, StateSnapshot
from deepseek_client import mcp_tools_to_openai, run_agentic_loop as ds_agentic_loop

# ── Map MCP tool JSON-Schema to Gemini FunctionDeclaration ───────────────────

def _to_gemini_tools() -> list[types.Tool]:
    """Convert MCP TOOLS list to Gemini function declarations."""
    declarations = []
    for t in TOOLS:
        schema = t.get("inputSchema", {})
        props = schema.get("properties", {})
        required = schema.get("required", [])

        # Build Gemini-compatible property dict
        gemini_props = {}
        for prop_name, prop_schema in props.items():
            p: dict = {"type": prop_schema.get("type", "string")}
            if "description" in prop_schema:
                p["description"] = prop_schema["description"]
            if "enum" in prop_schema:
                p["enum"] = prop_schema["enum"]
            if prop_schema.get("type") == "array":
                items = prop_schema.get("items", {})
                p["items"] = items
            gemini_props[prop_name] = p

        declarations.append(types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters={
                "type": "object",
                "properties": gemini_props,
                "required": required,
            },
        ))

    return [types.Tool(function_declarations=declarations)]


_GEMINI_TOOLS = _to_gemini_tools()
_DS_TOOLS = mcp_tools_to_openai(TOOLS)  # DeepSeek/OpenAI format fallback

_SYSTEM_INSTRUCTION = """
You are ChainSight Orchestrator — an autonomous supply chain intelligence agent.

Your job: orchestrate the full analysis pipeline by calling tools in strict order.

PIPELINE — follow exactly:
1. parse_sources(session_id)               ← call with ONLY session_id (sources already pre-loaded)
2. extract_insights(session_id)            ← causal chains + dollar exposure
3. plan_actions(session_id)               ← ranked action plan
4. execute_action(session_id, action_id)  ← call once with primary_action_id from step 3
5. Stop and return your final summary.

IMPORTANT RULES:
- Do NOT pass a 'sources' list to parse_sources — just session_id. Sources are pre-loaded.
- Do NOT call merge_and_analyze — use parse_sources instead.
- Do NOT call get_system_state unless explicitly asked.
- Pass the SAME session_id (given in the user message) to every tool call.
- After parse_sources succeeds, IMMEDIATELY call extract_insights — do not stop.
- After extract_insights succeeds, IMMEDIATELY call plan_actions — do not stop.
- After plan_actions succeeds, IMMEDIATELY call execute_action with primary_action_id — do not stop.
- After execute_action, STOP calling tools and return your summary.
- Never repeat a tool call that already succeeded.
- Never ask clarifying questions — just execute the pipeline.
"""


async def run_orchestrated(
    req: AnalyzeRequest,
    session_id: str,
    sse_emit,          # async callable: (event_type: str, data: dict) -> None
) -> AnalyzeResponse:
    """
    Run the full pipeline via Gemini function calling (Antigravity-style).
    Gemini decides which tool to call next; we execute it and feed results back.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    client = genai.Client(api_key=api_key)

    # Pre-load sources into session so Gemini doesn't need the bulk content.
    # parse_sources will pull "pending_sources" / "pending_content" from the session
    # instead of requiring them in the function args — keeps Gemini context small.
    if req.sources:
        source_count = len(req.sources)
        _sessions[session_id] = {
            "pending_sources": [
                {
                    "source_id": s.source_id,
                    "source_type": s.source_type.value,
                    "content": s.content,
                    "timestamp_utc": s.timestamp_utc,
                }
                for s in req.sources
            ]
        }
        user_message = (
            f"Analyze the supply chain event for session '{session_id}'. "
            f"There are {source_count} sources already loaded in the session. "
            f"Call parse_sources(session_id='{session_id}') — no need to pass sources list, "
            f"they are pre-loaded. Then call extract_insights, plan_actions, and execute_action."
        )
    else:
        content = req.content or ""
        _sessions[session_id] = {"pending_content": content}
        user_message = (
            f"Analyze the supply chain event for session '{session_id}'. "
            f"Content is pre-loaded in the session. "
            f"Call parse_sources(session_id='{session_id}') then extract_insights, "
            f"plan_actions, and execute_action."
        )

    # Conversation history for multi-turn function calling
    contents: list = [
        types.Content(role="user", parts=[types.Part(text=user_message)])
    ]

    trace: list[AgentStep] = []
    tool_call_count = 0
    MAX_TOOL_CALLS = 30  # safety cap

    await sse_emit("orchestrator_start", {
        "message": "Gemini orchestrator started",
        "session_id": session_id,
        "sources_count": len(req.sources) if req.sources else 1,
    })

    # ── Agentic loop ──────────────────────────────────────────────────────────
    gemini_quota_exhausted = False
    while tool_call_count < MAX_TOOL_CALLS:
        try:
            response = await generate_with_retry(
                client, contents,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_INSTRUCTION,
                    tools=_GEMINI_TOOLS,
                    temperature=0.1,
                ),
                preferred_model="gemini-2.5-flash-lite",
            )
        except Exception as gemini_exc:
            # All Gemini models exhausted — hand off to DeepSeek orchestrator
            await sse_emit("orchestrator_start", {
                "message": "Gemini quota exhausted — switching to DeepSeek orchestrator",
                "tool_calls_total": tool_call_count,
            })

            async def _tool_exec(name: str, args: dict):
                # Inject session_id if missing
                if "session_id" not in args and name not in (
                    "get_system_state", "get_inventory_state",
                    "reroute_shipment", "update_pricing", "send_notification", "reset_state",
                ):
                    args["session_id"] = session_id
                r = await _handle_tool_call(name, args, state)
                text = r["content"][0]["text"] if r.get("content") else "{}"
                return text, r.get("isError", False)

            await ds_agentic_loop(
                system_prompt=_SYSTEM_INSTRUCTION,
                user_message=user_message,
                tools=_DS_TOOLS,
                tool_executor=_tool_exec,
                sse_emit=sse_emit,
                max_turns=20,
            )

            await sse_emit("orchestrator_done", {
                "message": "DeepSeek orchestrator completed",
                "tool_calls_total": tool_call_count,
                "summary": "",
            })
            gemini_quota_exhausted = True
            break

        # Guard: no candidates (safety filter, quota, etc.)
        if not response.candidates:
            await sse_emit("orchestrator_done", {
                "message": "Gemini returned no candidates — orchestration complete",
                "tool_calls_total": tool_call_count,
                "summary": "",
            })
            break

        candidate = response.candidates[0]
        model_content = candidate.content

        # Guard: Gemini sometimes returns content=None (safety block / empty turn)
        if model_content is None or not model_content.parts:
            await sse_emit("orchestrator_done", {
                "message": "Gemini returned empty content — orchestration complete",
                "tool_calls_total": tool_call_count,
                "summary": "",
            })
            break

        # Add model's response to conversation
        contents.append(model_content)

        # Collect all function calls in this response
        function_calls = [
            p.function_call
            for p in model_content.parts
            if hasattr(p, "function_call") and p.function_call is not None
        ]

        if not function_calls:
            # Gemini has finished — no more tool calls
            await sse_emit("orchestrator_done", {
                "message": "Gemini orchestrator completed",
                "tool_calls_total": tool_call_count,
                "summary": model_content.parts[0].text if model_content.parts else "",
            })
            break

        # Execute each function call
        tool_results_parts = []
        for fc in function_calls:
            tool_call_count += 1
            tool_name = fc.name
            tool_args = {k: v for k, v in fc.args.items()} if fc.args else {}

            # Inject session_id from req if not present and tool supports it
            if "session_id" not in tool_args and session_id:
                if tool_name not in ("get_system_state", "get_inventory_state",
                                     "reroute_shipment", "update_pricing",
                                     "send_notification", "reset_state"):
                    tool_args["session_id"] = session_id

            await sse_emit("tool_call", {
                "tool": tool_name,
                "args": tool_args,
                "call_number": tool_call_count,
            })

            # Execute via same handler used by MCP server
            result_dict = await _handle_tool_call(tool_name, tool_args, state)
            result_text = result_dict["content"][0]["text"] if result_dict.get("content") else "{}"
            is_error = result_dict.get("isError", False)

            # Parse result for structured SSE output
            try:
                result_json = json.loads(result_text)
            except Exception:
                result_json = {"raw": result_text}

            await sse_emit("tool_result", {
                "tool": tool_name,
                "call_number": tool_call_count,
                "success": not is_error,
                "result": result_json,
            })

            # Map tool name to agent label for trace
            agent_label = _tool_to_agent(tool_name)
            trace.append(AgentStep(
                agent=agent_label,
                status="error" if is_error else "done",
                output=result_json if not is_error else None,
                error=result_text if is_error else None,
            ))

            # Compact summary for Gemini context (avoid bloating conversation)
            gemini_feedback = _compact_tool_result(tool_name, result_json, is_error)

            tool_results_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=tool_name,
                        response={"result": gemini_feedback},
                    )
                )
            )

        # Feed all tool results back to Gemini in one turn
        contents.append(
            types.Content(role="user", parts=tool_results_parts)
        )

    # ── Extract final pipeline state from session ────────────────────────────
    sess = _sessions.get(session_id, {})
    parsed   = sess.get("parsed")
    insight  = sess.get("insight")
    plan     = sess.get("plan")
    execution = sess.get("execution")

    # Build execution result from chain steps if execute_action was called
    # individually (steps stored per-call in session)
    if not execution and plan and sess.get("chain_steps"):
        steps = sess["chain_steps"]
        first_before = steps[0].state_before if steps else StateSnapshot(
            inventory={}, routes={}, pricing={}, notifications_count=0, penalty_exposure_usd=0
        )
        last_after = steps[-1].state_after if steps else first_before
        execution = ExecutionResult(
            chain_steps=steps,
            before_state=first_before,
            after_state=last_after,
            total_actions_attempted=len(steps),
            total_actions_succeeded=sum(1 for s in steps if s.status in ("success", "retried_ok")),
            total_actions_failed=sum(1 for s in steps if s.status in ("failed", "rolled_back")),
            outcome_summary="Orchestrated by Gemini via function calling.",
            penalty_reduction_usd=max(
                0, first_before.penalty_exposure_usd - last_after.penalty_exposure_usd
            ),
            eta_improvement_days=0.0,
            total_latency_ms=sum(s.latency_ms for s in steps),
        )

    # ── Python fallback: run any stages Gemini skipped ───────────────────────
    # Covers: Gemini stopped early, context overflow, OR full quota exhaustion.
    if not parsed:
        # Parse was never called — sources are pre-loaded in session (pending_sources /
        # pending_content), so just pass session_id; the handler pulls from the session.
        await sse_emit("tool_call", {"tool": "parse_sources", "args": {"session_id": session_id}, "call_number": "fallback"})
        result = await _handle_tool_call("parse_sources", {"session_id": session_id}, state)
        sess = _sessions.get(session_id, {})
        parsed = sess.get("parsed")
        await sse_emit("tool_result", {"tool": "parse_sources", "call_number": "fallback", "success": not result.get("isError", False), "result": {"status": "completed via fallback"}})
        trace.append(AgentStep(agent="parser", status="done", output={"fallback": True}))

    if parsed and not insight:
        await sse_emit("tool_call", {"tool": "extract_insights", "args": {"session_id": session_id}, "call_number": "fallback"})
        result = await _handle_tool_call("extract_insights", {"session_id": session_id}, state)
        sess = _sessions.get(session_id, {})
        insight = sess.get("insight")
        await sse_emit("tool_result", {"tool": "extract_insights", "call_number": "fallback", "success": not result.get("isError", False), "result": {"status": "completed via fallback"}})
        trace.append(AgentStep(agent="insight", status="done", output={"fallback": True}))

    if insight and not plan:
        await sse_emit("tool_call", {"tool": "plan_actions", "args": {"session_id": session_id}, "call_number": "fallback"})
        result = await _handle_tool_call("plan_actions", {"session_id": session_id}, state)
        sess = _sessions.get(session_id, {})
        plan = sess.get("plan")
        await sse_emit("tool_result", {"tool": "plan_actions", "call_number": "fallback", "success": not result.get("isError", False), "result": {"status": "completed via fallback"}})
        trace.append(AgentStep(agent="planner", status="done", output={"fallback": True}))

    if plan and not execution:
        # Execute the primary action automatically
        primary_id = plan.primary_action_id
        await sse_emit("tool_call", {"tool": "execute_action", "args": {"session_id": session_id, "action_id": primary_id}, "call_number": "fallback"})
        result = await _handle_tool_call("execute_action", {"session_id": session_id, "action_id": primary_id}, state)
        sess = _sessions.get(session_id, {})
        await sse_emit("tool_result", {"tool": "execute_action", "call_number": "fallback", "success": not result.get("isError", False), "result": {"status": "completed via fallback"}})
        trace.append(AgentStep(agent="executor", status="done", output={"fallback": True}))

    # Reload session after fallback runs
    sess = _sessions.get(session_id, {})
    parsed   = sess.get("parsed") or parsed
    insight  = sess.get("insight") or insight
    plan     = sess.get("plan") or plan
    execution = sess.get("execution") or execution

    if not parsed or not insight or not plan:
        raise RuntimeError(
            "Pipeline failed even with fallback. "
            f"parsed={bool(parsed)}, insight={bool(insight)}, plan={bool(plan)}"
        )

    return AnalyzeResponse(
        session_id=session_id,
        parsed=parsed,
        insight=insight,
        plan=plan,
        execution=execution,
        agent_trace=trace,
    )


def _compact_tool_result(tool_name: str, result: dict, is_error: bool) -> dict:
    """Return a compact summary of a tool result to avoid bloating Gemini's context."""
    if is_error:
        return {"status": "error", "message": str(result.get("raw", result))[:200]}

    if tool_name in ("parse_csv_source", "parse_pdf_source", "parse_news_source",
                     "parse_dashboard_source", "parse_realtime_source", "parse_sources"):
        return {"status": "success", "stage": "source_parsed",
                "message": "Sources parsed successfully.",
                "next_step": "Call extract_insights(session_id) now. Do NOT call merge_and_analyze."}

    if tool_name == "merge_and_analyze":
        items = result.get("facts_count", result.get("key_metrics_count", "?"))
        contradictions = result.get("contradictions_detected", 0)
        return {"status": "success", "stage": "parsed", "items_merged": items,
                "contradictions": contradictions,
                "next_step": "Call extract_insights(session_id) now."}

    if tool_name == "extract_insights":
        chains = result.get("causal_chains_count", result.get("causal_chains", "?"))
        exposure = result.get("total_exposure_usd", result.get("penalty_exposure_usd", "?"))
        return {"status": "success", "stage": "insight_extracted",
                "causal_chains": chains, "exposure_usd": exposure,
                "next_step": "Call plan_actions(session_id) now."}

    if tool_name == "plan_actions":
        actions = result.get("actions_count", result.get("ranked_actions", []))
        count = len(actions) if isinstance(actions, list) else actions
        primary = result.get("primary_action_id", "?")
        return {"status": "success", "stage": "plan_ready",
                "actions_count": count, "primary_action_id": primary,
                "next_step": f"Call execute_action(session_id, action_id='{primary}') now."}

    if tool_name == "execute_action":
        return {"status": result.get("status", "success"), "stage": "action_executed",
                "action_id": result.get("action_id", "?"),
                "next_step": "Call next execute_action or stop if all done."}

    if tool_name in ("get_system_state", "get_inventory_state"):
        return {"status": "success", "snapshot_captured": True}

    return {"status": "success"}


def _tool_to_agent(tool_name: str) -> str:
    """Map MCP tool name to a human-readable agent label for the trace."""
    mapping = {
        "parse_csv_source":       "parser_csv",
        "parse_pdf_source":       "parser_pdf",
        "parse_news_source":      "parser_news",
        "parse_dashboard_source": "parser_dashboard",
        "parse_realtime_source":  "parser_realtime",
        "parse_sources":          "parser",
        "merge_and_analyze":      "merger",
        "extract_insights":       "insight",
        "plan_actions":           "planner",
        "execute_action":         "executor",
        "execute_action_chain":   "executor",
        "get_system_state":       "state_monitor",
        "get_inventory_state":    "state_monitor",
        "reroute_shipment":       "routing_api",
        "update_pricing":         "pricing_api",
        "send_notification":      "notification_api",
        "reset_state":            "system",
    }
    return mapping.get(tool_name, tool_name)

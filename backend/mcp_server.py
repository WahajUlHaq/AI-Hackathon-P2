"""
MCP Server — Streamable HTTP endpoint for Google Antigravity.

Tool design: ONE tool per pipeline stage so Antigravity calls them sequentially,
reads each result, reasons about it, and decides what to call next.
This makes Antigravity the genuine orchestrator — its log shows every step.

Pipeline tools (call in order):
  1. parse_sources          → extracts entities, contradictions, credibility scores
  2. extract_insights       → causal chains + dollar exposure
  3. plan_actions           → ranked 3-5 actions with constraints
  4. execute_action_chain   → runs the full action chain with retry/rollback

Utility tools (call any time):
  get_system_state, get_inventory_state, reroute_shipment,
  update_pricing, send_notification, reset_state

Protocol: MCP Streamable HTTP (POST /mcp/)
"""
import json
import uuid
import state
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/mcp", tags=["mcp"])

# ── In-memory session store: session_id → pipeline intermediate results ───────
# Antigravity passes session_id across calls so each stage can pick up where
# the previous stage left off without Antigravity having to carry the full payload.
_sessions: dict[str, dict] = {}

# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    # ── Stage 1 ───────────────────────────────────────────────────────────────
    {
        "name": "parse_sources",
        "description": (
            "STAGE 1 — Parse one or more supply-chain content sources. "
            "Accepts up to 5 sources of different types (csv_json, pdf_report, "
            "news_article, dashboard, realtime_feed). "
            "Scores credibility, detects contradictions between sources, identifies "
            "temporal signals (rising/falling trends), and filters noise. "
            "Returns a session_id you MUST pass to the next stage."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "array",
                    "description": "List of content sources to parse simultaneously",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_id":    {"type": "string"},
                            "source_type":  {
                                "type": "string",
                                "enum": ["csv_json", "pdf_report", "news_article",
                                         "dashboard", "realtime_feed", "text"],
                            },
                            "content":      {"type": "string"},
                            "timestamp_utc": {"type": "string"},
                        },
                        "required": ["source_id", "source_type", "content"],
                    },
                },
                "content": {
                    "type": "string",
                    "description": "Fallback: single text blob if sources list is not provided",
                },
                "session_id": {
                    "type": "string",
                    "description": "Optional: reuse an existing session. Omit to create a new one.",
                },
            },
        },
    },
    # ── Stage 2 ───────────────────────────────────────────────────────────────
    {
        "name": "extract_insights",
        "description": (
            "STAGE 2 — Extract quantitative causal insights from the parsed data. "
            "Must be called AFTER parse_sources. Pass the session_id returned by "
            "parse_sources. Produces dollar-figure causal chains, urgency rating, "
            "affected SKUs, key risks, and contradiction resolution explanations."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "session_id returned by parse_sources",
                },
            },
            "required": ["session_id"],
        },
    },
    # ── Stage 3 ───────────────────────────────────────────────────────────────
    {
        "name": "plan_actions",
        "description": (
            "STAGE 3 — Generate a ranked 3-5 action plan with budget/deadline constraints. "
            "Must be called AFTER extract_insights. Pass the session_id. "
            "Each action has: type, parameters ready for execution, constraints "
            "(budget_usd, deadline_hours, max_retries, rollback_on_failure), "
            "feasibility_status (feasible/infeasible/modified), and depends_on links. "
            "Infeasible actions are flagged and will be skipped by the executor."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "session_id returned by parse_sources",
                },
            },
            "required": ["session_id"],
        },
    },
    # ── Stage 4 ───────────────────────────────────────────────────────────────
    {
        "name": "execute_action_chain",
        "description": (
            "STAGE 4 — Execute the full action chain produced by plan_actions. "
            "Must be called AFTER plan_actions. Pass the session_id. "
            "Runs every feasible action in order: calls mock APIs, retries on failure, "
            "rolls back state if rollback_on_failure=True, sends failure alerts as fallback, "
            "skips actions whose dependencies failed. "
            "Returns per-action before/after state snapshots, retry counts, and outcome summary."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "session_id returned by parse_sources",
                },
            },
            "required": ["session_id"],
        },
    },
    # ── Utility tools ─────────────────────────────────────────────────────────
    {
        "name": "get_system_state",
        "description": (
            "Get a full snapshot of current supply chain state "
            "(inventory, routes, pricing, notifications, penalty exposure). "
            "Call BEFORE stage 1 and AFTER stage 4 to produce a before/after comparison."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_inventory_state",
        "description": "Retrieve current inventory levels for all distribution centers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dc": {
                    "type": "string",
                    "description": "Specific DC (optional): lahore_dc | islamabad_dc | karachi_port",
                }
            },
        },
    },
    {
        "name": "reroute_shipment",
        "description": "Directly reroute shipments between two routes (bypasses planner).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_route_id": {"type": "string"},
                "to_route_id":   {"type": "string"},
                "shipment_count": {"type": "integer"},
            },
            "required": ["from_route_id", "to_route_id", "shipment_count"],
        },
    },
    {
        "name": "update_pricing",
        "description": "Apply a delivery pricing multiplier to a region (surge pricing).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "region":     {"type": "string", "description": "lahore | islamabad | karachi"},
                "multiplier": {"type": "number",  "description": "e.g. 1.25 = +25%"},
            },
            "required": ["region", "multiplier"],
        },
    },
    {
        "name": "send_notification",
        "description": "Dispatch a notification to recipients via email/SMS/push.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notification_type": {"type": "string", "enum": ["email", "sms", "push", "internal"]},
                "recipients": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "normal", "high", "critical"], "default": "normal"},
            },
            "required": ["notification_type", "recipients", "subject", "body"],
        },
    },
    {
        "name": "reset_state",
        "description": "Reset supply chain state to initial values (use before each demo run).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    # ── Per-content-type parse tools (Antigravity calls these individually) ───
    {
        "name": "parse_csv_source",
        "description": (
            "PARSER AGENT — CSV/JSON type. "
            "Feed one structured data source (warehouse spreadsheet, inventory CSV, ERP export). "
            "Antigravity calls this for each CSV/JSON source separately. "
            "Stores result in session. Call merge_and_analyze after all sources are fed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id":    {"type": "string", "description": "Reuse or omit to create new"},
                "source_id":     {"type": "string"},
                "content":       {"type": "string"},
                "timestamp_utc": {"type": "string"},
            },
            "required": ["source_id", "content"],
        },
    },
    {
        "name": "parse_pdf_source",
        "description": (
            "PARSER AGENT — PDF/Report type. "
            "Feed one PDF or text report (supplier audit, logistics report, policy document). "
            "Antigravity calls this for each PDF source separately."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id":    {"type": "string"},
                "source_id":     {"type": "string"},
                "content":       {"type": "string"},
                "timestamp_utc": {"type": "string"},
            },
            "required": ["source_id", "content"],
        },
    },
    {
        "name": "parse_news_source",
        "description": (
            "PARSER AGENT — News/Article type. "
            "Feed one news article or web page. "
            "Antigravity calls this for each news source separately."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id":    {"type": "string"},
                "source_id":     {"type": "string"},
                "content":       {"type": "string"},
                "timestamp_utc": {"type": "string"},
            },
            "required": ["source_id", "content"],
        },
    },
    {
        "name": "parse_dashboard_source",
        "description": (
            "PARSER AGENT — Dashboard/Table type. "
            "Feed one real-time dashboard export or table (sales metrics, KPI board). "
            "Antigravity calls this for each dashboard source separately."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id":    {"type": "string"},
                "source_id":     {"type": "string"},
                "content":       {"type": "string"},
                "timestamp_utc": {"type": "string"},
            },
            "required": ["source_id", "content"],
        },
    },
    {
        "name": "parse_realtime_source",
        "description": (
            "PARSER AGENT — Real-time feed type. "
            "Feed one live feed (IoT sensor, API stream, live alert). "
            "Antigravity calls this for each real-time source separately."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id":    {"type": "string"},
                "source_id":     {"type": "string"},
                "content":       {"type": "string"},
                "timestamp_utc": {"type": "string"},
            },
            "required": ["source_id", "content"],
        },
    },
    {
        "name": "merge_and_analyze",
        "description": (
            "MERGE AGENT — Combine all individually parsed sources into one unified analysis. "
            "Call this AFTER calling all parse_X_source tools. "
            "Runs contradiction detection across all sources, scores credibility, "
            "identifies temporal signals, filters noise. "
            "Returns session_id to pass to extract_insights."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "session_id from any parse_X_source call"},
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "execute_action",
        "description": (
            "EXECUTOR AGENT — Execute ONE specific action from the plan by action_id. "
            "Call this separately for each action so Antigravity controls the execution sequence. "
            "Handles retry, rollback, and failure alerts internally. "
            "Returns before/after state snapshot for that single action. "
            "Call get_system_state after each execution to see live state changes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "action_id":  {
                    "type": "string",
                    "description": "e.g. ACT-001 — must be an action_id from plan_actions output",
                },
            },
            "required": ["session_id", "action_id"],
        },
    },
]


def _tool_result(content: list, is_error: bool = False) -> dict:
    return {"content": content, "isError": is_error}


def _text(text: str) -> dict:
    return {"type": "text", "text": text}


async def _handle_tool_call(name: str, args: dict, app_state) -> dict:
    import httpx
    from agents import parser_agent, insight_agent, planner_agent, executor_agent
    from models import ContentSource, SourceType, AnalyzeRequest

    BASE = "http://localhost:8000"

    # ── STAGE 1: parse_sources ────────────────────────────────────────────────
    if name == "parse_sources":
        session_id = args.get("session_id") or str(uuid.uuid4())
        raw_sources = args.get("sources")

        # If orchestrator pre-loaded sources into the session, use those
        # (avoids passing bulk content through Gemini's context)
        existing_sess = _sessions.get(session_id, {})
        if not raw_sources and existing_sess.get("pending_sources"):
            raw_sources = existing_sess["pending_sources"]

        if raw_sources:
            from content_fetcher import resolve_content
            sources = []
            for s in raw_sources:
                resolved = await resolve_content(s["content"])
                sources.append(ContentSource(
                    source_id=s["source_id"],
                    source_type=SourceType(s["source_type"]),
                    content=resolved,
                    timestamp_utc=s.get("timestamp_utc"),
                ))
            parsed = await parser_agent.run(sources)
        else:
            # Fall back to inline content arg or pending_content from session
            content = args.get("content", "") or existing_sess.get("pending_content", "")
            from content_fetcher import resolve_content
            content = await resolve_content(content)
            parsed = await parser_agent.run(content)

        _sessions[session_id] = {"parsed": parsed}

        summary = {
            "session_id": session_id,
            "sources_parsed": parsed.sources_parsed,
            "noise_filtered": parsed.noise_filtered,
            "entities_found": len(parsed.entities),
            "contradictions_detected": len(parsed.contradictions),
            "temporal_signals": len(parsed.temporal_signals),
            "credibility_scores": parsed.credibility_scores,
            "contradictions": [c.model_dump() for c in parsed.contradictions],
            "temporal_signals_detail": [s.model_dump() for s in parsed.temporal_signals],
            "key_metrics": parsed.key_metrics,
            "time_horizon": parsed.time_horizon,
            "entities": [e.model_dump() for e in parsed.entities],
            "next_step": "Call extract_insights with this session_id",
        }
        return _tool_result([_text(json.dumps(summary, indent=2))])

    # ── STAGE 2: extract_insights ─────────────────────────────────────────────
    elif name == "extract_insights":
        session_id = args["session_id"]
        sess = _sessions.get(session_id)
        if not sess or "parsed" not in sess:
            return _tool_result(
                [_text(f"Session '{session_id}' not found or parse_sources not called yet.")],
                is_error=True,
            )

        insight = await insight_agent.run(sess["parsed"])
        sess["insight"] = insight

        summary = {
            "session_id": session_id,
            "title": insight.title,
            "urgency": insight.urgency,
            "total_exposure_usd": insight.total_exposure_usd,
            "affected_skus": insight.affected_skus,
            "key_risks": insight.key_risks,
            "contradiction_resolutions": insight.contradiction_resolutions,
            "causal_chains": [c.model_dump() for c in insight.causal_chains],
            "next_step": "Call plan_actions with this session_id",
        }
        return _tool_result([_text(json.dumps(summary, indent=2))])

    # ── STAGE 3: plan_actions ─────────────────────────────────────────────────
    elif name == "plan_actions":
        session_id = args["session_id"]
        sess = _sessions.get(session_id)
        if not sess or "insight" not in sess:
            return _tool_result(
                [_text(f"Session '{session_id}': call extract_insights first.")],
                is_error=True,
            )

        plan = await planner_agent.run(sess["parsed"], sess["insight"])
        sess["plan"] = plan

        actions_summary = []
        for a in plan.ranked_actions:
            actions_summary.append({
                "action_id": a.action_id,
                "action_type": a.action_type.value,
                "title": a.title,
                "confidence_pct": a.confidence_pct,
                "estimated_savings_usd": a.estimated_savings_usd,
                "feasibility_status": a.feasibility_status,
                "feasibility_note": a.feasibility_note,
                "depends_on": a.depends_on,
                "constraints": a.constraints.model_dump() if a.constraints else None,
                "parameters": a.parameters,
            })

        summary = {
            "session_id": session_id,
            "primary_action_id": plan.primary_action_id,
            "total_budget_usd": plan.total_budget_usd,
            "rationale": plan.rationale,
            "constraint_violations": plan.constraint_violations,
            "ranked_actions": actions_summary,
            "next_step": "Call execute_action_chain with this session_id",
        }
        return _tool_result([_text(json.dumps(summary, indent=2))])

    # ── STAGE 4: execute_action_chain ─────────────────────────────────────────
    elif name == "execute_action_chain":
        session_id = args["session_id"]
        sess = _sessions.get(session_id)
        if not sess or "plan" not in sess:
            return _tool_result(
                [_text(f"Session '{session_id}': call plan_actions first.")],
                is_error=True,
            )

        execution = await executor_agent.run(sess["plan"])
        sess["execution"] = execution

        chain_summary = []
        for step in execution.chain_steps:
            chain_summary.append({
                "action_id": step.action_id,
                "action_type": step.action_type,
                "title": step.action_title,
                "status": step.status,
                "attempt": step.attempt,
                "latency_ms": step.latency_ms,
                "recovery_note": step.recovery_note,
                "api_calls": len(step.api_steps),
                "api_calls_succeeded": sum(1 for s in step.api_steps if s.success),
                "state_delta": {
                    "penalty_before": step.state_before.penalty_exposure_usd,
                    "penalty_after": step.state_after.penalty_exposure_usd,
                    "notifications_before": step.state_before.notifications_count,
                    "notifications_after": step.state_after.notifications_count,
                },
            })

        summary = {
            "session_id": session_id,
            "outcome_summary": execution.outcome_summary,
            "total_actions_attempted": execution.total_actions_attempted,
            "total_actions_succeeded": execution.total_actions_succeeded,
            "total_actions_failed": execution.total_actions_failed,
            "penalty_reduction_usd": execution.penalty_reduction_usd,
            "eta_improvement_days": execution.eta_improvement_days,
            "total_latency_ms": execution.total_latency_ms,
            "before_state": {
                "penalty_exposure_usd": execution.before_state.penalty_exposure_usd,
                "notifications_count": execution.before_state.notifications_count,
            },
            "after_state": {
                "penalty_exposure_usd": execution.after_state.penalty_exposure_usd,
                "notifications_count": execution.after_state.notifications_count,
            },
            "chain_steps": chain_summary,
        }
        return _tool_result([_text(json.dumps(summary, indent=2))])

    # ── Utility tools ─────────────────────────────────────────────────────────
    elif name == "get_system_state":
        snap = state.snapshot()
        snap["notifications"] = snap["notifications"][-10:]
        return _tool_result([_text(json.dumps(snap, indent=2))])

    elif name == "get_inventory_state":
        inv = state.get_inventory(args.get("dc"))
        return _tool_result([_text(json.dumps(inv, indent=2))])

    elif name == "reroute_shipment":
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{BASE}/mock/routing/reroute",
                json={
                    "from_route_id": args["from_route_id"],
                    "to_route_id":   args["to_route_id"],
                    "shipment_count": args["shipment_count"],
                },
            )
            r.raise_for_status()
            return _tool_result([_text(json.dumps(r.json(), indent=2))])

    elif name == "update_pricing":
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{BASE}/mock/pricing/update",
                json={"region": args["region"], "multiplier": args["multiplier"]},
            )
            r.raise_for_status()
            return _tool_result([_text(json.dumps(r.json(), indent=2))])

    elif name == "send_notification":
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{BASE}/mock/notifications/send",
                json={
                    "notification_type": args["notification_type"],
                    "recipients": args["recipients"],
                    "subject": args["subject"],
                    "body": args["body"],
                    "priority": args.get("priority", "normal"),
                },
            )
            r.raise_for_status()
            return _tool_result([_text(json.dumps(r.json(), indent=2))])

    elif name == "reset_state":
        state.reset()
        _sessions.clear()
        return _tool_result([_text('{"success": true, "message": "State and sessions reset."}')])

    # ── Per-content-type parse tools ──────────────────────────────────────────
    elif name in ("parse_csv_source", "parse_pdf_source", "parse_news_source",
                  "parse_dashboard_source", "parse_realtime_source"):

        TYPE_MAP = {
            "parse_csv_source":       "csv_json",
            "parse_pdf_source":       "pdf_report",
            "parse_news_source":      "news_article",
            "parse_dashboard_source": "dashboard",
            "parse_realtime_source":  "realtime_feed",
        }
        session_id = args.get("session_id") or str(uuid.uuid4())
        if session_id not in _sessions:
            _sessions[session_id] = {}
        if "raw_sources" not in _sessions[session_id]:
            _sessions[session_id]["raw_sources"] = []

        from models import ContentSource, SourceType
        from content_fetcher import resolve_content

        # Auto-fetch if content is a URL
        raw_content = args["content"]
        resolved_content = await resolve_content(raw_content)

        source = ContentSource(
            source_id=args["source_id"],
            source_type=SourceType(TYPE_MAP[name]),
            content=resolved_content,
            timestamp_utc=args.get("timestamp_utc"),
        )
        _sessions[session_id]["raw_sources"].append(source)

        # Quick single-source parse for immediate feedback to Antigravity
        partial = await parser_agent.run(resolved_content)

        return _tool_result([_text(json.dumps({
            "session_id": session_id,
            "source_id": args["source_id"],
            "source_type": TYPE_MAP[name],
            "entities_found": len(partial.entities),
            "key_metrics": partial.key_metrics,
            "time_horizon": partial.time_horizon,
            "sources_in_session_so_far": len(_sessions[session_id]["raw_sources"]),
            "next_step": (
                "Call more parse_X_source tools for remaining sources, "
                "then call merge_and_analyze with this session_id"
            ),
        }, indent=2))])

    # ── Merge all collected sources into unified ParsedContent ────────────────
    elif name == "merge_and_analyze":
        session_id = args["session_id"]
        sess = _sessions.get(session_id, {})
        raw_sources = sess.get("raw_sources", [])

        # If parse_sources was already called (monolithic path), parsed is already set
        if sess.get("parsed") and not raw_sources:
            parsed = sess["parsed"]
        elif not raw_sources:
            return _tool_result(
                [_text("No sources found in session. Call parse_X_source tools first.")],
                is_error=True,
            )
        else:
            # Run full multi-source analysis (contradiction detection, credibility, trends)
            parsed = await parser_agent.run(raw_sources)
            _sessions[session_id]["parsed"] = parsed
        return _tool_result([_text(json.dumps({
            "session_id": session_id,
            "sources_merged": max(len(raw_sources), 1),
            "source_ids": [s.source_id for s in raw_sources],
            "noise_filtered": parsed.noise_filtered,
            "credibility_scores": parsed.credibility_scores,
            "contradictions_detected": len(parsed.contradictions),
            "contradictions": [c.model_dump() for c in parsed.contradictions],
            "temporal_signals": [s.model_dump() for s in parsed.temporal_signals],
            "entities_total": len(parsed.entities),
            "key_metrics": parsed.key_metrics,
            "time_horizon": parsed.time_horizon,
            "next_step": "Call extract_insights with this session_id",
        }, indent=2))])

    # ── Execute ONE action by action_id ───────────────────────────────────────
    elif name == "execute_action":
        session_id = args["session_id"]
        action_id  = args["action_id"]
        sess = _sessions.get(session_id, {})
        plan = sess.get("plan")
        if not plan:
            return _tool_result(
                [_text(f"Session '{session_id}': call plan_actions first.")],
                is_error=True,
            )

        completed_ids: set[str] = sess.get("completed_action_ids", set())
        step = await executor_agent.run_single_action(plan, action_id, completed_ids)

        if step.status in ("success", "retried_ok"):
            completed_ids.add(action_id)
            sess["completed_action_ids"] = completed_ids

        # Accumulate chain_steps so orchestrator.py can build ExecutionResult
        sess.setdefault("chain_steps", []).append(step)

        return _tool_result([_text(json.dumps({
            "session_id": session_id,
            "action_id": step.action_id,
            "action_type": step.action_type,
            "title": step.action_title,
            "status": step.status,
            "attempt": step.attempt,
            "latency_ms": step.latency_ms,
            "recovery_note": step.recovery_note,
            "api_calls_total": len(step.api_steps),
            "api_calls_succeeded": sum(1 for s in step.api_steps if s.success),
            "state_before": {
                "penalty_exposure_usd": step.state_before.penalty_exposure_usd,
                "notifications_count": step.state_before.notifications_count,
            },
            "state_after": {
                "penalty_exposure_usd": step.state_after.penalty_exposure_usd,
                "notifications_count": step.state_after.notifications_count,
            },
            "penalty_delta_usd": (
                step.state_before.penalty_exposure_usd - step.state_after.penalty_exposure_usd
            ),
            "completed_actions_so_far": list(completed_ids),
            "next_step": (
                "Call execute_action with the next action_id from the plan, "
                "or call get_system_state to see final state."
            ),
        }, indent=2))])

    else:
        return _tool_result([_text(f"Unknown tool: {name}")], is_error=True)


@router.post("/")
async def mcp_endpoint(request: Request):
    """
    MCP Streamable HTTP endpoint.
    Handles: initialize, tools/list, tools/call
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None},
            status_code=400,
        )

    rpc_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": "chainsight-mcp",
                    "version": "1.0.0",
                    "description": "ChainSight Supply Chain Intelligence MCP Server",
                },
            },
        })

    elif method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {"tools": TOOLS},
        })

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        try:
            result = await _handle_tool_call(tool_name, tool_args, request.app.state)
            return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": result})
        except Exception as e:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": _tool_result([_text(f"Tool execution error: {e}")], is_error=True),
            })

    elif method == "notifications/initialized":
        # Acknowledgement — no response needed
        return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": {}})

    else:
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        })

"""
ChainSight — Agentic Supply Chain Intelligence System
FastAPI backend entry point.

Endpoints:
  GET  /health            — liveness check
  GET  /state             — current supply chain state
  POST /state/reset       — reset to initial state (demo)
  POST /api/analyze       — run full 4-agent pipeline
  GET  /api/stream/{sid}  — SSE stream for real-time agent trace
  POST /mcp/              — MCP endpoint for Google Antigravity
  GET  /mock/inventory/   — mock inventory API
  POST /mock/inventory/adjust
  POST /mock/inventory/safety-stock/activate
  GET  /mock/inventory/exposure
  GET  /mock/routing/routes
  POST /mock/routing/reroute
  GET  /mock/pricing/
  POST /mock/pricing/update
  GET  /mock/notifications/
  POST /mock/notifications/send
"""
import asyncio
import json
import os
import pathlib
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

# Repo root is one level above backend/
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

import state
from models import AnalyzeRequest, AnalyzeResponse, AgentStep
from mock_apis import inventory, pricing, routing, notifications
from mcp_server import router as mcp_router
import orchestrator

load_dotenv()

# ── In-memory SSE queue store (session_id → asyncio.Queue) ───────────────────
_sse_queues: dict[str, asyncio.Queue] = {}

# ── IP Rate limiter (6 requests per hour per IP) ─────────────────────────────
_RATE_LIMIT = 3
_RATE_WINDOW = 4600  # 1 hour in seconds
_ip_timestamps: dict[str, list[float]] = defaultdict(list)

def _get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For (Render proxy)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def _check_rate_limit(ip: str) -> dict:
    """
    Returns a dict with rate limit info.
    Raises HTTPException 429 if limit exceeded.
    """
    now = time.time()
    window_start = now - _RATE_WINDOW
    # Prune old timestamps
    _ip_timestamps[ip] = [t for t in _ip_timestamps[ip] if t > window_start]
    used = len(_ip_timestamps[ip])

    if used >= _RATE_LIMIT:
        oldest = _ip_timestamps[ip][0]
        retry_after = int(oldest + _RATE_WINDOW - now) + 1
        reset_at_ts = oldest + _RATE_WINDOW
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "message": f"You have used all {_RATE_LIMIT} requests for this hour. Please wait.",
                "requests_used": used,
                "limit": _RATE_LIMIT,
                "retry_after_seconds": retry_after,
                "reset_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(reset_at_ts)),
                "reset_at_unix": int(reset_at_ts),
            }
        )

    # Record this request
    _ip_timestamps[ip].append(now)
    used += 1
    oldest = _ip_timestamps[ip][0]
    reset_at_ts = oldest + _RATE_WINDOW

    return {
        "requests_used": used,
        "limit": _RATE_LIMIT,
        "remaining": _RATE_LIMIT - used,
        "reset_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(reset_at_ts)),
        "reset_at_unix": int(reset_at_ts),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.environ.get("GEMINI_API_KEY"):
        print("⚠️  WARNING: GEMINI_API_KEY not set. Agent calls will fail.")
    yield


app = FastAPI(
    title="ChainSight API",
    version="1.0.0",
    description="Agentic Supply Chain Intelligence — powered by Google Antigravity + Gemini",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "X-RateLimit-Used"],
)

# ── Mount sub-routers ─────────────────────────────────────────────────────────
app.include_router(inventory.router)
app.include_router(pricing.router)
app.include_router(routing.router)
app.include_router(notifications.router)
app.include_router(mcp_router)


# ── Health & State ────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "version": "1.0.0", "service": "chainsight-backend"}


# ── Frontend static pages ─────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def serve_app():
    """Serve the interactive SPA (app.html) at the root URL."""
    f = _REPO_ROOT / "app.html"
    if not f.exists():
        return {"error": "app.html not found"}
    return FileResponse(f, media_type="text/html")


@app.get("/docs-site", include_in_schema=False)
def serve_docs():
    """Serve the static documentation page (index.html)."""
    f = _REPO_ROOT / "index.html"
    if not f.exists():
        return {"error": "index.html not found"}
    return FileResponse(f, media_type="text/html")


# ── Health & State ────────────────────────────────────────────────────────────

@app.get("/state", tags=["system"])
@app.get("/api/state", tags=["system"])
def get_state():
    """Full supply chain state snapshot."""
    return state.snapshot()


@app.post("/state/reset", tags=["system"])
@app.post("/api/state/reset", tags=["system"])
def reset_state():
    """Reset supply chain state to initial demo values."""
    state.reset()
    return {"success": True, "message": "State reset to initial values."}


# ── SSE helper ────────────────────────────────────────────────────────────────

async def _emit(session_id: str, event_type: str, data: dict):
    q = _sse_queues.get(session_id)
    if q:
        await q.put({"event": event_type, "data": json.dumps(data)})


# ── Main pipeline ─────────────────────────────────────────────────────────────

# ── Main pipeline — orchestrated by Gemini (Antigravity-style) ───────────────

async def _run_pipeline(session_id: str, req: AnalyzeRequest) -> AnalyzeResponse:
    """
    Gemini acts as the orchestrator.
    It decides which MCP tools to call, in what order, based on each result.
    Every tool call is emitted as an SSE event so mobile sees the full trace.
    """
    async def _emit_event(event_type: str, data: dict):
        await _emit(session_id, event_type, data)

    try:
        result = await orchestrator.run_orchestrated(req, session_id, _emit_event)
    except Exception as e:
        await _emit(session_id, "pipeline_error", {"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {e}")

    await _emit(session_id, "pipeline_done", json.loads(result.model_dump_json()))
    q = _sse_queues.get(session_id)
    if q:
        await q.put(None)  # sentinel — closes SSE stream

    return result


@app.post("/api/analyze", response_model=AnalyzeResponse, tags=["pipeline"])
async def analyze(req: AnalyzeRequest, request: Request):
    """
    Run the full 4-agent pipeline synchronously.
    Rate limited to 6 requests per hour per IP.
    For real-time trace, use GET /api/stream/{session_id} BEFORE calling this.
    """
    ip = _get_client_ip(request)
    rl = _check_rate_limit(ip)  # raises 429 if exceeded

    session_id = req.session_id or str(uuid.uuid4())
    req.session_id = session_id
    # Only create a new queue if SSE hasn't already registered one for this session.
    if session_id not in _sse_queues:
        _sse_queues[session_id] = asyncio.Queue()
    result = await _run_pipeline(session_id, req)
    _sse_queues.pop(session_id, None)

    # Attach rate-limit headers so the frontend can update its counter
    from fastapi.responses import JSONResponse as _JSONResponse
    import json as _json
    response_data = _json.loads(result.model_dump_json())
    headers = {
        "X-RateLimit-Limit": str(rl["limit"]),
        "X-RateLimit-Remaining": str(rl["remaining"]),
        "X-RateLimit-Reset": str(rl["reset_at_unix"]),
        "X-RateLimit-Used": str(rl["requests_used"]),
    }
    return _JSONResponse(content=response_data, headers=headers)


@app.get("/api/rate-limit", tags=["system"])
def rate_limit_status(request: Request):
    """Return current rate-limit status for the calling IP (non-destructive, does not consume quota)."""
    ip = _get_client_ip(request)
    now = time.time()
    window_start = now - _RATE_WINDOW
    _ip_timestamps[ip] = [t for t in _ip_timestamps[ip] if t > window_start]
    used = len(_ip_timestamps[ip])
    remaining = max(0, _RATE_LIMIT - used)
    if _ip_timestamps[ip]:
        reset_at_ts = _ip_timestamps[ip][0] + _RATE_WINDOW
    else:
        reset_at_ts = now + _RATE_WINDOW
    return {
        "requests_used": used,
        "limit": _RATE_LIMIT,
        "remaining": remaining,
        "reset_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(reset_at_ts)),
        "reset_at_unix": int(reset_at_ts),
        "window_seconds": _RATE_WINDOW,
    }


@app.get("/api/stream/{session_id}", tags=["pipeline"])
async def stream(session_id: str):
    """
    SSE stream for real-time agent trace.
    Open this BEFORE calling POST /api/analyze with the same session_id.
    """
    _sse_queues[session_id] = asyncio.Queue()

    async def generator() -> AsyncGenerator[dict, None]:
        q = _sse_queues[session_id]
        while True:
            item = await q.get()
            if item is None:
                break
            yield item
        _sse_queues.pop(session_id, None)

    return EventSourceResponse(generator())


# ── Scenario endpoint (demo shortcut) ────────────────────────────────────────

DEMO_SCENARIO = """  # kept for single-content /api/analyze backward-compat
URGENT LOGISTICS ALERT — Port of Karachi Operations Update
Date: May 13, 2026 | Source: Pakistan Ports Authority

The Port of Karachi (Pakistan's largest seaport handling 60% of national cargo) has entered 
its third consecutive day of a full dock-worker strike. As of 06:00 PKT, all container 
handling operations have been suspended indefinitely.

Key Statistics:
- 847 pallets of FMCG goods (SKU-A001, SKU-B042, SKU-C118) are stranded at port holding areas.
- 40% shipment backlog has accumulated across inbound logistics for Lahore and Islamabad DCs.
- Current estimated delay: 4-7 additional days beyond normal 2.5-day transit time.
- SLA breach threshold for downstream retail partners: 5 days (penalty clause: PKR 150/pallet/day).
- Lahore DC current inventory will cover only 2.3 days of demand before stockout risk.
- Islamabad DC has 230 units in transit on KHI-ISB-001 route, also affected.
- Alternate port: Gwadar (4.9-day transit, 24% higher per-pallet cost at PKR 310).
- 23 downstream retail partners have contractual delivery windows closing in 48 hours.

Regional Economic Context:
- Karachi handles $1.3B in daily trade volume.
- Previous 2024 strike (2 days) resulted in PKR 2.4B in economic losses.
- Current monsoon forecast adds 15% probability of additional road disruption within 72 hours.
"""

# ── 5-source demo scenario (Challenge 1 — multi-source with contradiction) ───

_DEMO_SOURCES_RAW = [
    {
        "source_id": "warehouse_csv",
        "source_type": "csv_json",
        "timestamp_utc": "2026-05-12T08:00:00Z",   # 2 days old — STALE
        "content": (
            "Inventory Report — Lahore DC — Generated: 2026-05-12 08:00 PKT\n"
            "SKU-A001: 2500 pallets (status: NORMAL)\n"
            "SKU-B042: 1200 pallets (status: NORMAL)\n"
            "SKU-C118:  890 pallets (status: NORMAL)\n"
            "Note: No shortages detected. All inbound shipments on schedule. "
            "Last WMS sync: 08:00."
        ),
    },
    {
        "source_id": "ppa_news",
        "source_type": "news_article",
        "timestamp_utc": "2026-05-14T06:00:00Z",
        "content": (
            "PORT OF KARACHI STRIKE — DAY 3 (Pakistan Ports Authority, May 14 2026)\n"
            "All container-handling at Karachi Port suspended since May 12. 847 pallets of FMCG "
            "goods (SKU-A001, SKU-B042, SKU-C118) stranded in port holding areas. 40% inbound "
            "shipment backlog accumulated. ETA for Lahore DC shipments extended from 2.5 to 7+ "
            "days. SLA penalty clause activates at day 5 (PKR 150/pallet/day). "
            "23 retail partners have contractual delivery windows closing in 48 hours."
        ),
    },
    {
        "source_id": "sales_dashboard",
        "source_type": "dashboard",
        "timestamp_utc": "2026-05-14T09:30:00Z",
        "content": (
            "Real-Time Sales Dashboard — ChainSight ERP (as of 09:30 PKT, May 14 2026)\n"
            "SKU-A001 daily demand: 650 units/day\n"
            "SKU-A001 current stock at Lahore DC: 1200 pallets\n"
            "Days of supply remaining: 1.85 days — STOCKOUT RISK IN < 48 HOURS\n"
            "SKU-B042 daily demand: 310 units/day; stock: 850 pallets; 2.7 days supply\n"
            "SKU-C118 daily demand: 190 units/day; stock: 600 pallets; 3.2 days supply\n"
            "Revenue at risk (stockout): $285,000 USD across all SKUs."
        ),
    },
    {
        "source_id": "supplier_report",
        "source_type": "pdf_report",
        "timestamp_utc": "2026-05-13T14:00:00Z",
        "content": (
            "Supplier Reliability Report — Hamza Logistics (Internal Audit, May 13 2026)\n"
            "Consecutive delays recorded: 3 shipments in last 14 days.\n"
            "On-time delivery rate: 55% (was 94% in Q1 2026 — drop of 39 pp).\n"
            "Root cause: driver shortages and fuel cost escalation in Sindh province.\n"
            "Recommendation: activate alternate carrier (Gwadar route GWD-LHR-001) and trigger "
            "safety stock buffer at lahore_dc. Emergency order budget estimate: $12,000 USD."
        ),
    },
    {
        "source_id": "port_sensor_feed",
        "source_type": "realtime_feed",
        "timestamp_utc": "2026-05-14T09:45:00Z",
        "content": (
            "IoT Port Sensor Feed — Pakistan Ports Authority API\n"
            "Timestamp: 2026-05-14 09:45:12 PKT\n"
            "Container moves (last 6 hours): 0\n"
            "Berths 1-12 status: IDLE\n"
            "Gate activity: 0 truck-ins, 0 truck-outs (last 4 hours)\n"
            "Strike status: ACTIVE — union sources confirm no resolution within 24h.\n"
            "Monsoon probability (next 72 hours): 18% — elevated road disruption risk."
        ),
    },
]


@app.post("/api/analyze/demo", response_model=AnalyzeResponse, tags=["pipeline"])
async def analyze_demo():
    """Run the pipeline with the canonical 5-source demo scenario (no input required)."""
    from models import ContentSource, SourceType
    sources = [
        ContentSource(
            source_id=s["source_id"],
            source_type=SourceType(s["source_type"]),
            content=s["content"],
            timestamp_utc=s.get("timestamp_utc"),
        )
        for s in _DEMO_SOURCES_RAW
    ]
    req = AnalyzeRequest(sources=sources)
    return await analyze(req)

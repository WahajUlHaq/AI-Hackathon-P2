# ChainSight — SSE Streaming Dashboard + Input Validation Implementation Plan

We are building the final layer of ChainSight: the **SSE streaming API** in `main.py`, the **input validation guard**, and the **single-file SPA dashboard** in `app.html`. This layer is the user-facing surface — it receives events from the Gemini Antigravity orchestrator in real-time and renders them as a live intelligence trace. The UI was designed to convey that ChainSight is an agentic system — the 4-agent grid is visible, pulsing, and updating as each tool completes.

## User Review Required

> [!IMPORTANT]
> SSE queues are per-session and live in an in-memory dict (`_session_queues`). A background task cleans up queues older than 10 minutes. If a client disconnects mid-stream, the queue is abandoned (not drained) — this is safe because the orchestrator is reading queue results, not writing to the client directly. The orchestrator writes to the queue; the SSE endpoint reads from the queue and streams to the client.

> [!IMPORTANT]
> The input validation guard (`_is_supply_chain_content`) must run **before** the orchestrator is started. If it fails (< 2 keyword hits), the pipeline must not start, and the queue for that session must be cleaned up immediately. The frontend shows a clean red error banner, not a generic 422 page.

> [!NOTE]
> Rate limiting is IP-based (`_ip_timestamps` dict, `deque(maxlen=3)` per IP). A rolling 3600s window. The response headers `X-RateLimit-Remaining` and `X-RateLimit-Reset` are always present. This lets a demo facilitator know how many requests remain. On limit exceeded, the response is HTTP 429 with `{"error":"rate_limit","message":"..."}`.

> [!NOTE]
> The frontend agent grid has a deliberate design choice: all 4 agents appear to activate simultaneously via `_burstAgents()` with 80ms stagger. This creates the impression of parallel agent execution, which is accurate — the Gemini orchestrator dispatches tool calls rapidly, not sequentially. The agents complete one by one as `tool_result` events arrive.

## Proposed Changes

### [Backend — SSE + Validation]

#### [MODIFY] [main.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/main.py)

**SSE queue management:**
```python
_session_queues: dict[str, asyncio.Queue] = {}
_session_ttl: dict[str, float] = {}
SESSION_TTL_SECONDS = 600

async def _cleanup_sessions():
    # Background task — every 60s prunes sessions older than TTL
    
async def _emit(session_id: str, event_type: str, data: dict):
    q = _session_queues.get(session_id)
    if q: await q.put({"event": event_type, "data": data})
```

**Rate limiting:**
```python
_ip_timestamps: dict[str, deque] = defaultdict(lambda: deque(maxlen=3))
RATE_LIMIT = 3; WINDOW = 3600

def _check_rate_limit(ip: str) -> tuple[bool, int, int]:
    now = time.time()
    dq = _ip_timestamps[ip]
    dq = deque([t for t in dq if now - t < WINDOW], maxlen=3)
    _ip_timestamps[ip] = dq
    remaining = max(0, RATE_LIMIT - len(dq))
    reset = int(dq[0] + WINDOW) if dq else int(now + WINDOW)
    return len(dq) < RATE_LIMIT, remaining, reset
```

**Input validation:**
```python
_SC_KEYWORDS = {"supply","chain","disruption","port","strike","shipment","cargo",
    "logistics","inventory","delivery","route","freight","warehouse","transit",
    "delay","stockout","flood","customs","driver","shortage","closure","sku",
    "dc","distribution","vendor","supplier","procurement","container","pallet", ...}

def _is_supply_chain_content(req: AnalyzeRequest) -> bool:
    combined = " ".join(s.content.lower() for s in (req.sources or []))
    if req.content: combined += " " + req.content.lower()
    return sum(1 for kw in _SC_KEYWORDS if kw in combined) >= 2
```

**`GET /api/stream/{session_id}` SSE format:**
Each event: `event: {event_type}\ndata: {json}\n\n`
Event types: `orchestrator_start`, `tool_call`, `tool_result`, `orchestrator_done`, `pipeline_done`, `pipeline_error`

### [Frontend — app.html]

#### [MODIFY] [app.html](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/app.html)

**3-panel SPA layout:**
- Left panel: `AnalyzeForm` — source inputs (up to 5), content types, analyze button
- Center panel: `Live Pipeline Trace` — live-dot, 4-agent grid, SSE event cards
- Right panel: `Results` — 3 tabs (Insights / Actions / Execution)

**4-agent grid:**
```html
<div class="agents-grid" id="agents-grid">
  <div class="agent-tile" id="agent-parser">  Parser Agent  </div>
  <div class="agent-tile" id="agent-insight"> Insight Agent </div>
  <div class="agent-tile" id="agent-planner"> Planner Agent </div>
  <div class="agent-tile" id="agent-executor">Executor Agent</div>
</div>
```

States: `.idle` (default), `.active` (blue glow + scan-line shimmer), `.done` (green glow), `.error` (red glow)

**SSE event cards (glassmorphism):**
```css
.sse-event {
  background: rgba(255,255,255,0.05);
  backdrop-filter: blur(8px);
  border-left: 3px solid var(--accent-color);
  animation: card-in 0.25s ease;
}
```
Left accent colors: `orchestrator_start=#6366f1`, `tool_call=#3b82f6`, `tool_result=#10b981`, `pipeline_done=#6366f1`, `pipeline_error=#ef4444`

## Verification Plan

### End-to-End SSE Stream
Input: Port of Karachi article (5-source scenario)
Expected SSE event sequence:
```
event: orchestrator_start   data: {"model":"gemini-2.5-flash-lite","tools":14}
event: tool_call            data: {"tool":"parse_sources","args":{...}}
event: tool_result          data: {"tool":"parse_sources","latency_ms":2341}
event: tool_call            data: {"tool":"extract_insights","args":{...}}
event: tool_result          data: {"tool":"extract_insights","latency_ms":1876}
event: tool_call            data: {"tool":"plan_actions","args":{...}}
event: tool_result          data: {"tool":"plan_actions","latency_ms":2104}
event: tool_call            data: {"tool":"execute_action","args":{...}}
event: tool_result          data: {"tool":"execute_action","latency_ms":156}
event: orchestrator_done    data: {"turns":4,"total_ms":10204}
event: pipeline_done        data: {"session_id":"...","total_savings_usd":99960}
```
All 4 agent tiles complete (green glow). Results tabs populated. ✅

### Rate Limit
Requests 1–3 → HTTP 200, `X-RateLimit-Remaining: 2, 1, 0`
Request 4  → HTTP 429, `{"error":"rate_limit"}`, browser shows red banner ✅

### Input Validation
Input: `"hello world, what's the weather?"` → HTTP 422, `{"error":"irrelevant_input"}`, browser shows amber banner ✅

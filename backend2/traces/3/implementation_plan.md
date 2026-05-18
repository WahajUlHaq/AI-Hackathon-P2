# ChainSight MCP Server — 14-Tool Registry Implementation Plan

We are building the core **MCP (Model Context Protocol) server** that exposes all pipeline tools as callable functions to both **Google Antigravity** (via `mcp_config.json`) and the **Gemini function-calling orchestrator** (via converted `FunctionDeclaration` objects). This server is the backbone of the entire Antigravity integration.

## User Review Required

> [!IMPORTANT]
> The MCP server uses JSON-RPC 2.0 over HTTP (Streamable HTTP transport). Google Antigravity connects to it via the URL declared in `mcp_config.json`. All 14 tools must have valid JSON Schema `inputSchema` definitions — Gemini will reject any tool with a malformed schema. Any tool that writes to session state must be idempotent to survive retry on 429.

> [!NOTE]
> We are using a single in-memory `_sessions` dict keyed by `session_id` to pass data between tool calls. This is intentional — it avoids Gemini's context window filling up with large JSON blobs. Gemini only sees compact summaries; full data lives in the session store.

## Proposed Changes

### [Backend — MCP Server]

#### [NEW] [mcp_server.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/mcp_server.py)

The MCP server is implemented as a FastAPI `APIRouter` mounted at `/mcp/`. It handles JSON-RPC 2.0 messages for `initialize`, `tools/list`, and `tools/call` methods.

**14 registered tools:**

| Tool | Description | Session writes |
|---|---|---|
| `parse_sources` | Unified multi-source parser (delegates to `parser_agent`) | `session["parsed"]` |
| `parse_csv_source` | CSV/JSON source parser | `session["pending_sources"]` |
| `parse_pdf_source` | PDF text parser | `session["pending_sources"]` |
| `parse_news_source` | News article parser | `session["pending_sources"]` |
| `parse_dashboard_source` | ERP/dashboard parser | `session["pending_sources"]` |
| `parse_realtime_source` | IoT/realtime feed parser | `session["pending_sources"]` |
| `extract_insights` | Causal chain extractor | `session["insight"]` |
| `plan_actions` | Action ranker + constraint validator | `session["plan"]` |
| `execute_action` | Mock API dispatcher | `session["execution"]` |
| `get_system_state` | Returns live state snapshot | — |
| `reset_state` | Resets all mock API state | — |
| `get_inventory` | Returns DC inventory | — |
| `get_routes` | Returns route status | — |
| `send_notification` | Sends mock notification | — |

**JSON Schema example for `execute_action`:**
```json
{
  "name": "execute_action",
  "description": "Execute a specific action from the plan using mock APIs. Captures before/after state.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session_id": { "type": "string", "description": "Active session ID" },
      "action_id": { "type": "string", "description": "Action ID from plan (e.g. ACT-001)" }
    },
    "required": ["session_id", "action_id"]
  }
}
```

#### [MODIFY] [main.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/main.py)
- Mount `mcp_router` at application level: `app.include_router(mcp_router)`
- Ensure CORS allows the Antigravity runtime origin

#### [NEW] [mcp_config.json](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/mcp_config.json)
- Declare the MCP server URL pointing to `POST /mcp/`
- This file is read by Google Antigravity to discover and register all tools at runtime

## Verification Plan

### Automated — `tools/list`
```bash
curl -X POST http://localhost:8000/mcp/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```
Expected: array of 14 tool objects, each with `name`, `description`, `inputSchema`.

### Automated — `tools/call`
```bash
curl -X POST http://localhost:8000/mcp/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_system_state","arguments":{}}}'
```
Expected: `{"content":[{"type":"text","text":"{...state json...}"}]}`

### Antigravity Registration
- Load `mcp_config.json` in Antigravity runtime
- Confirm Antigravity reports all 14 tools as `available`

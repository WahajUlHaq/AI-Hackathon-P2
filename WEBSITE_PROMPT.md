# ChainSight — Full Interactive Website Build Prompt

Use this prompt verbatim with any AI coding tool (Cursor, Claude, GPT-4, Copilot, v0, Bolt, etc.)

---

## PROMPT START

Build a complete single-page web application called **ChainSight** for an agentic supply chain intelligence system. The app must be built with **vanilla HTML + CSS + JavaScript only** — no frameworks, no build step, one self-contained `app.html` file. It should work by opening it directly in a browser.

---

## BACKEND BASE URL

```
http://localhost:8000
```

Add CORS is already enabled on the backend (`allow_origins=["*"]`), so fetch calls work directly from the browser.

---

## VISUAL DESIGN

- Dark theme: background `#0d1117`, surface `#161b22`, borders `#30363d`
- Accent colors: blue `#58a6ff`, green `#3fb950`, yellow `#d29922`, purple `#bc8cff`, red `#f85149`
- Font: system UI stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`)
- Monospace for JSON/code: `"Cascadia Code", "Fira Code", Consolas, monospace`
- The UI has three main panels laid out in a responsive grid:
  - **Left panel** — Input form (sources + submit button)
  - **Center panel** — Live SSE event stream (fills in real time as pipeline runs)
  - **Right panel** — Tabbed results (Parsed → Insights → Plan → Execution)

---

## FULL APP FLOW

1. User fills the input form and clicks **Analyze**
2. App generates a `session_id` = `"session-" + Date.now()`
3. App opens an SSE connection to `GET /api/stream/{session_id}` immediately
4. App POSTs to `POST /api/analyze` with the session_id and sources
5. SSE events stream in and fill the center panel in real time
6. When `pipeline_done` arrives, the full JSON response is already available from the POST — display it in the right panel tabs
7. User can click **Reset State** to call `POST /api/state/reset` before another run

---

## SECTION 1 — INPUT FORM (Left Panel)

### Session ID
Auto-generated but editable text field. Default: `"session-" + Date.now()`

### Source Builder
Users can add multiple sources. Each source has:

| Field | Type | Options |
|---|---|---|
| `source_id` | text input | auto-filled: `"src-1"`, `"src-2"`, etc. |
| `source_type` | dropdown | `realtime_feed`, `dashboard`, `news_article`, `pdf_report`, `csv_json` |
| `timestamp_utc` | datetime-local input | converted to ISO 8601 on submit |
| `content` | textarea (4 rows) | paste text or a URL (starts with http) |

**Buttons:**
- `+ Add Source` — appends another source card
- `× Remove` — removes that source card (minimum 1)

### Preset Examples Button Row
Six quick-load buttons that pre-fill the form:

**[Single: IoT Alert]** — loads:
```json
[{
  "source_id": "rt-1",
  "source_type": "realtime_feed",
  "timestamp_utc": "2026-05-14T06:00:00Z",
  "content": "IoT ALERT: 3 trucks on KHI-LHR-001 stopped at Sukkur checkpoint due to road blockage. Est delay 6-8 hrs. SKU-ELEC-001 shipment at risk."
}]
```

**[3 Sources: Aligned]** — loads:
```json
[
  {
    "source_id": "news-1",
    "source_type": "news_article",
    "timestamp_utc": "2026-05-14T04:00:00Z",
    "content": "Port of Karachi workers announced a 3-day strike starting May 15. All container terminals affected. Shipping companies report ~72hr cargo backlog."
  },
  {
    "source_id": "dashboard-1",
    "source_type": "dashboard",
    "timestamp_utc": "2026-05-14T05:30:00Z",
    "content": "ERP SNAPSHOT: KHI warehouse utilization 94%. Outbound orders queued: 847. On-hand SKU-ELEC-001: 120 units. Safety stock threshold: 200 units. ALERT: Below threshold."
  },
  {
    "source_id": "csv-1",
    "source_type": "csv_json",
    "timestamp_utc": "2026-05-14T05:00:00Z",
    "content": "dc,sku,on_hand,safety_stock,days_cover\nKHI,SKU-ELEC-001,120,200,2\nLHR,SKU-ELEC-001,380,200,8"
  }
]
```

**[4 Sources: WITH CONFLICTS]** — loads (this is the best demo — two contradictions):
```json
[
  {
    "source_id": "realtime-port",
    "source_type": "realtime_feed",
    "timestamp_utc": "2026-05-14T06:00:00Z",
    "content": "PORT AUTHORITY LIVE: Karachi port strike declared. Terminal 2 sealed. Est clearance 7-10 days. 1,200 containers backlogged. SKU-ELEC-001 batch #KHI-2026-447 held at gate 7."
  },
  {
    "source_id": "dashboard-erp",
    "source_type": "dashboard",
    "timestamp_utc": "2026-05-14T05:00:00Z",
    "content": "ERP: KHI port disruption logged. Estimated delay: 5 days. Penalty accrual: $2,100/day. Affected routes: KHI-LHR-001. On-hand KHI: 120 units. Safety stock: 200 units."
  },
  {
    "source_id": "csv-ops",
    "source_type": "csv_json",
    "timestamp_utc": "2026-05-13T12:00:00Z",
    "content": "event,delay_days,penalty_per_day\nport_strike,3,2100"
  },
  {
    "source_id": "news-1",
    "source_type": "news_article",
    "timestamp_utc": "2026-05-14T03:00:00Z",
    "content": "Karachi port strike enters day 2. Officials say resolution may take up to 2 weeks. Electronics supply chains most affected. Air freight prices up 40%."
  }
]
```

**[5 Sources: All Types]** — loads one of each source_type:
```json
[
  {
    "source_id": "rt-1",
    "source_type": "realtime_feed",
    "timestamp_utc": "2026-05-14T06:00:00Z",
    "content": "GPS TRACKER: Truck LHR-2026-T91 stopped 45km south of Lahore. Engine fault. SKU-FMCG-003 load. ETA delay: 4-6 hours."
  },
  {
    "source_id": "dash-1",
    "source_type": "dashboard",
    "timestamp_utc": "2026-05-14T05:00:00Z",
    "content": "WMS: LHR DC utilization 78%. SKU-FMCG-003 on-hand: 340 units (threshold 250). Pending inbound: 2 trucks delayed. Outbound fill rate today: 91%."
  },
  {
    "source_id": "news-1",
    "source_type": "news_article",
    "timestamp_utc": "2026-05-14T04:00:00Z",
    "content": "Heavy rainfall in Punjab causing road closures on N-5 highway. Logistics operators report 20-30% capacity reduction across Lahore-Islamabad corridor."
  },
  {
    "source_id": "pdf-1",
    "source_type": "pdf_report",
    "timestamp_utc": "2026-05-13T00:00:00Z",
    "content": "QUARTERLY RISK REPORT: N-5 highway historically prone to weather disruptions in monsoon season (May-August). Recommend pre-positioning safety stock at ISB DC. Estimated seasonal risk: 15-20% on-time delivery reduction."
  },
  {
    "source_id": "csv-1",
    "source_type": "csv_json",
    "timestamp_utc": "2026-05-14T05:30:00Z",
    "content": "dc,sku,on_hand,safety_stock,days_cover\nLHR,SKU-FMCG-003,340,250,4\nISB,SKU-FMCG-003,95,250,1"
  }
]
```

**[URL Fetch]** — loads a single news_article with a URL as content:
```json
[{
  "source_id": "web-1",
  "source_type": "news_article",
  "content": "https://www.dawn.com/news/supply-chain"
}]
```
*(backend auto-fetches and strips HTML)*

**[Reset & Clear]** — clears all sources back to one empty card.

### Submit Bar
- **[Reset State]** button — calls `POST /api/state/reset`, shows green toast "State reset ✓"
- **[▶ Analyze]** primary button — triggers the full flow
- Status badge shows: `Idle` / `Streaming...` / `Done ✓` / `Error ✗`

---

## SECTION 2 — LIVE SSE STREAM (Center Panel)

Title: **"Live Pipeline Trace"**

### How to connect

```javascript
const sessionId = document.getElementById('session-id').value;
const es = new EventSource(`http://localhost:8000/api/stream/${sessionId}`);

es.addEventListener('message', (e) => {
  const line = e.data;
  if (!line || line.startsWith(':')) return; // skip pings

  // The SSE format is: event type on first colon-separated token
  // Actually the backend sends named events like:
  // event: orchestrator_start\ndata: {...}\n\n
});

// Named event listeners:
es.addEventListener('orchestrator_start', (e) => appendEvent('start', JSON.parse(e.data)));
es.addEventListener('tool_call',          (e) => appendEvent('call',  JSON.parse(e.data)));
es.addEventListener('tool_result',        (e) => appendEvent('result',JSON.parse(e.data)));
es.addEventListener('orchestrator_done',  (e) => appendEvent('done',  JSON.parse(e.data)));
es.addEventListener('pipeline_done',      (e) => appendEvent('done',  JSON.parse(e.data)));
es.addEventListener('pipeline_error',     (e) => appendEvent('error', JSON.parse(e.data)));
```

**IMPORTANT:** Open the EventSource BEFORE firing the POST to `/api/analyze`.

### Event display format

Each event renders as a row:
```
[TAG]  tool_name  →  JSON summary  (timestamp)
```

Tag colors:
| Event type | Tag label | Color |
|---|---|---|
| `orchestrator_start` | `START` | blue |
| `tool_call` | `CALL` | yellow |
| `tool_result` | `RESULT` | green (or red if success=false) |
| `orchestrator_done` | `ORCH` | purple |
| `pipeline_done` | `DONE` | green |
| `pipeline_error` | `ERROR` | red |

For `tool_call` events, the data shape is:
```json
{ "tool": "parse_sources", "args": {"session_id": "..."}, "call_number": 1 }
```

For `tool_result` events, the data shape is:
```json
{ "tool": "parse_sources", "call_number": 1, "success": true, "result": { ... } }
```

Show a collapsible JSON detail for each event (click to expand).

The stream auto-scrolls to the bottom as events come in.

When `pipeline_done` fires, close the EventSource with `es.close()`.

---

## SECTION 3 — REQUEST / RESPONSE (Right Panel, Tabbed)

### How to send the request

```javascript
const body = {
  session_id: sessionId,   // same one used for SSE
  sources: [
    {
      source_id: "rt-1",
      source_type: "realtime_feed",      // one of: csv_json | pdf_report | news_article | dashboard | realtime_feed
      content: "IoT ALERT: ...",
      timestamp_utc: "2026-05-14T06:00:00Z"  // ISO 8601, optional
    }
    // ... more sources
  ]
};

const response = await fetch('http://localhost:8000/api/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body)
});

const data = await response.json();   // AnalyzeResponse
```

### Full AnalyzeResponse structure (parse this for the tabs)

```typescript
interface AnalyzeResponse {
  session_id: string;

  // TAB 1 — Parsed
  parsed: {
    sources_parsed: number;
    noise_filtered: number;
    entities: Array<{
      disruption_type: string;   // e.g. "port_strike"
      location: string;
      affected_region: string;
      duration_days: number;
      severity: string;          // "low" | "medium" | "high" | "critical"
      raw_facts: string[];
    }>;
    key_metrics: Record<string, any>;
    time_horizon: string;
    credibility_scores: Record<string, number>;   // source_id → 0.0–1.0
    temporal_signals: Array<{
      metric: string;
      trend: string;             // "rising" | "falling" | "stable" | "spike"
      change_pct: number;
      observation: string;
    }>;
    contradictions: Array<{
      metric: string;
      source_a_id: string;
      source_a_claim: string;
      source_b_id: string;
      source_b_claim: string;
      resolution: string;        // "source_a_preferred" | "source_b_preferred" | "unresolved"
      resolution_reason: string;
    }>;
  };

  // TAB 2 — Insight
  insight: {
    title: string;
    urgency: string;             // "immediate" | "24h" | "48h" | "week"
    total_exposure_usd: number;
    affected_skus: string[];
    key_risks: string[];
    causal_chains: Array<{
      cause: string;
      immediate_effect: string;
      downstream_effect: string;
      financial_impact_usd: number;
      probability_pct: number;
    }>;
    contradiction_resolutions: string[];
  };

  // TAB 3 — Plan
  plan: {
    primary_action_id: string;
    rationale: string;
    total_budget_usd: number;
    ranked_actions: Array<{
      action_id: string;
      action_type: string;       // "reroute_shipment" | "update_pricing" | "send_notification" | "activate_safety_stock" | "update_inventory"
      title: string;
      description: string;
      confidence_pct: number;
      estimated_savings_usd: number;
      feasibility_status: string;  // "feasible" | "infeasible" | "modified"
      feasibility_note: string | null;
      parameters: Record<string, any>;
      depends_on: string[];
    }>;
    constraint_violations: string[];
  };

  // TAB 4 — Execution (may be null if executor failed)
  execution: {
    total_actions_attempted: number;
    total_actions_succeeded: number;
    total_actions_failed: number;
    outcome_summary: string;
    penalty_reduction_usd: number;
    eta_improvement_days: number;
    total_latency_ms: number;
    before_state: {
      inventory: Record<string, any>;
      routes: Record<string, any>;
      pricing: Record<string, any>;
      notifications_count: number;
      penalty_exposure_usd: number;
    };
    after_state: {
      // same shape as before_state
    };
    chain_steps: Array<{
      action_id: string;
      action_type: string;
      action_title: string;
      status: string;            // "success" | "failed" | "retried_ok" | "rolled_back" | "skipped"
      attempt: number;
      latency_ms: number;
      error: string | null;
      recovery_note: string | null;
      api_steps: Array<{
        step: number;
        action: string;
        endpoint: string;
        request_payload: Record<string, any>;
        response_payload: Record<string, any>;
        latency_ms: number;
        success: boolean;
      }>;
    }>;
  } | null;

  // TAB 5 — Agent Trace
  agent_trace: Array<{
    agent: string;
    status: string;
    output: Record<string, any> | null;
    error: string | null;
  }>;
}
```

---

## RIGHT PANEL TAB DESIGNS

### Tab 1 — Parsed

**Summary bar (3 stat chips in a row):**
- `📦 {sources_parsed} Sources`
- `🔍 {entities.length} Entities`
- `⚠️ {contradictions.length} Conflicts`

**Entities section:**
Each entity as a card with a colored severity badge:
- `critical` → red badge
- `high` → orange badge
- `medium` → yellow badge
- `low` → green badge

Show: disruption_type · location → affected_region · duration_days days · bullet list of raw_facts

**Credibility Scores section:**
Horizontal bar chart per source_id. Bar width = credibility_score × 100%. Color gradient green→yellow→red for score 1.0→0.5→0.

**Contradictions section** (only if contradictions.length > 0, show warning box):
Each contradiction: `{metric}` — source A claimed `{source_a_claim}` vs source B claimed `{source_b_claim}` → Resolution: `{resolution}` because `{resolution_reason}`

**Temporal Signals:**
Small chips: `{metric}: {trend} {change_pct}%` — trend arrow (↑ rising, ↓ falling, → stable, ⚡ spike)

**Key Metrics:**
JSON object rendered as a readable key-value list.

---

### Tab 2 — Insights

**Hero metric row:**
- `💥 ${ (total_exposure_usd).toLocaleString() }` — total exposure
- Urgency badge: `immediate` = red, `24h` = orange, `48h` = yellow, `week` = green

**Causal Chains:**
Each chain as a 3-step visual flow:
```
[Cause] ──► [Immediate Effect] ──► [Downstream Effect]
                                    $XX,XXX  ·  XX% probability
```

**Key Risks:**
Bullet list of risk strings.

**Affected SKUs:**
Pill tags for each SKU.

---

### Tab 3 — Action Plan

**Header:** Primary action highlighted with star ★

**Action cards** in ranked order. Each card shows:
- Rank number (1, 2, 3...)
- ★ if this is primary_action_id
- Title + description
- Confidence bar (confidence_pct as a progress bar, green if >75, yellow if 50-75, red if <50)
- Estimated savings: `${ estimated_savings_usd.toLocaleString() }`
- Feasibility badge: `feasible` = green, `modified` = yellow, `infeasible` = red
- Parameters: expandable JSON block
- Depends on: list of action_id chips (if any)

**Constraint violations** (if any): red warning box

---

### Tab 4 — Execution

If `execution === null`: show a grey placeholder "Execution data not available"

Otherwise:

**Summary row (4 stat chips):**
- `✅ {total_actions_succeeded} Succeeded`
- `❌ {total_actions_failed} Failed`
- `💰 ${penalty_reduction_usd.toLocaleString()} Saved`
- `⏱ {total_latency_ms}ms`

**Before vs After state comparison:**
Side-by-side table. For each top-level key in before_state (inventory, routes, pricing, notifications_count, penalty_exposure_usd): show before value → after value with a colored diff (green if improved, red if worsened, grey if unchanged).

**Chain Steps:**
Accordion list. Each step:
- Status badge: `success`=green, `failed`=red, `retried_ok`=yellow, `rolled_back`=orange
- Action title + type
- Expand to show api_steps list (each API call: method, endpoint, request/response payloads)

---

### Tab 5 — Agent Trace

Timeline-style vertical list. Each step:
- Agent name pill
- Status icon (✅ done, ❌ error)
- If output: show key count or brief summary
- If error: show error string in red

---

## ADDITIONAL UI ELEMENTS

### Toast Notifications
Bottom-right corner. Auto-dismiss after 3s.
- Success: green border, "✓ " prefix
- Error: red border, "✗ " prefix

### Error State
If the POST fails (network error or non-200 response), show the error in the center panel and stop the SSE connection.

### Loading Skeleton
While waiting for the POST response, show animated pulse skeletons in the right panel tabs.

### Raw JSON Toggle
Add a "Show Raw JSON" toggle button in the right panel that reveals the full unformatted `AnalyzeResponse` in a scrollable `<pre>` block.

---

## OTHER ENDPOINTS TO USE

### Reset State
```javascript
await fetch('http://localhost:8000/api/state/reset', { method: 'POST' });
```

### Get Current State
```javascript
const state = await fetch('http://localhost:8000/api/state').then(r => r.json());
// Returns: { inventory: {...}, routes: {...}, pricing: {...} }
```
Display this in a collapsible "Current State" section at the bottom of the left panel.

### Health Check
On page load, call `GET /health` and show a green dot "Backend Online" or red dot "Backend Offline" in the nav bar.

---

## LAYOUT SPEC

```
┌─────────────────────────────────────────────────────────────────┐
│  NAV: "⛓ ChainSight"          [● Backend Online]  [Docs ↗]     │
├──────────────┬──────────────────┬───────────────────────────────┤
│  INPUT FORM  │   LIVE STREAM    │   RESULTS (tabbed)            │
│  (360px)     │   (flex 1)       │   (480px)                     │
│              │                  │  [Parsed][Insight][Plan]      │
│  Sources     │  Events fill     │  [Execution][Trace]           │
│  + Add       │  here in real    │                               │
│              │  time            │  Tab content renders after    │
│  Presets     │                  │  POST resolves                │
│              │  Auto-scroll     │                               │
│  [Reset][▶]  │  ↓               │  [Show Raw JSON]              │
└──────────────┴──────────────────┴───────────────────────────────┘
```

On mobile (<768px): stack all 3 panels vertically.

---

## IMPLEMENTATION NOTES

1. Generate `session_id` as `"session-" + Date.now()` each time Analyze is clicked.
2. Open EventSource FIRST, then fire the POST — otherwise early events are missed.
3. The POST to `/api/analyze` is a long-running request (10-30 seconds). Use `await fetch(...)` normally — it resolves when the full pipeline completes and returns the full `AnalyzeResponse`.
4. SSE events come in during the fetch wait — they fill the center panel while the right panel is still loading.
5. `timestamp_utc` from `<input type="datetime-local">` gives `"2026-05-14T06:00"` — append `":00Z"` to make it ISO 8601: `value + ":00Z"`.
6. Source types and their credibility hierarchy: `realtime_feed(0.92) > dashboard(0.85) > news_article(0.80) > pdf_report(0.75) > csv_json(0.70)`
7. If `content` starts with `http://` or `https://`, the backend auto-fetches and processes it — no special handling needed in the UI.
8. The `execution` field in the response can be `null` — always null-check before rendering Tab 4.

---

## OUTPUT

Produce a single file `app.html` with all HTML, CSS, and JavaScript inline. No external dependencies except fonts (use system fonts). The file must work by double-clicking it (file:// protocol) or serving from a local server.

## PROMPT END

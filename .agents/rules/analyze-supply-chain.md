# ChainSight: Autonomous Supply Chain Disruption Analysis
# Invoke with: /analyze-supply-chain
# Requires: backend running at http://localhost:8000

## Architecture
5 content-type agents run (you call them one by one, each independently).
Then merge → insight → plan → execute each action in series.
YOU control every call. Nothing runs automatically inside the backend.

---

## Step 0 — Baseline State
Call `get_system_state`.
Show a baseline table to the user before anything changes.

---

## Step 1 — Gather Input
Ask the user:
"Paste your 5 content sources, or type **demo** for the built-in scenario."

For **demo**, use the 5 sources below.

---

## Step 2 — PARALLEL: Feed 5 Content-Type Agents

Call all 5 parse tools. Each is a separate agent for a separate content type.
Use the session_id from the FIRST call in all subsequent calls.

### Agent 1 — CSV/JSON Parser
Call `parse_csv_source`:
```json
{
  "source_id": "warehouse_csv",
  "content": "Inventory Report Lahore DC 2026-05-12: SKU-A001 2500 pallets NORMAL, SKU-B042 1200 pallets NORMAL, SKU-C118 890 pallets NORMAL. No shortages detected. All inbound on schedule.",
  "timestamp_utc": "2026-05-12T08:00:00Z"
}
```
Display: "CSV Agent — found X entities, key metrics: ..."

### Agent 2 — PDF/Report Parser
Call `parse_pdf_source` with the same session_id:
```json
{
  "session_id": "<from above>",
  "source_id": "supplier_report",
  "content": "Supplier Reliability Audit May 13: On-time delivery 55% (was 94% Q1, drop 39pp). Root cause: driver shortage, fuel costs. Recommend: activate GWD-LHR-001 and safety stock lahore_dc.",
  "timestamp_utc": "2026-05-13T14:00:00Z"
}
```
Display: "PDF Agent — found X entities, key metrics: ..."

### Agent 3 — News/Article Parser
Call `parse_news_source` with the same session_id:
```json
{
  "session_id": "<from above>",
  "source_id": "ppa_news",
  "content": "PORT OF KARACHI STRIKE DAY 3. All container-handling suspended since May 12. 847 pallets stranded (SKU-A001, SKU-B042, SKU-C118). 40% backlog. ETA 2.5 → 7+ days. SLA penalty at day 5 (PKR 150/pallet/day). 23 retail partners closing 48h windows.",
  "timestamp_utc": "2026-05-14T06:00:00Z"
}
```
Display: "News Agent — found X entities, key metrics: ..."

### Agent 4 — Dashboard Parser
Call `parse_dashboard_source` with the same session_id:
```json
{
  "session_id": "<from above>",
  "source_id": "sales_dashboard",
  "content": "Real-Time Sales Dashboard 09:30 PKT May 14: SKU-A001 demand 650/day stock 1200 = 1.85 days STOCKOUT RISK. SKU-B042 demand 310/day stock 850 = 2.7 days. Revenue at risk $285,000.",
  "timestamp_utc": "2026-05-14T09:30:00Z"
}
```
Display: "Dashboard Agent — found X entities, key metrics: ..."

### Agent 5 — Real-Time Feed Parser
Call `parse_realtime_source` with the same session_id:
```json
{
  "session_id": "<from above>",
  "source_id": "port_sensor_feed",
  "content": "IoT Port Sensor 09:45 PKT: Container moves last 6h = 0. Berths 1-12 IDLE. Gate: 0 truck-ins 0 truck-outs last 4h. Strike ACTIVE, no resolution within 24h. Monsoon probability 72h = 18%.",
  "timestamp_utc": "2026-05-14T09:45:00Z"
}
```
Display: "Real-Time Feed Agent — found X entities, key metrics: ..."

---

## Step 3 — MERGE: Combine All 5 Agent Outputs
Call `merge_and_analyze` with the session_id.

This detects contradictions ACROSS all 5 sources.
Display clearly:

**Contradiction Found (CRITICAL):**
```
warehouse_csv  [2026-05-12, score: LOW — STALE]  → "Stock NORMAL, no shortages"
sales_dashboard [2026-05-14, score: HIGH — LIVE]  → "1.85 days to stockout"
RESOLUTION: sales_dashboard preferred (2 days newer, real-time source)
```

Show credibility scores for all 5 sources.
Show temporal signals (which metrics are rising/falling).

Tell the user: "Merge complete. Passing unified data to Insight Agent."

---

## Step 4 — INSIGHT AGENT
Call `extract_insights` with session_id.

Show each causal chain:
```
CAUSE → IMMEDIATE EFFECT → DOWNSTREAM EFFECT → $IMPACT (X% probability)
```
Show total exposure, urgency, key risks.

---

## Step 5 — PLANNER AGENT
Call `plan_actions` with session_id.

Show all 3-5 actions ranked. For each:
- Confidence bar (████░░ X%)
- Budget constraint and deadline
- Feasibility: FEASIBLE / INFEASIBLE / MODIFIED
- Dependencies (which actions must run first)

Explicitly tell the user which actions are INFEASIBLE and will be skipped.

---

## Step 6 — SERIAL: Execute Each Action Individually

You execute each action ONE BY ONE. After each, show state change.

### Execute Action 1 (Primary)
Call `execute_action` with session_id and the primary_action_id.
Show:
```
[ACT-001] Reroute Shipments to Gwadar
Status:  SUCCESS / RETRIED_OK / ROLLED_BACK
Attempts: X
Penalty before: $320,000 → after: $154,900  (saved $165,100)
Notifications: 0 → 2
Latency: Xms
```

Call `get_system_state` to show live state after this action.

### Execute Action 2
Call `execute_action` with action_id = ACT-002.
Show same format. Note if this action depended on ACT-001.

### Execute Action 3
Call `execute_action` with action_id = ACT-003.
If INFEASIBLE or dependency failed → show why it was skipped.

### Continue for remaining actions...

---

## Step 7 — Final Before / After
Call `get_system_state` one last time.
Show the full comparison table:
```
METRIC                  BEFORE      AFTER       DELTA
──────────────────────────────────────────────────────
Penalty exposure ($)    320,000     X           -X   ✅
KHI-LHR-001 ships       847         X           -X   ✅
GWD-LHR-001 ships       0           X           +X   ✅
Notifications sent      0           X           +X   ✅
Safety stock active     false       X                ✅
```

---

## Step 8 — Executive Summary
3 sentences:
1. Which sources detected the disruption, what contradiction was found and resolved
2. Which actions were planned, which were infeasible/skipped and why
3. Final measurable outcome: penalty reduced by $X, ETA improved by X days

Ask:
"Would you like to:
- **[F]** Simulate a FAILURE — I will force the next action to fail and show rollback
- **[R]** Reset state and run fresh demo"

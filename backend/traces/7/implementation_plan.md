# ChainSight — Mock API Layer + Shared State Management Implementation Plan

We are building the **4 Mock API modules** (Inventory, Routing, Pricing, Notifications) and the **shared state management layer** (`state.py`). These APIs simulate a real Pakistan logistics backend — they hold realistic data for 3 distribution centers, 5 active routes, and provide the executor agent with callable endpoints that produce observable state changes.

## User Review Required

> [!IMPORTANT]
> The mock APIs must be **stateful** — each call mutates shared state that persists for the session. When `activate_safety_stock` is called on `lahore_dc`, the penalty exposure must decrease and that change must be visible in subsequent `get_system_state` calls. The Executor Agent's before/after state capture depends entirely on this statefulness. A `reset_state` endpoint must restore the exact original baseline so demos can be replayed.

> [!NOTE]
> Pricing API surge adjustment is capped at ±25% of base price to avoid unrealistic outputs that could confuse the Planner Agent. The Routing API's reroute optimizer calculates cost and ETA delta relative to the current best route — if no route is active, it defaults to the Gwadar alternate (PKR 310/pallet, 4.9-day transit).

> [!IMPORTANT]
> All 4 API routers must be mounted in [main.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/main.py) at `/mock/` prefix. The MCP `execute_action` tool calls these endpoints internally (not via HTTP) — it imports the router functions directly. This avoids an HTTP round-trip and keeps the executor fast.

## Proposed Changes

### [Backend — State]

#### [NEW] [state.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/state.py)

Single module-level dict seeded with realistic baseline:
```python
_state = {
  "penalty_exposure_usd": 320_000,
  "holding_cost_usd": 38_115,
  "safety_stock_activated": False,
  "notifications": [],
  "inventory": {
    "karachi_dc":   {"SKU-A001": {"quantity": 847, "unit_cost": 45.0}, ...},
    "lahore_dc":    {"SKU-A001": {"quantity": 120, "unit_cost": 45.0}, ...},
    "islamabad_dc": {"SKU-A001": {"quantity": 230, "unit_cost": 45.0}, ...},
  },
  "routes": {
    "KHI-LHE-001": {"name": "Karachi–Lahore Main", "status": "disrupted", "eta_days": 7.5, ...},
    "KHI-ISB-001": {"name": "Karachi–Islamabad Express", "status": "disrupted", ...},
    "GWD-LHE-001": {"name": "Gwadar–Lahore Alternate", "status": "available", "eta_days": 4.9, ...},
    ...
  },
  "pricing": { "SKU-A001": {"base_price": 250.0, "surge_multiplier": 1.0}, ... }
}
```

**`get_snapshot()`** — returns a deep copy of state as `StateSnapshot` Pydantic model
**`reset()`** — restores `_state` to original baseline values

### [Backend — Mock APIs]

#### [NEW] [mock_apis/inventory.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/mock_apis/inventory.py)

Routes:
- `GET /mock/inventory/` — returns all DC inventory
- `POST /mock/inventory/adjust` — `{dc, sku, delta}` — adjusts quantity
- `POST /mock/inventory/safety-stock/activate` — `{dc}` — activates safety stock, reduces `penalty_exposure_usd` by 7%
- `GET /mock/inventory/exposure` — returns current `penalty_exposure_usd` and `holding_cost_usd`

**Safety stock activation logic:**
```python
reduction = state._state["penalty_exposure_usd"] * 0.07
state._state["penalty_exposure_usd"] -= reduction
state._state["safety_stock_activated"] = True
```

#### [NEW] [mock_apis/routing.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/mock_apis/routing.py)

Routes:
- `GET /mock/routing/routes` — returns all 5 routes with status and ETA
- `POST /mock/routing/reroute` — `{route_id, reason, new_waypoints}` — updates route status to `"rerouted"`, calculates cost delta

**Reroute penalty calculation:**
```python
# Gwadar alternate costs 24% more per pallet
cost_delta_per_pallet = 310 * 0.24  # PKR 74.4 extra
penalty_reduction = 847 * 45 * 0.85  # avoided holding cost per pallet × 85% probability
state._state["penalty_exposure_usd"] -= penalty_reduction
```

#### [NEW] [mock_apis/pricing.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/mock_apis/pricing.py)

Routes:
- `GET /mock/pricing/` — returns all SKU base prices and current multipliers
- `POST /mock/pricing/update` — `{region, multiplier}` — validates region, applies surge cap (max 1.25×, min 0.75×)

#### [NEW] [mock_apis/notifications.py](file:///c:/Users/Wahaj/Desktop/Hackathon--AI-Seekho/backend/mock_apis/notifications.py)

Routes:
- `GET /mock/notifications/` — returns notification audit log
- `POST /mock/notifications/send` — `{notification_type, recipients, subject, body, priority}` — appends to audit log with timestamp, increments `notifications_count`

## Verification Plan

### State Reset
```bash
POST /api/state/reset
GET /api/state  →  penalty_exposure_usd: 320000, notifications: []
```

### Safety Stock Activation
```bash
POST /mock/inventory/safety-stock/activate  body: {"dc":"lahore_dc"}
GET /api/state  →  penalty_exposure_usd: 297600  (320000 × 0.93)
```

### Reroute
```bash
POST /mock/routing/reroute  body: {"route_id":"KHI-LHE-001","reason":"port_strike","new_waypoints":["Gwadar","N-55","Lahore DC"]}
GET /mock/routing/routes  →  KHI-LHE-001.status: "rerouted"
GET /api/state  →  penalty_exposure_usd: 220040  (320000 - 99960 reroute saving)
```

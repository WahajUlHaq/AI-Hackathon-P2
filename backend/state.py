"""
In-memory supply chain state.
Provides snapshot(), update_*() helpers used by mock APIs and executor.
"""
import copy
from threading import Lock

_lock = Lock()

_initial_state = {
    "inventory": {
        "lahore_dc": {
            "SKU-A001": {"quantity": 1200, "unit": "pallets", "holding_cost_per_day": 45},
            "SKU-B042": {"quantity": 850,  "unit": "pallets", "holding_cost_per_day": 38},
            "SKU-C118": {"quantity": 600,  "unit": "pallets", "holding_cost_per_day": 52},
        },
        "islamabad_dc": {
            "SKU-A001": {"quantity": 300, "unit": "pallets", "holding_cost_per_day": 45},
            "SKU-B042": {"quantity": 120, "unit": "pallets", "holding_cost_per_day": 38},
        },
        "karachi_port": {
            "SKU-A001": {"quantity": 847, "unit": "pallets", "holding_cost_per_day": 45},
            "SKU-B042": {"quantity": 420, "unit": "pallets", "holding_cost_per_day": 38},
            "SKU-C118": {"quantity": 310, "unit": "pallets", "holding_cost_per_day": 52},
        },
    },
    "routes": {
        "KHI-LHR-001": {
            "name": "Karachi → Lahore (Primary)",
            "origin": "karachi_port",
            "destination": "lahore_dc",
            "status": "disrupted",
            "eta_days": 7.0,          # inflated due to strike
            "normal_eta_days": 2.5,
            "shipments_in_transit": 847,
            "cost_per_pallet": 250,
        },
        "GWD-LHR-001": {
            "name": "Gwadar → Lahore (Alternate)",
            "origin": "gwadar_port",
            "destination": "lahore_dc",
            "status": "available",
            "eta_days": 4.9,
            "normal_eta_days": 4.9,
            "shipments_in_transit": 0,
            "cost_per_pallet": 310,
        },
        "KHI-ISB-001": {
            "name": "Karachi → Islamabad",
            "origin": "karachi_port",
            "destination": "islamabad_dc",
            "status": "disrupted",
            "eta_days": 8.0,
            "normal_eta_days": 3.2,
            "shipments_in_transit": 230,
            "cost_per_pallet": 275,
        },
    },
    "pricing": {
        "lahore": {
            "base_delivery_fee": 250,
            "multiplier": 1.0,
            "surge_active": False,
        },
        "islamabad": {
            "base_delivery_fee": 275,
            "multiplier": 1.0,
            "surge_active": False,
        },
        "karachi": {
            "base_delivery_fee": 180,
            "multiplier": 1.0,
            "surge_active": False,
        },
    },
    "notifications": [],
    "safety_stock_activated": False,
    "penalty_exposure_usd": 320000,
    "holding_cost_usd": 180000,
}

# Live mutable state
_state: dict = copy.deepcopy(_initial_state)


def snapshot() -> dict:
    """Return a deep copy of current state."""
    with _lock:
        return copy.deepcopy(_state)


def reset():
    """Reset to initial state (used in tests / demo resets)."""
    global _state
    with _lock:
        _state = copy.deepcopy(_initial_state)


# ── Inventory ─────────────────────────────────────────────────────────────────

def get_inventory(dc: str | None = None) -> dict:
    with _lock:
        if dc:
            return copy.deepcopy(_state["inventory"].get(dc, {}))
        return copy.deepcopy(_state["inventory"])


def adjust_inventory(dc: str, sku: str, delta: int) -> dict:
    with _lock:
        current = _state["inventory"].get(dc, {}).get(sku, {}).get("quantity", 0)
        _state["inventory"][dc][sku]["quantity"] = max(0, current + delta)
        return copy.deepcopy(_state["inventory"][dc][sku])


# ── Routes ────────────────────────────────────────────────────────────────────

def get_routes() -> dict:
    with _lock:
        return copy.deepcopy(_state["routes"])


def reroute(route_id: str, new_route_id: str, shipment_count: int) -> dict:
    with _lock:
        if route_id not in _state["routes"] or new_route_id not in _state["routes"]:
            raise KeyError(f"Route {route_id} or {new_route_id} not found")
        old_route = _state["routes"][route_id]
        new_route = _state["routes"][new_route_id]
        transfer = min(shipment_count, old_route["shipments_in_transit"])
        old_route["shipments_in_transit"] -= transfer
        new_route["shipments_in_transit"] += transfer
        # Recalculate penalty
        _state["penalty_exposure_usd"] = max(
            0, _state["penalty_exposure_usd"] - int(transfer * 330)
        )
        return {
            "transferred_shipments": transfer,
            "from_route": copy.deepcopy(old_route),
            "to_route": copy.deepcopy(new_route),
            "new_penalty_exposure_usd": _state["penalty_exposure_usd"],
        }


# ── Pricing ───────────────────────────────────────────────────────────────────

def get_pricing() -> dict:
    with _lock:
        return copy.deepcopy(_state["pricing"])


def update_pricing(region: str, multiplier: float) -> dict:
    with _lock:
        if region not in _state["pricing"]:
            raise KeyError(f"Region {region} not found")
        _state["pricing"][region]["multiplier"] = multiplier
        _state["pricing"][region]["surge_active"] = multiplier > 1.0
        _state["pricing"][region]["effective_fee"] = round(
            _state["pricing"][region]["base_delivery_fee"] * multiplier, 2
        )
        return copy.deepcopy(_state["pricing"][region])


# ── Notifications ─────────────────────────────────────────────────────────────

def get_notifications() -> list:
    with _lock:
        return copy.deepcopy(_state["notifications"])


def add_notification(notif: dict) -> dict:
    with _lock:
        _state["notifications"].append(notif)
        return notif


# ── Safety Stock ──────────────────────────────────────────────────────────────

def activate_safety_stock(dc: str) -> dict:
    with _lock:
        _state["safety_stock_activated"] = True
        # Add buffer inventory
        for sku in _state["inventory"].get(dc, {}):
            _state["inventory"][dc][sku]["quantity"] += 150
            _state["inventory"][dc][sku]["safety_stock_active"] = True
        # Reduce holding cost as risk is mitigated
        _state["holding_cost_usd"] = int(_state["holding_cost_usd"] * 0.6)
        return {
            "dc": dc,
            "safety_stock_activated": True,
            "new_holding_cost_usd": _state["holding_cost_usd"],
        }


def get_exposure() -> dict:
    with _lock:
        return {
            "penalty_exposure_usd": _state["penalty_exposure_usd"],
            "holding_cost_usd": _state["holding_cost_usd"],
        }


def restore(raw: dict) -> None:
    """Restore state from a previously captured snapshot dict (rollback support)."""
    global _state
    with _lock:
        _state = copy.deepcopy(raw)

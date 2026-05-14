"""Mock Inventory API — simulates a warehouse management system."""
import asyncio
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import state

router = APIRouter(prefix="/mock/inventory", tags=["mock-inventory"])


class AdjustRequest(BaseModel):
    dc: str
    sku: str
    delta: int  # positive = add, negative = remove


@router.get("/")
async def list_inventory(dc: str | None = None):
    """Get current inventory levels for all or a specific DC."""
    await asyncio.sleep(0.05)  # simulate network latency
    return {
        "timestamp": int(time.time()),
        "inventory": state.get_inventory(dc),
    }


@router.post("/adjust")
async def adjust_inventory(req: AdjustRequest):
    """Adjust inventory level for a specific SKU at a DC."""
    await asyncio.sleep(0.08)
    try:
        updated = state.adjust_inventory(req.dc, req.sku, req.delta)
        return {
            "success": True,
            "dc": req.dc,
            "sku": req.sku,
            "updated": updated,
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/safety-stock/activate")
async def activate_safety_stock(dc: str):
    """Activate safety stock protocol for a distribution center."""
    await asyncio.sleep(0.12)
    result = state.activate_safety_stock(dc)
    return {"success": True, **result}


@router.get("/exposure")
async def get_exposure():
    """Get current financial exposure (penalty + holding costs)."""
    await asyncio.sleep(0.03)
    return state.get_exposure()

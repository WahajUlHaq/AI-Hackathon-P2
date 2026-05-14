"""Mock Pricing API — simulates a dynamic pricing / ERP system."""
import asyncio
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import state

router = APIRouter(prefix="/mock/pricing", tags=["mock-pricing"])


class UpdatePricingRequest(BaseModel):
    region: str
    multiplier: float  # e.g. 1.25 means 25% surcharge


@router.get("/")
async def get_pricing():
    """Get current pricing table for all regions."""
    await asyncio.sleep(0.04)
    return {
        "timestamp": int(time.time()),
        "pricing": state.get_pricing(),
    }


@router.post("/update")
async def update_pricing(req: UpdatePricingRequest):
    """
    Apply a pricing multiplier to a region (surge pricing).
    Returns the updated pricing row including effective_fee.
    """
    await asyncio.sleep(0.09)
    if req.multiplier <= 0 or req.multiplier > 5:
        raise HTTPException(status_code=422, detail="Multiplier must be between 0 and 5")
    try:
        updated = state.update_pricing(req.region, req.multiplier)
        return {
            "success": True,
            "timestamp": int(time.time()),
            "region": req.region,
            "pricing": updated,
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

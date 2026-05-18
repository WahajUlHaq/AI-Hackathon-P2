"""Mock Routing API — simulates a transport management system."""
import asyncio
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import state

router = APIRouter(prefix="/mock/routing", tags=["mock-routing"])


class RerouteRequest(BaseModel):
    from_route_id: str
    to_route_id: str
    shipment_count: int


@router.get("/routes")
async def list_routes():
    """Get all active routes and their current status."""
    await asyncio.sleep(0.05)
    return {
        "timestamp": int(time.time()),
        "routes": state.get_routes(),
    }


@router.post("/reroute")
async def reroute(req: RerouteRequest):
    """
    Reroute shipments from a disrupted route to an alternate route.
    Idempotent: calling twice with the same count won't over-transfer
    since shipment_count is capped to available inventory.
    """
    await asyncio.sleep(0.15)  # simulate TMS call latency
    try:
        result = state.reroute(req.from_route_id, req.to_route_id, req.shipment_count)
        return {
            "success": True,
            "timestamp": int(time.time()),
            **result,
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

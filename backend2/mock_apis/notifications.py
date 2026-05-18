"""Mock Notifications API — simulates SMS / email / push dispatch."""
import asyncio
import time
import uuid
from fastapi import APIRouter
from pydantic import BaseModel
import state

router = APIRouter(prefix="/mock/notifications", tags=["mock-notifications"])


class NotificationRequest(BaseModel):
    notification_type: str          # "sms" | "email" | "push" | "internal"
    recipients: list[str]           # phone numbers, emails, or user IDs
    subject: str
    body: str
    priority: str = "normal"        # "low" | "normal" | "high" | "critical"


class NotificationResponse(BaseModel):
    notification_id: str
    timestamp: int
    delivered_count: int
    failed_count: int
    preview: dict


@router.get("/")
async def list_notifications():
    """Get all dispatched notifications (audit log)."""
    await asyncio.sleep(0.03)
    return {
        "total": len(state.get_notifications()),
        "notifications": state.get_notifications(),
    }


@router.post("/send", response_model=NotificationResponse)
async def send_notification(req: NotificationRequest):
    """
    Simulate dispatching a notification.
    Returns delivery receipt with preview.
    """
    await asyncio.sleep(0.20)  # simulate gateway latency
    notif_id = str(uuid.uuid4())[:8].upper()
    notif = {
        "id": notif_id,
        "type": req.notification_type,
        "subject": req.subject,
        "body": req.body,
        "recipients_count": len(req.recipients),
        "priority": req.priority,
        "status": "delivered",
        "timestamp": int(time.time()),
    }
    state.add_notification(notif)
    return NotificationResponse(
        notification_id=notif_id,
        timestamp=notif["timestamp"],
        delivered_count=len(req.recipients),
        failed_count=0,
        preview={
            "subject": req.subject,
            "body_excerpt": req.body[:120] + ("..." if len(req.body) > 120 else ""),
            "channel": req.notification_type,
        },
    )

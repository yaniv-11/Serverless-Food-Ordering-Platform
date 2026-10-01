import hashlib
import hmac
import json
import os
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    """Receives Stripe webhook events. Never trusts the frontend's claim that
    a payment succeeded - this signed, server-to-server call from Stripe is
    the only source of truth an order's status is updated from. Point the
    Stripe CLI at this locally: `stripe listen --forward-to localhost:8000/webhooks/stripe`."""
    raw_body = (await request.body()).decode("utf-8")

    if not _verify_signature(raw_body, stripe_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    stripe_event = json.loads(raw_body)
    event_type = stripe_event.get("type")
    payment_intent_id = stripe_event.get("data", {}).get("object", {}).get("id")

    if event_type == "payment_intent.succeeded":
        _update_order_status(db, payment_intent_id, "paid")
    elif event_type == "payment_intent.payment_failed":
        _update_order_status(db, payment_intent_id, "payment_failed")

    # Any other event type is simply not one we act on - still 200, so
    # Stripe doesn't retry delivering an event we deliberately ignore.
    return {"received": True}


def _verify_signature(raw_body: str, signature_header: str) -> bool:
    try:
        parts = dict(p.split("=", 1) for p in signature_header.split(","))
        timestamp = parts["t"]
        signature = parts["v1"]
    except (KeyError, ValueError):
        return False

    # Reject old signatures - stops a captured request from being replayed
    # later to forge a fake "payment succeeded" event.
    if abs(time.time() - int(timestamp)) > 300:
        return False

    signed_payload = f"{timestamp}.{raw_body}"
    expected_signature = hmac.new(
        STRIPE_WEBHOOK_SECRET.encode(), signed_payload.encode(), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


def _update_order_status(db: Session, payment_intent_id, status):
    if not payment_intent_id:
        return

    order = (
        db.query(models.Order)
        .filter(models.Order.payment_intent_id == payment_intent_id)
        .first()
    )
    if not order:
        print(f"No order found for payment_intent_id={payment_intent_id}")
        return

    order.status = status
    db.commit()
    print(f"Order {order.id} -> {status}")

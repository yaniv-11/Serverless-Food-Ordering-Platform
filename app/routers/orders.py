import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..cache import idempotency_cache
from ..database import get_db
from ..deps import get_current_user, get_current_user_id

router = APIRouter(prefix="/orders", tags=["orders"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
IDEMPOTENCY_TTL_SECONDS = 86400  # 24h, same window orders-api uses


@router.post("", response_model=schemas.OrderOut)
@router.post("/", response_model=schemas.OrderOut, include_in_schema=False)
def create_order(
    payload: schemas.OrderCreateIn,
    user_id: str = Depends(get_current_user_id),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    if not idempotency_key:
        # No key sent - proceed unprotected, same as the Lambda.
        return _create_order_core(payload, user_id, db)

    # Scoped per-user, same as orders-api's redis_key.
    cache_key = f"idempotency:{user_id}:{idempotency_key}"

    if idempotency_cache.set_nx(cache_key, "processing", IDEMPOTENCY_TTL_SECONDS):
        try:
            result = _create_order_core(payload, user_id, db)
        except Exception:
            # Don't leave a retry stuck behind a "processing" claim just
            # because this attempt failed - release it for a clean retry.
            idempotency_cache.delete(cache_key)
            raise
        idempotency_cache.set(cache_key, json.dumps(result), IDEMPOTENCY_TTL_SECONDS)
        return result

    # Another request already holds (or has completed) this key.
    cached = idempotency_cache.get(cache_key)
    if cached is None or cached == "processing":
        raise HTTPException(
            status_code=409,
            detail="A request with this idempotency key is already in progress, please retry shortly",
        )
    # cached is the exact response from the original successful request -
    # including the same PaymentIntent client_secret.
    return json.loads(cached)


def _create_order_core(payload: schemas.OrderCreateIn, user_id: str, db: Session) -> dict:
    if not payload.restaurant_id or not payload.items:
        raise HTTPException(status_code=400, detail="restaurant_id and items are required")

    restaurant = db.get(models.Restaurant, payload.restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=400, detail="Invalid restaurant_id")

    order_items = []
    total_amount = Decimal("0")
    for item in payload.items:
        menu_item = db.get(models.MenuItem, item.menu_item_id)
        if not menu_item or menu_item.restaurant_id != payload.restaurant_id:
            raise HTTPException(status_code=400, detail=f"Invalid menu_item_id: {item.menu_item_id}")

        price = Decimal(str(menu_item.price))
        quantity = int(item.quantity)
        total_amount += price * quantity
        order_items.append(
            {"menu_item_id": item.menu_item_id, "name": menu_item.name, "quantity": quantity, "price": price}
        )

    created_at = datetime.now(timezone.utc).isoformat()
    order_id = f"{created_at}#{uuid.uuid4().hex[:8]}"

    try:
        payment_intent = _create_payment_intent(total_amount, order_id)
    except Exception as e:
        print(f"Stripe PaymentIntent creation failed: {e}")
        raise HTTPException(status_code=502, detail="Could not initiate payment, please try again")

    order = models.Order(
        id=order_id,
        user_id=user_id,
        restaurant_id=payload.restaurant_id,
        restaurant_name=restaurant.name,
        status="pending_payment",
        total_amount=float(total_amount),
        created_at=created_at,
        payment_intent_id=payment_intent["id"],
    )
    db.add(order)
    db.flush()
    for oi in order_items:
        db.add(
            models.OrderItem(
                order_id=order_id,
                menu_item_id=oi["menu_item_id"],
                name=oi["name"],
                quantity=oi["quantity"],
                price=float(oi["price"]),
            )
        )
    db.commit()
    db.refresh(order)

    result = _format_order(order)
    # client_secret is only needed once, right now, for the frontend to
    # confirm the card payment - never stored, never returned on later GETs.
    result["client_secret"] = payment_intent["client_secret"]
    return result


def _create_payment_intent(amount: Decimal, order_id: str):
    if not stripe.api_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured - set it in backend/.env")

    amount_in_paise = int(amount * 100)
    return stripe.PaymentIntent.create(
        amount=amount_in_paise,
        currency="inr",
        payment_method_types=["card"],
        metadata={"order_id": order_id},
    )


@router.get("/user/{user_id}", response_model=List[schemas.OrderOut])
def list_user_orders(
    user_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user_id != current_user.email and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Cannot view another user's orders")

    orders = (
        db.query(models.Order)
        .filter(models.Order.user_id == user_id)
        .order_by(models.Order.created_at.desc())
        .all()
    )
    return [_format_order(o) for o in orders]


@router.get("/restaurant/{restaurant_id}", response_model=List[schemas.OrderOut])
def list_restaurant_orders(
    restaurant_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """New for RBAC - a restaurant_owner viewing orders placed at their own
    restaurant. No AWS equivalent: orders-api only ever supports the
    per-consumer lookup above, since that backend has no owner role."""
    restaurant = db.get(models.Restaurant, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if current_user.role != "admin" and restaurant.owner_id != current_user.email:
        raise HTTPException(status_code=403, detail="You do not own this restaurant")

    orders = (
        db.query(models.Order)
        .filter(models.Order.restaurant_id == restaurant_id)
        .order_by(models.Order.created_at.desc())
        .all()
    )
    return [_format_order(o) for o in orders]


@router.post("/{order_id}/cancel", response_model=schemas.OrderOut)
def cancel_order(
    order_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """No delete endpoint exists, and won't - by the time an Order row
    exists, a Stripe PaymentIntent already exists for it, and the webhook
    looks orders up BY payment_intent_id whenever Stripe calls back. Deleting
    the row would leave a live/paid PaymentIntent with nothing to reconcile
    it against. Cancelling is a state transition backed by the matching
    Stripe action instead - the row, and the audit trail, always survive."""
    order = db.get(models.Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    is_placer = order.user_id == current_user.email
    is_admin = current_user.role == "admin"
    is_restaurant_owner = False
    if not (is_placer or is_admin) and current_user.role == "restaurant_owner":
        restaurant = db.get(models.Restaurant, order.restaurant_id)
        is_restaurant_owner = bool(restaurant and restaurant.owner_id == current_user.email)

    if not (is_placer or is_admin or is_restaurant_owner):
        raise HTTPException(status_code=403, detail="You cannot cancel this order")

    if order.status == "pending_payment":
        try:
            stripe.PaymentIntent.cancel(order.payment_intent_id)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Could not cancel payment: {e}")
        order.status = "cancelled"
    elif order.status == "paid":
        try:
            stripe.Refund.create(payment_intent=order.payment_intent_id)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Could not refund payment: {e}")
        order.status = "refunded"
    else:
        raise HTTPException(
            status_code=400, detail=f"Order cannot be cancelled from status '{order.status}'"
        )

    db.commit()
    db.refresh(order)
    return _format_order(order)


def _format_order(order: models.Order) -> dict:
    return {
        "id": order.id,
        "user_id": order.user_id,
        "restaurant_id": order.restaurant_id,
        "status": order.status,
        "total_amount": float(order.total_amount),
        "created_at": order.created_at,
        "restaurant": {"id": order.restaurant_id, "name": order.restaurant_name},
        "items": [
            {
                "id": item.menu_item_id,
                "menu_item_id": item.menu_item_id,
                "quantity": int(item.quantity),
                "price": float(item.price),
                "menu_item": {"name": item.name},
            }
            for item in order.items
        ],
    }

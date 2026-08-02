from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", response_model=schemas.OrderOut)
def create_order(payload: schemas.OrderCreate, db: Session = Depends(get_db)):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    menu_item_ids = [item.menu_item_id for item in payload.items]
    menu_items = (
        db.query(models.MenuItem).filter(models.MenuItem.id.in_(menu_item_ids)).all()
    )
    menu_item_map = {item.id: item for item in menu_items}

    if len(menu_item_map) != len(set(menu_item_ids)):
        raise HTTPException(status_code=400, detail="One or more menu items are invalid")

    order = models.Order(
        user_id=payload.user_id, restaurant_id=payload.restaurant_id, status="placed"
    )
    db.add(order)
    db.flush()  # assigns order.id before we attach order items

    total = 0.0
    for item in payload.items:
        menu_item = menu_item_map[item.menu_item_id]
        total += menu_item.price * item.quantity
        db.add(
            models.OrderItem(
                order_id=order.id,
                menu_item_id=item.menu_item_id,
                quantity=item.quantity,
                price=menu_item.price,
            )
        )

    order.total_amount = total
    db.commit()
    db.refresh(order)
    return order


@router.get("/user/{user_id}", response_model=List[schemas.OrderOut])
def get_user_orders(user_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Order)
        .filter(models.Order.user_id == user_id)
        .order_by(models.Order.created_at.desc())
        .all()
    )


@router.get("/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

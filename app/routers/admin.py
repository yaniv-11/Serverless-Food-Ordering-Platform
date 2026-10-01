from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_roles
from .orders import _format_order

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_roles("admin"))])


@router.get("/users", response_model=List[schemas.UserOut])
def list_users(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    return [_format_user(u) for u in users]


@router.patch("/users/{email}/role", response_model=schemas.UserOut)
def update_user_role(email: str, payload: schemas.RoleUpdateIn, db: Session = Depends(get_db)):
    user = db.get(models.User, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = payload.role
    db.commit()
    db.refresh(user)
    return _format_user(user)


@router.get("/orders", response_model=List[schemas.OrderOut])
def list_all_orders(db: Session = Depends(get_db)):
    """Unscoped order view - no per-user or per-restaurant equivalent exists
    anywhere else in this app, deliberately: everywhere else, "which orders
    can I see" is always tied to being the person who placed it or the owner
    of the restaurant it was placed at. This route is the one place that
    isn't true, which is exactly why it's admin-only."""
    orders = db.query(models.Order).order_by(models.Order.created_at.desc()).all()
    return [_format_order(o) for o in orders]


def _format_user(u: models.User) -> dict:
    return {"id": u.email, "name": u.name, "email": u.email, "role": u.role}

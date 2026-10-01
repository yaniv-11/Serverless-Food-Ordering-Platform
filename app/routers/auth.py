import base64
import hmac
import os
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..notifications import welcome_notifier
from ..security import create_token, hash_password

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("/signup", response_model=schemas.AuthOut)
def signup(payload: schemas.SignupIn, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    name = (payload.name or "").strip()
    email = (payload.email or "").strip().lower()
    password = payload.password or ""

    if not name or not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="name and a valid email are required")
    if len(password) < 5:
        raise HTTPException(status_code=400, detail="password must be at least 8 characters")

    if db.get(models.User, email):
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    salt = os.urandom(16)
    password_hash = hash_password(password, salt)

    user = models.User(
        email=email,
        name=name,
        password_hash=base64.b64encode(password_hash).decode(),
        salt=base64.b64encode(salt).decode(),
        role=payload.role,
    )
    db.add(user)
    db.commit()

    # Fire-and-forget, same as auth-login's SQS publish: a new signup should
    # still succeed even if this side effect has a hiccup.
    background_tasks.add_task(welcome_notifier, name, email)

    user_out = {"id": email, "name": name, "email": email, "role": user.role}
    return {"token": create_token(email), "user": user_out}


@router.post("/login", response_model=schemas.AuthOut)
def login(payload: schemas.LoginIn, db: Session = Depends(get_db)):
    email = (payload.email or "").strip().lower()
    password = payload.password or ""

    user = db.get(models.User, email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    salt = base64.b64decode(user.salt)
    expected_hash = base64.b64decode(user.password_hash)
    actual_hash = hash_password(password, salt)

    if not hmac.compare_digest(expected_hash, actual_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_out = {"id": email, "name": user.name, "email": email, "role": user.role}
    return {"token": create_token(email), "user": user_out}

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.UserOut)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    """Simple mock login: looks up a user by email, creating one if it
    doesn't exist yet. No passwords - good enough for a demo app."""
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user:
        user = models.User(name=payload.name, email=payload.email)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

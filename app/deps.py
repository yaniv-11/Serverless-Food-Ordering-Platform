from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from . import models
from .database import get_db
from .security import verify_token


def get_current_user_id(authorization: str = Header(default=None)) -> str:
    """FastAPI equivalent of the jwt-authorizer Lambda: verifies the Bearer
    token and returns the caller's verified identity (email). Used by any
    route that previously relied on API Gateway's authorizer context -
    never trust a client-supplied user_id instead of this."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization[len("Bearer "):]
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return user_id


def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> models.User:
    """Like get_current_user_id, but looks the user row up fresh so .role
    reflects its current value rather than whatever it was when the token
    was issued (tokens live up to an hour) - a role change from an admin
    should take effect on the next request, not the next login. The AWS
    backend has no roles, so there's nothing to mirror here; this exists
    purely for the local RBAC layer."""
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


def require_roles(*roles: str):
    """Dependency factory: 403s unless the caller's role is one of `roles`.
    Role membership alone doesn't imply resource ownership - e.g. any
    restaurant_owner passes require_roles("restaurant_owner") here, but must
    still be checked against the specific restaurant's owner_id afterward.
    See _assert_can_manage in routers/restaurants.py for that second check.
    """

    def dependency(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency

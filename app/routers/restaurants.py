import json
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..cache import restaurant_cache
from ..database import get_db
from ..deps import get_current_user, require_roles

router = APIRouter(prefix="/restaurants", tags=["restaurants"])

CACHE_TTL_SECONDS = 60  # same TTL restaurants-api uses for its Upstash cache


@router.get("", response_model=List[schemas.RestaurantOut])
@router.get("/", response_model=List[schemas.RestaurantOut], include_in_schema=False)
def list_restaurants(db: Session = Depends(get_db)):
    cache_key = "restaurants:all"
    cached = restaurant_cache.get(cache_key)
    if cached is not None:
        return json.loads(cached)

    restaurants = db.query(models.Restaurant).all()
    result = [_format_restaurant(r) for r in restaurants]
    restaurant_cache.set(cache_key, json.dumps(result), CACHE_TTL_SECONDS)
    return result


@router.get("/{restaurant_id}", response_model=schemas.RestaurantDetailOut)
def get_restaurant(restaurant_id: str, db: Session = Depends(get_db)):
    cache_key = f"restaurant:{restaurant_id}"
    cached = restaurant_cache.get(cache_key)
    if cached is not None:
        return json.loads(cached)

    restaurant = db.get(models.Restaurant, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    result = _format_restaurant(restaurant)
    result["menu_items"] = [_format_menu_item(m) for m in restaurant.menu_items]
    restaurant_cache.set(cache_key, json.dumps(result), CACHE_TTL_SECONDS)
    return result


@router.post("", response_model=schemas.RestaurantOut, status_code=201)
def create_restaurant(
    payload: schemas.RestaurantCreateIn,
    user: models.User = Depends(require_roles("restaurant_owner", "admin")),
    db: Session = Depends(get_db),
):
    restaurant = models.Restaurant(
        id=uuid.uuid4().hex,
        name=payload.name,
        cuisine=payload.cuisine,
        rating=payload.rating or 0,
        image_url=payload.image_url,
        address=payload.address,
        owner_id=user.email,
    )
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)
    _invalidate_cache()
    return _format_restaurant(restaurant)


@router.put("/{restaurant_id}", response_model=schemas.RestaurantOut)
def update_restaurant(
    restaurant_id: str,
    payload: schemas.RestaurantUpdateIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    restaurant = db.get(models.Restaurant, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    _assert_can_manage(restaurant, user)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(restaurant, field, value)
    db.commit()
    db.refresh(restaurant)
    _invalidate_cache(restaurant_id)
    return _format_restaurant(restaurant)


@router.delete("/{restaurant_id}", status_code=204)
def delete_restaurant(
    restaurant_id: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    restaurant = db.get(models.Restaurant, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    _assert_can_manage(restaurant, user)

    db.delete(restaurant)  # cascades to menu_items
    db.commit()
    _invalidate_cache(restaurant_id)


@router.post("/{restaurant_id}/menu-items", response_model=schemas.MenuItemOut, status_code=201)
def create_menu_item(
    restaurant_id: str,
    payload: schemas.MenuItemCreateIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    restaurant = db.get(models.Restaurant, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    _assert_can_manage(restaurant, user)

    menu_item = models.MenuItem(id=uuid.uuid4().hex, restaurant_id=restaurant_id, **payload.model_dump())
    db.add(menu_item)
    db.commit()
    db.refresh(menu_item)
    _invalidate_cache(restaurant_id)
    return _format_menu_item(menu_item)


@router.put("/{restaurant_id}/menu-items/{menu_item_id}", response_model=schemas.MenuItemOut)
def update_menu_item(
    restaurant_id: str,
    menu_item_id: str,
    payload: schemas.MenuItemUpdateIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    restaurant = db.get(models.Restaurant, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    _assert_can_manage(restaurant, user)

    menu_item = db.get(models.MenuItem, menu_item_id)
    if not menu_item or menu_item.restaurant_id != restaurant_id:
        raise HTTPException(status_code=404, detail="Menu item not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(menu_item, field, value)
    db.commit()
    db.refresh(menu_item)
    _invalidate_cache(restaurant_id)
    return _format_menu_item(menu_item)


@router.delete("/{restaurant_id}/menu-items/{menu_item_id}", status_code=204)
def delete_menu_item(
    restaurant_id: str,
    menu_item_id: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    restaurant = db.get(models.Restaurant, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    _assert_can_manage(restaurant, user)

    menu_item = db.get(models.MenuItem, menu_item_id)
    if not menu_item or menu_item.restaurant_id != restaurant_id:
        raise HTTPException(status_code=404, detail="Menu item not found")

    db.delete(menu_item)
    db.commit()
    _invalidate_cache(restaurant_id)


def _assert_can_manage(restaurant: models.Restaurant, user: models.User) -> None:
    """Role membership (checked by require_roles at signup/creation time)
    isn't enough on its own here - an owner may only manage restaurants they
    actually own. Admins bypass ownership entirely."""
    if user.role == "admin":
        return
    if restaurant.owner_id != user.email:
        raise HTTPException(status_code=403, detail="You do not own this restaurant")


def _invalidate_cache(restaurant_id: str = None) -> None:
    restaurant_cache.delete("restaurants:all")
    if restaurant_id:
        restaurant_cache.delete(f"restaurant:{restaurant_id}")


def _format_restaurant(r: models.Restaurant) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "cuisine": r.cuisine,
        "rating": float(r.rating),
        "image_url": r.image_url,
        "address": r.address,
        "owner_id": r.owner_id,
    }


def _format_menu_item(m: models.MenuItem) -> dict:
    return {
        "id": m.id,
        "restaurant_id": m.restaurant_id,
        "name": m.name,
        "description": m.description,
        "price": float(m.price),
        "category": m.category,
        "is_veg": m.is_veg,
        "image_url": m.image_url,
    }

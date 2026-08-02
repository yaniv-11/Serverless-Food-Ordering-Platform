from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class MenuItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    category: Optional[str] = None
    is_veg: bool = True


class MenuItemOut(MenuItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restaurant_id: int


class RestaurantBase(BaseModel):
    name: str
    cuisine: Optional[str] = None
    rating: Optional[float] = 0
    image_url: Optional[str] = None
    address: Optional[str] = None


class RestaurantOut(RestaurantBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class RestaurantDetailOut(RestaurantOut):
    menu_items: List[MenuItemOut] = []


class UserLogin(BaseModel):
    name: str
    email: EmailStr


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str


class OrderItemIn(BaseModel):
    menu_item_id: int
    quantity: int = 1


class OrderCreate(BaseModel):
    user_id: int
    restaurant_id: int
    items: List[OrderItemIn]


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    menu_item_id: int
    quantity: int
    price: float
    menu_item: MenuItemOut


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    restaurant_id: int
    status: str
    total_amount: float
    created_at: datetime
    items: List[OrderItemOut] = []
    restaurant: RestaurantOut

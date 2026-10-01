from typing import List, Literal, Optional

from pydantic import BaseModel

Role = Literal["consumer", "restaurant_owner", "admin"]


class MenuItemOut(BaseModel):
    id: str
    restaurant_id: str
    name: str
    description: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    category: Optional[str] = None
    is_veg: bool = True


class MenuItemCreateIn(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    category: Optional[str] = None
    is_veg: bool = True


class MenuItemUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    category: Optional[str] = None
    is_veg: Optional[bool] = None


class RestaurantOut(BaseModel):
    id: str
    name: str
    cuisine: Optional[str] = None
    rating: Optional[float] = 0
    image_url: Optional[str] = None
    address: Optional[str] = None
    owner_id: Optional[str] = None


class RestaurantDetailOut(RestaurantOut):
    menu_items: List[MenuItemOut] = []


class RestaurantCreateIn(BaseModel):
    name: str
    cuisine: Optional[str] = None
    rating: Optional[float] = 0
    image_url: Optional[str] = None
    address: Optional[str] = None


class RestaurantUpdateIn(BaseModel):
    name: Optional[str] = None
    cuisine: Optional[str] = None
    rating: Optional[float] = None
    image_url: Optional[str] = None
    address: Optional[str] = None


class SignupIn(BaseModel):
    name: str
    email: str
    password: str
    # "admin" deliberately isn't an option here - it's never self-assignable
    # via public signup, only granted by an existing admin (see
    # PATCH /admin/users/{email}/role). Pydantic rejects any other value
    # with a 422 automatically, so there's no separate check needed for that.
    role: Literal["consumer", "restaurant_owner"] = "consumer"


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str  # email, matching the Lambda's {"id": email, ...} shape
    name: str
    email: str
    role: Role


class AuthOut(BaseModel):
    token: str
    user: UserOut


class RoleUpdateIn(BaseModel):
    role: Role


class OrderItemIn(BaseModel):
    menu_item_id: str
    quantity: int = 1


class OrderCreateIn(BaseModel):
    restaurant_id: str
    items: List[OrderItemIn]


class OrderItemOut(BaseModel):
    id: str  # menu_item_id, matching the Lambda's _format_order shape
    menu_item_id: str
    quantity: int
    price: float
    menu_item: dict  # {"name": ...}


class OrderRestaurantOut(BaseModel):
    id: str
    name: str


class OrderOut(BaseModel):
    id: str
    user_id: str
    restaurant_id: str
    status: str
    total_amount: float
    created_at: str
    restaurant: OrderRestaurantOut
    items: List[OrderItemOut] = []
    client_secret: Optional[str] = None

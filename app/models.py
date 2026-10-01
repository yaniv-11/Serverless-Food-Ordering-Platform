from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    """Mirrors the AWS `users` DynamoDB table: PK is the email itself."""

    __tablename__ = "users"

    email = Column(String(255), primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    password_hash = Column(String(255), nullable=False)  # base64-encoded PBKDF2 digest
    salt = Column(String(255), nullable=False)  # base64-encoded random salt
    # "consumer" | "restaurant_owner" | "admin" - no equivalent on the AWS
    # side (that backend has no roles at all); new for local RBAC.
    role = Column(String(30), nullable=False, default="consumer")


class Restaurant(Base):
    """Mirrors the `restaurants` DynamoDB table: PK is a string id."""

    __tablename__ = "restaurants"

    id = Column(String(50), primary_key=True)
    name = Column(String(150), nullable=False)
    cuisine = Column(String(150))
    rating = Column(Float, default=0)
    image_url = Column(String(500))
    address = Column(String(255))
    # Nullable: seeded/legacy restaurants have no owner and can only be
    # managed by an admin. A real FK (unlike Order.restaurant_id below) since
    # ownership needs to be enforceable, not just a point-in-time snapshot.
    owner_id = Column(String(255), ForeignKey("users.email"), nullable=True)

    menu_items = relationship(
        "MenuItem", back_populates="restaurant", cascade="all, delete-orphan"
    )


class MenuItem(Base):
    """Mirrors the `menu_items` DynamoDB table: PK restaurant_id, SK menu_item_id."""

    __tablename__ = "menu_items"

    id = Column(String(50), primary_key=True)  # matches Dynamo's menu_item_id
    restaurant_id = Column(String(50), ForeignKey("restaurants.id"), nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(String(500))
    price = Column(Float, nullable=False)
    image_url = Column(String(500))
    category = Column(String(100))
    is_veg = Column(Boolean, default=True)

    restaurant = relationship("Restaurant", back_populates="menu_items")


class Order(Base):
    """Mirrors the `orders` DynamoDB table: PK user_id (email), SK order_id.

    Item lines are stored as denormalized snapshots (name/price captured at
    order time), same as the Lambda - never re-joined against menu_items so a
    later price change can't retroactively alter a placed order's total.
    """

    __tablename__ = "orders"

    id = Column(String(80), primary_key=True)  # order_id: "{created_at}#{uuid8}"
    user_id = Column(String(255), ForeignKey("users.email"), nullable=False, index=True)
    restaurant_id = Column(String(50), nullable=False)
    restaurant_name = Column(String(150), nullable=False)
    # pending_payment -> paid | payment_failed (via Stripe webhook), or
    # pending_payment -> cancelled | paid -> refunded (via /orders/{id}/cancel).
    # Never deleted - see cancel_order for why.
    status = Column(String(50), default="pending_payment")
    total_amount = Column(Float, default=0)
    created_at = Column(String(50), nullable=False)  # ISO-8601, same format as the Lambda
    payment_intent_id = Column(String(100), index=True)

    items = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(80), ForeignKey("orders.id"), nullable=False)
    menu_item_id = Column(String(50), nullable=False)
    name = Column(String(150), nullable=False)
    quantity = Column(Integer, default=1)
    price = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")

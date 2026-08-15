import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from mcp.server.mcpserver import MCPServer

ORDERS_TABLE = os.environ["ORDERS_TABLE"]
RESTAURANTS_TABLE = os.environ["RESTAURANTS_TABLE"]
MENU_ITEMS_TABLE = os.environ["MENU_ITEMS_TABLE"]
AWS_REGION = ap-southeast-2

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
orders_table = dynamodb.Table(ORDERS_TABLE)
restaurants_table = dynamodb.Table(RESTAURANTS_TABLE)
menu_items_table = dynamodb.Table(MENU_ITEMS_TABLE)

mcp = MCPServer("foodie-mcp-server")


@mcp.tool()
def get_recent_orders(user_id: str, limit: int = 5) -> list[dict]:
    """Get a user's most recent orders: restaurant, items, total, status, and date."""
    response = orders_table.query(
        KeyConditionExpression=Key("user_id").eq(user_id),
        ScanIndexForward=False,
        Limit=limit,
    )
    return [
        {
            "order_id": o["order_id"],
            "restaurant": o["restaurant_name"],
            "status": o["status"],
            "total_amount": float(o["total_amount"]),
            "created_at": o["created_at"],
            "items": [{"name": i["name"], "quantity": int(i["quantity"])} for i in o["items"]],
        }
        for o in response["Items"]
    ]


@mcp.tool()
def get_spending_summary(user_id: str, days: int = 30) -> dict:
    """Get total amount spent and number of paid orders for a user over the last N days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    response = orders_table.query(
        KeyConditionExpression=Key("user_id").eq(user_id) & Key("order_id").gte(cutoff),
    )
    paid_orders = [o for o in response["Items"] if o["status"] == "paid"]
    return {
        "period_days": days,
        "paid_order_count": len(paid_orders),
        "total_spent": float(sum(Decimal(str(o["total_amount"])) for o in paid_orders)),
    }


@mcp.tool()
def get_top_rated_restaurants(cuisine: str = "", limit: int = 5) -> list[dict]:
    """Get the highest-rated restaurants, optionally filtered by cuisine."""
    items = restaurants_table.scan()["Items"]
    if cuisine:
        items = [r for r in items if cuisine.lower() in r["cuisine"].lower()]
    items.sort(key=lambda r: float(r["rating"]), reverse=True)
    return [
        {"id": r["id"], "name": r["name"], "cuisine": r["cuisine"], "rating": float(r["rating"])}
        for r in items[:limit]
    ]


@mcp.tool()
def get_restaurant_menu(restaurant_id: str) -> dict:
    """Get a restaurant's full menu, grouped by category."""
    restaurant = restaurants_table.get_item(Key={"id": restaurant_id}).get("Item")
    if not restaurant:
        raise ValueError(f"No restaurant found with id {restaurant_id}")

    menu_items = menu_items_table.query(
        KeyConditionExpression=Key("restaurant_id").eq(restaurant_id)
    )["Items"]

    return {
        "restaurant": restaurant["name"],
        "menu": [
            {"name": m["name"], "price": float(m["price"]), "category": m["category"], "is_veg": m["is_veg"]}
            for m in menu_items
        ],
    }


@mcp.tool()
def get_order_status(user_id: str, order_id: str) -> dict:
    """Check the current status of one specific order belonging to a user."""
    # GetItem requires the exact composite key - a caller who doesn't already
    # know both user_id AND order_id simply gets no match, so this can't be
    # used to probe another user's orders.
    order = orders_table.get_item(Key={"user_id": user_id, "order_id": order_id}).get("Item")
    if not order:
        raise ValueError("No matching order found for this user")
    return {"order_id": order["order_id"], "status": order["status"]}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)

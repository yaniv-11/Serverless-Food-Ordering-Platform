"""Local replica of the AWS mcp-server Lambda (also deployed standalone in
mcp-render-server/): a read-only MCP tool server over JSON-RPC 2.0, backed
by the same SQLite data everything else in this app uses instead of
DynamoDB. Note this is the tool server itself, not the Langflow/AI Central
agent the ChatWidget talks to - that's an external Aptean-hosted service
with no local equivalent; this endpoint exists so the tools it calls can be
exercised/tested locally with any MCP client.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal
from ..security import verify_token

router = APIRouter(tags=["mcp"])

MCP_PROTOCOL_VERSION = "2024-11-05"

# Tools that answer per-user questions verify the caller's JWT and use its
# subject as user_id, rather than accepting user_id as a client-supplied
# argument - same reasoning as orders-api never trusting a client body.
AUTHENTICATED_TOOLS = {"get_recent_orders", "get_spending_summary", "get_order_status"}

TOOLS = [
    {
        "name": "get_recent_orders",
        "description": "Get the authenticated caller's most recent orders: restaurant, items, total, status, and date.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max orders to return", "default": 5},
            },
        },
    },
    {
        "name": "get_spending_summary",
        "description": "Get the authenticated caller's total amount spent and number of paid orders over the last N days.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Look-back window in days", "default": 30},
            },
        },
    },
    {
        "name": "get_top_rated_restaurants",
        "description": "Get the highest-rated restaurants, optionally filtered by cuisine.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cuisine": {"type": "string", "description": "Optional cuisine substring filter, e.g. 'Italian'"},
                "limit": {"type": "integer", "default": 5},
            },
        },
    },
    {
        "name": "get_restaurant_menu",
        "description": "Get a restaurant's full menu, grouped by category.",
        "inputSchema": {
            "type": "object",
            "properties": {"restaurant_id": {"type": "string"}},
            "required": ["restaurant_id"],
        },
    },
    {
        "name": "get_order_status",
        "description": "Check the current status of one specific order belonging to the authenticated caller.",
        "inputSchema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
]


class Unauthorized(Exception):
    pass


def _authenticated_user_id(request: Request) -> str:
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise Unauthorized("Missing bearer token")
    token = auth_header[len("Bearer "):]

    user_id = verify_token(token)
    if not user_id:
        raise Unauthorized("Invalid or expired token")
    return user_id


@router.post("/mcp")
async def mcp_endpoint(request: Request):
    try:
        message = json.loads((await request.body()) or b"{}")
    except json.JSONDecodeError:
        return JSONResponse(_jsonrpc_error(None, -32700, "Parse error"), status_code=400)

    method = message.get("method")
    msg_id = message.get("id")  # absent/None => this is a notification

    if method == "initialize":
        return _jsonrpc_result(msg_id, {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "foodie-mcp-server-local", "version": "1.0.0"},
        })

    if method == "notifications/initialized":
        # A notification - no "id", no response body expected, just ack.
        return Response(status_code=202)

    if method == "tools/list":
        return _jsonrpc_result(msg_id, {"tools": TOOLS})

    if method == "tools/call":
        params = message.get("params") or {}
        return _call_tool(msg_id, params.get("name"), params.get("arguments") or {}, request)

    return _jsonrpc_error(msg_id, -32601, f"Method not found: {method}")


def _call_tool(msg_id, name: Optional[str], args: dict, request: Request):
    handlers = {
        "get_recent_orders": _get_recent_orders,
        "get_spending_summary": _get_spending_summary,
        "get_top_rated_restaurants": _get_top_rated_restaurants,
        "get_restaurant_menu": _get_restaurant_menu,
        "get_order_status": _get_order_status,
    }
    handler = handlers.get(name)
    if not handler:
        return _jsonrpc_error(msg_id, -32602, f"Unknown tool: {name}")

    db: Session = SessionLocal()
    try:
        if name in AUTHENTICATED_TOOLS:
            result_data = handler(args, db, _authenticated_user_id(request))
        else:
            result_data = handler(args, db)
    except Unauthorized as e:
        return _jsonrpc_result(msg_id, {
            "content": [{"type": "text", "text": f"Unauthorized: {e}"}],
            "isError": True,
        })
    except Exception as e:
        # Tool errors are reported IN the result (isError), not as a
        # JSON-RPC protocol error - the call itself succeeded, the tool's
        # own logic just failed.
        return _jsonrpc_result(msg_id, {
            "content": [{"type": "text", "text": f"Tool failed: {e}"}],
            "isError": True,
        })
    finally:
        db.close()

    return _jsonrpc_result(msg_id, {"content": [{"type": "text", "text": json.dumps(result_data)}]})


def _get_recent_orders(args, db, user_id):
    limit = int(args.get("limit", 5))
    orders = (
        db.query(models.Order)
        .filter(models.Order.user_id == user_id)
        .order_by(models.Order.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "order_id": o.id,
            "restaurant": o.restaurant_name,
            "status": o.status,
            "total_amount": float(o.total_amount),
            "created_at": o.created_at,
            "items": [{"name": i.name, "quantity": int(i.quantity)} for i in o.items],
        }
        for o in orders
    ]


def _get_spending_summary(args, db, user_id):
    days = int(args.get("days", 30))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    orders = (
        db.query(models.Order)
        .filter(models.Order.user_id == user_id, models.Order.created_at >= cutoff)
        .all()
    )
    paid_orders = [o for o in orders if o.status == "paid"]
    return {
        "period_days": days,
        "paid_order_count": len(paid_orders),
        "total_spent": float(sum(o.total_amount for o in paid_orders)),
    }


def _get_top_rated_restaurants(args, db):
    cuisine = (args.get("cuisine") or "").lower()
    limit = int(args.get("limit", 5))

    restaurants = db.query(models.Restaurant).all()
    if cuisine:
        restaurants = [r for r in restaurants if cuisine in (r.cuisine or "").lower()]
    restaurants.sort(key=lambda r: float(r.rating), reverse=True)

    return [
        {"id": r.id, "name": r.name, "cuisine": r.cuisine, "rating": float(r.rating)}
        for r in restaurants[:limit]
    ]


def _get_restaurant_menu(args, db):
    restaurant_id = args["restaurant_id"]
    restaurant = db.get(models.Restaurant, restaurant_id)
    if not restaurant:
        raise ValueError(f"No restaurant found with id {restaurant_id}")

    return {
        "restaurant": restaurant.name,
        "menu": [
            {"name": m.name, "price": float(m.price), "category": m.category, "is_veg": m.is_veg}
            for m in restaurant.menu_items
        ],
    }


def _get_order_status(args, db, user_id):
    order_id = args["order_id"]
    order = (
        db.query(models.Order)
        .filter(models.Order.id == order_id, models.Order.user_id == user_id)
        .first()
    )
    if not order:
        raise ValueError("No matching order found for this user")
    return {"order_id": order.id, "status": order.status}


def _jsonrpc_result(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _jsonrpc_error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}

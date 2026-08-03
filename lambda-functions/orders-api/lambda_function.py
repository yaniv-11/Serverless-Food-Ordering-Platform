import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

ORDERS_TABLE = os.environ["ORDERS_TABLE"]
MENU_ITEMS_TABLE = os.environ["MENU_ITEMS_TABLE"]
RESTAURANTS_TABLE = os.environ["RESTAURANTS_TABLE"]
STRIPE_SECRET_KEY = os.environ["STRIPE_SECRET_KEY"]

dynamodb = boto3.resource("dynamodb")
orders_table = dynamodb.Table(ORDERS_TABLE)
menu_items_table = dynamodb.Table(MENU_ITEMS_TABLE)
restaurants_table = dynamodb.Table(RESTAURANTS_TABLE)


def lambda_handler(event, context):
    # Set by the JWT authorizer once it's Allowed the request - this is the
    # cryptographically verified identity, never anything the client sent.
    authenticated_user_id = (event.get("requestContext", {}).get("authorizer") or {}).get("user_id")

    if event.get("httpMethod") == "POST":
        return create_order(event, authenticated_user_id)

    path_user_id = (event.get("pathParameters") or {}).get("user_id")
    if path_user_id:
        return list_user_orders(path_user_id, authenticated_user_id)

    return _response(404, {"detail": "Not found"})


def create_order(event, authenticated_user_id):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"detail": "Invalid JSON body"})

    user_id = authenticated_user_id
    restaurant_id = body.get("restaurant_id")
    items = body.get("items") or []

    if not user_id or not restaurant_id or not items:
        return _response(400, {"detail": "restaurant_id and items are required"})

    restaurant = restaurants_table.get_item(Key={"id": restaurant_id}).get("Item")
    if not restaurant:
        return _response(400, {"detail": "Invalid restaurant_id"})

    order_items = []
    total_amount = Decimal("0")
    for item in items:
        menu_item_id = item.get("menu_item_id")
        quantity = int(item.get("quantity", 1))
        menu_item = menu_items_table.get_item(
            Key={"restaurant_id": restaurant_id, "menu_item_id": menu_item_id}
        ).get("Item")
        if not menu_item:
            return _response(400, {"detail": f"Invalid menu_item_id: {menu_item_id}"})

        price = Decimal(str(menu_item["price"]))
        total_amount += price * quantity
        order_items.append({
            "menu_item_id": menu_item_id,
            "name": menu_item["name"],
            "quantity": quantity,
            "price": price,
        })

    created_at = datetime.now(timezone.utc).isoformat()
    order_id = f"{created_at}#{uuid.uuid4().hex[:8]}"

    try:
        payment_intent = _create_payment_intent(total_amount, order_id)
    except urllib.error.HTTPError as e:
        print(f"Stripe PaymentIntent creation failed: {e.read().decode()}")
        return _response(502, {"detail": "Could not initiate payment, please try again"})

    order = {
        "user_id": user_id,
        "order_id": order_id,
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant["name"],
        "status": "pending_payment",
        "total_amount": total_amount,
        "created_at": created_at,
        "items": order_items,
        "payment_intent_id": payment_intent["id"],
    }
    orders_table.put_item(Item=order)

    result = _format_order(order)
    # client_secret is only needed once, right now, for the frontend to
    # confirm the card payment - it's never stored and never returned again
    # on subsequent GETs.
    result["client_secret"] = payment_intent["client_secret"]
    return _response(200, result)


def _create_payment_intent(amount, order_id):
    amount_in_paise = int(amount * 100)
    data = urllib.parse.urlencode({
        "amount": amount_in_paise,
        "currency": "inr",
        "metadata[order_id]": order_id,
        "payment_method_types[]": "card",
    }).encode()

    req = urllib.request.Request(
        "https://api.stripe.com/v1/payment_intents",
        data=data,
        headers={
            "Authorization": f"Bearer {STRIPE_SECRET_KEY}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def list_user_orders(path_user_id, authenticated_user_id):
    if path_user_id != authenticated_user_id:
        return _response(403, {"detail": "Cannot view another user's orders"})

    response = orders_table.query(
        KeyConditionExpression=Key("user_id").eq(path_user_id),
        ScanIndexForward=False,
    )
    return _response(200, [_format_order(o) for o in response["Items"]])


def _format_order(order):
    return {
        "id": order["order_id"],
        "user_id": order["user_id"],
        "restaurant_id": order["restaurant_id"],
        "status": order["status"],
        "total_amount": float(order["total_amount"]),
        "created_at": order["created_at"],
        "restaurant": {"id": order["restaurant_id"], "name": order["restaurant_name"]},
        "items": [
            {
                "id": item["menu_item_id"],
                "menu_item_id": item["menu_item_id"],
                "quantity": int(item["quantity"]),
                "price": float(item["price"]),
                "menu_item": {"name": item["name"]},
            }
            for item in order["items"]
        ],
    }


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
        },
        "body": json.dumps(body),
    }

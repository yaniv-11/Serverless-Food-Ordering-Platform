import hashlib
import hmac
import json
import os
import time

import boto3
from boto3.dynamodb.conditions import Key

ORDERS_TABLE = os.environ["ORDERS_TABLE"]
STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

dynamodb = boto3.resource("dynamodb")
orders_table = dynamodb.Table(ORDERS_TABLE)


def lambda_handler(event, context):
    """Receives Stripe webhook events. Never trusts the frontend's claim that
    a payment succeeded - this signed, server-to-server call from Stripe is
    the only source of truth an order's status is updated from."""
    raw_body = event.get("body") or ""
    signature_header = (event.get("headers") or {}).get("Stripe-Signature", "")

    if not _verify_signature(raw_body, signature_header):
        return _response(400, {"detail": "Invalid signature"})

    stripe_event = json.loads(raw_body)
    event_type = stripe_event.get("type")
    payment_intent_id = stripe_event.get("data", {}).get("object", {}).get("id")

    if event_type == "payment_intent.succeeded":
        _update_order_status(payment_intent_id, "paid")
    elif event_type == "payment_intent.payment_failed":
        _update_order_status(payment_intent_id, "payment_failed")

    # Any other event type is simply not one we act on - still 200, so
    # Stripe doesn't retry delivering an event we deliberately ignore.
    return _response(200, {"received": True})


def _verify_signature(raw_body, signature_header):
    try:
        parts = dict(p.split("=", 1) for p in signature_header.split(","))
        timestamp = parts["t"]
        signature = parts["v1"]
    except (KeyError, ValueError):
        return False

    # Reject old signatures - stops a captured request from being replayed
    # later to forge a fake "payment succeeded" event.
    if abs(time.time() - int(timestamp)) > 300:
        return False

    signed_payload = f"{timestamp}.{raw_body}"
    expected_signature = hmac.new(
        STRIPE_WEBHOOK_SECRET.encode(), signed_payload.encode(), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


def _update_order_status(payment_intent_id, status):
    if not payment_intent_id:
        return

    response = orders_table.query(
        IndexName="payment_intent_id-index",
        KeyConditionExpression=Key("payment_intent_id").eq(payment_intent_id),
    )
    items = response.get("Items", [])
    if not items:
        print(f"No order found for payment_intent_id={payment_intent_id}")
        return

    order = items[0]
    orders_table.update_item(
        Key={"user_id": order["user_id"], "order_id": order["order_id"]},
        UpdateExpression="SET #s = :status",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":status": status},
    )
    print(f"Order {order['order_id']} -> {status}")


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }

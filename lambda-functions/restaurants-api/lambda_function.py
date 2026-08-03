import json
import os
import urllib.request

import boto3
from boto3.dynamodb.conditions import Key

RESTAURANTS_TABLE = os.environ["RESTAURANTS_TABLE"]
MENU_ITEMS_TABLE = os.environ["MENU_ITEMS_TABLE"]
UPSTASH_URL = os.environ["UPSTASH_REDIS_REST_URL"]
UPSTASH_TOKEN = os.environ["UPSTASH_REDIS_REST_TOKEN"]
CACHE_TTL_SECONDS = 60

dynamodb = boto3.resource("dynamodb")
restaurants_table = dynamodb.Table(RESTAURANTS_TABLE)
menu_items_table = dynamodb.Table(MENU_ITEMS_TABLE)


def lambda_handler(event, context):
    restaurant_id = (event.get("pathParameters") or {}).get("id")

    if restaurant_id:
        return get_restaurant_detail(restaurant_id)
    return list_restaurants()


def list_restaurants():
    cache_key = "restaurants:all"
    cached = cache_get(cache_key)
    if cached is not None:
        print(f"Cache HIT for {cache_key}")
        return _response(200, json.loads(cached))

    print(f"Cache MISS for {cache_key}")
    items = restaurants_table.scan()["Items"]
    result = [_format_restaurant(r) for r in items]
    cache_set(cache_key, json.dumps(result))
    return _response(200, result)


def get_restaurant_detail(restaurant_id):
    cache_key = f"restaurant:{restaurant_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        print(f"Cache HIT for {cache_key}")
        return _response(200, json.loads(cached))

    print(f"Cache MISS for {cache_key}")
    restaurant = restaurants_table.get_item(Key={"id": restaurant_id}).get("Item")
    if not restaurant:
        return _response(404, {"detail": "Restaurant not found"})

    menu_items = menu_items_table.query(
        KeyConditionExpression=Key("restaurant_id").eq(restaurant_id)
    )["Items"]

    result = _format_restaurant(restaurant)
    result["menu_items"] = [_format_menu_item(m) for m in menu_items]
    cache_set(cache_key, json.dumps(result))
    return _response(200, result)


def cache_get(key):
    """Returns the cached JSON string, or None on a cache miss / any cache
    failure - a broken cache should degrade to a normal DynamoDB read, never
    break the actual request."""
    try:
        req = urllib.request.Request(
            f"{UPSTASH_URL}/get/{key}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            return json.loads(resp.read()).get("result")
    except Exception as e:
        print(f"Cache read failed, falling back to DynamoDB: {e}")
        return None


def cache_set(key, value):
    """Fire-and-forget: a caching failure should never fail the request that
    triggered it, so any error here is just logged."""
    try:
        req = urllib.request.Request(
            f"{UPSTASH_URL}/set/{key}?EX={CACHE_TTL_SECONDS}",
            data=value.encode("utf-8"),
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception as e:
        print(f"Cache write failed (non-fatal): {e}")


def _format_restaurant(r):
    return {
        "id": r["id"],
        "name": r["name"],
        "cuisine": r["cuisine"],
        "rating": float(r["rating"]),
        "image_url": r["image_url"],
        "address": r["address"],
    }


def _format_menu_item(m):
    return {
        "id": m["menu_item_id"],
        "restaurant_id": m["restaurant_id"],
        "name": m["name"],
        "description": m["description"],
        "price": float(m["price"]),
        "category": m["category"],
        "is_veg": m["is_veg"],
        "image_url": m["image_url"],
    }


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "OPTIONS,GET",
        },
        "body": json.dumps(body),
    }

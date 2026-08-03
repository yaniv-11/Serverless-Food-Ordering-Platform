import base64
import hashlib
import hmac
import json
import os
import re
import time

import boto3

TABLE_NAME = os.environ["TABLE_NAME"]
NEW_USER_QUEUE_URL = os.environ["NEW_USER_QUEUE_URL"]
JWT_SECRET = os.environ["JWT_SECRET"]

TOKEN_TTL_SECONDS = 60 * 60  # access token good for 1 hour
PBKDF2_ITERATIONS = 600_000  # OWASP-recommended minimum for PBKDF2-HMAC-SHA256

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)
sqs = boto3.client("sqs")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def lambda_handler(event, context):
    """Routes to signup or login based on the path - same Lambda, two
    resources in API Gateway, same pattern as restaurants-api/orders-api
    branching on pathParameters/httpMethod."""
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"detail": "Invalid JSON body"})

    path = event.get("path", "")
    if path.endswith("/signup"):
        return signup(body)
    if path.endswith("/login"):
        return login(body)
    return _response(404, {"detail": "Not found"})


def signup(body):
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not name or not EMAIL_RE.match(email):
        return _response(400, {"detail": "name and a valid email are required"})
    if len(password) < 5:
        return _response(400, {"detail": "password must be at least 8 characters"})

    if table.get_item(Key={"email": email}).get("Item"):
        return _response(409, {"detail": "An account with this email already exists"})

    salt = os.urandom(16)
    password_hash = _hash_password(password, salt)

    table.put_item(Item={
        "email": email,
        "name": name,
        "password_hash": base64.b64encode(password_hash).decode(),
        "salt": base64.b64encode(salt).decode(),
    })

    new_user = {"id": email, "name": name, "email": email}

    # Fire-and-forget: a new signup should still succeed even if this
    # queue send has a transient hiccup, so we log rather than raise.
    try:
        sqs.send_message(QueueUrl=NEW_USER_QUEUE_URL, MessageBody=json.dumps(new_user))
    except Exception as e:
        print(f"Failed to queue new-user event: {e}")

    return _response(200, {"token": _create_token(email), "user": new_user})


def login(body):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    user = table.get_item(Key={"email": email}).get("Item")
    if not user or "password_hash" not in user:
        # Covers both "no such user" and legacy passwordless accounts from
        # before this change - either way, there's no password to check.
        return _response(401, {"detail": "Invalid email or password"})

    salt = base64.b64decode(user["salt"])
    expected_hash = base64.b64decode(user["password_hash"])
    actual_hash = _hash_password(password, salt)

    if not hmac.compare_digest(expected_hash, actual_hash):
        return _response(401, {"detail": "Invalid email or password"})

    user_out = {"id": email, "name": user["name"], "email": email}
    return _response(200, {"token": _create_token(email), "user": user_out})


def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)


def _b64url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _create_token(email):
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"sub": email, "iat": now, "exp": now + TOKEN_TTL_SECONDS}

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()

    signature = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "OPTIONS,POST",
        },
        "body": json.dumps(body),
    }

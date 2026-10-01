"""JWT and password hashing, byte-for-byte the same scheme as the AWS
auth-login/jwt-authorizer Lambdas: HS256 hand-rolled (no PyJWT dependency),
PBKDF2-HMAC-SHA256 with 600k iterations. Kept identical so a token minted
here has the same structure/semantics as one minted in production.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

JWT_SECRET = os.getenv("JWT_SECRET")
TOKEN_TTL_SECONDS = 60 * 60  # 1 hour, same as production
PBKDF2_ITERATIONS = 600_000


def hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(subject_email: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"sub": subject_email, "iat": now, "exp": now + TOKEN_TTL_SECONDS}

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()

    signature = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def verify_token(token: str) -> Optional[str]:
    """Returns the verified subject (email), or None if invalid/expired -
    same checks as jwt-authorizer's lambda_handler."""
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError:
        return None

    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected_signature = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()

    try:
        actual_signature = _b64url_decode(signature_b64)
    except Exception:
        return None

    if not hmac.compare_digest(expected_signature, actual_signature):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception:
        return None

    if payload.get("exp", 0) < time.time():
        return None

    return payload.get("sub")

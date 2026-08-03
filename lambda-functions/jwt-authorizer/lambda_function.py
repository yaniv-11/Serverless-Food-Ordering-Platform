import base64
import hashlib
import hmac
import json
import os
import time

JWT_SECRET = os.environ["JWT_SECRET"]


def lambda_handler(event, context):
    """API Gateway TOKEN authorizer. Verifies the JWT from Step 1 and, if
    valid, allows the request through with the verified user_id attached as
    authorizer context - which the downstream Lambda reads instead of
    trusting anything the client sent in the request body.

    Raising "Unauthorized" (not returning a Deny policy) is deliberate: API
    Gateway maps an authorizer exception with this exact message to a clean
    401, whereas a returned Deny policy produces a 403 - 401 is the correct
    signal here ("you're not authenticated"), not 403 ("you're authenticated
    but not allowed")."""
    token = _extract_token(event.get("authorizationToken"))
    if not token:
        raise Exception("Unauthorized")

    user_id = _verify_token(token)
    if not user_id:
        raise Exception("Unauthorized")

    return _allow_policy(user_id, event["methodArn"])


def _extract_token(auth_header):
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    return auth_header[len("Bearer "):]


def _verify_token(token):
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


def _b64url_decode(data):
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _allow_policy(user_id, method_arn):
    # arn:aws:execute-api:{region}:{account}:{api-id}/{stage}/{method}/{path}
    # Widen to {api-id}/{stage}/*/* so this one Allow decision is cached and
    # reused for every route, not just the exact method that was called.
    prefix, arn_suffix = method_arn.rsplit(":", 1)
    api_id, stage = arn_suffix.split("/")[0], arn_suffix.split("/")[1]
    wildcard_resource = f"{prefix}:{api_id}/{stage}/*/*"

    return {
        "principalId": user_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "execute-api:Invoke",
                "Effect": "Allow",
                "Resource": wildcard_resource,
            }],
        },
        "context": {"user_id": user_id},
    }

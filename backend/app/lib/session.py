import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.config import get_settings


COOKIE_NAME = "skillshelf_session"
STATE_COOKIE_NAME = "skillshelf_oauth_state"


def sign_payload(payload: dict[str, Any], max_age_seconds: int | None = None) -> str:
    body = dict(payload)
    body["iat"] = int(time.time())
    if max_age_seconds is not None:
        body["exp"] = body["iat"] + max_age_seconds
    return sign_static_payload(body)


def sign_static_payload(payload: dict[str, Any]) -> str:
    body = dict(payload)
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    data = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    sig = _signature(data)
    return f"{data}.{sig}"


def read_payload(value: str | None) -> dict[str, Any] | None:
    if not value or "." not in value:
        return None
    data, sig = value.rsplit(".", 1)
    if not hmac.compare_digest(sig, _signature(data)):
        return None
    try:
        padded = data + "=" * (-len(data) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except Exception:
        return None
    exp = payload.get("exp")
    if isinstance(exp, int) and exp < int(time.time()):
        return None
    return payload


def _signature(data: str) -> str:
    secret = get_settings().session_secret.encode()
    return hmac.new(secret, data.encode(), hashlib.sha256).hexdigest()

"""Telegram Mini App initData HMAC-SHA256 validation."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs, unquote


import os
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ALLOWED_USER_ID = 435926703
# Max age of initData in seconds (1 hour)
MAX_AGE = 3600


def validate_init_data(init_data: str) -> dict | None:
    """Validate Telegram Mini App initData.

    Returns parsed user dict if valid, None otherwise.
    """
    if not init_data:
        return None

    try:
        parsed = parse_qs(init_data, keep_blank_values=True)
    except Exception:
        return None

    # Extract hash
    received_hash = parsed.get("hash", [None])[0]
    if not received_hash:
        return None

    # Build check string: sorted key=value pairs excluding hash
    data_check_pairs = []
    for key, values in parsed.items():
        if key == "hash":
            continue
        data_check_pairs.append(f"{key}={values[0]}")
    data_check_pairs.sort()
    data_check_string = "\n".join(data_check_pairs)

    # HMAC-SHA256 validation
    secret_key = hmac.new(
        b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    # Check auth_date freshness
    auth_date_str = parsed.get("auth_date", [None])[0]
    if auth_date_str:
        try:
            auth_date = int(auth_date_str)
            if time.time() - auth_date > MAX_AGE:
                return None
        except ValueError:
            return None

    # Parse user
    user_str = parsed.get("user", [None])[0]
    if not user_str:
        return None

    try:
        user = json.loads(unquote(user_str))
    except (json.JSONDecodeError, TypeError):
        return None

    # Check allowed user
    if user.get("id") != ALLOWED_USER_ID:
        return None

    return user

"""Tests for auth.py — Telegram initData HMAC validation."""
import hmac
import hashlib
import os
import time
import urllib.parse
import json

# Set BOT_TOKEN before importing auth
os.environ["BOT_TOKEN"] = "test:token"

from auth import validate_init_data


def _make_init_data(user_id=435926703, bot_token="test:token", auth_date=None):
    """Generate valid Telegram initData string."""
    if auth_date is None:
        auth_date = int(time.time())
    params = {
        "auth_date": str(auth_date),
        "user": json.dumps({"id": user_id, "first_name": "Test"}),
        "query_id": "ABC123",
    }
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    params["hash"] = h
    return urllib.parse.urlencode(params)


def test_validate_init_data_valid():
    init_data = _make_init_data()
    user = validate_init_data(init_data)
    assert user is not None
    assert user["id"] == 435926703


def test_validate_init_data_invalid_hash():
    init_data = _make_init_data()
    tampered = init_data.replace("hash=", "hash=0000")
    result = validate_init_data(tampered)
    # Function returns None on invalid hash (per its signature)
    assert result is None or result is False


def test_validate_init_data_empty():
    assert validate_init_data("") is None

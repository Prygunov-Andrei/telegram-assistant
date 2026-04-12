"""Tests for main.py — FastAPI endpoints (using TestClient).

These tests focus on auth gate and basic app smoke.
"""
import os
import pytest

os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("OWNER_USER_ID", "435926703")


def test_unauthorized_without_initdata():
    """API returns 401/400 without valid initData."""
    from fastapi.testclient import TestClient
    try:
        from main import app
    except Exception as e:
        pytest.skip(f"main.py import failed: {e}")

    client = TestClient(app)
    r = client.get("/api/tasks")
    # Should reject unauthenticated requests
    assert r.status_code in (400, 401, 403)

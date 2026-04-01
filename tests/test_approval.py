from __future__ import annotations

from src.utils.approval import ApprovalManager


def test_register_and_approve():
    mgr = ApprovalManager()
    token = mgr.register("delete_email", {"message_id": "abc123"}, "Delete email from Ivan")
    assert mgr.pending_count() == 1

    pending = mgr.get_pending(token)
    assert pending is not None
    assert pending.action == "delete_email"

    result = mgr.approve(token)
    assert result is not None
    assert result.payload == {"message_id": "abc123"}
    assert mgr.pending_count() == 0


def test_approve_unknown_token():
    mgr = ApprovalManager()
    assert mgr.approve("nonexistent") is None


def test_double_approve():
    mgr = ApprovalManager()
    token = mgr.register("test", {}, "test")
    mgr.approve(token)
    assert mgr.approve(token) is None

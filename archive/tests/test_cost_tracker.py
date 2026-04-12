from __future__ import annotations

from src.utils.cost_tracker import CostTracker


def test_record_and_today_cost(cost_tracker: CostTracker):
    cost_tracker.record("claude-haiku-4-5-20251001", {
        "input_tokens": 1000,
        "output_tokens": 500,
    })
    assert cost_tracker.today_cost() > 0


def test_over_limit(cost_tracker: CostTracker):
    assert not cost_tracker.is_over_limit()
    for _ in range(100):
        cost_tracker.record("claude-opus-4-6", {
            "input_tokens": 100000,
            "output_tokens": 50000,
        })
    assert cost_tracker.is_over_limit()


def test_summary(cost_tracker: CostTracker):
    cost_tracker.record("claude-haiku-4-5-20251001", {"input_tokens": 500, "output_tokens": 200})
    s = cost_tracker.summary()
    assert s["today"]["requests"] == 1
    assert "claude-haiku-4-5-20251001" in s["model_breakdown"]

from __future__ import annotations

import asyncio
from pathlib import Path

from src.brain.conversation import ConversationStore
from src.tools.registry import ToolRegistry
from src.tools.admin_tools import register_admin_tools
from src.utils.cost_tracker import CostTracker


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_get_usage_summary(tmp_path: Path):
    registry = ToolRegistry()
    tracker = CostTracker(usage_dir=str(tmp_path / "usage"), daily_limit_usd=5.0)
    conversations = ConversationStore()
    register_admin_tools(registry, tracker, conversations)
    result = _run(registry.execute("get_usage_summary", {}))
    assert "Расход" in result or "Запросов" in result


def test_get_status(tmp_path: Path):
    registry = ToolRegistry()
    tracker = CostTracker(usage_dir=str(tmp_path / "usage"), daily_limit_usd=5.0)
    conversations = ConversationStore()
    register_admin_tools(registry, tracker, conversations)
    result = _run(registry.execute("get_status", {}))
    assert "Uptime" in result
    assert "Инструментов" in result


def test_admin_tools_count(tmp_path: Path):
    registry = ToolRegistry()
    tracker = CostTracker(usage_dir=str(tmp_path / "usage"), daily_limit_usd=5.0)
    conversations = ConversationStore()
    register_admin_tools(registry, tracker, conversations)
    assert registry.tool_count() == 2

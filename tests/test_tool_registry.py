from __future__ import annotations

import asyncio

from src.tools.registry import ToolRegistry


def test_register_and_get_definitions(tool_registry: ToolRegistry):
    tool_registry.register(
        "test_tool",
        "A test tool",
        {"type": "object", "properties": {"x": {"type": "string"}}},
        lambda x="": f"result: {x}",
    )
    defs = tool_registry.get_definitions()
    assert len(defs) == 1
    assert defs[0]["name"] == "test_tool"
    assert defs[0]["description"] == "A test tool"


def test_execute_sync_tool(tool_registry: ToolRegistry):
    tool_registry.register(
        "greet", "Greet", {"type": "object", "properties": {}}, lambda: "hello!"
    )
    result = asyncio.get_event_loop().run_until_complete(
        tool_registry.execute("greet", {})
    )
    assert result == "hello!"


def test_execute_unknown_tool(tool_registry: ToolRegistry):
    result = asyncio.get_event_loop().run_until_complete(
        tool_registry.execute("nonexistent", {})
    )
    assert "Unknown tool" in result


def test_tool_count(tool_registry: ToolRegistry):
    assert tool_registry.tool_count() == 0
    tool_registry.register("a", "A", {"type": "object"}, lambda: "")
    tool_registry.register("b", "B", {"type": "object"}, lambda: "")
    assert tool_registry.tool_count() == 2

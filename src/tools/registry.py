from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Union

logger = logging.getLogger(__name__)

ToolHandler = Callable[..., Union[Awaitable[str], str]]


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: ToolHandler,
    ) -> None:
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
        )

    def get_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    async def execute(self, name: str, tool_input: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Unknown tool: {name}"
        try:
            result = tool.handler(**tool_input)
            if hasattr(result, "__await__"):
                result = await result
            return str(result)
        except Exception as e:
            logger.exception("Tool %s failed", name)
            return f"Error executing {name}: {e}"

    def tool_count(self) -> int:
        return len(self._tools)

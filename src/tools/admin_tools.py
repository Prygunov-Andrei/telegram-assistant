from __future__ import annotations

import time
from datetime import datetime

from src.brain.conversation import ConversationStore
from src.tools.registry import ToolRegistry
from src.utils.cost_tracker import CostTracker

_start_time = time.time()


def register_admin_tools(
    registry: ToolRegistry,
    cost_tracker: CostTracker,
    conversations: ConversationStore,
) -> None:

    def get_usage_summary() -> str:
        s = cost_tracker.summary()
        today = s["today"]
        lines = [
            f"**Расход за сегодня:**",
            f"- Запросов: {today['requests']}",
            f"- Токенов: {today['tokens']:,}",
            f"- Стоимость: ${today['cost_usd']:.4f} / ${today['limit_usd']:.2f}",
        ]
        for model, data in s.get("model_breakdown", {}).items():
            short_name = model.split("-")[1] if "-" in model else model
            lines.append(f"  - {short_name}: {data['requests']} запр., ${data['cost_usd']:.4f}")
        return "\n".join(lines)

    registry.register(
        name="get_usage_summary",
        description="Показать расход API за сегодня: количество запросов, токенов, стоимость.",
        input_schema={"type": "object", "properties": {}},
        handler=get_usage_summary,
    )

    def get_status() -> str:
        uptime_sec = int(time.time() - _start_time)
        hours, remainder = divmod(uptime_sec, 3600)
        minutes, secs = divmod(remainder, 60)
        uptime_str = f"{hours}ч {minutes}м {secs}с"

        active_chats = conversations.active_count()
        tools = registry.tool_count()
        today_cost = cost_tracker.today_cost()
        limit = cost_tracker.daily_limit_usd

        lines = [
            "**Статус бота:**",
            f"- Uptime: {uptime_str}",
            f"- Активных чатов: {active_chats}",
            f"- Инструментов: {tools}",
            f"- Расход сегодня: ${today_cost:.4f} / ${limit:.2f}",
        ]
        return "\n".join(lines)

    registry.register(
        name="get_status",
        description="Показать статус бота: uptime, количество чатов, расход.",
        input_schema={"type": "object", "properties": {}},
        handler=get_status,
    )

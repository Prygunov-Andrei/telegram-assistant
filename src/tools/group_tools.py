from __future__ import annotations

from src.tools.registry import ToolRegistry
from src.transport.group_logger import GroupLogger
from src.transport.telegram_policy import TelegramPolicy


def register_group_tools(
    registry: ToolRegistry,
    group_logger: GroupLogger,
    policy: TelegramPolicy,
) -> None:

    def _resolve_group(title: str) -> int | None:
        """Resolve group title to chat_id from policy."""
        title_lower = title.lower()
        for chat_id, rule in policy.groups.items():
            if title_lower in rule.title.lower():
                return chat_id
        return None

    def search_group_logs(query: str, group_title: str = "", days: int = 7) -> str:
        chat_id = None
        if group_title:
            chat_id = _resolve_group(group_title)
            if not chat_id:
                available = ", ".join(r.title for r in policy.groups.values())
                return f"Группа «{group_title}» не найдена. Доступные: {available}"

        results = group_logger.search_logs(chat_id=chat_id, query=query, days=days)
        if not results:
            scope = f"в «{group_title}»" if group_title else "во всех группах"
            return f"По запросу «{query}» {scope} за {days} дней ничего не найдено."

        # Обрезаем до 5000 символов для безопасности
        output = "\n".join(results)
        if len(output) > 5000:
            output = output[:5000] + "\n... (обрезано)"
        return output

    registry.register(
        name="search_group_logs",
        description=(
            "Поиск по логам групповых чатов Telegram. "
            "Можно искать по конкретной группе или по всем сразу."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос (текст)"},
                "group_title": {
                    "type": "string",
                    "description": "Название группы (необязательно). Например: 'GT24', 'Август', 'ЦРБ Коломна'",
                },
                "days": {"type": "integer", "description": "За сколько дней искать (по умолчанию 7)"},
            },
            "required": ["query"],
        },
        handler=search_group_logs,
    )

    def list_group_activity(days: int = 7) -> str:
        counts = group_logger.count_messages(days=days)
        if not counts:
            return f"За последние {days} дней сообщений в группах не найдено."

        lines = []
        for chat_id_str, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            chat_id = int(chat_id_str)
            group = policy.groups.get(chat_id)
            title = group.title if group else f"chat {chat_id_str}"
            lines.append(f"- **{title}**: {count} сообщений")

        total = sum(counts.values())
        lines.append(f"\nВсего: {total} сообщений за {days} дней")
        return "\n".join(lines)

    registry.register(
        name="list_group_activity",
        description="Сводка активности в группах: количество сообщений по каждой группе за N дней.",
        input_schema={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "За сколько дней (по умолчанию 7)"},
            },
        },
        handler=list_group_activity,
    )

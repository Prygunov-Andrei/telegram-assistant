from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.integrations.google_services import GoogleServices
from src.tools.registry import ToolRegistry


def register_calendar_tools(registry: ToolRegistry, google: GoogleServices, timezone: str) -> None:
    tz = ZoneInfo(timezone)

    def get_today_events() -> str:
        now = datetime.now(tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        events = google.calendar_list(start.isoformat(), end.isoformat(), max_results=30)
        if not events:
            return "На сегодня событий в календаре нет."
        lines = []
        for event in events:
            start_block = event.get("start", {})
            start_time = start_block.get("dateTime", start_block.get("date", ""))
            if "T" in start_time:
                try:
                    dt = datetime.fromisoformat(start_time)
                    time_str = dt.strftime("%H:%M")
                except ValueError:
                    time_str = start_time
            else:
                time_str = "весь день"
            lines.append(f"- {time_str} | {event.get('summary', '(без названия)')}")
        return "События на сегодня:\n" + "\n".join(lines)

    registry.register(
        name="get_today_events",
        description="Показать события из Google Calendar на сегодня.",
        input_schema={"type": "object", "properties": {}},
        handler=get_today_events,
    )

    def get_events(date_from: str, date_to: str) -> str:
        try:
            start = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=tz)
            end = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=tz) + timedelta(days=1)
        except ValueError:
            return "Некорректный формат дат. Используйте YYYY-MM-DD."
        events = google.calendar_list(start.isoformat(), end.isoformat(), max_results=50)
        if not events:
            return f"Событий с {date_from} по {date_to} нет."
        lines = []
        for event in events:
            start_block = event.get("start", {})
            start_time = start_block.get("dateTime", start_block.get("date", ""))
            lines.append(f"- {start_time} | {event.get('summary', '(без названия)')}")
        return "\n".join(lines)

    registry.register(
        name="get_events",
        description="Показать события из Google Calendar за указанный период.",
        input_schema={
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "Начало периода (YYYY-MM-DD)"},
                "date_to": {"type": "string", "description": "Конец периода (YYYY-MM-DD)"},
            },
            "required": ["date_from", "date_to"],
        },
        handler=get_events,
    )

    def create_event(title: str, start_time: str, end_time: str, description: str = "") -> str:
        event_id = google.calendar_create(title, start_time, end_time, description)
        return f"Событие «{title}» создано (id={event_id})."

    registry.register(
        name="create_event",
        description="Создать событие в Google Calendar.",
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Название события"},
                "start_time": {"type": "string", "description": "Начало в ISO 8601 (например 2026-04-02T10:00:00+02:00)"},
                "end_time": {"type": "string", "description": "Конец в ISO 8601"},
                "description": {"type": "string", "description": "Описание (необязательно)"},
            },
            "required": ["title", "start_time", "end_time"],
        },
        handler=create_event,
    )

    def delete_event(event_id: str) -> str:
        google.calendar_delete(event_id)
        return f"Событие {event_id} удалено."

    registry.register(
        name="delete_event",
        description="Удалить событие из Google Calendar по ID. Опасная операция — запроси подтверждение у пользователя.",
        input_schema={
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "ID события в Google Calendar"},
            },
            "required": ["event_id"],
        },
        handler=delete_event,
    )

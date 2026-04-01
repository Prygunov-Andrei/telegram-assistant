# Dev Guide — Telegram Assistant

## Структура проекта

```
telegram-assistant/
├── src/
│   ├── __init__.py
│   ├── main.py              # Entrypoint: PID lock, init, run
│   ├── config.py            # Pydantic BaseSettings (.env)
│   ├── logging_config.py    # Structured logging + secret masking
│   ├── brain/
│   │   ├── anthropic_engine.py  # Agentic tool_use loop
│   │   ├── conversation.py      # Per-chat message history
│   │   ├── model_router.py      # haiku vs opus routing
│   │   └── system_prompt.py     # Multi-role system prompt
│   ├── tools/
│   │   ├── registry.py          # ToolRegistry: register/execute
│   │   ├── vault_tools.py       # Задачи Obsidian (6 tools)
│   │   ├── calendar_tools.py    # Google Calendar (4 tools)
│   │   ├── gmail_tools.py       # Gmail (4 tools)
│   │   ├── github_tools.py      # GitHub (5 tools)
│   │   ├── fitness_tools.py     # Тренировки/питание (3 tools)
│   │   ├── deutsch_tools.py     # Немецкий язык (2 tools)
│   │   └── admin_tools.py       # Статус/расход (2 tools)
│   ├── transport/
│   │   ├── telegram_bot.py      # Telegram handlers
│   │   └── telegram_policy.py   # Access control
│   ├── integrations/
│   │   ├── google_services.py   # Gmail + Calendar + Contacts
│   │   └── groq_stt.py          # Whisper STT (Groq API)
│   ├── memory/
│   │   ├── vault_adapter.py     # CRUD для .md задач
│   │   └── memory_store.py      # Загрузка memory/*.md
│   └── utils/
│       ├── formatting.py        # Русские даты, split_message
│       ├── approval.py          # Token-based confirmation
│       └── cost_tracker.py      # Учёт токенов и стоимости
├── tests/                       # Unit тесты
├── scripts/                     # daemon.sh, watchdog.sh, run.sh
├── config/                      # .env, policy.json
├── memory/                      # Memory-файлы бота
├── logs/                        # Логи (в .gitignore)
└── docs/                        # Документация
```

## Тесты

```bash
python3 -m pytest -q          # Все тесты
python3 -m pytest -q -x       # Остановить на первой ошибке
python3 -m pytest tests/test_vault_adapter.py -v  # Один файл
```

## Как добавить новый tool

1. Создать файл `src/tools/<name>_tools.py`
2. Написать `register_<name>_tools(registry, ...)` функцию
3. Внутри — определить handler-функции и `registry.register()` для каждой
4. В `src/main.py` — import и вызов `register_<name>_tools()`
5. Написать тесты

Пример:

```python
# src/tools/weather_tools.py
from src.tools.registry import ToolRegistry

def register_weather_tools(registry: ToolRegistry) -> None:
    def get_weather(city: str) -> str:
        # ... логика ...
        return f"Погода в {city}: солнечно, +20°C"

    registry.register(
        name="get_weather",
        description="Получить текущую погоду в городе.",
        input_schema={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Название города"},
            },
            "required": ["city"],
        },
        handler=get_weather,
    )
```

## ToolRegistry API

```python
registry = ToolRegistry()

# Регистрация
registry.register(
    name="tool_name",
    description="Описание для Claude",
    input_schema={...},  # JSON Schema (Anthropic format)
    handler=my_function,  # sync или async
)

# Для Anthropic API
tools = registry.get_definitions()  # list[dict] для tools= parameter

# Выполнение
result = await registry.execute("tool_name", {"arg": "value"})  # str
```

Handler может быть sync или async. Registry автоматически оборачивает sync в `asyncio.to_thread()`.

## Anthropic API формат

Каждый tool отправляется в API как:
```json
{
  "name": "list_tasks",
  "description": "Показать открытые задачи по проекту.",
  "input_schema": {
    "type": "object",
    "properties": {
      "project": {"type": "string", "description": "..."}
    },
    "required": ["project"]
  }
}
```

Ответ с tool_use:
```json
{
  "stop_reason": "tool_use",
  "content": [
    {"type": "text", "text": "Посмотрю задачи..."},
    {"type": "tool_use", "id": "tu_abc", "name": "list_tasks", "input": {"project": "life"}}
  ]
}
```

Мы выполняем tool и отправляем результат:
```json
{
  "role": "user",
  "content": [
    {"type": "tool_result", "tool_use_id": "tu_abc", "content": "...список задач..."}
  ]
}
```

## Conversation management

- Per-chat dict: `{chat_id: Conversation}`
- Максимум 50 пар сообщений (FIFO при переполнении)
- Поддерживает text, images, tool_use/tool_result
- В памяти (не персистентный) — при рестарте бота история сбрасывается

## Зависимости

Управляются через `pyproject.toml`:
```bash
pip install -e ".[dev]"  # Установить с dev-зависимостями
```

Ключевые:
- `anthropic` — Anthropic Messages API
- `python-telegram-bot` — Telegram bot framework
- `pydantic-settings` — Config management
- `google-api-python-client` — Google API
- `PyGithub` — GitHub API
- `httpx` — HTTP client (Groq API)
- `PyYAML` — Frontmatter parsing

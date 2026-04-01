# CLAUDE.md — Telegram Assistant

Персональный Telegram-ассистент на Anthropic API (tool_use agentic loop).

## Структура

- `src/` — исходный код
  - `brain/` — ядро AI: Anthropic API, model routing, system prompt, conversation history
  - `transport/` — Telegram bot (python-telegram-bot, polling)
  - `tools/` — инструменты для Claude (задачи, calendar, gmail, github, fitness, deutsch)
  - `integrations/` — внешние сервисы (Google API, GitHub, Groq STT)
  - `memory/` — vault adapter, memory store
  - `utils/` — formatting, approval, cost tracker
- `scripts/` — daemon, watchdog, run
- `config/` — .env с ключами (в .gitignore)
- `memory/` — файлы памяти бота
- `tests/` — unit тесты
- `docs/` — документация

## Ключевые команды

```bash
cd telegram-assistant
source config/.env && python3 -m src.main          # Локальный запуск
bash scripts/daemon.sh                              # Запуск daemon в tmux
python3 -m pytest -q                                # Тесты
```

## Архитектура

Бот работает через Anthropic Messages API с tool_use. Claude получает описания инструментов и сам решает когда и какой вызвать. Нет ручной if/elif маршрутизации команд.

Model routing: claude-haiku-4-5 для рутины (slash-команды), claude-opus-4-6 для сложных задач.

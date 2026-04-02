# CLAUDE.md — Telegram Assistant

Персональный Telegram-ассистент на Anthropic API (tool_use agentic loop).

## Структура

- `src/` — исходный код
  - `brain/` — ядро AI: Anthropic API, model routing, system prompt, conversation history, context gatherer (авто-подгрузка данных)
  - `transport/` — Telegram bot (polling), group logger, policy, TTS (ElevenLabs)
  - `tools/` — инструменты для Claude: vault (задачи, дашборд, recurring), calendar, gmail, drive, github, contacts, maps, fitness (+ Apple Health), deutsch, groups, web (поиск + чтение), admin
  - `integrations/` — внешние сервисы: Google API (Gmail, Calendar, Drive, Contacts), GitHub, Groq STT, ElevenLabs TTS, Apple Health, Serper.dev (Google Search)
  - `memory/` — vault adapter, memory store
  - `utils/` — formatting (strip_html, sanitize), approval, cost tracker
- `scripts/` — daemon, watchdog, run
- `config/` — .env с ключами (в .gitignore), policy.json (группы), groups-registry.md
- `memory/` — файлы памяти бота (fitness, conversations, usage)
- `logs/groups/` — логи групповых чатов (по chat_id, дневные файлы + media)
- `tests/` — unit тесты (86+)
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

### ContextGatherer (авто-память)

Перед каждым вызовом Claude автоматически подгружаются релевантные данные в system prompt: дневник питания (если вопрос про еду), дашборд (если про задачи), Apple Health (если про здоровье). Claude видит данные без вызова tools.

### Групповые чаты

Все сообщения из зарегистрированных групп логируются в `logs/groups/{chat_id}/{YYYY-MM-DD}.txt` + медиа. Три режима: interactive, monitoring, logging.

### Gmail

Полноценная работа с почтой: inbox, чтение тела/вложений, ответ, пересылка, архивация. Модифицирующие операции через approval.

### Google Drive

Полный доступ: поиск, чтение, загрузка файлов, создание папок, сохранение вложений из Gmail. Через approval.

### Web Search

Поиск в Google (через Serper.dev) + чтение веб-страниц по URL.

### TTS (ElevenLabs)

Голосовые ответы при словах "скажи", "расскажи". Голос Ivan (русский мужской).

### Apple Health

Данные с Apple Watch через Health Auto Export → iCloud Drive: пульс, шаги, калории, сон, SpO2.

### Задачи и дашборд

Управление задачами в Obsidian vault (YAML frontmatter). Дашборд (ДАШБОРД.md). Повторяющиеся задачи (R001-R100). Все модификации через approval.

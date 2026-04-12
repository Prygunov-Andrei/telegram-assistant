# OpenClaw — Telegram-бот на VPS

Персональный AI-ассистент на базе **OpenClaw** (v2026.4.9), работающий 24/7 на VPS.

## Быстрый старт

- **Сервер:** `72.56.80.247` (Ubuntu 24.04, root)
- **SSH:** `ssh -i ~/.ssh/id_ed25519_server root@72.56.80.247`
- **Telegram Bot ID:** `8513400764`
- **AI модель:** `anthropic/claude-sonnet-4-6`
- **Статус бота:** `systemctl --user status openclaw-gateway`

## Документация

| Файл | Описание |
|------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Архитектура, компоненты, потоки данных |
| [CONFIG.md](CONFIG.md) | Конфигурация OpenClaw — все параметры `openclaw.json` |
| [SKILLS.md](SKILLS.md) | Установленные skills: задачи, питание, Apple Health |
| [INTEGRATIONS.md](INTEGRATIONS.md) | MCP-серверы: Gmail, Calendar, Google Drive |
| [SYNC.md](SYNC.md) | Синхронизация задач Mac <-> VPS |
| [OPERATIONS.md](OPERATIONS.md) | Управление: systemd, логи, перезапуск, обновление |
| [MEMORY.md](MEMORY.md) | Workspace memory: как бот запоминает контекст |

## Ключевые возможности

- Telegram DM и группы (с @mention)
- Управление задачами в Obsidian-формате (9 проектов)
- Трекинг питания (КБЖУ, дневник, профиль нутрициолога)
- Apple Health (шаги, пульс, калории, VO2max)
- Gmail (чтение, отправка, архивация)
- Google Calendar (события)
- Google Drive (файлы)
- Голосовые сообщения (STT: Groq Whisper)
- Веб-поиск (Google через Gemini)
- Записи снов с анализом
- Трекинг покупок с КБЖУ

## Что не работает / известные ограничения

- Rate limit Anthropic API: 30K input tokens/min — при активном использовании бот может упасть в 429
- Нет crontab для автоматической синхронизации задач (только ручные скрипты)
- Apple Health: sleep данные не поступают (все нули)
- TTS не настроен (только STT)

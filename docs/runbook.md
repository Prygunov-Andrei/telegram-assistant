# Runbook — Telegram Assistant

## Запуск

### Локально (debug)

```bash
cd /Users/andrei_prygunov/obsidian/telegram-assistant
source config/.env && python3 -m src.main
```

### Daemon (production)

```bash
bash scripts/daemon.sh
```

Скрипт:
1. Убивает старую tmux-сессию `claude-assistant`
2. Создаёт новую с `caffeinate -i` (не даёт маку заснуть)
3. Source-ит `config/.env`, запускает `python3 -m src.main`
4. Ставит описание бота и отправляет уведомление в Telegram

### Watchdog (автоперезапуск)

Установка launchd agent:

```bash
cp scripts/watchdog.plist ~/Library/LaunchAgents/com.andrei.claude-assistant-watchdog.plist
launchctl load ~/Library/LaunchAgents/com.andrei.claude-assistant-watchdog.plist
```

Watchdog проверяет каждые 30 секунд:
- tmux-сессия `claude-assistant` жива
- процесс `src.main` запущен
- Каждые 5 минут — healthcheck через Telegram API

Удаление:

```bash
launchctl unload ~/Library/LaunchAgents/com.andrei.claude-assistant-watchdog.plist
rm ~/Library/LaunchAgents/com.andrei.claude-assistant-watchdog.plist
```

## Остановка

```bash
tmux kill-session -t claude-assistant
```

Или послать SIGTERM процессу — бот обработает graceful shutdown (удалит PID lock, залогирует).

## Логи

| Лог | Путь |
|-----|------|
| Основной | `logs/assistant.log` (ротация 7 дней) |
| Watchdog | `~/.claude/logs/claude-assistant-watchdog.log` |
| Watchdog stdout | `~/.claude/logs/claude-assistant-watchdog-stdout.log` |
| Расход API | `memory/usage/YYYY-MM.jsonl` |

## Конфигурация

Файл: `config/.env`

| Переменная | Описание | Default |
|------------|----------|---------|
| `ANTHROPIC_API_KEY` | API ключ Anthropic | (обязательно) |
| `ANTHROPIC_MODEL_MAIN` | Модель для сложных запросов | claude-opus-4-6 |
| `ANTHROPIC_MODEL_ROUTINE` | Модель для рутины | claude-haiku-4-5-20251001 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token | (обязательно) |
| `TELEGRAM_OWNER_ID` | ID владельца в Telegram | 435926703 |
| `OBSIDIAN_ROOT` | Путь к Obsidian vault | /Users/andrei_prygunov/obsidian |
| `GMAIL_TOKEN_PATH` | Путь к OAuth2 credentials | ~/.gmail-mcp/credentials.json |
| `GROQ_API_KEY` | API ключ Groq (для STT) | (необязательно) |
| `GITHUB_TOKEN` | GitHub personal access token | (необязательно) |
| `TIMEZONE` | Часовой пояс | Europe/Berlin |
| `DAILY_COST_LIMIT_USD` | Дневной лимит расхода | 5.00 |

## Политика доступа

Файл: `config/policy.json`

```json
{
  "owner_id": 435926703,
  "dm_allow_from": [],
  "groups": [
    {
      "chat_id": -1001234567890,
      "require_mention": true,
      "allow_from": [435926703],
      "mode": "interactive",
      "title": "Рабочая группа"
    }
  ]
}
```

- `owner_id` — всегда имеет доступ в личке
- `dm_allow_from` — дополнительные user_id для DM
- `groups` — правила для групповых чатов

## Диагностика

### Бот не отвечает

1. Проверить tmux: `tmux ls`
2. Проверить процесс: `pgrep -f src.main`
3. Проверить PID lock: `cat /tmp/telegram-assistant.lock`
4. Посмотреть лог: `tail -50 logs/assistant.log`
5. Проверить .env: `source config/.env && echo $ANTHROPIC_API_KEY | head -c10`

### Ошибки Anthropic API

- `401/403` — невалидный ключ, проверить `ANTHROPIC_API_KEY`
- `429` — rate limit, бот retry-ит автоматически (exponential backoff)
- `500+` — сбой API, бот retry-ит до 3 раз

### Google OAuth expired

Если Gmail/Calendar перестали работать — обновить токен:

```bash
# Токен обновляется автоматически через refresh_token
# Если refresh_token тоже истёк — нужна реавторизация
```

### Дублирование бота

PID lock (`/tmp/telegram-assistant.lock`) предотвращает запуск двух инстансов. Если бот не запускается с "Already running":

```bash
cat /tmp/telegram-assistant.lock  # проверить PID
ps aux | grep src.main            # жив ли процесс
rm /tmp/telegram-assistant.lock   # если процесс мёртв — удалить lock
```

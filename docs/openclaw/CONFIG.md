# Конфигурация OpenClaw

Главный конфиг: `/root/.openclaw/openclaw.json`

## Полная структура конфига

### gateway

```json
{
  "mode": "local",
  "port": 18789,
  "bind": "loopback",
  "auth": {
    "mode": "token",
    "token": "de604a29...e32ab870"
  },
  "tailscale": { "mode": "off" },
  "nodes": {
    "denyCommands": [
      "camera.snap", "camera.clip", "screen.record",
      "contacts.add", "calendar.add", "reminders.add",
      "sms.send", "sms.search"
    ]
  }
}
```

Gateway работает в режиме `local` на `loopback:18789`. Auth по токену. Tailscale выключен. Запрещены опасные команды (камера, SMS и т.д.).

### channels.telegram

```json
{
  "enabled": true,
  "botToken": "8513400764:AAFE...",
  "groups": {
    "*": { "requireMention": true }
  }
}
```

Telegram включён. Во всех группах (`*`) бот отвечает только при @mention.

### agents.defaults

```json
{
  "model": {
    "primary": "anthropic/claude-sonnet-4-6"
  },
  "workspace": "/root/.openclaw/workspace",
  "models": {
    "anthropic/claude-sonnet-4-6": {}
  }
}
```

Основная модель — Claude Sonnet 4.6. Workspace в `/root/.openclaw/workspace`.

### session

```json
{
  "dmScope": "per-channel-peer"
}
```

Каждый DM-чат = отдельная сессия агента. Контекст не шарится между чатами.

### tools

```json
{
  "profile": "coding",
  "web": {
    "search": {
      "provider": "gemini",
      "enabled": true
    }
  },
  "media": {
    "audio": {
      "enabled": true,
      "echoTranscript": true,
      "echoFormat": "🎤 \"{transcript}\"",
      "models": [
        { "provider": "groq", "model": "whisper-large-v3" }
      ]
    }
  }
}
```

- **Tool profile:** `coding` — полный набор файловых инструментов
- **Web search:** через Google (Gemini provider)
- **Audio STT:** Groq Whisper Large V3, показывает транскрипт пользователю

### auth.profiles

```json
{
  "anthropic:default": {
    "provider": "anthropic",
    "mode": "api_key"
  }
}
```

Anthropic API key берётся из `/root/.env` → `ANTHROPIC_API_KEY`.

### plugins

```json
{
  "anthropic": { "enabled": true },
  "google": {
    "enabled": true,
    "config": {
      "webSearch": {
        "apiKey": "AIzaSyAt..."
      }
    }
  }
}
```

Плагины: Anthropic (AI) + Google (веб-поиск).

### skills.entries

```json
{
  "goplaces": { "apiKey": "AIzaSyDm..." },
  "openai-whisper-api": { "apiKey": "sk-proj-..." },
  "sag": { "apiKey": "sk_9ff9..." }
}
```

- **goplaces** — Google Places API (карты, POI)
- **openai-whisper-api** — OpenAI Whisper (альтернативный STT)
- **sag** — неизвестный skill (возможно SAG = Smart Agent?)

### hooks.internal

```json
{
  "enabled": true,
  "entries": {
    "boot-md": { "enabled": true },
    "bootstrap-extra-files": { "enabled": true },
    "command-logger": { "enabled": true },
    "session-memory": { "enabled": true }
  }
}
```

Все 4 внутренних hook включены.

## Переменные окружения

### /root/.env

```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### /root/.bashrc (экспорт)

```bash
export NODE_COMPILE_CACHE=/var/tmp/openclaw-compile-cache
export OPENCLAW_NO_RESPAWN=1
export GROQ_API_KEY=gsk_Hf...
```

### systemd override (env.conf)

```
[Service]
Environment=GROQ_API_KEY=gsk_Hf...
```

## Управление конфигом

```bash
# Прочитать значение
openclaw config get <path>

# Установить значение
openclaw config set <path> <value>

# Пример: сменить модель
openclaw config set agents.defaults.model.primary "anthropic/claude-opus-4-6"

# Пример: включить аудио
openclaw config set tools.media.audio.enabled true
```

После изменения конфига перезапуск gateway:
```bash
systemctl --user restart openclaw-gateway
```

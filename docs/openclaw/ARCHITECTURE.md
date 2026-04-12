# Архитектура OpenClaw

## Общая схема

```
┌─────────────────┐
│  Telegram API   │
│  (polling)      │
└────────┬────────┘
         │
┌────────▼────────┐
│  OpenClaw       │  Node.js, порт 18789 (loopback)
│  Gateway        │  systemd user service
│  v2026.4.9      │  PID: openclaw-gateway
└────┬───┬───┬────┘
     │   │   │
     │   │   └──────────────────────────┐
     │   │                              │
┌────▼───▼────┐  ┌──────────────┐  ┌───▼──────────┐
│  Agent      │  │  MCP-серверы │  │  Skills      │
│  (Claude    │  │  (mcporter)  │  │  (workspace) │
│  Sonnet 4.6)│  │              │  │              │
└─────────────┘  └──────────────┘  └──────────────┘
```

## Компоненты

### 1. OpenClaw Gateway

- **Что:** Node.js приложение, установленное глобально через npm
- **Бинарник:** `/usr/lib/node_modules/openclaw/dist/index.js`
- **Версия:** 2026.4.9
- **Порты:**
  - `18789` — основной gateway (loopback)
  - `18791` — вспомогательный (loopback)
  - `35145` — внутренний (loopback)
- **Конфиг:** `/root/.openclaw/openclaw.json`

### 2. Telegram Channel

- **Bot Token:** `8513400764:AAFEVfel...`
- **Режим:** polling (не webhook)
- **DM scope:** `per-channel-peer` (каждый чат = отдельная сессия)
- **Группы:** `requireMention: true` — бот отвечает только на @mention
- **Offset файл:** `/root/.openclaw/telegram/update-offset-default.json`

### 3. AI Agent

- **Модель:** `anthropic/claude-sonnet-4-6` (Anthropic API)
- **API key:** в `/root/.env` (ANTHROPIC_API_KEY)
- **Workspace:** `/root/.openclaw/workspace/`
- **Tool profile:** `coding`

### 4. MCP-серверы (через mcporter)

Конфиг: `/root/.openclaw/workspace/config/mcporter.json`

| Сервер | npm пакет | Назначение |
|--------|-----------|------------|
| `gmail` | `@gongrzhe/server-gmail-autoauth-mcp` v1.1.11 | Gmail: чтение, отправка, архивация |
| `calendar` | `@cocal/google-calendar-mcp` v2.6.1 | Google Calendar: события |

Оба используют OAuth credentials из `/root/.gmail-mcp/`.

### 5. Skills (встроенные навыки)

Хранятся в `/root/.openclaw/workspace/skills/`:

| Skill | Версия | Описание |
|-------|--------|----------|
| `tasks` | custom | Система задач в Obsidian-формате |
| `apple-health-sync` | 0.8.1 | Синхронизация Apple Health с iPhone |
| `healthkit-sync` | 1.0.0 | HealthKit CLI (reference) |

### 6. Internal Hooks

Активные hooks в конфигурации:
- `boot-md` — загрузка MEMORY.md/TOOLS.md при старте сессии
- `bootstrap-extra-files` — дополнительные файлы при bootstrap
- `command-logger` — логирование команд
- `session-memory` — сохранение памяти между сессиями

## Потоки данных

### Сообщение от пользователя

```
Telegram → Gateway → Agent (Claude Sonnet 4.6)
                         ├── читает workspace файлы (MEMORY.md, TOOLS.md, skills)
                         ├── вызывает MCP tools (gmail, calendar)
                         ├── пишет в workspace (memory/, nutrition/)
                         └── ответ → Telegram
```

### Голосовое сообщение

```
Telegram (voice) → Gateway → Groq Whisper STT → текст → Agent → ответ
```

### Apple Health синхронизация

```
iPhone (Health Sync app)
    ↓ encrypted data (v5: X25519-ChaCha20Poly1305)
OpenClaw cron job → fetch_health_data.py
    ↓ decrypt + validate
SQLite DB (/root/.apple-health-sync/health_data.db)
    ↓ agent reads on demand
Agent → ответ пользователю
```

## Файловая структура на VPS

```
/root/
├── .openclaw/
│   ├── openclaw.json              # Главный конфиг
│   ├── openclaw.json.bak.*        # Бэкапы конфига
│   ├── logs/                      # Audit логи
│   ├── telegram/                  # Telegram state (offset, commands)
│   └── workspace/                 # Рабочая директория агента
│       ├── MEMORY.md              # Долгосрочная память
│       ├── TOOLS.md               # Справка по инструментам
│       ├── config/
│       │   └── mcporter.json      # MCP-серверы
│       ├── memory/                # Дневные записи
│       │   ├── 2026-04-11.md      # Питание, утро
│       │   ├── shopping-*.md      # Покупки
│       │   ├── dreams.md          # Сны
│       │   └── shopping-registry.md
│       ├── nutrition/
│       │   ├── PROFILE.md         # Профиль (вес, цели, КБЖУ)
│       │   └── log/               # Дневники питания
│       ├── skills/
│       │   ├── tasks/SKILL.md     # Система задач
│       │   ├── apple-health-sync/ # Apple Health skill
│       │   └── healthkit-sync/    # HealthKit reference
│       └── .git/                  # Git-репо workspace
├── .apple-health-sync/            # Apple Health данные
│   ├── config/                    # Ключи, QR, конфиг
│   └── health_data.db             # SQLite с данными здоровья
├── .gmail-mcp/                    # Google OAuth credentials
│   ├── credentials.json           # Gmail tokens
│   ├── calendar_credentials.json  # Calendar+Drive+Contacts tokens
│   └── gcp-oauth.keys.json       # OAuth client keys
├── .config/
│   ├── systemd/user/              # systemd service
│   ├── google-calendar-mcp/       # Calendar MCP tokens
│   └── clawhub/                   # ClawhHub registry config
├── obsidian-tasks/                # Задачи (синхронизируются с Mac)
│   ├── ДАШБОРД.md
│   ├── april/ЗАДАЧИ/
│   ├── avgust/ЗАДАЧИ/
│   ├── avgust/ERP_Avgust/ЗАДАЧИ/
│   ├── books/ЗАДАЧИ/
│   ├── deutsch/ЗАДАЧИ/
│   ├── gt24realestate.de/ЗАДАЧИ/
│   ├── kaz_nach_berlin/ЗАДАЧИ/
│   ├── life/ЗАДАЧИ/
│   └── life/ЗАДАЧИ_RECURRING/
└── .env                           # API ключи (ANTHROPIC_API_KEY)
```

## Инфраструктура

- **ОС:** Ubuntu 24.04.4 LTS (Noble Numbat)
- **Node.js:** v22.22.2
- **Python:** 3.12.3
- **Память:** ~577 MB (пик 1.1 GB)
- **Firewall:** UFW (SSH, 80, 443)
- **Linger:** включён (сервис работает без логина)
- **Мониторинг:** Zabbix agent (порт 10050)

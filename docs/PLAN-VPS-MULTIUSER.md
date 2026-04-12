# План: Семейный AI-ассистент на Agent SDK → VPS → ERP

## Контекст

**Сейчас:** Персональный Telegram-бот одного пользователя (Андрей, ID 435926703), локально на Mac, с кастомным agentic loop через Anthropic API.

**Цель:** Транспорт-независимый AI-ассистент на Claude Agent SDK для семьи (3 пользователя), задеплоенный на VPS 24/7. Архитектура должна масштабироваться до корпоративного "мозга компании" (100+ сотрудников, Django ERP, RAG по 10K+ документов).

### Решения пользователя:
- Agent SDK как ядро (не кастомный движок, не Claude Code CLI)
- Кастомные инструменты → MCP-серверы (стандарт, переиспользуемые)
- Telegram сейчас, Django ERP чат потом — один бэкенд, разные фронтенды
- Vault → своя система md-файлов (без Obsidian)
- Google → у каждого свой аккаунт (отдельные OAuth токены)
- Apple Health → push через iOS Shortcuts на HTTP-эндпоинт
- Бюджет → $5/день на каждого пользователя
- Рабочие группы → удалить, бот семейный/личный
- Документы → каждый кидает фотки/файлы, бот сохраняет раздельно
- Всё делаем сразу, без переходных вариантов

---

## Архитектура

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Telegram    │  │ Django ERP  │  │  Другие     │
│  (сейчас)   │  │ (потом)     │  │  (будущее)  │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────┬───────┴────────┬───────┘
                │                │
         ┌──────▼──────┐  Transport-agnostic
         │   Gateway   │  API (принимает сообщение,
         │   Router    │  возвращает ответ)
         └──────┬──────┘
                │  user_id → какому агенту
       ┌────────┼────────┐
       ▼        ▼        ▼
   ┌───────┐ ┌───────┐ ┌───────┐
   │Agent  │ │Agent  │ │Agent  │  Claude Agent SDK
   │Андрей │ │Люда   │ │Полина │  per-user сессии
   └───┬───┘ └───┬───┘ └───┬───┘
       │         │         │
       ▼         ▼         ▼
   ┌─────────────────────────────┐
   │  Встроенные tools Agent SDK │  Read, Write, Edit,
   │  (файлы, bash, grep, glob) │  Bash, Grep, Glob
   └─────────────────────────────┘
   ┌─────────────────────────────┐
   │  MCP-серверы (кастомные)    │  Gmail, Calendar, Drive,
   │  (переиспользуемые)        │  Contacts, Fitness, Maps,
   └─────────────────────────────┘  Web, Notes, Documents, Health
       │
       ▼
   ┌─────────────────────────────┐
   │  Per-user данные            │
   │  /data/users/{user_id}/     │
   └─────────────────────────────┘
```

### Ключевые принципы:
1. **Transport-agnostic** — ядро не знает о Telegram/Django. Gateway адаптирует.
2. **Agent SDK = ядро** — заменяет наш AnthropicEngine. Встроенные файловые tools + MCP.
3. **MCP-серверы** — все кастомные инструменты (Gmail, Calendar, etc.) как отдельные MCP-серверы. Стандарт, переиспользуемые в ERP.
4. **Per-user изоляция** — каждый пользователь = свой агент, своя директория, свои credentials.

---

## Фаза 0: Проверка Agent SDK

> Прежде чем строить — убедиться, что фундамент работает.

### 0.1 Установка и проверка Agent SDK
- `pip install claude-agent-sdk`
- Проверить: создание агента, встроенные tools (Read/Write/Edit/Bash), сессии, resume
- Проверить: подключение MCP-серверов к Agent SDK
- Проверить: per-user cwd изоляция
- Проверить: контекст-менеджмент (компактификация, max_turns)

### 0.2 Прототип MCP-сервера
- Написать минимальный MCP-сервер (например, для web_search)
- Подключить его к Agent SDK агенту
- Убедиться, что кастомные tools работают рядом со встроенными

**Если Agent SDK не поддерживает MCP или кастомные tools** — fallback: оставляем Agent SDK для файловых операций, а кастомные tools передаём через Anthropic API tool_use напрямую (гибридный подход).

---

## Фаза 1: Ядро — Agent Gateway

### 1.1 Система пользователей
**Новые файлы:** `src/core/users.py`

```python
@dataclass
class UserProfile:
    user_id: int
    name: str               # "Андрей"
    full_name: str          # "Андрей Пригунов"
    timezone: str = "Europe/Berlin"
    daily_cost_limit_usd: float = 5.0
    voice_id: str = ""      # ElevenLabs
    is_admin: bool = False
    google_enabled: bool = True

class UserRegistry:
    def get(user_id: int) -> UserProfile | None
    def is_allowed(user_id: int) -> bool
    def all_users() -> list[UserProfile]
```

Загружает из `data/users.json`.

### 1.2 Agent Manager (центральный компонент)
**Новый файл:** `src/core/agent_manager.py`

Управляет per-user Agent SDK сессиями:

```python
class AgentManager:
    """Создаёт и управляет per-user Agent SDK агентами."""
    
    def __init__(self, data_dir, user_registry, mcp_configs):
        self._sessions: dict[int, AgentSession] = {}
    
    async def process_message(self, user_id: int, text: str) -> str:
        """Главный метод — принимает сообщение, возвращает ответ."""
        session = self._get_or_create_session(user_id)
        result = await session.query(text)
        return result
    
    async def process_message_with_image(self, user_id, text, image_b64) -> str:
        ...
    
    def _get_or_create_session(self, user_id) -> AgentSession:
        """Lazy init: создаёт агента с cwd=user_data_dir, подключает MCP."""
        ...
```

Каждый AgentSession:
- `cwd` = `/data/users/{user_id}/` (изолированный доступ)
- Встроенные tools: Read, Write, Edit, Bash, Grep, Glob
- MCP-серверы: Gmail, Calendar, Drive, Notes, Fitness, и т.д.
- Персонализированный system prompt
- Автоматическая компактификация контекста
- Per-user cost tracking

### 1.3 Transport-agnostic Gateway API
**Новый файл:** `src/core/gateway.py`

```python
class Gateway:
    """Единый интерфейс для всех транспортов."""
    
    def __init__(self, agent_manager, user_registry):
        ...
    
    async def handle_text(self, user_id: int, text: str) -> GatewayResponse:
        if not self.user_registry.is_allowed(user_id):
            return GatewayResponse(denied=True)
        return GatewayResponse(text=await self.agent_manager.process_message(user_id, text))
    
    async def handle_image(self, user_id, text, image_b64) -> GatewayResponse:
        ...
    
    async def handle_voice(self, user_id, audio_bytes) -> GatewayResponse:
        ...
    
    async def handle_file(self, user_id, file_bytes, filename) -> GatewayResponse:
        ...

@dataclass
class GatewayResponse:
    text: str = ""
    voice_bytes: bytes | None = None
    denied: bool = False
```

### 1.4 Per-user CostTracker
**Файл:** `src/core/cost_tracker.py` (рефакторинг из `src/utils/cost_tracker.py`)

`CostTrackerRegistry` — per-user лимиты ($5/день каждый). Файлы: `data/users/{user_id}/usage/{YYYY-MM-DD}.jsonl`.

---

## Фаза 2: MCP-серверы (кастомные инструменты)

Каждый кастомный инструмент — отдельный MCP-сервер. Стандарт, переиспользуемый.

### 2.1 MCP: Google Services (Gmail + Calendar + Drive + Contacts)
**Новая директория:** `src/mcp/google/`

Per-user OAuth токены из `data/users/{user_id}/google/`. MCP-сервер резолвит user_id из контекста и загружает нужные credentials.

Tools:
- `search_emails`, `read_email`, `send_email`, `reply_email`, `archive_email`
- `get_events`, `create_event`, `delete_event`
- `search_drive`, `read_drive_file`, `upload_to_drive`, `create_drive_folder`
- `search_contacts`, `create_contact`

Модифицирующие операции требуют подтверждения (approval).

### 2.2 MCP: Notes (замена Vault)
**Новая директория:** `src/mcp/notes/`

Per-user задачи и заметки. Структура: `data/users/{user_id}/notes/`.

Tools:
- `list_tasks`, `create_task`, `update_task`, `get_dashboard`
- `create_note`, `search_notes`, `read_note`
- `list_recurring`, `create_recurring`

YAML frontmatter для задач (сохраняем). Dashboard.md per-user.

### 2.3 MCP: Fitness + Health
**Новая директория:** `src/mcp/fitness/`

Per-user фитнес-логи (`data/users/{user_id}/fitness/`) + Apple Health данные (`data/users/{user_id}/health/`).

Tools:
- `log_workout`, `log_meal`, `get_fitness_summary`
- `get_health_summary`, `get_heart_rate`, `get_sleep`, `get_weight`

### 2.4 MCP: Documents
**Новая директория:** `src/mcp/documents/`

Хранение и поиск документов per-user: `data/users/{user_id}/documents/`.

Tools:
- `save_document(file_path, caption, category)` — сохраняет с метаданными
- `list_documents(date_from, date_to, category)`
- `search_documents(query)` — поиск по caption/category
- `get_document(doc_id)` — метаданные + путь

Метаданные: `documents/index.json` — caption, дата, категория, оригинальное имя.

### 2.5 MCP: Web (поиск + чтение)
**Новая директория:** `src/mcp/web/`

Общий (не per-user). Serper.dev API.

Tools: `web_search`, `web_read`

### 2.6 MCP: Maps
**Новая директория:** `src/mcp/maps/`

Общий. Google Maps API.

Tools: `search_places`, `get_directions`, `geocode`

### 2.7 MCP: Admin
**Новая директория:** `src/mcp/admin/`

Только для is_admin. Показывает per-user и общую статистику.

Tools: `get_usage_summary`, `get_status`, `list_users`

### 2.8 MCP: Deutsch (опционально, только для Андрея)
**Новая директория:** `src/mcp/deutsch/`

Per-user: `data/users/{user_id}/notes/deutsch/`.

Tools: `add_word`, `get_recent_words`, `quiz`

---

## Фаза 3: Транспорты

### 3.1 Telegram Transport (рефакторинг)
**Файл:** `src/transport/telegram_bot.py` (значительный рефакторинг)

Telegram-бот становится тонким шлюзом:

```python
class TelegramTransport:
    def __init__(self, token, gateway, user_registry, stt_provider, tts_provider):
        ...
    
    async def _on_message(self, update, context):
        user_id = update.effective_user.id
        text = update.message.text
        
        response = await self.gateway.handle_text(user_id, text)
        
        if response.denied:
            return
        
        await update.message.reply_text(response.text)
        
        if response.voice_bytes:
            await update.message.reply_voice(response.voice_bytes)
```

Обработка:
- Текст → `gateway.handle_text()`
- Фото → скачать, сохранить в user dir, `gateway.handle_image()`
- Голос → STT → `gateway.handle_text()`, опционально TTS ответ
- Файл → скачать, сохранить, `gateway.handle_file()`
- Семейная группа → @mention → извлечь user_id → тот же gateway

### 3.2 Рефакторинг политики
**Файл:** `src/transport/telegram_policy.py`

Упрощение: `allowed_users` (из UserRegistry) + `family_group_id`. Удалить 20 рабочих групп.

### 3.3 Health API endpoint
**Новый файл:** `src/transport/health_api.py`

aiohttp на порту 8080. `POST /health` — принимает Apple Health JSON. `Authorization: Bearer KEY`. Сохраняет в `data/users/{user_id}/health/`.

### 3.4 Django ERP Transport (заготовка)
**Новый файл:** `src/transport/django_api.py` (stub)

REST API для будущей интеграции с Django ERP:
- `POST /api/chat` — `{user_id, text}` → `{response}`
- `POST /api/chat/image` — multipart
- `GET /api/chat/history/{user_id}`

Пока только интерфейс, реализация при интеграции с ERP.

---

## Фаза 4: Данные и хранение

### 4.1 Структура данных на VPS
```
/opt/family-assistant/                 # Код (git clone)
/opt/family-assistant/data/
    users.json                         # Реестр пользователей
    shared/
        logs/                          # Логи приложения
    users/
        435926703/                     # Андрей
            conversations/             # Сессии Agent SDK
            fitness/                   # Дневники питания/тренировок
            health/                    # Apple Health JSON (push)
            documents/                 # Фото, файлы
                photos/
                files/
                index.json
            notes/                     # Заметки, задачи
                tasks/
                dashboard.md
                recurring/
                deutsch/
            usage/                     # Cost tracking JSONL
            google/                    # OAuth токены
                credentials.json
                calendar_credentials.json
            memory/                    # Персональная память агента
        {LUDMILA_ID}/                  # Людмила — та же структура
        {POLINA_ID}/                   # Полина — та же структура
```

### 4.2 Конфигурация
**Файл:** `src/config.py` (полная переработка)

```python
class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str
    anthropic_model_main: str = "claude-opus-4-6"
    anthropic_model_routine: str = "claude-haiku-4-5-20251001"
    
    # Telegram
    telegram_bot_token: str
    
    # Data
    data_dir: str = "data"
    
    # Voice
    stt_provider: str = "openai"
    stt_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_model: str = "eleven_multilingual_v2"
    
    # Shared APIs
    google_maps_api_key: str = ""
    serper_api_key: str = ""
    
    # Health API
    health_api_key: str = ""
    health_api_port: int = 8080
    
    # General
    timezone: str = "Europe/Berlin"
    daily_cost_limit_usd: float = 5.0
```

---

## Фаза 5: Инфраструктура и деплой

### 5.1 Docker
**`deploy/Dockerfile`:**
```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY src/ src/
COPY config/ config/
VOLUME /app/data
VOLUME /app/logs
EXPOSE 8080
CMD ["python3", "-m", "src.main"]
```

**`deploy/docker-compose.yml`:**
```yaml
version: "3.8"
services:
  assistant:
    build: {context: .., dockerfile: deploy/Dockerfile}
    container_name: family-assistant
    restart: always
    env_file: ../config/.env
    volumes:
      - ../data:/app/data
      - ../logs:/app/logs
    ports:
      - "8080:8080"
    environment:
      - TZ=Europe/Berlin
```

### 5.2 Systemd (альтернатива Docker)
**`deploy/family-assistant.service`** — Restart=always, EnvironmentFile, security hardening.

### 5.3 Настройка VPS
1. Очистить старый проект
2. SSH-ключи, сменить пароль, `ufw`, `fail2ban`
3. Установить: Python 3.12, ffmpeg, git, docker
4. Установить Claude Code (для разработки по SSH): `curl -fsSL https://claude.ai/install.sh | bash`
5. `ANTHROPIC_API_KEY` в env

### 5.4 Удалить Mac-специфичное
- `scripts/daemon.sh`, `scripts/watchdog.sh`, `scripts/watchdog.plist` — удалить
- Хардкоды `/Users/andrei_prygunov/` — убрать отовсюду

---

## Фаза 6: Рефакторинг main.py

```python
async def main():
    settings = Settings()
    data_dir = Path(settings.data_dir)
    
    # 1. Пользователи
    user_registry = UserRegistry(data_dir / "users.json")
    
    # 2. MCP-серверы
    mcp_configs = {
        "google": GoogleMCPConfig(data_dir),
        "notes": NotesMCPConfig(data_dir),
        "fitness": FitnessMCPConfig(data_dir),
        "documents": DocumentsMCPConfig(data_dir),
        "web": WebMCPConfig(settings.serper_api_key),
        "maps": MapsMCPConfig(settings.google_maps_api_key),
        "admin": AdminMCPConfig(data_dir),
        "deutsch": DeutschMCPConfig(data_dir),
    }
    
    # 3. Agent Manager (ядро)
    agent_manager = AgentManager(
        api_key=settings.anthropic_api_key,
        main_model=settings.anthropic_model_main,
        routine_model=settings.anthropic_model_routine,
        data_dir=data_dir,
        user_registry=user_registry,
        mcp_configs=mcp_configs,
        default_cost_limit=settings.daily_cost_limit_usd,
    )
    
    # 4. Gateway
    gateway = Gateway(agent_manager, user_registry)
    
    # 5. Транспорты
    telegram = TelegramTransport(
        token=settings.telegram_bot_token,
        gateway=gateway,
        user_registry=user_registry,
        stt_api_key=settings.stt_api_key,
        tts_api_key=settings.elevenlabs_api_key,
    )
    
    health_api = HealthAPI(data_dir, settings.health_api_key, settings.health_api_port)
    
    # 6. Запуск всего параллельно
    await asyncio.gather(
        telegram.run(),
        health_api.run(),
    )
```

---

## Фаза 7: Тесты и миграция

### Тесты
- **core/**: test_users, test_agent_manager, test_gateway, test_cost_tracker
- **mcp/**: test_google_mcp, test_notes_mcp, test_fitness_mcp, test_documents_mcp
- **transport/**: test_telegram_transport, test_health_api, test_policy
- **integration/**: test_multiuser_isolation, test_family_group

### Миграция данных Андрея
- `scripts/migrate_data.py` — задачи из Obsidian → `data/users/435926703/notes/`, conversations, fitness
- Google OAuth токены — скопировать вручную

### Получение Telegram ID
- Людмила и Полина → @userinfobot → ID → `data/users.json`

---

## Что удаляем

| Файл/директория | Причина |
|---|---|
| `src/brain/anthropic_engine.py` | Заменён на Agent SDK через AgentManager |
| `src/brain/system_prompt.py` | Интегрирован в AgentManager |
| `src/brain/context_gatherer.py` | Заменён MCP + Agent SDK контекстом |
| `src/brain/model_router.py` | Интегрирован в AgentManager |
| `src/brain/conversation.py` | Agent SDK управляет сессиями |
| `src/tools/` (вся директория) | Заменена на `src/mcp/` серверы |
| `src/memory/vault_adapter.py` | Заменён на MCP Notes |
| `src/memory/memory_store.py` | Интегрирован в per-user память |
| `src/transport/group_logger.py` | Рабочие группы удалены |
| `src/utils/approval.py` | Интегрирован в MCP-серверы |
| `scripts/daemon.sh` | Systemd/Docker |
| `scripts/watchdog.sh` | Systemd/Docker |
| `scripts/watchdog.plist` | macOS-only |
| `config/policy.json` | Упрощён до users.json |
| `config/groups-registry.md` | Рабочие группы удалены |

## Что сохраняем/переиспользуем

| Компонент | Как используется |
|---|---|
| `src/integrations/google_services.py` | Внутри Google MCP-сервера |
| `src/integrations/apple_health.py` | Внутри Fitness MCP-сервера |
| `src/integrations/elevenlabs_tts.py` | В TelegramTransport |
| `src/integrations/groq_stt.py` | В TelegramTransport |
| `src/utils/cost_tracker.py` | В CostTrackerRegistry (рефакторинг) |
| Логика всех tool-модулей | Миграция в MCP-серверы |

---

## Порядок выполнения

| # | Задача | Новые/изменённые файлы |
|---|--------|------------------------|
| 0 | Проверка Agent SDK + MCP прототип | скрипт-прототип |
| 1 | UserProfile + UserRegistry | `src/core/users.py` |
| 2 | Рефакторинг config.py | `src/config.py` |
| 3 | AgentManager (Agent SDK ядро) | `src/core/agent_manager.py` |
| 4 | Gateway (transport-agnostic API) | `src/core/gateway.py` |
| 5 | CostTrackerRegistry | `src/core/cost_tracker.py` |
| 6 | MCP: Notes (замена vault) | `src/mcp/notes/` |
| 7 | MCP: Google (Gmail+Calendar+Drive+Contacts) | `src/mcp/google/` |
| 8 | MCP: Fitness + Health | `src/mcp/fitness/` |
| 9 | MCP: Documents | `src/mcp/documents/` |
| 10 | MCP: Web + Maps + Admin + Deutsch | `src/mcp/web/`, `maps/`, `admin/`, `deutsch/` |
| 11 | TelegramTransport (рефакторинг) | `src/transport/telegram_bot.py` |
| 12 | TelegramPolicy (упрощение) | `src/transport/telegram_policy.py` |
| 13 | Health API endpoint | `src/transport/health_api.py` |
| 14 | Django API stub | `src/transport/django_api.py` |
| 15 | Рефакторинг main.py | `src/main.py` |
| 16 | Удаление старого кода | `src/brain/`, `src/tools/`, старые scripts |
| 17 | Тесты | `tests/` |
| 18 | Docker + systemd | `deploy/` |
| 19 | Миграция данных + деплой на VPS | скрипты + ручная настройка |

---

## Верификация

1. **Фаза 0:** Agent SDK прототип работает с MCP-сервером
2. **Локально:** Отправить сообщение от Андрея → бот отвечает, имеет доступ к его файлам
3. **Изоляция:** Данные пользователя A не видны пользователю B
4. **Группа:** Бот в семейной группе → @mention → использует контекст вызвавшего
5. **Health API:** `curl -X POST http://localhost:8080/health -H "Authorization: Bearer KEY" -d '...'`
6. **Тесты:** `python3 -m pytest -q` — все проходят
7. **VPS:** `docker-compose up -d` → бот отвечает всем трём пользователям
8. **Claude Code:** `ssh user@VPS` → `claude` → доступ к файлам проекта для разработки

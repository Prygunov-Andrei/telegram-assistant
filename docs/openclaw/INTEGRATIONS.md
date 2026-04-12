# Интеграции (MCP-серверы)

OpenClaw подключает внешние сервисы через MCP (Model Context Protocol) серверы. Конфигурация MCP: `/root/.openclaw/workspace/config/mcporter.json`.

## Gmail

**Пакет:** `@gongrzhe/server-gmail-autoauth-mcp` v1.1.11
**Команда:** `gmail-mcp`

**Возможности:**
- Чтение входящих писем
- Отправка писем
- Ответ на письма
- Архивация

**OAuth credentials:** `/root/.gmail-mcp/credentials.json`
- Scopes: `gmail.settings.basic`, `gmail.modify`
- Client ID: `694277164083-jvfrks5k0kic2f3f3odbur30f9p42cmq`

---

## Google Calendar

**Пакет:** `@cocal/google-calendar-mcp` v2.6.1
**Команда:** `google-calendar-mcp`

**Возможности:**
- Просмотр событий
- Создание событий
- Удаление событий

**OAuth credentials:**
- Основной: `/root/.gmail-mcp/calendar_credentials.json`
  - Scopes: `calendar`, `contacts`, `drive`
- Токены: `/root/.config/google-calendar-mcp/tokens.json`
- OAuth keys: `/root/.gmail-mcp/gcp-oauth.keys.json`

**Env переменная в mcporter.json:**
```json
{
  "GOOGLE_OAUTH_CREDENTIALS": "/root/.gmail-mcp/gcp-oauth.keys.json"
}
```

---

## Google Drive & Contacts

Токены с scope `drive` и `contacts` присутствуют в `calendar_credentials.json`, но отдельных MCP-серверов для Drive и Contacts нет. Доступ возможен через тот же OAuth, если установить соответствующие MCP-серверы.

---

## Web Search

**Провайдер:** Google через Gemini plugin
**API key:** в `plugins.entries.google.config.webSearch.apiKey`

Встроен в OpenClaw как плагин, не MCP-сервер.

---

## Google Places (GoPlaces)

**Skill:** `goplaces`
**API key:** в `skills.entries.goplaces.apiKey`

Поиск мест, навигация.

---

## STT (Speech-to-Text)

**Основной:** Groq Whisper Large V3
- API key: `GROQ_API_KEY` в .bashrc и systemd env
- Настройка: `tools.media.audio.models`

**Запасной:** OpenAI Whisper API
- API key: в `skills.entries.openai-whisper-api.apiKey`

**Поведение:** при получении голосового сообщения:
1. Транскрипт через Groq Whisper
2. Показывает `🎤 "транскрипт"` пользователю
3. Обрабатывает текст как обычное сообщение

---

## Apple Health

Не MCP-сервер, а skill с Python-скриптами. См. [SKILLS.md](SKILLS.md#2-apple-health-sync-v081).

---

## Добавление нового MCP-сервера

1. Установить npm пакет глобально:
   ```bash
   npm install -g @example/my-mcp-server
   ```

2. Добавить в mcporter.json:
   ```bash
   cat /root/.openclaw/workspace/config/mcporter.json
   # Отредактировать, добавив новый сервер
   ```

3. Перезапустить gateway:
   ```bash
   systemctl --user restart openclaw-gateway
   ```

## Текущие OAuth scopes

| Scope | Файл credentials | Статус |
|-------|------------------|--------|
| `gmail.modify` | credentials.json | Активен |
| `gmail.settings.basic` | credentials.json | Активен |
| `calendar` | calendar_credentials.json | Активен |
| `contacts` | calendar_credentials.json | Есть scope, нет MCP |
| `drive` | calendar_credentials.json | Есть scope, нет MCP |

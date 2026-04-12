# Операции и управление

## Подключение к серверу

```bash
ssh -i ~/.ssh/id_ed25519_server root@72.56.80.247
```

## systemd сервис

OpenClaw работает как **user-level systemd сервис** (не system-level).

### Основные команды

```bash
# Статус
systemctl --user status openclaw-gateway

# Перезапуск
systemctl --user restart openclaw-gateway

# Остановка
systemctl --user stop openclaw-gateway

# Запуск
systemctl --user start openclaw-gateway

# Логи (последние 100 строк)
journalctl --user -u openclaw-gateway -n 100 --no-pager

# Логи в реальном времени
journalctl --user -u openclaw-gateway -f

# Включить автозапуск
systemctl --user enable openclaw-gateway
```

### Файлы сервиса

| Файл | Путь |
|------|------|
| Unit файл | `/root/.config/systemd/user/openclaw-gateway.service` |
| Override (env) | `/root/.config/systemd/user/openclaw-gateway.service.d/env.conf` |
| Symlink autostart | `default.target.wants/openclaw-gateway.service` |

### Параметры сервиса

- **ExecStart:** `/usr/bin/node /usr/lib/node_modules/openclaw/dist/index.js gateway --port 18789`
- **Restart:** always (RestartSec=5)
- **KillMode:** control-group
- **Environment:**
  - `HOME=/root`
  - `OPENCLAW_GATEWAY_PORT=18789`
  - `GROQ_API_KEY` (через override)

### Linger

`loginctl enable-linger root` — включён. Сервис работает даже когда никто не залогинен по SSH.

## Обновление OpenClaw

```bash
# Обновить npm пакет
npm update -g openclaw

# Перезапустить
systemctl --user restart openclaw-gateway

# Проверить версию
openclaw --version
```

## Обновление MCP-серверов

```bash
# Gmail MCP
npm update -g @gongrzhe/server-gmail-autoauth-mcp

# Calendar MCP
npm update -g @cocal/google-calendar-mcp

# mcporter
npm update -g mcporter

# ClawhHub CLI
npm update -g clawhub
```

## Логи

### Системные логи (journalctl)

```bash
# Все логи бота
journalctl --user -u openclaw-gateway --since "1 hour ago" --no-pager

# Только ошибки
journalctl --user -u openclaw-gateway -p err --no-pager

# Поиск rate limit ошибок
journalctl --user -u openclaw-gateway | grep "rate_limit"
```

### Логи конфигурации

```bash
# Здоровье конфига
cat /root/.openclaw/logs/config-health.json

# Аудит изменений конфига
cat /root/.openclaw/logs/config-audit.jsonl
```

## Мониторинг

### Проверка что бот жив

```bash
# Процесс
ps aux | grep openclaw

# Порт
ss -tlnp | grep 18789

# Статус systemd
systemctl --user is-active openclaw-gateway
```

### Потребление ресурсов

```bash
# Память
systemctl --user status openclaw-gateway | grep Memory

# CPU
systemctl --user status openclaw-gateway | grep CPU

# Диск
du -sh /root/.openclaw/ /root/obsidian-tasks/ /root/.apple-health-sync/
```

Типичное потребление:
- RAM: ~577 MB (пик 1.1 GB)
- Диск: ~14 MB

## Бэкапы

### Конфиг

OpenClaw автоматически создаёт бэкапы конфига:
```
/root/.openclaw/openclaw.json.bak.1
/root/.openclaw/openclaw.json.bak.2
/root/.openclaw/openclaw.json.bak.3
```

### Workspace

Workspace имеет git-репо (`/root/.openclaw/workspace/.git/`):
```bash
cd /root/.openclaw/workspace
git log --oneline
```

### Задачи

Задачи синхронизируются на Mac через rsync. Mac = бэкап.

## Firewall (UFW)

```
SSH (22)  — ALLOW
HTTP (80) — ALLOW
443       — ALLOW
```

Порт 18789 (gateway) НЕ открыт наружу — только loopback. Это правильно.

## Типичные проблемы

### Rate limit (429)

```
error=⚠️ API rate limit reached
rawError=429 rate_limit_error
30,000 input tokens per minute
```

**Причина:** Anthropic API лимит 30K input tokens/min для данного org.
**Решение:** Подождать минуту. Или поднять лимит в Anthropic Console.

### Бот не отвечает в Telegram

1. Проверить что сервис запущен: `systemctl --user status openclaw-gateway`
2. Проверить логи: `journalctl --user -u openclaw-gateway -n 50`
3. Перезапустить: `systemctl --user restart openclaw-gateway`

### OAuth токены истекли

Gmail/Calendar токены используют refresh_token, но refresh_token тоже истекает (~7 дней для Gmail).

```bash
# Проверить expiry
cat /root/.gmail-mcp/credentials.json | python3 -m json.tool | grep expiry
cat /root/.config/google-calendar-mcp/tokens.json | python3 -m json.tool | grep expiry
```

Если истекли — нужна повторная авторизация через OAuth flow.

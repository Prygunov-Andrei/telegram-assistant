# VPS deployment

Код с production-сервера `72.56.80.247` (Ubuntu 24.04).

## Компоненты

| Папка | Назначение |
|-------|------------|
| `task-webapp/` | FastAPI + HTML — Telegram Mini App для управления задачами |
| `voice-sidecar/` | Python-демон: мониторит `media/inbound/` OpenClaw, транскрибирует голосовые через Groq, удаляет оригинал |
| `systemd/` | Unit-файлы для systemd |
| `Caddyfile` | Конфиг reverse proxy для HTTPS |

## Деплой

### 1. Секреты
```bash
cp .env.example /root/.env
# Заполнить все значения
source /root/.env
```

### 2. Task webapp
```bash
mkdir -p /root/task-webapp
cp -r vps/task-webapp/* /root/task-webapp/
cd /root/task-webapp
pip3 install -r requirements.txt --break-system-packages
```

### 3. Voice sidecar
```bash
mkdir -p /root/voice-sidecar
cp vps/voice-sidecar/main.py /root/voice-sidecar/
apt install -y inotify-tools
```

### 4. systemd
```bash
cp vps/systemd/*.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now task-webapp voice-sidecar
```

### 5. Caddy (HTTPS)
```bash
apt install -y caddy
cp vps/Caddyfile /etc/caddy/Caddyfile
systemctl reload caddy
```

### 6. OpenClaw (отдельно)
OpenClaw — npm-пакет:
```bash
npm install -g openclaw
# Конфиг в /root/.openclaw/openclaw.json (не в этом репо — содержит секреты)
```

## Переменные окружения

См. `.env.example`. Все секреты только в env, не в коде.

## URL Mini App

- Production: `https://hvac-news.online/app/`
- BotFather Menu Button: URL задан через `setChatMenuButton` API

## Управление

```bash
systemctl status task-webapp
systemctl restart task-webapp
journalctl -u task-webapp -f
```

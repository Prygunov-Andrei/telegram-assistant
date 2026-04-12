#!/bin/bash
set -euo pipefail

DAEMON_SESSION="claude-assistant"
DAEMON_SCRIPT="/Users/andrei_prygunov/obsidian/telegram-assistant/scripts/daemon.sh"
LOG="$HOME/.claude/logs/claude-assistant-watchdog.log"

mkdir -p "$HOME/.claude/logs"

# Ротация лога: оставляем последние 1000 строк если > 5000
if [ -f "$LOG" ]; then
  LINES=$(wc -l < "$LOG" | tr -d ' ')
  if [ "$LINES" -gt 5000 ]; then
    tail -1000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
  fi
fi

# Проверка tmux-сессии
if ! tmux has-session -t "$DAEMON_SESSION" 2>/dev/null; then
  echo "$(date): tmux session '$DAEMON_SESSION' not found, restarting..." >> "$LOG"
  bash "$DAEMON_SCRIPT"
  exit 0
fi

# Проверка процесса Python
if ! pgrep -f 'src.main' > /dev/null 2>&1; then
  echo "$(date): src.main process dead, restarting..." >> "$LOG"
  bash "$DAEMON_SCRIPT"
  exit 0
fi

# Каждые 5 минут — healthcheck через Telegram API
MINUTE=$(date +%M)
if [ $((MINUTE % 5)) -eq 0 ]; then
  ENV_FILE="/Users/andrei_prygunov/obsidian/telegram-assistant/config/.env"
  if [ -f "$ENV_FILE" ]; then
    T=$(grep TELEGRAM_BOT_TOKEN "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
    if [ -n "$T" ]; then
      RESULT=$(curl -s -m 5 "https://api.telegram.org/bot${T}/getMe" | python3 -c "import sys,json; print(1 if json.load(sys.stdin).get('ok') else 0)" 2>/dev/null || echo 0)
      if [ "$RESULT" -eq 0 ]; then
        echo "$(date): Telegram API check failed" >> "$LOG"
      fi
    fi
  fi
fi

#!/bin/bash
set -euo pipefail

DAEMON_SESSION="claude-assistant"
WORK_DIR="/Users/andrei_prygunov/obsidian"
PROJECT_ROOT="/Users/andrei_prygunov/obsidian/telegram-assistant"
LOG="$HOME/.claude/logs/claude-assistant-watchdog.log"

mkdir -p "$HOME/.claude/logs"
echo "$(date): Starting Claude assistant daemon..." >> "$LOG"

# Убиваем старую сессию
tmux kill-session -t "$DAEMON_SESSION" 2>/dev/null || true
sleep 1

# Запускаем в tmux с caffeinate (не даёт маку уснуть)
tmux new-session -d -s "$DAEMON_SESSION" -c "$WORK_DIR" \
  "caffeinate -i bash $PROJECT_ROOT/scripts/run.sh"

sleep 3

# Ставим статус бота и уведомляем владельца
ENV_FILE="$PROJECT_ROOT/config/.env"
if [ -f "$ENV_FILE" ]; then
  T=$(grep TELEGRAM_BOT_TOKEN "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
  if [ -n "$T" ]; then
    curl -s "https://api.telegram.org/bot${T}/setMyDescription" \
      -d 'description=Claude Assistant (Anthropic API)' > /dev/null 2>&1 || true
    curl -s "https://api.telegram.org/bot${T}/sendMessage" \
      -d "chat_id=435926703" \
      -d "text=Claude Assistant (re)started at $(date +%H:%M)" > /dev/null 2>&1 || true
  fi
fi

echo "$(date): Claude assistant daemon started (tmux: $DAEMON_SESSION)" >> "$LOG"

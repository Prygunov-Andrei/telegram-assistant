#!/usr/bin/env bash
# sync-tasks: двухсторонняя синхронизация Mac ↔ VPS
# Сначала pull (забрать изменения бота), потом push (отправить свои)
# Безопасно: rsync --update синхронизирует только более новые файлы

set -euo pipefail

VPS="root@72.56.80.247"
SSH_KEY="$HOME/.ssh/id_ed25519_server"
LOCAL_ROOT="$HOME/obsidian"
REMOTE_ROOT="/root/obsidian-tasks"

TASK_DIRS=(
  "april/ЗАДАЧИ"
  "avgust/ЗАДАЧИ"
  "avgust/ERP_Avgust/ЗАДАЧИ"
  "books/ЗАДАЧИ"
  "deutsch/ЗАДАЧИ"
  "gt24realestate.de/ЗАДАЧИ"
  "kaz_nach_berlin/ЗАДАЧИ"
  "life/ЗАДАЧИ"
  "life/ЗАДАЧИ_RECURRING"
)

# 1. Pull: VPS → Mac (забрать что бот наделал)
for dir in "${TASK_DIRS[@]}"; do
  rsync -az --update \
    -e "ssh -i $SSH_KEY -o ConnectTimeout=5" \
    "$VPS:$REMOTE_ROOT/$dir/" \
    "$LOCAL_ROOT/$dir/" 2>/dev/null
done

rsync -az --update \
  -e "ssh -i $SSH_KEY -o ConnectTimeout=5" \
  "$VPS:$REMOTE_ROOT/ДАШБОРД.md" \
  "$LOCAL_ROOT/ДАШБОРД.md" 2>/dev/null

# 2. Push: Mac → VPS (отправить свои изменения)
cd "$LOCAL_ROOT"
rsync -az --update --relative \
  -e "ssh -i $SSH_KEY -o ConnectTimeout=5" \
  "${TASK_DIRS[@]}" \
  "./ДАШБОРД.md" \
  "$VPS:$REMOTE_ROOT/" 2>/dev/null

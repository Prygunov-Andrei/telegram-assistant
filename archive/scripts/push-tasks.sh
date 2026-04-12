#!/usr/bin/env bash
# push-tasks: Mac → VPS (отправить изменения задач на сервер)
# Использование: bash scripts/push-tasks.sh

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

echo "=== PUSH: Mac → VPS ==="
echo ""

cd "$LOCAL_ROOT"

# Sync task directories
rsync -avz --delete --relative \
  -e "ssh -i $SSH_KEY" \
  "${TASK_DIRS[@]}" \
  "./ДАШБОРД.md" \
  "$VPS:$REMOTE_ROOT/"

echo ""
echo "Done. Tasks pushed to VPS."

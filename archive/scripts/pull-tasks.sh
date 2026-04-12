#!/usr/bin/env bash
# pull-tasks: VPS → Mac (забрать изменения задач с сервера)
# Использование: bash scripts/pull-tasks.sh

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

echo "=== PULL: VPS → Mac ==="
echo ""

for dir in "${TASK_DIRS[@]}"; do
  echo "Pulling $dir..."
  rsync -avz --delete \
    -e "ssh -i $SSH_KEY" \
    "$VPS:$REMOTE_ROOT/$dir/" \
    "$LOCAL_ROOT/$dir/"
done

# Dashboard
echo "Pulling ДАШБОРД.md..."
rsync -avz \
  -e "ssh -i $SSH_KEY" \
  "$VPS:$REMOTE_ROOT/ДАШБОРД.md" \
  "$LOCAL_ROOT/ДАШБОРД.md"

echo ""
echo "Done. Tasks pulled from VPS to Obsidian."

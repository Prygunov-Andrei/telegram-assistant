#!/usr/bin/env bash
# sync-tasks-git: двухсторонняя синхронизация через GitHub
# Mac (Obsidian) ↔ GitHub ↔ VPS (бот)
set -euo pipefail

GIT_REPO="$HOME/obsidian-tasks-git"
OBSIDIAN="$HOME/obsidian"
# Load secrets from ~/.github-tasks-sync.env (not in git). Format:
#   GITHUB_USER=Prygunov-Andrei
#   GITHUB_PAT=ghp_xxxxx
#   GIT_REPO_NAME=obsidian-tasks
if [ -f "$HOME/.github-tasks-sync.env" ]; then
  source "$HOME/.github-tasks-sync.env"
fi
GITHUB_USER="${GITHUB_USER:-Prygunov-Andrei}"
GIT_REPO_NAME="${GIT_REPO_NAME:-obsidian-tasks}"
GITHUB_URL="https://${GITHUB_USER}:${GITHUB_PAT}@github.com/${GITHUB_USER}/${GIT_REPO_NAME}.git"

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

# 1. Clone or pull git repo
if [ ! -d "$GIT_REPO/.git" ]; then
  git clone "$GITHUB_URL" "$GIT_REPO"
else
  cd "$GIT_REPO"
  git pull --ff-only origin master 2>/dev/null || true
fi

# 2. Pull: GitHub → Obsidian (бот → мак)
for dir in "${TASK_DIRS[@]}"; do
  mkdir -p "$OBSIDIAN/$dir"
  rsync -a --update "$GIT_REPO/$dir/" "$OBSIDIAN/$dir/" 2>/dev/null || true
done
rsync -a --update "$GIT_REPO/ДАШБОРД.md" "$OBSIDIAN/ДАШБОРД.md" 2>/dev/null || true

# 3. Push: Obsidian → GitHub (мак → бот)
for dir in "${TASK_DIRS[@]}"; do
  mkdir -p "$GIT_REPO/$dir"
  rsync -a --update "$OBSIDIAN/$dir/" "$GIT_REPO/$dir/" 2>/dev/null || true
done
rsync -a --update "$OBSIDIAN/ДАШБОРД.md" "$GIT_REPO/ДАШБОРД.md" 2>/dev/null || true

# 4. Commit & push if changed
cd "$GIT_REPO"
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -m "sync from Mac: $(date +%Y-%m-%d_%H:%M)" --quiet
  git push origin master --quiet 2>/dev/null
fi

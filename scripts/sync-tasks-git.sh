#!/usr/bin/env bash
# sync-tasks-git: двухсторонняя синхронизация через GitHub
# Mac (Obsidian) ↔ GitHub ↔ VPS (бот)
set -euo pipefail

GIT_REPO="$HOME/obsidian-tasks-git"
OBSIDIAN="$HOME/obsidian"
OBSIDIAN_VAULT="$OBSIDIAN/_ЗАДАЧИ"
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

# Пути относительно vault root (_ЗАДАЧИ/) и зеркала
TASK_DIRS=(
  "задачи/life"
  "задачи/realestate"
  "задачи/avgust"
  "задачи/avgust-erp"
  "задачи/april"
  "задачи/deutsch"
  "задачи/books"
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
  mkdir -p "$OBSIDIAN_VAULT/$dir"
  rsync -a --update "$GIT_REPO/$dir/" "$OBSIDIAN_VAULT/$dir/" 2>/dev/null || true
done
rsync -a --update "$GIT_REPO/ДАШБОРД.md" "$OBSIDIAN_VAULT/ДАШБОРД.md" 2>/dev/null || true

# 2b. Dedupe: if the same filename exists both in a task dir AND in its
# `archive/` subfolder, the archive version wins (bot explicitly moved it
# there). Remove the active copy from both Obsidian and GIT_REPO so the
# next rsync push doesn't resurrect it. This is the only safe way to
# propagate bot-side archive moves given rsync's no-delete semantics.
dedupe_against_archive() {
  local root=$1
  for dir in "${TASK_DIRS[@]}"; do
    local full="$root/$dir"
    [ -d "$full/archive" ] || continue
    for archived in "$full/archive/"*.md; do
      [ -f "$archived" ] || continue
      local base
      base=$(basename "$archived")
      if [ -f "$full/$base" ]; then
        rm -f "$full/$base"
      fi
    done
  done
}
dedupe_against_archive "$OBSIDIAN_VAULT"
dedupe_against_archive "$GIT_REPO"

# 3. Push: Obsidian → GitHub (мак → бот)
for dir in "${TASK_DIRS[@]}"; do
  mkdir -p "$GIT_REPO/$dir"
  rsync -a --update "$OBSIDIAN_VAULT/$dir/" "$GIT_REPO/$dir/" 2>/dev/null || true
done
rsync -a --update "$OBSIDIAN_VAULT/ДАШБОРД.md" "$GIT_REPO/ДАШБОРД.md" 2>/dev/null || true

# 4. Commit & push if changed
cd "$GIT_REPO"
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -m "sync from Mac: $(date +%Y-%m-%d_%H:%M)" --quiet
  git push origin master --quiet 2>/dev/null
fi

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

# Разделы НЕ хардкодятся — обнаруживаются автоматически как папки задачи/*/
# (единый источник истины — файловая структура). TASK_DIRS вычисляется ниже,
# после синхронизации зеркала.

# 0. Regenerate dashboard from current task statuses
#    (статусы могут меняться вручную в Obsidian — выпадающий список через
#    Metadata Menu пишет в frontmatter, но дашборд сам не обновляется)
PYTHONPATH="$OBSIDIAN_VAULT/telegram-assistant/vps/task-webapp" \
  python3 -c "from vault import VaultAdapter; VaultAdapter('$OBSIDIAN_VAULT').regenerate_dashboard()" 2>/dev/null || true

echo "[$(date '+%F %T')] sync start"

# 1. Clone, or hard-sync local mirror to origin.
#    origin/master — единственный источник истины для БАЗЫ: после reset --hard
#    локальное зеркало никогда не расходится с GitHub, поэтому push (шаг 4)
#    всегда fast-forward. Именно отсутствие этого приводило к split-brain
#    (pull --ff-only молча падал, push молча отклонялся → данные застревали).
if [ ! -d "$GIT_REPO/.git" ]; then
  git clone "$GITHUB_URL" "$GIT_REPO"
  cd "$GIT_REPO"
else
  cd "$GIT_REPO"
  git remote set-url origin "$GITHUB_URL"
  git fetch origin master
  git reset --hard origin/master
fi

# 1b. Авто-обнаружение разделов = папки задачи/*/.
list_sections() {            # $1 = базовый каталог → печатает имена папок-разделов
  [ -d "$1/задачи" ] || return 0
  for p in "$1"/задачи/*/; do [ -d "$p" ] && basename "$p"; done
}
# Раздел, который есть в зеркале, но пропал в Obsidian (удалён/переименован
# пользователем) → удаляем из зеркала, чтобы удаление уехало в GitHub и Mini App.
# Webapp новые РАЗДЕЛЫ не создаёт, поэтому «лишний» раздел в зеркале = удалённый.
while IFS= read -r sec; do
  if [ -n "$sec" ] && [ ! -d "$OBSIDIAN_VAULT/задачи/$sec" ]; then
    echo "[$(date '+%F %T')] раздел удалён в Obsidian → убираю из зеркала: $sec"
    rm -rf "${GIT_REPO:?}/задачи/$sec"
  fi
done < <(list_sections "$GIT_REPO")

# TASK_DIRS = текущие разделы Obsidian (авторитетный набор папок)
TASK_DIRS=()
while IFS= read -r sec; do
  [ -n "$sec" ] && TASK_DIRS+=("задачи/$sec")
done < <(list_sections "$OBSIDIAN_VAULT")

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
  if git push origin master; then
    echo "[$(date '+%F %T')] push OK ($(git rev-parse --short HEAD))"
  else
    echo "[$(date '+%F %T')] push FAILED" >&2
  fi
else
  echo "[$(date '+%F %T')] nothing to sync"
fi

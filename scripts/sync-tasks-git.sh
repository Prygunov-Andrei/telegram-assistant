#!/usr/bin/env bash
# sync-tasks-git: двухсторонняя синхронизация через GitHub
# Mac (Obsidian) ↔ GitHub ↔ VPS (бот)
set -euo pipefail

# Пути можно переопределить через окружение (используется в тестах,
# scripts/test-sync-delete.sh указывает их на локальный bare-репозиторий).
GIT_REPO="${GIT_REPO:-$HOME/obsidian-tasks-git}"
OBSIDIAN="${OBSIDIAN:-$HOME/obsidian}"
OBSIDIAN_VAULT="${OBSIDIAN_VAULT:-$OBSIDIAN/_ЗАДАЧИ}"
# Load secrets from ~/.github-tasks-sync.env (not in git). Format:
#   GITHUB_USER=Prygunov-Andrei
#   GITHUB_PAT=ghp_xxxxx
#   GIT_REPO_NAME=obsidian-tasks
if [ -f "$HOME/.github-tasks-sync.env" ]; then
  source "$HOME/.github-tasks-sync.env"
fi
GITHUB_USER="${GITHUB_USER:-Prygunov-Andrei}"
GIT_REPO_NAME="${GIT_REPO_NAME:-obsidian-tasks}"
GITHUB_PAT="${GITHUB_PAT:-}"
# GITHUB_URL можно задать заранее (тесты подставляют путь к локальному bare-репо);
# иначе собираем авторизованный URL GitHub из PAT.
GITHUB_URL="${GITHUB_URL:-https://${GITHUB_USER}:${GITHUB_PAT}@github.com/${GITHUB_USER}/${GIT_REPO_NAME}.git}"

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
OLD_HEAD=""
NEW_HEAD=""
REMOTE_DELETED=""
if [ ! -d "$GIT_REPO/.git" ]; then
  git clone "$GITHUB_URL" "$GIT_REPO"
  cd "$GIT_REPO"
else
  cd "$GIT_REPO"
  git remote set-url origin "$GITHUB_URL"
  OLD_HEAD=$(git rev-parse HEAD 2>/dev/null || echo "")
  git fetch origin master
  git reset --hard origin/master
  NEW_HEAD=$(git rev-parse HEAD 2>/dev/null || echo "")
  # Файлы задач, удалённые на GitHub с прошлой синхронизации. Сюда попадает
  # удаление через Mini App (кнопка «Удалить» = git rm + commit + push).
  # diff-filter=D берёт ТОЛЬКО то, что git явно зафиксировал как удаление —
  # никаких догадок по «есть/нет файла». Архивирование (move в archive/) сюда
  # тоже попадает как удаление активного пути и обрабатывается корректно.
  if [ -n "$OLD_HEAD" ] && [ -n "$NEW_HEAD" ] && [ "$OLD_HEAD" != "$NEW_HEAD" ]; then
    REMOTE_DELETED=$(git -c core.quotePath=false diff --name-only --diff-filter=D \
      "$OLD_HEAD" "$NEW_HEAD" -- 'задачи/' 2>/dev/null || true)
  fi
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

# 2a. Применяем удаления, сделанные на GitHub (Mini App «Удалить»), к Obsidian.
#     rsync (шаги 2–3) работает как --update и НИКОГДА не удаляет, поэтому без
#     этого шага ещё живущая в Obsidian копия за один цикл (шаг 3 → 4) воскрешает
#     задачу обратно в GitHub и Mini App. Здесь — единственный безопасный способ
#     протащить удаление: берём ровно те файлы, которые git пометил удалёнными.
if [ -n "$REMOTE_DELETED" ]; then
  while IFS= read -r relpath; do
    [ -n "$relpath" ] || continue
    obsfile="$OBSIDIAN_VAULT/$relpath"
    [ -f "$obsfile" ] || continue
    # Защита от потери данных: если файл правили в Obsidian после прошлой
    # синхронизации (содержимое разошлось с версией на момент OLD_HEAD) — удаление
    # с remote НЕ применяем, локальная правка важнее (файл уедет обратно как новый).
    if git -C "$GIT_REPO" cat-file -e "${OLD_HEAD}:${relpath}" 2>/dev/null \
       && ! git -C "$GIT_REPO" show "${OLD_HEAD}:${relpath}" 2>/dev/null | cmp -s - "$obsfile"; then
      echo "[$(date '+%F %T')] $relpath удалён на GitHub, но изменён в Obsidian — оставляю"
      continue
    fi
    rm -f "$obsfile"
    echo "[$(date '+%F %T')] удалено в Mini App → убираю из Obsidian: $relpath"
  done <<< "$REMOTE_DELETED"
fi

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

#!/usr/bin/env bash
# Регресс-тест распространения удалений для sync-tasks-git.sh.
#
# Сценарий A: Mini App жмёт «Удалить» → задача удаляется на GitHub (git rm).
#   После Mac-синхронизации она должна исчезнуть из Obsidian и НЕ воскреснуть
#   на следующем цикле (ни в Obsidian, ни обратно на GitHub).
# Сценарий B: та же задача удалена на GitHub, но локально (в Obsidian) её правили
#   после прошлой синхронизации → удаление НЕ применяется (правка важнее).
#
# Запускается без сети и без секретов: «GitHub» — локальный bare-репозиторий.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC="$SCRIPT_DIR/sync-tasks-git.sh"

SANDBOX="$(mktemp -d)"
trap 'rm -rf "$SANDBOX"' EXIT

ORIGIN="$SANDBOX/origin.git"   # роль GitHub
MIRROR="$SANDBOX/mirror"       # $HOME/obsidian-tasks-git (локальное зеркало)
VAULT="$SANDBOX/vault"         # $OBSIDIAN_VAULT (Obsidian на Mac)
FAKEHOME="$SANDBOX/home"       # изоляция от реального ~/.github-tasks-sync.env
WORK="$SANDBOX/work"           # рабочий клон, имитирующий записи Mini App

mkdir -p "$FAKEHOME" "$VAULT"

fail() { echo "FAIL: $1"; exit 1; }

gitw() { git -C "$WORK" -c user.email=t@t -c user.name=t "$@"; }

run_sync() {
  HOME="$FAKEHOME" \
  GIT_REPO="$MIRROR" \
  OBSIDIAN_VAULT="$VAULT" \
  GITHUB_URL="$ORIGIN" \
  GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=t@t \
  GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=t@t \
  bash "$SYNC" >/dev/null 2>&1
}

write_task() {  # $1=path $2=id $3=title
  cat > "$1" <<EOF
---
task_id: $2
title: $3
status: todo
project: test
---
# $3
EOF
}

# ── Seed «GitHub» (origin) двумя задачами ────────────────────────────────
git init -q --bare "$ORIGIN"
git symbolic-ref HEAD refs/heads/master --short >/dev/null 2>&1 || true
git -C "$ORIGIN" symbolic-ref HEAD refs/heads/master

git clone -q "$ORIGIN" "$WORK"
git -C "$WORK" symbolic-ref HEAD refs/heads/master
mkdir -p "$WORK/задачи/test"
printf -- '---\nname: Тест\norder: 1\n---\n' > "$WORK/задачи/test/_index.md"
write_task "$WORK/задачи/test/5-foo.md" 5 Foo
write_task "$WORK/задачи/test/6-bar.md" 6 Bar
printf '# dashboard\n' > "$WORK/ДАШБОРД.md"
gitw add -A
gitw commit -q -m seed
gitw push -q origin master

# Имитируем уже синхронизированный Mac: те же файлы лежат в Obsidian.
cp -R "$WORK/задачи" "$VAULT/"
cp "$WORK/ДАШБОРД.md" "$VAULT/"

# ── Run 1: первичная синхронизация (создаёт зеркало) ─────────────────────
run_sync
[ -f "$VAULT/задачи/test/5-foo.md" ] || fail "run1: 5-foo.md пропал из vault"
[ -f "$VAULT/задачи/test/6-bar.md" ] || fail "run1: 6-bar.md пропал из vault"
echo "ok: run1 — зеркало создано, обе задачи на месте"

# ── Сценарий A: Mini App удаляет задачу #5 (git rm на origin) ─────────────
rm -rf "$WORK"; git clone -q "$ORIGIN" "$WORK"
gitw rm -q "задачи/test/5-foo.md"
gitw commit -q -m "delete: task 5"
gitw push -q origin master

run_sync
[ -f "$VAULT/задачи/test/5-foo.md" ] && fail "run2: 5-foo.md воскрес (не удалён из vault)"
[ -f "$VAULT/задачи/test/6-bar.md" ] || fail "run2: 6-bar.md удалён по ошибке"
echo "ok: run2 — удаление доехало до Obsidian, соседняя задача цела"

# ── Run 3: изменений на remote нет — удаление должно ЗАЛИПНУТЬ ────────────
run_sync
[ -f "$VAULT/задачи/test/5-foo.md" ] && fail "run3: 5-foo.md воскрес в vault"
rm -rf "$WORK"; git clone -q "$ORIGIN" "$WORK"
[ -f "$WORK/задачи/test/5-foo.md" ] && fail "run3: 5-foo.md воскрес на origin (был re-push)"
echo "ok: run3 — удаление залипло везде (vault + GitHub)"

# ── Сценарий B: удалено на GitHub, но локально правилось → не трогаем ─────
# #6 правим в Obsidian (несинхронизированная локальная правка), затем удаляем
# его на origin. Удаление НЕ должно применяться — локальная правка важнее.
printf '\n- локальная правка до синка\n' >> "$VAULT/задачи/test/6-bar.md"
rm -rf "$WORK"; git clone -q "$ORIGIN" "$WORK"
gitw rm -q "задачи/test/6-bar.md"
gitw commit -q -m "delete: task 6"
gitw push -q origin master

run_sync
[ -f "$VAULT/задачи/test/6-bar.md" ] || fail "run4: 6-bar.md удалён, несмотря на локальную правку"
grep -q "локальная правка" "$VAULT/задачи/test/6-bar.md" || fail "run4: локальная правка потеряна"
echo "ok: run4 — конфликт удаление-vs-правка решён в пользу правки"

echo "PASS"

# Archive

Исторический код и старая документация. НЕ используется в работе.

Текущая система — на VPS (см. `vps/` и `docs/openclaw/`).

## Содержимое

| Папка | Что было |
|-------|----------|
| `scripts/` | Старые скрипты запуска (daemon.sh, run.sh, watchdog), OAuth-скрипт, rsync-скрипты pull/push/sync (заменены на `scripts/sync-tasks-git.sh`) |
| `tests/` | 17 unit-тестов для старого Python-бота в `src/` |
| `docs/` | Старая документация: architecture.md, dev-guide.md, runbook.md (заменены на `docs/openclaw/*`) |

## Зачем храним

Для истории и референса. Могут быть полезны идеи (например, паттерны из `src/memory/vault_adapter.py`).

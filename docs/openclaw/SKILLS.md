# Skills (навыки OpenClaw)

Skills — это расширения workspace, которые добавляют агенту специализированные знания и инструкции. Хранятся в `/root/.openclaw/workspace/skills/`.

## Установленные skills

### 1. tasks (кастомный)

**Файл:** `skills/tasks/SKILL.md`

Система управления задачами в Obsidian-формате. Задачи хранятся в `/root/obsidian-tasks/`.

**9 проектов:**

| Slash-команда | Папка | Описание |
|---------------|-------|----------|
| `/life` | `life/ЗАДАЧИ/` | Личные задачи |
| `/gt24` | `gt24realestate.de/ЗАДАЧИ/` | Недвижимость GT24 |
| `/avgust` | `avgust/ЗАДАЧИ/` | Компания Август |
| `/erp` | `avgust/ERP_Avgust/ЗАДАЧИ/` | Django ERP |
| `/deutsch` | `deutsch/ЗАДАЧИ/` | Немецкий язык |
| `/april` | `april/ЗАДАЧИ/` | Агентство April |
| `/books` | `books/ЗАДАЧИ/` | Книги, фильмы |
| `/kaz` | `kaz_nach_berlin/ЗАДАЧИ/` | Сайт Kaz nach Berlin |
| `/all` | все папки | Сводка по всем проектам |

**Формат задачи:** Markdown с YAML frontmatter:

```yaml
---
task_id: 185
title: Название задачи
status: todo          # todo | in_progress | done | cancelled
type: org             # org | dev | research
project: life
created: 2025-04-01
due: 2025-04-15       # опционально
assignee: null        # опционально
tags: []
---
```

**Повторяющиеся задачи:** `life/ЗАДАЧИ_RECURRING/` (R001-R100)

**Дашборд:** `/root/obsidian-tasks/ДАШБОРД.md`

---

### 2. apple-health-sync (v0.8.1)

**Файл:** `skills/apple-health-sync/SKILL.md`
**Источник:** ClawhHub (clawhub.ai)

Синхронизация данных Apple Health с iPhone через приложение "Health Sync for OpenClaw".

**Протокол:** v5 (X25519-ChaCha20Poly1305, Ed25519)
**Хранение:** SQLite (`/root/.apple-health-sync/health_data.db`)

**Доступные метрики:**
- Активность: шаги, калории, расстояние, упражнения, этажи
- Сердце: пульс, HRV, SpO2, resting HR, walking HR, VO2max
- Сон: фазы (REM, core, deep), время в кровати
- Тело: вес, ИМТ, жир

**Скрипты:**

```bash
# Синхронизация данных
python3 /root/.openclaw/workspace/skills/apple-health-sync/scripts/fetch_health_data.py

# Создание отчёта
python3 /root/.openclaw/workspace/skills/apple-health-sync/scripts/create_data_summary.py --period daily

# Отвязка устройства
python3 /root/.openclaw/workspace/skills/apple-health-sync/scripts/unlink_device.py
```

**Текущие данные (3 дня):**

| Дата | Шаги | Акт. ккал | Пульс покоя | VO2max |
|------|-------|-----------|-------------|--------|
| 08.04 | 7 510 | 466 | 88 | 29.03 |
| 09.04 | 16 112 | 875 | 89 | 28.8 |
| 10.04 | 3 087 | 296 | 84 | — |

---

### 3. healthkit-sync (v1.0.0)

**Файл:** `skills/healthkit-sync/SKILL.md`
**Источник:** ClawhHub

Справочный skill для CLI-утилиты `healthsync` (Mac-only). На VPS используется как reference — основная работа через apple-health-sync.

---

## Кастомные workspace файлы

### MEMORY.md

Долгосрочная память агента. Содержит:
- Описание системы задач и синхронизации
- Правило: "создавать задачи сразу в `/root/obsidian-tasks/`"
- Правило: "если Андрей говорит 'обновил задачи' — перечитать файлы"

### TOOLS.md

Справка по доступным инструментам:
- Файловая система задач (пути, структура)
- Правила синхронизации (rsync --update, двухсторонняя)
- SSH: 72.56.80.247
- TTS: ElevenLabs Ivan (cgSgspJ2msm6clMCkdW9)
- Timezone: Europe/Berlin

### nutrition/PROFILE.md

Профиль нутрициолога:
- Цель: -1 кг/месяц (дефицит 250 ккал)
- Вес: 100 кг, рост 185 см, возраст 47
- TDEE: 2793 ккал, целевой: 2543 ккал
- Макросы: Б 180г, Ж 79г, У 278г

### memory/ (дневные записи)

- `YYYY-MM-DD.md` — утро (подъём, вес), питание (КБЖУ по приёмам)
- `shopping-YYYY-MM-DD.md` — покупки с ценами и КБЖУ
- `shopping-registry.md` — реестр часто покупаемых продуктов
- `dreams.md` — реестр снов с анализом

## Установка новых skills

```bash
# Через ClawhHub
clawhub install <skill-name>

# Вручную
mkdir -p /root/.openclaw/workspace/skills/<name>/
# создать SKILL.md с frontmatter
```

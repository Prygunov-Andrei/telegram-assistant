# Руководство пользователя

Система управления задачами: **Telegram-бот + Mini App + Obsidian**.

## 1. Что это такое

```
┌────────────┐    ┌──────────────┐    ┌──────────┐
│  Telegram  │◄──►│  VPS (бот +  │◄──►│  GitHub  │◄──►│ Mac (Obsidian) │
│  (чат + MA)│    │   Mini App)  │    │  (задачи)│    │                │
└────────────┘    └──────────────┘    └──────────┘    └────────────────┘
```

- **Telegram-бот** (`@my_claude_prygunov_bot`) — пишете ему текст или голос, он отвечает, создаёт/меняет задачи
- **Mini App** — кнопка "Задачи" внизу чата бота, открывает визуальный интерфейс
- **Obsidian на Mac** — задачи лежат в `~/obsidian/*/ЗАДАЧИ/` как markdown-файлы
- **Синхронизация** — автоматическая каждые 2 минуты через GitHub

## 2. Ежедневное использование

### 2.1 Посмотреть задачи на сегодня
1. Открой бота в Telegram
2. Нажми кнопку **"Задачи"** внизу
3. В левой панели клик **"Сегодня!"**
4. Видишь: Просрочено (красным), На сегодня, В работе

### 2.2 Создать задачу голосом
1. В Mini App смахни слайдер внизу вправо на **"ЗАПИСЬ!"**
2. Тапни — запись пошла
3. Наговори
4. Тапни ещё раз — транскрипция ~0.3 сек
5. Откроется форма с текстом, правь, нажми **"Создать"**

### 2.3 Отредактировать задачу
1. Клик на строку задачи в таблице
2. Открылась модалка: название, статус, дата, исполнитель, теги, содержание
3. Меняй что надо → **"Сохранить"**

### 2.4 Удалить (архивировать) задачу
**Свайп влево** → красное "Архивировать" → подтверди. Файл перемещается в `*/ЗАДАЧИ/archive/`, не удаляется.

### 2.5 Отменить задачу
**Свайп вправо** → оранжевое "Отменить" → подтверди. Статус становится `cancelled`.

### 2.6 Поменять теги (подразделы)
1. Открой задачу
2. Поле **"Теги"**: синие чипы — текущие (крестик удалит), ниже серые — существующие (клик добавит)
3. Поле ввода — для нового тега → кнопка `+`
4. **"Сохранить"**

## 3. Синхронизация

### Автоматически
Каждые **2 минуты** cron на маке тянет изменения из GitHub в Obsidian.

### Вручную из Mini App
В нижнем слайдере:
- **ПУЛ** — получить с Mac (git pull)
- **ПУШ** — отправить на Mac (git push + регенерация дашборда)

### Если задачи не появились
1. Проверь что бот реально их создал: `ssh root@72.56.80.247 "cd /root/obsidian-tasks && git log --oneline -5"`
2. В Mini App нажми **ПУШ** вручную
3. На Mac запусти: `bash ~/obsidian/telegram-assistant/scripts/sync-tasks-git.sh`

## 4. Работа с ботом в чате

### Команды
- `/sync` — бот делает git push → GitHub → Mac
- `/all` — сводка по всем проектам
- `/life`, `/erp`, `/august`, `/april`, `/gt24`, `/books`, `/deutsch`, `/kaz` — задачи проекта

### Голосовые сообщения
Отправь голосовое → через 1-2 сек оригинал удалится, появится текст "🎤 ...".
Текст обрабатывается ботом как обычное сообщение.

### Запросы бот понимает
- "создай задачу в life купить молоко завтра"
- "покажи задачи на сегодня"
- "закрой задачу 185"
- "перенеси 200 на понедельник"

## 5. Obsidian на Mac

### Где задачи
- `~/obsidian/life/ЗАДАЧИ/100-buy-milk.md` и т.д.
- Архив: `~/obsidian/life/ЗАДАЧИ/archive/`
- Recurring: `~/obsidian/life/ЗАДАЧИ_RECURRING/R001-*.md`
- Дашборд: `~/obsidian/ДАШБОРД.md`

### Формат файла
```yaml
---
task_id: 100
title: Купить молоко
status: todo          # todo | in_progress | done | cancelled
type: org             # org | dev | research
project: life
created: 2026-04-10
due: 2026-04-12       # опционально
assignee: null        # опционально
tags: [shopping]
---
# Заголовок
Содержание задачи в markdown
```

## 6. Troubleshooting

### Бот не отвечает
```bash
ssh root@72.56.80.247
systemctl --user status openclaw-gateway
systemctl --user restart openclaw-gateway
```

### Задачи не синхронизируются
```bash
# Проверить cron на Mac
crontab -l | grep sync-tasks

# Логи синхронизации
tail -20 /tmp/sync-tasks-git.log

# Ручной запуск
bash ~/obsidian/telegram-assistant/scripts/sync-tasks-git.sh
```

### Mini App не грузится / показывает старую версию
1. Telegram → Настройки → Данные и память → Очистить кеш
2. Или: убить приложение Telegram (свайп вверх в карточках)
3. Открыть заново

### Голос не транскрибируется
1. Разреши микрофон: Настройки iPad → Telegram → Микрофон
2. Проверь sidecar: `ssh root@72.56.80.247 "systemctl --user status voice-sidecar"`

### Rate limit от Anthropic
Бот делит лимит 30K tokens/min с Claude Code. Если работаешь с Claude Code — бот может временно молчать. Решение: подождать минуту.

## 7. Для себя (admin)

### Сервисы на VPS
```bash
ssh -i ~/.ssh/id_ed25519_server root@72.56.80.247

# Основные сервисы
systemctl --user status openclaw-gateway
systemctl status task-webapp
systemctl --user status voice-sidecar

# Логи
journalctl --user -u openclaw-gateway -f
journalctl -u task-webapp -n 100 --no-pager

# Рестарт
systemctl --user restart openclaw-gateway
systemctl restart task-webapp
```

### Бэкапы
- GitHub — автоматически
- Mac — автоматически через rsync
- VPS tarball: `/root/backups/tasks-*.tar.gz` (создавать вручную перед рискованными операциями)

### Конфиг OpenClaw
```bash
openclaw config get agents.defaults.model.primary
openclaw config set agents.defaults.model.primary "openai/gpt-5.2"
systemctl --user restart openclaw-gateway
```

### Документация
- `docs/openclaw/ARCHITECTURE.md` — устройство бота
- `docs/openclaw/CONFIG.md` — все параметры
- `docs/openclaw/OPERATIONS.md` — управление
- `vps/README.md` — деплой с нуля

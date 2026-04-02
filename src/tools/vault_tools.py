from __future__ import annotations

from pathlib import Path

from src.memory.vault_adapter import VaultAdapter, COMMAND_PATHS
from src.tools.registry import ToolRegistry
from src.utils.approval import ApprovalManager


def _require_approval(approval: ApprovalManager, action: str, payload: dict, description: str) -> str:
    token = approval.register(action=action, payload=payload, description=description)
    return (
        f"Требуется подтверждение:\n{description}\n\n"
        f"Для подтверждения вызови approve_vault_action с токеном: {token}"
    )


def register_vault_tools(registry: ToolRegistry, vault: VaultAdapter, approval: ApprovalManager, timezone: str = "Europe/Berlin") -> None:

    # ── Read-only tools (без подтверждения) ───────────────────

    def list_tasks(project: str) -> str:
        command = project if project.startswith("/") else f"/{project}"
        sections = vault.list_open_tasks(command)
        chunks = []
        for title in ("С дедлайном", "Делегировано", "Когда-нибудь"):
            items = sections.get(title, [])
            if not items:
                continue
            chunks.append(f"**{title}:**\n" + "\n".join(f"- {item}" for item in items))
        return "\n\n".join(chunks) if chunks else "Открытых задач нет."

    registry.register(
        name="list_tasks",
        description="Показать открытые задачи по проекту. Проекты: life, gt24, avgust, erp, deutsch, april, books, kaz, daemon, assistant.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Название проекта (без слэша): life, gt24, avgust, erp, deutsch, april, books, kaz, daemon, assistant",
                },
            },
            "required": ["project"],
        },
        handler=list_tasks,
    )

    def get_all_projects_summary() -> str:
        counts = vault.project_counts()
        if not counts:
            return "Открытых задач не найдено."
        lines = [f"{cmd}: {count}" for cmd, count in sorted(counts.items())]
        total = sum(counts.values())
        lines.append(f"\nВсего: {total}")
        return "\n".join(lines)

    registry.register(
        name="get_all_projects_summary",
        description="Показать количество открытых задач по всем проектам (сводка).",
        input_schema={"type": "object", "properties": {}},
        handler=get_all_projects_summary,
    )

    def read_task(project: str, task_id: int) -> str:
        command = project if project.startswith("/") else f"/{project}"
        task_file = vault.find_task_file(command, task_id)
        if not task_file:
            return f"Задача #{task_id} не найдена в проекте {project}."
        if not vault.validate_path(task_file):
            return "Ошибка: путь за пределами vault."
        data = vault.read_task(task_file)
        fm = data["frontmatter"]
        lines = [f"**#{fm.get('task_id', '')} {fm.get('title', '')}**"]
        for key in ("status", "type", "due", "assignee", "created"):
            val = fm.get(key, "")
            if val:
                lines.append(f"- {key}: {val}")
        if data["body"].strip():
            lines.append(f"\n{data['body'].strip()}")
        return "\n".join(lines)

    registry.register(
        name="read_task",
        description="Прочитать полное содержимое задачи по ID.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Проект: life, gt24 и т.д."},
                "task_id": {"type": "integer", "description": "ID задачи"},
            },
            "required": ["project", "task_id"],
        },
        handler=read_task,
    )

    def read_dashboard() -> str:
        content = vault.read_dashboard()
        return content if content else "Дашборд не найден."

    registry.register(
        name="read_dashboard",
        description="Прочитать текущее содержимое ДАШБОРД.md — основной файл задач в корне Obsidian vault.",
        input_schema={"type": "object", "properties": {}},
        handler=read_dashboard,
    )

    def list_recurring_tasks() -> str:
        tasks = vault.list_recurring_tasks(only_active=True)
        if not tasks:
            return "Повторяющихся задач нет."
        lines = []
        for t in tasks:
            tid = t.get("task_id", "")
            title = t.get("title", "")
            rec = t.get("recurrence", "")
            rule = t.get("recurrence_rule") or ""
            time = t.get("time") or ""
            status = t.get("status", "")
            info = f"**{tid}** {title} — {rec}"
            if rule:
                info += f" ({rule})"
            if time:
                info += f", {time}"
            if status != "active":
                info += f" [{status}]"
            lines.append(info)
        return "\n".join(lines)

    registry.register(
        name="list_recurring_tasks",
        description="Показать все активные повторяющиеся задачи (recurring).",
        input_schema={"type": "object", "properties": {}},
        handler=list_recurring_tasks,
    )

    def get_today_recurring() -> str:
        from calendar import monthrange
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(timezone))
        _, last = monthrange(now.year, now.month)
        tasks = vault.get_today_recurring(now.weekday(), now.day, now.day == last)
        if not tasks:
            return "На сегодня повторяющихся задач нет."
        lines = []
        for t in tasks:
            tid = t.get("task_id", "")
            title = t.get("title", "")
            time = t.get("time") or ""
            prefix = f"{time} — " if time else ""
            lines.append(f"{prefix}**{tid}** {title}")
        return "\n".join(lines)

    registry.register(
        name="get_today_recurring",
        description="Какие повторяющиеся задачи запланированы на сегодня (по дню недели и числу).",
        input_schema={"type": "object", "properties": {}},
        handler=get_today_recurring,
    )

    def search_tasks(query: str) -> str:
        query_lower = query.lower()
        results = []
        for command, rel in COMMAND_PATHS.items():
            task_dir = vault.root / rel
            if not task_dir.exists():
                continue
            for file_path in task_dir.glob("*.md"):
                text = file_path.read_text(encoding="utf-8")
                if query_lower in text.lower():
                    from src.memory.vault_adapter import _split_frontmatter
                    fm, _ = _split_frontmatter(text)
                    status = str(fm.get("status", "")).strip().lower()
                    title = str(fm.get("title", "")).strip() or file_path.stem
                    tid = str(fm.get("task_id", "")).strip()
                    results.append(f"[{command}] #{tid} {title} ({status})")
        if not results:
            return f"Задач по запросу «{query}» не найдено."
        return "\n".join(results[:20])

    registry.register(
        name="search_tasks",
        description="Поиск задач по текстовому запросу во всех проектах.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос"},
            },
            "required": ["query"],
        },
        handler=search_tasks,
    )

    # ── Модифицирующие tools (через подтверждение) ────────────

    def create_task(
        project: str,
        title: str,
        task_id: int,
        task_type: str = "org",
        due: str = "",
        assignee: str = "",
    ) -> str:
        return _require_approval(approval, "create_task", {
            "project": project, "title": title, "task_id": task_id,
            "task_type": task_type, "due": due, "assignee": assignee,
        }, f"Создать задачу #{task_id} «{title}» в проекте {project}")

    registry.register(
        name="create_task",
        description="Создать новую задачу в указанном проекте. Требует подтверждения.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Проект: life, gt24, avgust и т.д."},
                "title": {"type": "string", "description": "Название задачи"},
                "task_id": {"type": "integer", "description": "Уникальный ID задачи (число)"},
                "task_type": {"type": "string", "enum": ["dev", "bug", "org", "personal", "idea"], "description": "Тип задачи"},
                "due": {"type": "string", "description": "Дедлайн в формате YYYY-MM-DD (необязательно)"},
                "assignee": {"type": "string", "description": "Кому делегировано (необязательно)"},
            },
            "required": ["project", "title", "task_id"],
        },
        handler=create_task,
    )

    def update_task_status(project: str, task_id: int, new_status: str) -> str:
        return _require_approval(approval, "update_task_status", {
            "project": project, "task_id": task_id, "new_status": new_status,
        }, f"Изменить статус задачи #{task_id} ({project}) → {new_status}")

    registry.register(
        name="update_task_status",
        description="Изменить статус задачи. Требует подтверждения. Статусы: backlog, todo, in_progress, done, cancelled.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Проект: life, gt24 и т.д."},
                "task_id": {"type": "integer", "description": "ID задачи"},
                "new_status": {"type": "string", "enum": ["backlog", "todo", "in_progress", "done", "cancelled"]},
            },
            "required": ["project", "task_id", "new_status"],
        },
        handler=update_task_status,
    )

    def update_dashboard(content: str) -> str:
        lines_count = len(content.splitlines())
        return _require_approval(approval, "update_dashboard", {
            "content": content,
        }, f"Перезаписать ДАШБОРД.md ({lines_count} строк)")

    registry.register(
        name="update_dashboard",
        description=(
            "Записать новое содержимое ДАШБОРД.md. Требует подтверждения. "
            "Всегда сначала вызови read_dashboard, чтобы получить текущий контент."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Полное новое содержимое файла ДАШБОРД.md",
                },
            },
            "required": ["content"],
        },
        handler=update_dashboard,
    )

    def regenerate_dashboard() -> str:
        return _require_approval(approval, "regenerate_dashboard", {},
            "Перегенерировать ДАШБОРД.md из актуальных задач (секция «Сегодня» сохранится)")

    registry.register(
        name="regenerate_dashboard",
        description=(
            "Перегенерировать ДАШБОРД.md из актуальных задач во всех проектах. Требует подтверждения."
        ),
        input_schema={"type": "object", "properties": {}},
        handler=regenerate_dashboard,
    )

    def generate_today_plan() -> str:
        return _require_approval(approval, "generate_today_plan", {},
            "Сгенерировать план на сегодня и обновить секцию «Сегодня» в дашборде")

    registry.register(
        name="generate_today_plan",
        description=(
            "Собрать план дня: recurring + дедлайны сегодня. Требует подтверждения. "
            "Обновляет секцию «Сегодня» в ДАШБОРД.md."
        ),
        input_schema={"type": "object", "properties": {}},
        handler=generate_today_plan,
    )

    def create_recurring_task(
        task_id: str,
        title: str,
        recurrence: str,
        recurrence_rule: str = "",
        time: str = "",
        duration_min: int = 0,
        project: str = "life",
    ) -> str:
        return _require_approval(approval, "create_recurring_task", {
            "task_id": task_id, "title": title, "recurrence": recurrence,
            "recurrence_rule": recurrence_rule, "time": time,
            "duration_min": duration_min, "project": project,
        }, f"Создать повторяющуюся задачу {task_id} «{title}» ({recurrence})")

    registry.register(
        name="create_recurring_task",
        description="Создать новую повторяющуюся задачу. Требует подтверждения. ID формат: R001-R100.",
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "ID задачи (R001-R100). Узнай следующий свободный через list_recurring_tasks."},
                "title": {"type": "string", "description": "Название задачи"},
                "recurrence": {"type": "string", "enum": ["daily", "weekdays", "weekly", "monthly"], "description": "Частота повторения"},
                "recurrence_rule": {"type": "string", "description": "Правило: день недели (пн-вс) для weekly, число или 'last' для monthly"},
                "time": {"type": "string", "description": "Время по умолчанию (HH:MM)"},
                "duration_min": {"type": "integer", "description": "Длительность в минутах"},
                "project": {"type": "string", "description": "Проект (life, avgust, deutsch и т.д.)"},
            },
            "required": ["task_id", "title", "recurrence"],
        },
        handler=create_recurring_task,
    )

    def update_recurring_task(task_id: str, **fields) -> str:
        return _require_approval(approval, "update_recurring_task", {
            "task_id": task_id, **fields,
        }, f"Изменить повторяющуюся задачу {task_id}: {fields}")

    registry.register(
        name="update_recurring_task",
        description="Изменить повторяющуюся задачу. Требует подтверждения.",
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "ID задачи (R001, R002 и т.д.)"},
                "status": {"type": "string", "enum": ["active", "paused", "cancelled"], "description": "Новый статус"},
                "time": {"type": "string", "description": "Новое время (HH:MM)"},
                "recurrence": {"type": "string", "enum": ["daily", "weekdays", "weekly", "monthly"], "description": "Новая частота"},
                "recurrence_rule": {"type": "string", "description": "Новое правило"},
            },
            "required": ["task_id"],
        },
        handler=update_recurring_task,
    )

    def convert_to_recurring(
        project: str,
        task_id: int,
        recurrence: str,
        recurrence_rule: str = "",
        time: str = "",
    ) -> str:
        return _require_approval(approval, "convert_to_recurring", {
            "project": project, "task_id": task_id, "recurrence": recurrence,
            "recurrence_rule": recurrence_rule, "time": time,
        }, f"Конвертировать задачу #{task_id} ({project}) в повторяющуюся ({recurrence})")

    registry.register(
        name="convert_to_recurring",
        description=(
            "Конвертировать обычную задачу в повторяющуюся. Требует подтверждения. "
            "Читает задачу, создаёт R-файл, помечает оригинал как done."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Проект задачи: life, gt24, avgust, erp и т.д."},
                "task_id": {"type": "integer", "description": "ID исходной задачи"},
                "recurrence": {"type": "string", "enum": ["daily", "weekdays", "weekly", "monthly"], "description": "Частота повторения"},
                "recurrence_rule": {"type": "string", "description": "День недели (пн-вс) для weekly, число или 'last' для monthly"},
                "time": {"type": "string", "description": "Время по умолчанию (HH:MM)"},
            },
            "required": ["project", "task_id", "recurrence"],
        },
        handler=convert_to_recurring,
    )

    # ── Approval execution ────────────────────────────────────

    def approve_vault_action(token: str) -> str:
        pending = approval.approve(token)
        if not pending:
            return f"Токен {token} не найден или уже использован."

        p = pending.payload

        if pending.action == "create_task":
            command = p["project"] if p["project"].startswith("/") else f"/{p['project']}"
            if command not in COMMAND_PATHS:
                return f"Неизвестный проект: {p['project']}"
            path = vault.create_task(
                command=command, title=p["title"], task_id=p["task_id"],
                task_type=p.get("task_type", "org"),
                due=p.get("due", ""), assignee=p.get("assignee", ""),
            )
            return f"Задача создана: {path.name}"

        if pending.action == "update_task_status":
            command = p["project"] if p["project"].startswith("/") else f"/{p['project']}"
            task_file = vault.find_task_file(command, p["task_id"])
            if not task_file:
                return f"Задача #{p['task_id']} не найдена."
            vault.update_task_status(task_file, p["new_status"])
            return f"Статус задачи #{p['task_id']} изменён на {p['new_status']}."

        if pending.action == "update_dashboard":
            vault.write_dashboard(p["content"])
            return "Дашборд обновлён."

        if pending.action == "regenerate_dashboard":
            vault.regenerate_dashboard()
            return "Дашборд перегенерирован."

        if pending.action == "generate_today_plan":
            result = vault.generate_today_plan()
            return f"План на сегодня обновлён.\n\n{result}"

        if pending.action == "create_recurring_task":
            path = vault.create_recurring_task(
                task_id=p["task_id"], title=p["title"], recurrence=p["recurrence"],
                recurrence_rule=p.get("recurrence_rule", ""),
                time=p.get("time", ""), duration_min=p.get("duration_min", 0),
                project=p.get("project", "life"),
            )
            return f"Повторяющаяся задача создана: {path.name}"

        if pending.action == "update_recurring_task":
            task_id = p.pop("task_id")
            result = vault.update_recurring_task(task_id, **p)
            if not result:
                return f"Задача {task_id} не найдена."
            return f"Задача {task_id} обновлена."

        if pending.action == "convert_to_recurring":
            command = p["project"] if p["project"].startswith("/") else f"/{p['project']}"
            try:
                new_id, new_path = vault.convert_to_recurring(
                    command=command, task_id=p["task_id"], recurrence=p["recurrence"],
                    recurrence_rule=p.get("recurrence_rule", ""),
                    time=p.get("time", ""),
                )
            except ValueError as e:
                return str(e)
            return f"Задача #{p['task_id']} конвертирована в {new_id} ({new_path.name})"

        return f"Неизвестное действие: {pending.action}"

    registry.register(
        name="approve_vault_action",
        description="Подтвердить и выполнить отложенное действие с задачами/дашбордом по токену.",
        input_schema={
            "type": "object",
            "properties": {
                "token": {"type": "string", "description": "Токен подтверждения"},
            },
            "required": ["token"],
        },
        handler=approve_vault_action,
    )

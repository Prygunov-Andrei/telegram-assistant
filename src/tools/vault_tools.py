from __future__ import annotations

from pathlib import Path

from src.memory.vault_adapter import VaultAdapter, COMMAND_PATHS
from src.tools.registry import ToolRegistry


def register_vault_tools(registry: ToolRegistry, vault: VaultAdapter) -> None:

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

    def create_task(
        project: str,
        title: str,
        task_id: int,
        task_type: str = "org",
        priority: str = "medium",
        due: str = "",
        assignee: str = "",
    ) -> str:
        command = project if project.startswith("/") else f"/{project}"
        if command not in COMMAND_PATHS:
            return f"Неизвестный проект: {project}. Доступные: {', '.join(COMMAND_PATHS.keys())}"
        path = vault.create_task(
            command=command,
            title=title,
            task_id=task_id,
            task_type=task_type,
            priority=priority,
            due=due,
            assignee=assignee,
        )
        return f"Задача создана: {path.name}"

    registry.register(
        name="create_task",
        description="Создать новую задачу в указанном проекте.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Проект: life, gt24, avgust и т.д."},
                "title": {"type": "string", "description": "Название задачи"},
                "task_id": {"type": "integer", "description": "Уникальный ID задачи (число)"},
                "task_type": {"type": "string", "enum": ["dev", "bug", "org", "personal", "idea"], "description": "Тип задачи"},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"], "description": "Приоритет"},
                "due": {"type": "string", "description": "Дедлайн в формате YYYY-MM-DD (необязательно)"},
                "assignee": {"type": "string", "description": "Кому делегировано (необязательно)"},
            },
            "required": ["project", "title", "task_id"],
        },
        handler=create_task,
    )

    def update_task_status(project: str, task_id: int, new_status: str) -> str:
        command = project if project.startswith("/") else f"/{project}"
        task_file = vault.find_task_file(command, task_id)
        if not task_file:
            return f"Задача #{task_id} не найдена в проекте {project}."
        if not vault.validate_path(task_file):
            return "Ошибка: путь за пределами vault."
        vault.update_task_status(task_file, new_status)
        return f"Статус задачи #{task_id} изменён на {new_status}."

    registry.register(
        name="update_task_status",
        description="Изменить статус задачи. Статусы: backlog, todo, in_progress, done, cancelled.",
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
        for key in ("status", "type", "priority", "due", "assignee", "created"):
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

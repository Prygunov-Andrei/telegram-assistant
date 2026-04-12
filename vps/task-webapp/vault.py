"""Vault adapter for Obsidian-format task files (YAML frontmatter)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

STATUS_CLOSED = {"done", "cancelled"}

COMMAND_PATHS = {
    "life": "life/ЗАДАЧИ",
    "gt24": "gt24realestate.de/ЗАДАЧИ",
    "avgust": "avgust/ЗАДАЧИ",
    "erp": "avgust/ERP_Avgust/ЗАДАЧИ",
    "deutsch": "deutsch/ЗАДАЧИ",
    "april": "april/ЗАДАЧИ",
    "books": "books/ЗАДАЧИ",
    "kaz": "kaz_nach_berlin/ЗАДАЧИ",
    "recurring": "life/ЗАДАЧИ_RECURRING",
}

PROJECT_DISPLAY = {
    "life": "Life",
    "gt24": "GT24 Недвижимость",
    "avgust": "Август",
    "erp": "ERP Август",
    "deutsch": "Deutsch",
    "april": "April",
    "books": "Books",
    "kaz": "Kaz nach Berlin",
    "recurring": "Повторяющиеся",
}


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}, text
    raw_yaml = parts[1]
    body = parts[2]
    try:
        data = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError:
        return {}, text
    return data, body


class VaultAdapter:
    def __init__(self, root_path: str) -> None:
        self.root = Path(root_path)

    def list_tasks(
        self,
        project: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List tasks, optionally filtered by project and/or status."""
        projects = [project] if project else list(COMMAND_PATHS.keys())
        tasks: list[dict[str, Any]] = []
        for proj in projects:
            rel = COMMAND_PATHS.get(proj)
            if not rel:
                continue
            task_dir = self.root / rel
            if not task_dir.exists():
                continue
            for fp in sorted(task_dir.glob("*.md")):
                text = fp.read_text(encoding="utf-8")
                fm, _ = _split_frontmatter(text)
                if not fm:
                    continue
                fm_status = str(fm.get("status", "")).strip().lower()
                if status and fm_status != status:
                    continue
                task = {
                    "task_id": fm.get("task_id"),
                    "title": fm.get("title", fp.stem),
                    "status": fm_status,
                    "type": fm.get("type", ""),
                    "project": proj,
                    "created": str(fm.get("created", "")),
                    "due": str(fm.get("due") or ""),
                    "assignee": str(fm.get("assignee") or ""),
                    "tags": fm.get("tags", []),
                    "_filename": fp.name,
                }
                # Normalize "None"/"null" strings
                if task["due"].lower() in ("none", "null", ""):
                    task["due"] = ""
                if task["assignee"].lower() in ("none", "null", ""):
                    task["assignee"] = ""
                tasks.append(task)
        return tasks

    def project_counts(self, open_only: bool = True) -> dict[str, dict[str, Any]]:
        """Return project slug -> {name, count}."""
        result: dict[str, dict[str, Any]] = {}
        for slug, rel in COMMAND_PATHS.items():
            task_dir = self.root / rel
            count = 0
            if task_dir.exists():
                for fp in task_dir.glob("*.md"):
                    text = fp.read_text(encoding="utf-8")
                    fm, _ = _split_frontmatter(text)
                    fm_status = str(fm.get("status", "")).strip().lower()
                    if open_only and fm_status in STATUS_CLOSED:
                        continue
                    count += 1
            result[slug] = {
                "name": PROJECT_DISPLAY.get(slug, slug),
                "count": count,
            }
        return result

    def find_task_file(self, project: str, task_id: int) -> Path | None:
        rel = COMMAND_PATHS.get(project)
        if not rel:
            return None
        task_dir = self.root / rel
        if not task_dir.exists():
            return None
        for fp in task_dir.glob("*.md"):
            if fp.name.startswith(f"{task_id}-"):
                return fp
        return None

    def create_task(
        self,
        project: str,
        title: str,
        task_type: str = "org",
        due: str = "",
        assignee: str = "",
    ) -> dict[str, Any]:
        rel = COMMAND_PATHS.get(project)
        if not rel:
            raise ValueError(f"Unknown project: {project}")
        task_dir = self.root / rel
        task_dir.mkdir(parents=True, exist_ok=True)

        # Determine next task_id across ALL projects
        max_id = 0
        for _, r in COMMAND_PATHS.items():
            d = self.root / r
            if not d.exists():
                continue
            for fp in d.glob("*.md"):
                text = fp.read_text(encoding="utf-8")
                fm, _ = _split_frontmatter(text)
                tid = fm.get("task_id")
                if isinstance(tid, int) and tid > max_id:
                    max_id = tid
        task_id = max_id + 1

        slug = "-".join(
            [part for part in title.lower().replace("/", " ").split() if part]
        )
        filename = f"{task_id}-{slug}.md"
        target = task_dir / filename

        frontmatter = {
            "task_id": task_id,
            "title": title,
            "status": "todo",
            "type": task_type,
            "project": project,
            "created": datetime.now().strftime("%Y-%m-%d"),
            "due": due or None,
            "assignee": assignee or None,
            "tags": [],
        }
        content = (
            "---\n"
            f"{yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)}"
            "---\n\n"
            f"# {title}\n\n"
            "## Связанные задачи\n\n"
            "## Обсуждения\n\n"
            "## История изменений\n"
            f"- {datetime.now().strftime('%Y-%m-%d')} [Web App]: Создана задача\n"
        )
        target.write_text(content, encoding="utf-8")

        return {
            "task_id": task_id,
            "title": title,
            "status": "todo",
            "type": task_type,
            "project": project,
            "created": frontmatter["created"],
            "due": due,
            "assignee": assignee,
            "tags": [],
            "_filename": filename,
        }

    def update_task(
        self, project: str, task_id: int, fields: dict[str, Any]
    ) -> dict[str, Any] | None:
        fp = self.find_task_file(project, task_id)
        if not fp:
            return None
        text = fp.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(text)

        allowed = {"status", "due", "assignee", "title", "type", "tags"}
        for key, value in fields.items():
            if key in allowed:
                fm[key] = value

        now = datetime.now().strftime("%Y-%m-%d")
        changes = ", ".join(f"{k}={v}" for k, v in fields.items() if k in allowed)
        history_line = f"- {now} [Web App]: {changes}\n"
        marker = "## История изменений"
        if marker not in body:
            body = body.rstrip() + f"\n\n{marker}\n"

        updated = (
            "---\n"
            f"{yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)}"
            "---\n"
            f"{body}{history_line}"
        )
        fp.write_text(updated, encoding="utf-8")

        return {
            "task_id": fm.get("task_id"),
            "title": fm.get("title", fp.stem),
            "status": str(fm.get("status", "")),
            "type": fm.get("type", ""),
            "project": project,
            "created": str(fm.get("created", "")),
            "due": str(fm.get("due") or ""),
            "assignee": str(fm.get("assignee") or ""),
            "tags": fm.get("tags", []),
            "_filename": fp.name,
        }

    def archive_task(self, project: str, task_id: int) -> bool:
        """Move task to archive/ subfolder."""
        fp = self.find_task_file(project, task_id)
        if not fp:
            return False
        archive_dir = fp.parent / "archive"
        archive_dir.mkdir(exist_ok=True)
        dest = archive_dir / fp.name
        fp.rename(dest)
        return True


    def regenerate_dashboard(self) -> bool:
        """Regenerate ДАШБОРД.md from all tasks."""
        from datetime import datetime
        today = datetime.now()
        months = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря']
        days = ['понедельник','вторник','среда','четверг','пятница','суббота','воскресенье']
        date_str = f"{today.day} {months[today.month-1]}, {days[today.weekday()]}"

        lines = []
        lines.append(f"# 📋 Дашборд — {date_str}\n")
        lines.append(f"\u003E Обновлён: {today.strftime('%Y-%m-%d %H:%M')}\n\n")

        today_str = today.strftime('%Y-%m-%d')

        # Collect all open tasks grouped by project
        all_tasks = self.list_tasks()
        open_tasks = [t for t in all_tasks if t.get('status') not in ('done', 'cancelled')]

        # Today section
        overdue = [t for t in open_tasks if t.get('due') and t['due'] < today_str]
        today_tasks = [t for t in open_tasks if t.get('due') == today_str]
        in_progress = [t for t in open_tasks if t.get('status') == 'in_progress' and t.get('due') != today_str]

        lines.append("## 📅 Сегодня\n\n")
        if overdue:
            lines.append(f"### ⚠️ Просрочено ({len(overdue)})\n")
            for t in overdue:
                lines.append(f"- [ ] [[{t['project']}/ЗАДАЧИ/{t.get('_filename','')}|#{t.get('task_id','')} {t.get('title','')}]] ({t.get('due','')})\n")
            lines.append("\n")
        if today_tasks:
            lines.append(f"### На сегодня ({len(today_tasks)})\n")
            for t in today_tasks:
                lines.append(f"- [ ] [[{t['project']}/ЗАДАЧИ/{t.get('_filename','')}|#{t.get('task_id','')} {t.get('title','')}]]\n")
            lines.append("\n")
        if in_progress:
            lines.append(f"### В работе ({len(in_progress)})\n")
            for t in in_progress:
                lines.append(f"- [ ] [[{t['project']}/ЗАДАЧИ/{t.get('_filename','')}|#{t.get('task_id','')} {t.get('title','')}]]\n")
            lines.append("\n")

        # Group by project
        from collections import defaultdict
        by_project = defaultdict(list)
        for t in open_tasks:
            by_project[t['project']].append(t)

        lines.append("---\n\n")
        lines.append("## Проекты\n\n")
        for proj in sorted(by_project.keys()):
            tasks = by_project[proj]
            lines.append(f"### {PROJECT_DISPLAY.get(proj, proj)} ({len(tasks)})\n")
            for t in sorted(tasks, key=lambda x: (x.get('due') or '9999', -(x.get('task_id') or 0))):
                due = f" 📅 {t['due']}" if t.get('due') else ""
                assignee = f" 👤 {t['assignee']}" if t.get('assignee') else ""
                lines.append(f"- [ ] [[{proj}/ЗАДАЧИ/{t.get('_filename','')}|#{t.get('task_id','')} {t.get('title','')}]]{due}{assignee}\n")
            lines.append("\n")

        dashboard_path = self.root / 'ДАШБОРД.md'
        dashboard_path.write_text(''.join(lines), encoding='utf-8')
        return True

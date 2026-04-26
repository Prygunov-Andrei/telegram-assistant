"""Vault adapter for Obsidian-format task files (YAML frontmatter)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

STATUS_CLOSED = {"done", "cancelled"}

COMMAND_PATHS = {
    "life": "life/ЗАДАЧИ",
    "realestate": "realestate/ЗАДАЧИ",
    "avgust": "avgust/ЗАДАЧИ",
    "erp": "avgust/ERP_Avgust/ЗАДАЧИ",
    "deutsch": "deutsch/ЗАДАЧИ",
    "april": "april/ЗАДАЧИ",
    "books": "books/ЗАДАЧИ",
}

PROJECT_DISPLAY = {
    "life": "Life",
    "realestate": "Недвижимость (GT24+KAZ)",
    "avgust": "Август (организационное)",
    "erp": "ERP Август",
    "deutsch": "Deutsch",
    "april": "April",
    "books": "Books",
}

DASHBOARD_ORDER = ["life", "realestate", "avgust", "erp", "deutsch", "books", "april"]

RU_MONTHS = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"]
RU_WEEKDAYS = ["понедельник","вторник","среда","четверг","пятница","суббота","воскресенье"]


def _split_frontmatter(text):
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
    def __init__(self, root_path):
        self.root = Path(root_path)

    def list_tasks(self, project=None, status=None):
        projects = [project] if project else list(COMMAND_PATHS.keys())
        tasks = []
        for proj in projects:
            rel = COMMAND_PATHS.get(proj)
            if not rel:
                continue
            task_dir = self.root / rel
            if not task_dir.exists():
                continue
            for fp in sorted(task_dir.glob("*.md")):
                if fp.name == "_index.md":
                    continue
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
                    "subproject": str(fm.get("subproject") or ""),
                    "created": str(fm.get("created", "")),
                    "due": str(fm.get("due") or ""),
                    "assignee": str(fm.get("assignee") or ""),
                    "priority": str(fm.get("priority") or ""),
                    "tags": fm.get("tags", []),
                    "recurring": str(fm.get("recurring") or ""),
                    "recurring_duration": str(fm.get("recurring_duration") or ""),
                    "_filename": fp.name,
                }
                if task["due"].lower() in ("none", "null", ""):
                    task["due"] = ""
                if task["assignee"].lower() in ("none", "null", ""):
                    task["assignee"] = ""
                tasks.append(task)
        return tasks

    def project_counts(self, open_only=True):
        result = {}
        for slug, rel in COMMAND_PATHS.items():
            task_dir = self.root / rel
            count = 0
            if task_dir.exists():
                for fp in task_dir.glob("*.md"):
                    if fp.name == "_index.md":
                        continue
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

    def find_task_file(self, project, task_id):
        rel = COMMAND_PATHS.get(project)
        if not rel:
            return None
        task_dir = self.root / rel
        if not task_dir.exists():
            return None
        for fp in task_dir.glob("*.md"):
            if fp.name.startswith(f"{task_id}-"):
                return fp
        arch = task_dir / "archive"
        if arch.exists():
            for fp in arch.glob("*.md"):
                if fp.name.startswith(f"{task_id}-"):
                    return fp
        return None

    def create_task(self, project, title, task_type="org", due="", assignee=""):
        rel = COMMAND_PATHS.get(project)
        if not rel:
            raise ValueError(f"Unknown project: {project}")
        task_dir = self.root / rel
        task_dir.mkdir(parents=True, exist_ok=True)

        max_id = 0
        for _, r in COMMAND_PATHS.items():
            d = self.root / r
            if not d.exists():
                continue
            search = list(d.glob("*.md"))
            arch = d / "archive"
            if arch.exists():
                search += list(arch.glob("*.md"))
            for fp in search:
                if fp.name == "_index.md":
                    continue
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
            "priority": "medium",
            "tags": [],
        }
        content = (
            "---\n"
            + yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
            + "---\n\n"
            + f"# {title}\n\n"
            + "## Связанные задачи\n\n"
            + "## Обсуждения\n\n"
            + "## История изменений\n"
            + f"- {datetime.now().strftime('%Y-%m-%d')} [Web App]: Создана задача\n"
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
            "priority": "medium",
            "tags": [],
            "_filename": filename,
        }

    def update_task(self, project, task_id, fields):
        fp = self.find_task_file(project, task_id)
        if not fp:
            return None
        text = fp.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(text)

        allowed = {"status", "due", "assignee", "title", "type", "tags", "priority", "subproject", "recurring", "recurring_duration"}
        for key, value in fields.items():
            if key in allowed:
                fm[key] = value

        if "body" in fields and fields["body"] is not None:
            body = fields["body"].rstrip() + "\n"

        now = datetime.now().strftime("%Y-%m-%d")
        change_keys = [k for k in fields if k in allowed or k == "body"]
        changes = ", ".join(change_keys) if change_keys else "—"
        history_line = f"- {now} [Web App]: {changes}\n"
        marker = "## История изменений"
        if marker not in body:
            body = body.rstrip() + f"\n\n{marker}\n"

        updated = (
            "---\n"
            + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
            + "---\n"
            + f"{body}{history_line}"
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
            "priority": str(fm.get("priority") or ""),
            "tags": fm.get("tags", []),
            "_filename": fp.name,
        }

    def delete_task(self, project, task_id):
        fp = self.find_task_file(project, task_id)
        if not fp:
            return False
        fp.unlink()
        return True

    def archive_task(self, project, task_id):
        fp = self.find_task_file(project, task_id)
        if not fp:
            return False
        if fp.parent.name == "archive":
            return True
        archive_dir = fp.parent / "archive"
        archive_dir.mkdir(exist_ok=True)
        dest = archive_dir / fp.name
        fp.rename(dest)
        return True

    def regenerate_dashboard(self):
        """Regenerate ДАШБОРД.md with new schema (recurring, subproject)."""
        today = datetime.now()
        date_str = f"{today.day} {RU_MONTHS[today.month-1]}, {RU_WEEKDAYS[today.weekday()]}"
        today_iso = today.strftime("%Y-%m-%d")

        all_tasks = self.list_tasks()
        open_tasks = [t for t in all_tasks if t.get("status") not in STATUS_CLOSED]

        overdue = sorted(
            [t for t in open_tasks if t.get("due") and t["due"] < today_iso and not t.get("recurring")],
            key=lambda t: t["due"],
        )
        today_tasks = [t for t in open_tasks if t.get("due") == today_iso]
        in_progress = [
            t for t in open_tasks
            if t.get("status") == "in_progress" and t.get("due") != today_iso
        ]
        recurring = [t for t in open_tasks if t.get("recurring")]

        def wikilink(t):
            rel = COMMAND_PATHS.get(t["project"], t["project"])
            stem = t["_filename"]
            if stem.endswith(".md"):
                stem = stem[:-3]
            return f"[[{rel}/{stem}|#{t.get('task_id', '?')} {t.get('title', '')}]]"

        lines = []
        lines.append(f"# 📋 Дашборд — {date_str}\n")
        lines.append(f"> Обновлён: {today.strftime('%Y-%m-%d %H:%M')} (Mini App regenerate)\n\n")
        lines.append("## 📅 Сегодня\n\n")

        if overdue:
            lines.append(f"### ⚠️ Просрочено ({len(overdue)})\n")
            for t in overdue:
                lines.append(f"- [ ] {wikilink(t)} ({t['due']})\n")
            lines.append("\n")
        if today_tasks:
            lines.append(f"### На сегодня ({len(today_tasks)})\n")
            for t in today_tasks:
                lines.append(f"- [ ] {wikilink(t)}\n")
            lines.append("\n")
        if in_progress:
            lines.append(f"### В работе ({len(in_progress)})\n")
            for t in in_progress:
                lines.append(f"- [ ] {wikilink(t)}\n")
            lines.append("\n")
        if recurring:
            lines.append(f"### 🔁 Регулярные ({len(recurring)})\n")
            for t in sorted(recurring, key=lambda x: x.get("recurring", "")):
                lines.append(f"- [ ] {wikilink(t)} — *{t['recurring']}*\n")
            lines.append("\n")

        lines.append("---\n\n## По проектам\n\n")
        for slug in DASHBOARD_ORDER:
            project_tasks = [t for t in open_tasks if t["project"] == slug]
            if not project_tasks:
                continue
            display = PROJECT_DISPLAY.get(slug, slug)
            lines.append(f"### {display} ({len(project_tasks)})\n")
            project_tasks.sort(
                key=lambda t: (
                    t.get("due") or "9999-99-99",
                    -(int(t["task_id"]) if isinstance(t.get("task_id"), int) else 0),
                )
            )
            for t in project_tasks:
                suffix = ""
                if t.get("due"):
                    suffix += f" 📅 {t['due']}"
                if t.get("assignee"):
                    suffix += f" 👤 {t['assignee']}"
                if t.get("recurring"):
                    suffix += f" 🔁 {t['recurring']}"
                if t.get("subproject"):
                    suffix += f" [{t['subproject']}]"
                lines.append(f"- [ ] {wikilink(t)}{suffix}\n")
            lines.append("\n")

        (self.root / "ДАШБОРД.md").write_text("".join(lines), encoding="utf-8")
        return True

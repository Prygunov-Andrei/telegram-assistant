from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.utils.formatting import display_due

STATUS_CLOSED = {"done", "cancelled"}

COMMAND_PATHS = {
    "/gt24": "gt24realestate.de/ЗАДАЧИ",
    "/avgust": "avgust/ЗАДАЧИ",
    "/erp": "avgust/ERP_Avgust/ЗАДАЧИ",
    "/deutsch": "deutsch/ЗАДАЧИ",
    "/life": "life/ЗАДАЧИ",
    "/april": "april/ЗАДАЧИ",
    "/books": "books/ЗАДАЧИ",
    "/kaz": "kaz_nach_berlin/ЗАДАЧИ",
    "/daemon": "telegram-daemon/ЗАДАЧИ",
    "/assistant": "telegram-assistant/ЗАДАЧИ",
}


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}, text
    raw_yaml = parts[1]
    body = parts[2]
    data = yaml.safe_load(raw_yaml) or {}
    return data, body


class VaultAdapter:
    def __init__(self, root_path: str) -> None:
        self.root = Path(root_path)

    def list_open_tasks(self, command: str) -> dict[str, list[str]]:
        rel = COMMAND_PATHS.get(command)
        if not rel:
            return {"С дедлайном": [], "Делегировано": [], "Когда-нибудь": []}
        task_dir = self.root / rel
        if not task_dir.exists():
            return {"С дедлайном": [], "Делегировано": [], "Когда-нибудь": []}
        with_due: list[tuple[str, str]] = []
        delegated: list[str] = []
        someday: list[str] = []
        for file_path in sorted(task_dir.glob("*.md")):
            text = file_path.read_text(encoding="utf-8")
            frontmatter, _ = _split_frontmatter(text)
            status = str(frontmatter.get("status", "")).strip().lower()
            if status in STATUS_CLOSED:
                continue
            title = str(frontmatter.get("title", "")).strip() or file_path.stem
            task_id = str(frontmatter.get("task_id", "")).strip()
            assignee = str(frontmatter.get("assignee", "")).strip()
            due_raw = frontmatter.get("due", "")
            due = "" if due_raw is None else str(due_raw).strip()
            prefix = f"#{task_id} {title}" if task_id else title
            if due and due.lower() not in {"none", "null"}:
                try:
                    formatted_due = display_due(due)
                except ValueError:
                    formatted_due = due
                with_due.append((due, f"{prefix} — {formatted_due}"))
                continue
            if assignee:
                delegated.append(f"{prefix} — {assignee}")
                continue
            someday.append(prefix)
        with_due.sort(key=lambda row: row[0])
        return {
            "С дедлайном": [item for _, item in with_due],
            "Делегировано": delegated,
            "Когда-нибудь": someday,
        }

    def project_counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for command, rel in COMMAND_PATHS.items():
            task_dir = self.root / rel
            if not task_dir.exists():
                continue
            count = 0
            for file_path in task_dir.glob("*.md"):
                text = file_path.read_text(encoding="utf-8")
                frontmatter, _ = _split_frontmatter(text)
                status = str(frontmatter.get("status", "")).strip().lower()
                if status in STATUS_CLOSED:
                    continue
                count += 1
            result[command] = count
        return result

    def create_task(
        self,
        command: str,
        title: str,
        task_id: int,
        task_type: str = "org",
        priority: str = "medium",
        due: str = "",
        assignee: str = "",
    ) -> Path:
        rel = COMMAND_PATHS.get(command)
        if not rel:
            raise ValueError(f"Unsupported command: {command}")
        task_dir = self.root / rel
        task_dir.mkdir(parents=True, exist_ok=True)
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
            "project": rel.split("/")[0],
            "created": datetime.now().strftime("%Y-%m-%d"),
            "due": due,
            "assignee": assignee,
            "priority": priority,
            "tags": [],
            "kanban-plugin": "basic",
        }
        content = (
            "---\n"
            f"{yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)}"
            "---\n\n"
            f"# {title}\n\n"
            "## Связанные задачи\n\n"
            "## Обсуждения\n\n"
            "## История изменений\n"
            f"- {datetime.now().strftime('%Y-%m-%d')} [Claude Assistant]: Создана задача\n"
        )
        target.write_text(content, encoding="utf-8")
        return target

    def update_task_status(
        self, task_file: Path, new_status: str, author: str = "Claude Assistant"
    ) -> None:
        text = task_file.read_text(encoding="utf-8")
        frontmatter, body = _split_frontmatter(text)
        frontmatter["status"] = new_status
        now = datetime.now().strftime("%Y-%m-%d")
        history_line = f"- {now} [{author}]: Статус изменен на {new_status}\n"
        marker = "## История изменений"
        if marker not in body:
            body = body.rstrip() + f"\n\n{marker}\n"
        updated = (
            "---\n"
            f"{yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)}"
            "---\n"
            f"{body}{history_line}"
        )
        task_file.write_text(updated, encoding="utf-8")

    def read_task(self, task_file: Path) -> dict[str, Any]:
        text = task_file.read_text(encoding="utf-8")
        frontmatter, body = _split_frontmatter(text)
        return {"frontmatter": frontmatter, "body": body, "path": str(task_file)}

    def find_task_file(self, command: str, task_id: int) -> Path | None:
        rel = COMMAND_PATHS.get(command)
        if not rel:
            return None
        task_dir = self.root / rel
        if not task_dir.exists():
            return None
        for file_path in task_dir.glob("*.md"):
            if file_path.name.startswith(f"{task_id}-"):
                return file_path
        return None

    def validate_path(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
            return str(resolved).startswith(str(self.root.resolve()))
        except (OSError, ValueError):
            return False

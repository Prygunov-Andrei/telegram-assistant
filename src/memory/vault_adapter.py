from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.utils.formatting import display_due, RU_MONTHS, RU_WEEKDAYS

STATUS_CLOSED = {"done", "cancelled"}

RECURRING_DIR = "life/ЗАДАЧИ_RECURRING"

WEEKDAY_MAP = {"пн": 0, "вт": 1, "ср": 2, "чт": 3, "пт": 4, "сб": 5, "вс": 6}

DASHBOARD_FILE = "ДАШБОРД.md"

DASHBOARD_PROJECTS: list[tuple[str, str]] = [
    ("/gt24", "GT24 Недвижимость"),
    ("/avgust", "Август"),
    ("/erp", "ERP Август"),
    ("/april", "April"),
    ("/books", "Books"),
    ("/deutsch", "Deutsch"),
    ("/kaz", "Kaz nach Berlin"),
    ("/life", "Life"),
]

CALLOUT_TYPES = {
    "С дедлайном": "calendar",
    "Делегировано": "todo",
    "Когда-нибудь": "note",
}

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

    # ── Dashboard ─────────────────────────────────────────────

    def read_dashboard(self) -> str:
        path = self.root / DASHBOARD_FILE
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def write_dashboard(self, content: str) -> None:
        path = self.root / DASHBOARD_FILE
        path.write_text(content, encoding="utf-8")

    def regenerate_dashboard(self) -> str:
        dashboard_path = self.root / DASHBOARD_FILE

        # Сохраняем секцию «Сегодня» из текущего дашборда
        today_section = ""
        if dashboard_path.exists():
            text = dashboard_path.read_text(encoding="utf-8")
            parts = text.split("\n---\n", 1)
            if len(parts) == 2:
                today_section = parts[0].rstrip()

        # Собираем секции проектов из реальных данных
        project_sections = []
        for command, display_name in DASHBOARD_PROJECTS:
            section = self._build_dashboard_section(command, display_name)
            project_sections.append(section)

        if today_section:
            content = today_section + "\n\n---\n\n" + "\n".join(project_sections)
        else:
            content = "\n".join(project_sections)

        dashboard_path.write_text(content, encoding="utf-8")
        return content

    def _build_dashboard_section(self, command: str, display_name: str) -> str:
        rel = COMMAND_PATHS.get(command)
        if not rel:
            return f"## {display_name}\n"

        task_dir = self.root / rel
        with_due: list[tuple[str, str]] = []
        delegated: list[str] = []
        someday: list[str] = []

        if task_dir.exists():
            for file_path in sorted(task_dir.glob("*.md")):
                text = file_path.read_text(encoding="utf-8")
                frontmatter, _ = _split_frontmatter(text)
                status = str(frontmatter.get("status", "")).strip().lower()
                if status in STATUS_CLOSED:
                    continue

                task_id = str(frontmatter.get("task_id") or "").strip()
                if not task_id:
                    continue
                title = str(frontmatter.get("title") or "").strip() or file_path.stem
                assignee = str(frontmatter.get("assignee") or "").strip()
                due = str(frontmatter.get("due") or "").strip()
                if due.lower() in {"none", "null"}:
                    due = ""

                # Wikilink
                rel_path = file_path.relative_to(self.root)
                wiki_path = str(rel_path).removesuffix(".md")
                display = f"#{task_id} {title}" if task_id else title
                wikilink = f"[[{wiki_path}|{display}]]"

                if assignee:
                    suffix = assignee
                    if due:
                        try:
                            dt = datetime.strptime(due, "%Y-%m-%d")
                            suffix += f", до {dt.day} {RU_MONTHS[dt.month]}"
                        except ValueError:
                            pass
                    delegated.append(f"- [ ] {wikilink} — {suffix}")
                elif due:
                    try:
                        formatted_due = display_due(due)
                    except ValueError:
                        formatted_due = due
                    with_due.append((due, f"- [ ] {wikilink} — {formatted_due}"))
                else:
                    someday.append(f"- [ ] {wikilink}")

        with_due.sort(key=lambda row: row[0])

        lines = [f"## {display_name}", ""]
        categories = [
            ("С дедлайном", [item for _, item in with_due]),
            ("Делегировано", delegated),
            ("Когда-нибудь", someday),
        ]
        for cat_name, items in categories:
            callout_type = CALLOUT_TYPES[cat_name]
            state = "+" if items else "-"
            lines.append(f"> [!{callout_type}]{state} {cat_name}")
            if items:
                for item in items:
                    lines.append(f"> {item}")
            else:
                lines.append("> *Нет задач*")
            lines.append("")

        return "\n".join(lines)

    # ── Recurring tasks ──────────────────────────────────────

    def _recurring_dir(self) -> Path:
        return self.root / RECURRING_DIR

    def list_recurring_tasks(self, only_active: bool = True) -> list[dict[str, Any]]:
        rec_dir = self._recurring_dir()
        if not rec_dir.exists():
            return []
        results: list[dict[str, Any]] = []
        for fp in sorted(rec_dir.glob("R*.md")):
            text = fp.read_text(encoding="utf-8")
            fm, _ = _split_frontmatter(text)
            if only_active and str(fm.get("status", "")).strip().lower() != "active":
                continue
            fm["_path"] = str(fp)
            results.append(fm)
        return results

    def get_today_recurring(self, weekday: int, day: int, last_day: bool = False) -> list[dict[str, Any]]:
        tasks = self.list_recurring_tasks(only_active=True)
        matched: list[dict[str, Any]] = []
        for t in tasks:
            rec = str(t.get("recurrence", "")).strip().lower()
            rule = str(t.get("recurrence_rule") or "").strip().lower()
            if rec == "daily":
                matched.append(t)
            elif rec == "weekdays" and weekday <= 4:
                matched.append(t)
            elif rec == "weekly" and rule:
                if WEEKDAY_MAP.get(rule) == weekday:
                    matched.append(t)
            elif rec == "monthly":
                if rule == "last" and last_day:
                    matched.append(t)
                elif rule.isdigit() and int(rule) == day:
                    matched.append(t)
        matched.sort(key=lambda t: str(t.get("time") or "99:99"))
        return matched

    def create_recurring_task(
        self,
        task_id: str,
        title: str,
        recurrence: str,
        recurrence_rule: str = "",
        time: str = "",
        duration_min: int = 0,
        project: str = "life",
    ) -> Path:
        rec_dir = self._recurring_dir()
        rec_dir.mkdir(parents=True, exist_ok=True)
        slug = "-".join(
            [part for part in title.lower().replace("/", " ").split() if part]
        )
        filename = f"{task_id}-{slug}.md"
        target = rec_dir / filename
        frontmatter: dict[str, Any] = {
            "task_id": task_id,
            "title": title,
            "status": "active",
            "recurrence": recurrence,
            "recurrence_rule": recurrence_rule or None,
            "time": time or None,
            "duration_min": duration_min or None,
            "project": project,
        }
        content = (
            "---\n"
            f"{yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)}"
            "---\n"
            f"# {title}\n"
        )
        target.write_text(content, encoding="utf-8")
        return target

    def update_recurring_task(self, task_id: str, **fields: Any) -> Path | None:
        fp = self.find_recurring_file(task_id)
        if not fp:
            return None
        text = fp.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(text)
        fm.update(fields)
        updated = (
            "---\n"
            f"{yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)}"
            "---\n"
            f"{body}"
        )
        fp.write_text(updated, encoding="utf-8")
        return fp

    def find_recurring_file(self, task_id: str) -> Path | None:
        rec_dir = self._recurring_dir()
        if not rec_dir.exists():
            return None
        tid = task_id.upper()
        for fp in rec_dir.glob("R*.md"):
            if fp.name.upper().startswith(f"{tid}-"):
                return fp
        return None

    def next_recurring_id(self) -> str:
        rec_dir = self._recurring_dir()
        if not rec_dir.exists():
            return "R001"
        max_num = 0
        for fp in rec_dir.glob("R*.md"):
            name = fp.stem.split("-")[0]
            num_str = name[1:]
            if num_str.isdigit():
                max_num = max(max_num, int(num_str))
        return f"R{max_num + 1:03d}"

    def convert_to_recurring(
        self,
        command: str,
        task_id: int,
        recurrence: str,
        recurrence_rule: str = "",
        time: str = "",
    ) -> tuple[str, Path]:
        task_file = self.find_task_file(command, task_id)
        if not task_file:
            raise ValueError(f"Задача #{task_id} не найдена в проекте")
        data = self.read_task(task_file)
        fm = data["frontmatter"]
        title = str(fm.get("title") or "").strip() or task_file.stem
        project = str(fm.get("project") or command.lstrip("/"))

        new_id = self.next_recurring_id()
        new_path = self.create_recurring_task(
            task_id=new_id,
            title=title,
            recurrence=recurrence,
            recurrence_rule=recurrence_rule,
            time=time,
            project=project,
        )

        # Помечаем оригинал
        fm["status"] = "done"
        fm["migrated_to"] = new_id
        text = task_file.read_text(encoding="utf-8")
        _, body = _split_frontmatter(text)
        now = datetime.now().strftime("%Y-%m-%d")
        history_line = f"- {now} [Claude Assistant]: Мигрировано в повторяющуюся {new_id}\n"
        marker = "## История изменений"
        if marker not in body:
            body = body.rstrip() + f"\n\n{marker}\n"
        updated = (
            "---\n"
            f"{yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)}"
            "---\n"
            f"{body}{history_line}"
        )
        task_file.write_text(updated, encoding="utf-8")

        return new_id, new_path

    def get_tasks_with_due(self, due_date: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for command, rel in COMMAND_PATHS.items():
            task_dir = self.root / rel
            if not task_dir.exists():
                continue
            for fp in task_dir.glob("*.md"):
                text = fp.read_text(encoding="utf-8")
                fm, _ = _split_frontmatter(text)
                status = str(fm.get("status", "")).strip().lower()
                if status in STATUS_CLOSED:
                    continue
                due = str(fm.get("due") or "").strip()
                if due == due_date:
                    fm["_command"] = command
                    rel_path = fp.relative_to(self.root)
                    fm["_wiki_path"] = str(rel_path).removesuffix(".md")
                    results.append(fm)
        return results

    def generate_today_plan(self, tz: str = "Europe/Berlin") -> str:
        from calendar import monthrange
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(tz))
        weekday = now.weekday()
        day = now.day
        _, last = monthrange(now.year, now.month)
        is_last_day = day == last
        today_iso = now.strftime("%Y-%m-%d")

        date_header = f"{now.day} {RU_MONTHS[now.month]}, {RU_WEEKDAYS[weekday]}"

        # Recurring задачи на сегодня
        recurring = self.get_today_recurring(weekday, day, is_last_day)

        # One-off задачи с дедлайном сегодня
        due_tasks = self.get_tasks_with_due(today_iso)

        # Формируем строки
        lines: list[str] = []
        for t in recurring:
            time_str = str(t.get("time") or "").strip()
            title = str(t.get("title") or "")
            tid = str(t.get("task_id") or "")
            rec_file = self.find_recurring_file(tid)
            if rec_file:
                rel_path = rec_file.relative_to(self.root)
                wiki = str(rel_path).removesuffix(".md")
                display = f"#{tid} {title}" if tid else title
                entry = f"[[{wiki}|{display}]]"
            else:
                entry = f"#{tid} {title}" if tid else title
            if time_str:
                lines.append(f"> - [ ] {time_str} — {entry}")
            else:
                lines.append(f"> - [ ] {entry}")

        for t in due_tasks:
            title = str(t.get("title") or "")
            tid = str(t.get("task_id") or "")
            wiki_path = t.get("_wiki_path", "")
            display = f"#{tid} {title}" if tid else title
            entry = f"[[{wiki_path}|{display}]]" if wiki_path else display
            lines.append(f"> - [ ] {entry} (дедлайн сегодня)")

        today_section = f"## 📅 Сегодня — {date_header}\n\n> [!todo]+ Задачи на день\n"
        if lines:
            today_section += "\n".join(lines)
        else:
            today_section += "> *Нет запланированных задач*"

        # Записываем в дашборд
        dashboard_path = self.root / DASHBOARD_FILE
        if dashboard_path.exists():
            text = dashboard_path.read_text(encoding="utf-8")
            parts = text.split("\n---\n", 1)
            if len(parts) == 2:
                content = today_section + "\n\n---\n" + parts[1]
            else:
                content = today_section + "\n\n---\n\n" + text
        else:
            content = today_section

        dashboard_path.write_text(content, encoding="utf-8")
        return today_section

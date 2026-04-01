from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.tools.registry import ToolRegistry


def register_fitness_tools(registry: ToolRegistry, obsidian_root: str, timezone: str) -> None:
    fitness_dir = Path(obsidian_root) / "telegram-assistant" / "memory" / "fitness"
    fitness_dir.mkdir(parents=True, exist_ok=True)
    tz = ZoneInfo(timezone)

    def _today_file() -> Path:
        return fitness_dir / f"{date.today().isoformat()}.md"

    def _ensure_file(path: Path) -> None:
        if not path.exists():
            path.write_text(
                f"# Дневник {path.stem}\n\n## Тренировки\n\n## Питание\n\n## Заметки\n",
                encoding="utf-8",
            )

    def log_workout(workout_type: str, exercises: str, duration_min: int = 0, notes: str = "") -> str:
        path = _today_file()
        _ensure_file(path)
        now = datetime.now(tz).strftime("%H:%M")
        entry = f"\n- **{now}** {workout_type}"
        if duration_min:
            entry += f" ({duration_min} мин)"
        entry += f": {exercises}"
        if notes:
            entry += f" — {notes}"
        text = path.read_text(encoding="utf-8")
        marker = "## Питание"
        if marker in text:
            text = text.replace(marker, f"{entry}\n\n{marker}")
        else:
            text += entry + "\n"
        path.write_text(text, encoding="utf-8")
        return f"Тренировка записана: {workout_type} ({exercises})"

    registry.register(
        name="log_workout",
        description="Записать тренировку в дневник.",
        input_schema={
            "type": "object",
            "properties": {
                "workout_type": {"type": "string", "description": "Тип: бег, силовая, йога, растяжка и т.д."},
                "exercises": {"type": "string", "description": "Описание упражнений"},
                "duration_min": {"type": "integer", "description": "Продолжительность в минутах"},
                "notes": {"type": "string", "description": "Заметки (необязательно)"},
            },
            "required": ["workout_type", "exercises"],
        },
        handler=log_workout,
    )

    def log_meal(description: str, calories: int = 0, protein: int = 0, fat: int = 0, carbs: int = 0) -> str:
        path = _today_file()
        _ensure_file(path)
        now = datetime.now(tz).strftime("%H:%M")
        entry = f"\n- **{now}** {description}"
        macros = []
        if calories:
            macros.append(f"{calories} ккал")
        if protein:
            macros.append(f"Б:{protein}г")
        if fat:
            macros.append(f"Ж:{fat}г")
        if carbs:
            macros.append(f"У:{carbs}г")
        if macros:
            entry += f" ({', '.join(macros)})"
        text = path.read_text(encoding="utf-8")
        marker = "## Заметки"
        if marker in text:
            text = text.replace(marker, f"{entry}\n\n{marker}")
        else:
            text += entry + "\n"
        path.write_text(text, encoding="utf-8")
        return f"Приём пищи записан: {description}"

    registry.register(
        name="log_meal",
        description="Записать приём пищи в дневник (КБЖУ).",
        input_schema={
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Что было съедено"},
                "calories": {"type": "integer", "description": "Калории (необязательно)"},
                "protein": {"type": "integer", "description": "Белки в граммах"},
                "fat": {"type": "integer", "description": "Жиры в граммах"},
                "carbs": {"type": "integer", "description": "Углеводы в граммах"},
            },
            "required": ["description"],
        },
        handler=log_meal,
    )

    def get_fitness_summary(days: int = 7) -> str:
        files = sorted(fitness_dir.glob("*.md"), reverse=True)[:days]
        if not files:
            return "Записей в дневнике нет."
        lines = []
        for f in files:
            text = f.read_text(encoding="utf-8")
            workout_count = text.count("## Тренировки") and text.split("## Тренировки")[1].split("##")[0].count("- **")
            meal_count = text.count("## Питание") and text.split("## Питание")[1].split("##")[0].count("- **")
            lines.append(f"- {f.stem}: тренировок={workout_count}, приёмов пищи={meal_count}")
        return "\n".join(lines)

    registry.register(
        name="get_fitness_summary",
        description="Статистика тренировок и питания за последние N дней.",
        input_schema={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Количество дней (по умолчанию 7)"},
            },
        },
        handler=get_fitness_summary,
    )

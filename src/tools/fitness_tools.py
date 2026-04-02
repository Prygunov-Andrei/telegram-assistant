from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.integrations.apple_health import HealthDataReader
from src.tools.registry import ToolRegistry


def register_fitness_tools(
    registry: ToolRegistry, obsidian_root: str, timezone: str,
    health_reader: HealthDataReader | None = None,
) -> None:
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

    def read_fitness_log(date: str = "") -> str:
        if not date:
            date = datetime.now(tz).strftime("%Y-%m-%d")
        path = fitness_dir / f"{date}.md"
        if not path.exists():
            return f"Записей за {date} нет."
        return path.read_text(encoding="utf-8")

    registry.register(
        name="read_fitness_log",
        description="Прочитать полный дневник питания и тренировок за конкретный день. Показывает ВСЕ приёмы пищи с КБЖУ и тренировки.",
        input_schema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Дата YYYY-MM-DD (по умолчанию сегодня)"},
            },
        },
        handler=read_fitness_log,
    )

    def get_fitness_summary(days: int = 7) -> str:
        files = sorted(fitness_dir.glob("*.md"), reverse=True)[:days]
        if not files:
            return "Записей в дневнике нет."
        lines = []
        for f in files:
            text = f.read_text(encoding="utf-8")
            # Извлекаем реальные записи питания
            meals = []
            if "## Питание" in text:
                meal_section = text.split("## Питание")[1].split("##")[0]
                for line in meal_section.strip().split("\n"):
                    line = line.strip()
                    if line.startswith("- **"):
                        meals.append(line[2:])  # убираем "- "
            workouts = []
            if "## Тренировки" in text:
                workout_section = text.split("## Тренировки")[1].split("##")[0]
                for line in workout_section.strip().split("\n"):
                    line = line.strip()
                    if line.startswith("- **"):
                        workouts.append(line[2:])

            day_info = f"**{f.stem}**:"
            if meals:
                day_info += f"\n  Питание: {'; '.join(m[:60] for m in meals)}"
            if workouts:
                day_info += f"\n  Тренировки: {'; '.join(w[:60] for w in workouts)}"
            if not meals and not workouts:
                day_info += " пусто"
            lines.append(day_info)
        return "\n".join(lines)

    registry.register(
        name="get_fitness_summary",
        description="Сводка питания и тренировок за N дней с реальными данными (что ел, какие тренировки).",
        input_schema={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Количество дней (по умолчанию 7)"},
            },
        },
        handler=get_fitness_summary,
    )

    # ── Apple Health tools ────────────────────────────────────

    def get_health_summary(date: str = "") -> str:
        if not health_reader or not health_reader.is_available():
            return "Данные Apple Health недоступны. Установите Health Auto Export на iPhone и настройте экспорт в iCloud Drive."
        summary = health_reader.get_daily_summary(date)
        if "error" in summary:
            return summary["error"]
        lines = [f"**Здоровье за {summary.get('date', 'сегодня')}**"]
        if "heart_rate" in summary:
            hr = summary["heart_rate"]
            lines.append(f"Пульс: avg {hr['avg']}, min {hr['min']}, max {hr['max']} ({hr['readings']} замеров)")
        if "steps" in summary:
            lines.append(f"Шаги: {summary['steps']:,}")
        if "distance_km" in summary:
            lines.append(f"Дистанция: {summary['distance_km']} км")
        if "active_calories" in summary:
            lines.append(f"Активные калории: {summary['active_calories']} ккал")
        if "resting_calories" in summary:
            lines.append(f"Калории покоя: {summary['resting_calories']} ккал")
        if "sleep_hours" in summary:
            lines.append(f"Сон: {summary['sleep_hours']} ч")
        if "weight_kg" in summary:
            lines.append(f"Вес: {summary['weight_kg']} кг")
        if "spo2" in summary:
            lines.append(f"SpO2: {summary['spo2']}%")
        return "\n".join(lines) if len(lines) > 1 else "Данных за этот день нет."

    registry.register(
        name="get_health_summary",
        description="Сводка здоровья за день из Apple Health: пульс, шаги, калории, сон, вес, SpO2.",
        input_schema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Дата YYYY-MM-DD (по умолчанию сегодня)"},
            },
        },
        handler=get_health_summary,
    )

    def get_heart_rate(days: int = 1) -> str:
        if not health_reader or not health_reader.is_available():
            return "Данные Apple Health недоступны."
        entries = health_reader.get_metric("heart_rate", days=days)
        if not entries:
            return f"Данных о пульсе за {days} дней нет."
        # HR entries use Avg/Min/Max fields (summarized) or qty (raw)
        avgs = [float(e.get("Avg", e.get("qty", 0))) for e in entries if e.get("Avg") or e.get("qty")]
        mins = [float(e.get("Min", e.get("qty", 0))) for e in entries if e.get("Min") or e.get("qty")]
        maxs = [float(e.get("Max", e.get("qty", 0))) for e in entries if e.get("Max") or e.get("qty")]
        if not avgs:
            return "Нет числовых данных о пульсе."
        return (
            f"**Пульс за {days} дн.**\n"
            f"Средний: {round(sum(avgs) / len(avgs))} bpm\n"
            f"Мин: {round(min(mins))} bpm\n"
            f"Макс: {round(max(maxs))} bpm\n"
            f"Замеров: {len(entries)}"
        )

    registry.register(
        name="get_heart_rate",
        description="Детали пульса из Apple Health за N дней: среднее, мин, макс.",
        input_schema={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "За сколько дней (по умолчанию 1)"},
            },
        },
        handler=get_heart_rate,
    )

    def get_sleep_data(days: int = 7) -> str:
        if not health_reader or not health_reader.is_available():
            return "Данные Apple Health недоступны."
        entries = health_reader.get_metric("sleep", days=days)
        if not entries:
            return f"Данных о сне за {days} дней нет."
        lines = ["**Сон:**"]
        for e in entries[:14]:
            date_str = e.get("date", e.get("start", ""))[:10]
            value = e.get("qty", e.get("value", 0))
            hours = round(float(value) / 60, 1) if float(value) > 10 else float(value)
            lines.append(f"- {date_str}: {hours} ч")
        return "\n".join(lines)

    registry.register(
        name="get_sleep_data",
        description="Данные сна из Apple Health за N дней.",
        input_schema={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "За сколько дней (по умолчанию 7)"},
            },
        },
        handler=get_sleep_data,
    )

    def get_workouts(days: int = 7) -> str:
        if not health_reader or not health_reader.is_available():
            return "Данные Apple Health недоступны."
        workouts = health_reader.get_workout_details(days=days)
        if not workouts:
            return f"Тренировок за {days} дней нет."
        lines = [f"**Тренировки за {days} дн. (Apple Watch):**"]
        for w in workouts:
            info = f"- {w['start'][:10]} {w['type']} ({w['duration_min']} мин, {w['calories']} ккал)"
            if w.get("avg_hr"):
                info += f" HR avg:{w['avg_hr']}"
            if w.get("distance_km"):
                info += f" {w['distance_km']}км"
            lines.append(info)
        return "\n".join(lines)

    registry.register(
        name="get_workouts",
        description="Тренировки из Apple Watch за N дней: тип, длительность, пульс, калории.",
        input_schema={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "За сколько дней (по умолчанию 7)"},
            },
        },
        handler=get_workouts,
    )

    def get_weight_trend(days: int = 30) -> str:
        if not health_reader or not health_reader.is_available():
            return "Данные Apple Health недоступны."
        entries = health_reader.get_metric("weight", days=days)
        if not entries:
            entries = health_reader.get_metric("body_mass", days=days)
        if not entries:
            return f"Данных о весе за {days} дней нет."
        lines = [f"**Вес за {days} дн.:**"]
        for e in entries:
            date_str = e.get("date", e.get("start", ""))[:10]
            value = round(float(e.get("qty", e.get("value", 0))), 1)
            lines.append(f"- {date_str}: {value} кг")
        return "\n".join(lines)

    registry.register(
        name="get_weight_trend",
        description="Тренд веса из Apple Health за N дней.",
        input_schema={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "За сколько дней (по умолчанию 30)"},
            },
        },
        handler=get_weight_trend,
    )

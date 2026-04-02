"""Auto-context: подгружает релевантные данные перед каждым вызовом Claude.

Решает проблему "бот не помнит" — вместо надежды что Claude вызовет tool,
данные подгружаются АВТОМАТИЧЕСКИ в system prompt на основе ключевых слов.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

FOOD_KEYWORDS = {"ел", "еда", "завтрак", "обед", "ужин", "калори", "кбжу",
                  "питани", "съел", "перекус", "поел", "кушал", "пил", "выпил"}
TASK_KEYWORDS = {"задач", "план", "дашборд", "сегодня", "завтра", "расписани",
                  "дела", "список"}
HEALTH_KEYWORDS = {"пульс", "шаг", "калори", "сон", "вес", "здоров",
                    "тренировк", "спорт", "фитнес", "spo2", "кислород"}


class ContextGatherer:
    def __init__(
        self,
        fitness_dir: str,
        dashboard_path: str = "",
        health_reader: Any = None,
    ) -> None:
        self.fitness_dir = Path(fitness_dir)
        self.dashboard_path = Path(dashboard_path) if dashboard_path else None
        self.health_reader = health_reader

    def gather(self, user_text: str) -> str:
        """Собрать релевантный контекст для user_text."""
        lower = user_text.lower()
        parts: list[str] = []

        if any(kw in lower for kw in FOOD_KEYWORDS):
            fitness = self._read_today_fitness()
            if fitness:
                parts.append(f"[Дневник питания/тренировок за сегодня]\n{fitness}")

        if any(kw in lower for kw in TASK_KEYWORDS):
            dashboard = self._read_today_dashboard()
            if dashboard:
                parts.append(f"[План на сегодня из дашборда]\n{dashboard}")

        if any(kw in lower for kw in HEALTH_KEYWORDS):
            health = self._read_health_summary()
            if health:
                parts.append(f"[Данные здоровья с Apple Watch]\n{health}")

        return "\n\n".join(parts)

    def _read_today_fitness(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        path = self.fitness_dir / f"{today}.md"
        if not path.exists():
            return ""
        try:
            text = path.read_text(encoding="utf-8")
            return text[:3000]  # лимит чтобы не раздувать prompt
        except Exception:
            return ""

    def _read_today_dashboard(self) -> str:
        if not self.dashboard_path or not self.dashboard_path.exists():
            return ""
        try:
            text = self.dashboard_path.read_text(encoding="utf-8")
            # Только секция "Сегодня" (до ---)
            parts = text.split("\n---\n", 1)
            return parts[0][:2000] if parts else ""
        except Exception:
            return ""

    def _read_health_summary(self) -> str:
        if not self.health_reader or not self.health_reader.is_available():
            return ""
        try:
            summary = self.health_reader.get_daily_summary()
            if "error" in summary:
                return ""
            lines = []
            if "heart_rate" in summary:
                hr = summary["heart_rate"]
                lines.append(f"Пульс: avg {hr['avg']}, min {hr['min']}, max {hr['max']}")
            if "steps" in summary:
                lines.append(f"Шаги: {summary['steps']}")
            if "active_calories" in summary:
                lines.append(f"Активные калории: {summary['active_calories']} ккал")
            if "sleep_hours" in summary:
                lines.append(f"Сон: {summary['sleep_hours']} ч")
            if "weight_kg" in summary:
                lines.append(f"Вес: {summary['weight_kg']} кг")
            if "spo2" in summary:
                lines.append(f"SpO2: {summary['spo2']}%")
            return "\n".join(lines)
        except Exception:
            logger.debug("Failed to read health summary for context")
            return ""

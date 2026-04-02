"""Apple Health data reader.

Reads daily JSON files from Health Auto Export app (iPhone → iCloud Drive → Mac).
File format: HealthAutoExport-YYYY-MM-DD.json
Structure: {"data": {"metrics": [...], "workouts": [...]}}
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Mapping from Health Auto Export metric names to our names
METRIC_ALIASES = {
    "heart_rate": ["heart_rate"],
    "steps": ["step_count"],
    "active_calories": ["active_energy"],
    "resting_calories": ["basal_energy_burned"],
    "spo2": ["blood_oxygen_saturation"],
    "distance": ["walking_running_distance"],
    "exercise_time": ["apple_exercise_time"],
    "stand_hours": ["apple_stand_hour"],
    "flights": ["flights_climbed"],
    "walking_speed": ["walking_speed"],
    "weight": ["body_mass", "weight"],
    "sleep": ["sleep_analysis", "sleep_duration", "sleep_in_bed"],
}

# Metrics where values are in kJ and need conversion to kcal
KJ_METRICS = {"active_energy", "basal_energy_burned"}

KJ_TO_KCAL = 1 / 4.184


class HealthDataReader:
    def __init__(self, export_dir: str) -> None:
        self.export_dir = Path(export_dir).expanduser()

    def is_available(self) -> bool:
        if not self.export_dir.exists():
            return False
        return any(self.export_dir.rglob("HealthAutoExport-*.json"))

    def get_daily_summary(self, date: str = "") -> dict[str, Any]:
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        data = self._load_day(date)
        if not data:
            return {"error": f"Нет данных Apple Health за {date}."}

        metrics = data.get("data", {}).get("metrics", [])
        summary: dict[str, Any] = {"date": date}

        for m in metrics:
            name = m.get("name", "")
            units = m.get("units", "")
            entries = m.get("data", [])
            if not entries:
                continue
            values = [e["qty"] for e in entries if "qty" in e]

            if name == "heart_rate":
                # HR entries may use Avg/Min/Max fields instead of qty
                avgs = [float(e.get("Avg", e.get("qty", 0))) for e in entries if e.get("Avg") or e.get("qty")]
                mins = [float(e.get("Min", e.get("qty", 0))) for e in entries if e.get("Min") or e.get("qty")]
                maxs = [float(e.get("Max", e.get("qty", 0))) for e in entries if e.get("Max") or e.get("qty")]
                if avgs:
                    summary["heart_rate"] = {
                        "avg": round(sum(avgs) / len(avgs)),
                        "min": round(min(mins)) if mins else round(min(avgs)),
                        "max": round(max(maxs)) if maxs else round(max(avgs)),
                        "readings": len(entries),
                    }
            elif not values:
                continue
            elif name == "step_count":
                summary["steps"] = sum(int(float(v)) for v in values)
            elif name == "active_energy":
                kcal = sum(float(v) for v in values) * KJ_TO_KCAL
                summary["active_calories"] = round(kcal)
            elif name == "basal_energy_burned":
                kcal = sum(float(v) for v in values) * KJ_TO_KCAL
                summary["resting_calories"] = round(kcal)
            elif name == "walking_running_distance":
                summary["distance_km"] = round(sum(float(v) for v in values), 2)
            elif name == "blood_oxygen_saturation":
                avg = sum(float(v) for v in values) / len(values)
                summary["spo2"] = round(avg, 1)
            elif name == "apple_exercise_time":
                summary["exercise_min"] = round(sum(float(v) for v in values))
            elif name == "apple_stand_hour":
                summary["stand_hours"] = sum(int(float(v)) for v in values)
            elif name in ("body_mass", "weight"):
                summary["weight_kg"] = round(float(values[-1]), 1)
            elif name in ("sleep_analysis", "sleep_duration", "sleep_in_bed"):
                total_min = sum(float(v) for v in values)
                if total_min > 24:
                    summary["sleep_hours"] = round(total_min / 60, 1)
                else:
                    summary["sleep_hours"] = round(total_min, 1)
            elif name == "flights_climbed":
                summary["flights_climbed"] = sum(int(float(v)) for v in values)

        # Total calories
        if "active_calories" in summary and "resting_calories" in summary:
            summary["total_calories"] = summary["active_calories"] + summary["resting_calories"]

        return summary

    def get_metric(self, metric: str, days: int = 7) -> list[dict[str, Any]]:
        # Resolve alias
        target_names = METRIC_ALIASES.get(metric.lower(), [metric.lower()])

        all_entries: list[dict[str, Any]] = []
        today = datetime.now()

        for i in range(days):
            date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            data = self._load_day(date_str)
            if not data:
                continue
            for m in data.get("data", {}).get("metrics", []):
                if m.get("name", "") in target_names or metric.lower() in m.get("name", "").lower():
                    for e in m.get("data", []):
                        e["_date"] = date_str
                        # Convert kJ to kcal if needed
                        if m.get("name", "") in KJ_METRICS and "qty" in e:
                            e["qty_kcal"] = round(float(e["qty"]) * KJ_TO_KCAL, 1)
                        all_entries.append(e)
        return all_entries

    def get_workout_details(self, days: int = 7) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        today = datetime.now()

        for i in range(days):
            date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            data = self._load_day(date_str)
            if not data:
                continue
            for w in data.get("data", {}).get("workouts", []):
                result.append({
                    "date": date_str,
                    "type": w.get("name", w.get("workoutActivityType", "Unknown")),
                    "start": w.get("start", ""),
                    "end": w.get("end", ""),
                    "duration_min": round(float(w.get("duration", 0)) / 60, 1) if w.get("duration") else None,
                    "calories": round(float(w.get("totalEnergyBurned", 0))) if w.get("totalEnergyBurned") else None,
                    "avg_hr": w.get("avgHeartRate"),
                    "max_hr": w.get("maxHeartRate"),
                    "distance_km": round(float(w.get("totalDistance", 0)) / 1000, 2) if w.get("totalDistance") else None,
                })
        return result

    def get_daily_summaries(self, days: int = 7) -> list[dict[str, Any]]:
        """Сводки за несколько дней (для трендов)."""
        result = []
        today = datetime.now()
        for i in range(days):
            date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            s = self.get_daily_summary(date_str)
            if "error" not in s:
                result.append(s)
        return result

    def _load_day(self, date: str) -> dict[str, Any] | None:
        """Load JSON for a specific date."""
        # Try multiple locations
        patterns = [
            self.export_dir / f"HealthAutoExport-{date}.json",
            self.export_dir / "New Automation" / f"HealthAutoExport-{date}.json",
            self.export_dir / "autosync" / f"HealthAutoExport-{date}.json",
        ]
        for path in patterns:
            if path.exists():
                return self._read_json(path)

        # Fallback: search recursively
        for f in self.export_dir.rglob(f"HealthAutoExport-{date}.json"):
            return self._read_json(f)
        return None

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to read health data from %s", path)
            return None

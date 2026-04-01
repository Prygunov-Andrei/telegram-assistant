from __future__ import annotations

import asyncio
from pathlib import Path

from src.tools.registry import ToolRegistry
from src.tools.fitness_tools import register_fitness_tools


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_log_workout(tmp_path: Path):
    registry = ToolRegistry()
    register_fitness_tools(registry, str(tmp_path), "Europe/Berlin")
    result = _run(registry.execute("log_workout", {
        "workout_type": "бег",
        "exercises": "5 км парк",
        "duration_min": 30,
    }))
    assert "бег" in result
    # Check file was created
    fitness_dir = tmp_path / "telegram-assistant" / "memory" / "fitness"
    files = list(fitness_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "бег" in content
    assert "5 км парк" in content
    assert "30 мин" in content


def test_log_meal(tmp_path: Path):
    registry = ToolRegistry()
    register_fitness_tools(registry, str(tmp_path), "Europe/Berlin")
    result = _run(registry.execute("log_meal", {
        "description": "Овсянка с бананом",
        "calories": 350,
        "protein": 12,
    }))
    assert "Овсянка" in result
    fitness_dir = tmp_path / "telegram-assistant" / "memory" / "fitness"
    files = list(fitness_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "350 ккал" in content
    assert "Б:12г" in content


def test_get_fitness_summary_empty(tmp_path: Path):
    registry = ToolRegistry()
    register_fitness_tools(registry, str(tmp_path), "Europe/Berlin")
    result = _run(registry.execute("get_fitness_summary", {}))
    assert "нет" in result.lower()


def test_fitness_tools_count(tmp_path: Path):
    registry = ToolRegistry()
    register_fitness_tools(registry, str(tmp_path), "Europe/Berlin")
    assert registry.tool_count() == 3

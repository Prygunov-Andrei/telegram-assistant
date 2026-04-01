from __future__ import annotations

import asyncio
from pathlib import Path

from src.tools.registry import ToolRegistry
from src.tools.deutsch_tools import register_deutsch_tools


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_add_word_to_anki(tmp_path: Path):
    registry = ToolRegistry()
    register_deutsch_tools(registry, str(tmp_path))
    result = _run(registry.execute("add_word_to_anki", {
        "german": "der Hund",
        "russian": "собака",
        "example": "Der Hund ist groß.",
        "grammar_note": "m, -e/-e",
    }))
    assert "der Hund" in result
    anki_file = tmp_path / "deutsch" / "Словарь" / "слова_для_anki.md"
    assert anki_file.exists()
    content = anki_file.read_text(encoding="utf-8")
    assert "der Hund" in content
    assert "собака" in content
    assert "Der Hund ist groß." in content


def test_get_recent_words_empty(tmp_path: Path):
    registry = ToolRegistry()
    register_deutsch_tools(registry, str(tmp_path))
    result = _run(registry.execute("get_recent_words", {}))
    assert "пуст" in result.lower()


def test_get_recent_words(tmp_path: Path):
    registry = ToolRegistry()
    register_deutsch_tools(registry, str(tmp_path))
    _run(registry.execute("add_word_to_anki", {"german": "die Katze", "russian": "кошка"}))
    _run(registry.execute("add_word_to_anki", {"german": "das Haus", "russian": "дом"}))
    result = _run(registry.execute("get_recent_words", {"count": 5}))
    assert "die Katze" in result
    assert "das Haus" in result


def test_deutsch_tools_count(tmp_path: Path):
    registry = ToolRegistry()
    register_deutsch_tools(registry, str(tmp_path))
    assert registry.tool_count() == 2

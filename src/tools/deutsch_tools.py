from __future__ import annotations

from datetime import date
from pathlib import Path

from src.tools.registry import ToolRegistry


def register_deutsch_tools(registry: ToolRegistry, obsidian_root: str) -> None:
    anki_file = Path(obsidian_root) / "deutsch" / "Словарь" / "слова_для_anki.md"

    def add_word_to_anki(
        german: str,
        russian: str,
        example: str = "",
        grammar_note: str = "",
    ) -> str:
        anki_file.parent.mkdir(parents=True, exist_ok=True)
        if not anki_file.exists():
            anki_file.write_text("# Слова для Anki\n\n| Немецкий | Русский | Пример | Грамматика | Дата |\n|---|---|---|---|---|\n", encoding="utf-8")

        today = date.today().isoformat()
        row = f"| {german} | {russian} | {example} | {grammar_note} | {today} |"
        text = anki_file.read_text(encoding="utf-8")
        text += row + "\n"
        anki_file.write_text(text, encoding="utf-8")
        return f"Слово добавлено: {german} — {russian}"

    registry.register(
        name="add_word_to_anki",
        description="Добавить немецкое слово в список для Anki-карточек.",
        input_schema={
            "type": "object",
            "properties": {
                "german": {"type": "string", "description": "Слово/фраза на немецком"},
                "russian": {"type": "string", "description": "Перевод на русский"},
                "example": {"type": "string", "description": "Пример предложения (необязательно)"},
                "grammar_note": {"type": "string", "description": "Грамматическая заметка (род, падеж, спряжение)"},
            },
            "required": ["german", "russian"],
        },
        handler=add_word_to_anki,
    )

    def get_recent_words(count: int = 10) -> str:
        if not anki_file.exists():
            return "Список слов пуст."
        lines = anki_file.read_text(encoding="utf-8").strip().split("\n")
        table_lines = [l for l in lines if l.startswith("|") and not l.startswith("| Немецкий") and not l.startswith("|---")]
        if not table_lines:
            return "Список слов пуст."
        recent = table_lines[-count:]
        return "\n".join(recent)

    registry.register(
        name="get_recent_words",
        description="Показать последние добавленные немецкие слова.",
        input_schema={
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "Количество слов (по умолчанию 10)"},
            },
        },
        handler=get_recent_words,
    )

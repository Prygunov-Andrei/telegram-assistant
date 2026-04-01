from __future__ import annotations

from dataclasses import dataclass

ROUTINE_PREFIXES = (
    "/all", "/plan", "/gt24", "/avgust", "/erp", "/deutsch",
    "/life", "/april", "/books", "/kaz", "/daemon", "/assistant",
    "/usage", "/status",
)

HIGH_REASONING_MARKERS = (
    "архитект", "спроект", "рефактор", "интеграц", "сложн",
    "стратег", "end-to-end", "проанализ", "сравн", "объясн",
)


@dataclass(frozen=True)
class ModelRoute:
    model: str
    reason: str


def choose_model(text: str, main_model: str, routine_model: str) -> ModelRoute:
    clean = (text or "").strip().lower()
    if not clean:
        return ModelRoute(model=routine_model, reason="empty_input_defaults_to_routine")
    if clean.startswith(ROUTINE_PREFIXES):
        return ModelRoute(model=routine_model, reason="slash_command_routine")
    if any(marker in clean for marker in HIGH_REASONING_MARKERS):
        return ModelRoute(model=main_model, reason="high_reasoning_marker")
    if len(clean) > 350:
        return ModelRoute(model=main_model, reason="long_message")
    return ModelRoute(model=routine_model, reason="default_routine")

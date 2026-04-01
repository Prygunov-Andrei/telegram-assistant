from __future__ import annotations

from src.brain.model_router import choose_model


def test_slash_command_uses_routine():
    route = choose_model("/life", "opus", "haiku")
    assert route.model == "haiku"
    assert route.reason == "slash_command_routine"


def test_complex_query_uses_main():
    route = choose_model("спроектируй архитектуру системы задач", "opus", "haiku")
    assert route.model == "opus"
    assert route.reason == "high_reasoning_marker"


def test_long_message_uses_main():
    route = choose_model("a" * 400, "opus", "haiku")
    assert route.model == "opus"
    assert route.reason == "long_message"


def test_empty_uses_routine():
    route = choose_model("", "opus", "haiku")
    assert route.model == "haiku"


def test_short_message_uses_routine():
    route = choose_model("привет", "opus", "haiku")
    assert route.model == "haiku"
    assert route.reason == "default_routine"

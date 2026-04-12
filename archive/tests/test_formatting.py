from __future__ import annotations

from src.utils.formatting import display_due, sanitize_output, split_message


def test_display_due():
    assert display_due("2026-04-01") == "1 апреля (среда)"
    assert display_due("2026-01-01") == "1 января (четверг)"


def test_split_message_short():
    assert split_message("hello") == ["hello"]


def test_split_message_long():
    text = "A" * 5000
    chunks = split_message(text, limit=4096)
    assert len(chunks) >= 2
    assert all(len(c) <= 4096 for c in chunks)


def test_split_message_paragraphs():
    text = ("Paragraph one.\n\n" * 50).strip()
    chunks = split_message(text, limit=100)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)


def test_sanitize_output_anthropic_key():
    text = "Key is sk-ant-" + "x" * 40 + " end"  # fake key for test
    result = sanitize_output(text)
    assert "sk-ant" not in result
    assert "[REDACTED]" in result


def test_sanitize_output_github_token():
    text = "ghp_" + "a" * 36 + " is secret"  # fake token for test
    result = sanitize_output(text)
    assert "ghp_" not in result
    assert "[REDACTED]" in result


def test_sanitize_output_no_secrets():
    text = "This is a normal message without secrets."
    assert sanitize_output(text) == text

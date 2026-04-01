from __future__ import annotations

import re
from datetime import datetime

_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[a-zA-Z0-9_-]{6,}"),      # Anthropic
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),             # OpenAI
    re.compile(r"ghp_[a-zA-Z0-9]{36,}"),            # GitHub PAT
    re.compile(r"gsk_[a-zA-Z0-9]{20,}"),            # Groq
    re.compile(r"xoxb-[a-zA-Z0-9-]{20,}"),          # Slack bot
    re.compile(r"AIza[a-zA-Z0-9_-]{35}"),           # Google API key
]


def sanitize_output(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text

RU_WEEKDAYS = {
    0: "понедельник",
    1: "вторник",
    2: "среда",
    3: "четверг",
    4: "пятница",
    5: "суббота",
    6: "воскресенье",
}

RU_MONTHS = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def display_due(due_iso: str) -> str:
    dt = datetime.strptime(due_iso, "%Y-%m-%d")
    return f"{dt.day} {RU_MONTHS[dt.month]} ({RU_WEEKDAYS[dt.weekday()]})"


def split_message(text: str, limit: int = 4096) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(paragraph) <= limit:
                current = paragraph
            else:
                for line in paragraph.split("\n"):
                    if len(current) + len(line) + 1 <= limit:
                        current = f"{current}\n{line}" if current else line
                    else:
                        if current:
                            chunks.append(current)
                        if len(line) > limit:
                            while line:
                                chunks.append(line[:limit])
                                line = line[limit:]
                            current = ""
                        else:
                            current = line
    if current:
        chunks.append(current)
    return chunks if chunks else [text[:limit]]

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MemoryContext:
    blocks: list[dict[str, str]]


def load_memory_context(memory_dir: str) -> MemoryContext:
    root = Path(memory_dir)
    if not root.exists():
        return MemoryContext(blocks=[])

    blocks: list[dict[str, str]] = []
    for md in sorted(root.glob("*.md")):
        if md.name.startswith("."):
            continue
        text = md.read_text(encoding="utf-8").strip()
        if not text:
            continue
        blocks.append(
            {
                "type": "text",
                "text": f"[memory:{md.name}]\n{text}",
            }
        )
    return MemoryContext(blocks=blocks)

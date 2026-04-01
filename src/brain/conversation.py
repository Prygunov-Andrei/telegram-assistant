from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MAX_PAIRS = 50


@dataclass
class Conversation:
    chat_id: int
    messages: list[dict[str, Any]] = field(default_factory=list)

    def add_user_message(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})
        self._trim()

    def add_user_message_with_image(self, text: str, image_base64: str, media_type: str = "image/jpeg") -> None:
        content: list[dict[str, Any]] = []
        if text:
            content.append({"type": "text", "text": text})
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": image_base64},
        })
        self.messages.append({"role": "user", "content": content})
        self._trim()

    def add_assistant_response(self, content: Any) -> None:
        if isinstance(content, list):
            serialized = []
            for block in content:
                if hasattr(block, "type"):
                    if block.type == "text":
                        serialized.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        serialized.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                elif isinstance(block, dict):
                    serialized.append(block)
            self.messages.append({"role": "assistant", "content": serialized})
        else:
            self.messages.append({"role": "assistant", "content": str(content)})

    def add_tool_results(self, results: list[dict[str, Any]]) -> None:
        self.messages.append({"role": "user", "content": results})

    def get_messages(self) -> list[dict[str, Any]]:
        return list(self.messages)

    def _trim(self) -> None:
        pair_count = sum(1 for m in self.messages if m["role"] == "user") // 2
        while pair_count > MAX_PAIRS and len(self.messages) >= 2:
            self.messages.pop(0)
            if self.messages and self.messages[0]["role"] != "user":
                self.messages.pop(0)
            pair_count = sum(1 for m in self.messages if m["role"] == "user") // 2


class ConversationStore:
    def __init__(self) -> None:
        self._conversations: dict[int, Conversation] = {}

    def get_or_create(self, chat_id: int) -> Conversation:
        if chat_id not in self._conversations:
            self._conversations[chat_id] = Conversation(chat_id=chat_id)
        return self._conversations[chat_id]

    def active_count(self) -> int:
        return len(self._conversations)

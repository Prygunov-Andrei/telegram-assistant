from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

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
    def __init__(self, persist_dir: str = "") -> None:
        self._conversations: dict[int, Conversation] = {}
        self._persist_dir = Path(persist_dir) if persist_dir else None
        if self._persist_dir:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            self._load_all()

    def get_or_create(self, chat_id: int) -> Conversation:
        if chat_id not in self._conversations:
            self._conversations[chat_id] = Conversation(chat_id=chat_id)
        return self._conversations[chat_id]

    def active_count(self) -> int:
        return len(self._conversations)

    def save(self, chat_id: int) -> None:
        """Сохранить историю чата на диск."""
        if not self._persist_dir:
            return
        conv = self._conversations.get(chat_id)
        if not conv or not conv.messages:
            return
        # Фильтруем сообщения с image data (слишком большие)
        clean_messages = self._strip_images(conv.messages)
        path = self._persist_dir / f"{chat_id}.json"
        try:
            path.write_text(
                json.dumps(clean_messages, ensure_ascii=False, indent=None),
                encoding="utf-8",
            )
        except Exception:
            logger.warning("Failed to persist conversation %d", chat_id)

    def _load_all(self) -> None:
        """Загрузить все сохранённые истории при старте."""
        if not self._persist_dir:
            return
        for path in self._persist_dir.glob("*.json"):
            try:
                chat_id = int(path.stem)
                messages = json.loads(path.read_text(encoding="utf-8"))
                conv = Conversation(chat_id=chat_id, messages=messages)
                self._conversations[chat_id] = conv
                logger.info("Loaded conversation %d (%d messages)", chat_id, len(messages))
            except Exception:
                logger.warning("Failed to load conversation from %s", path)

    @staticmethod
    def _strip_images(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Убрать base64 image data перед сохранением (слишком большие)."""
        result = []
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                clean_blocks = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "image":
                        clean_blocks.append({"type": "text", "text": "[изображение]"})
                    else:
                        clean_blocks.append(block)
                result.append({"role": msg["role"], "content": clean_blocks})
            else:
                result.append(msg)
        return result

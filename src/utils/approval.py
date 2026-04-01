from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingAction:
    action: str
    payload: dict[str, Any]
    description: str


class ApprovalManager:
    def __init__(self) -> None:
        self._pending: dict[str, PendingAction] = {}

    def register(self, action: str, payload: dict[str, Any], description: str) -> str:
        token = secrets.token_hex(4)
        self._pending[token] = PendingAction(
            action=action, payload=payload, description=description
        )
        return token

    def get_pending(self, token: str) -> PendingAction | None:
        return self._pending.get(token)

    def approve(self, token: str) -> PendingAction | None:
        return self._pending.pop(token, None)

    def pending_count(self) -> int:
        return len(self._pending)

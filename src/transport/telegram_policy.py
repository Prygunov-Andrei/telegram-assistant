from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class GroupRule:
    require_mention: bool
    allow_from: frozenset[int]
    mode: str
    title: str


@dataclass(frozen=True)
class TelegramPolicy:
    owner_id: int
    dm_allow_from: frozenset[int] = field(default_factory=frozenset)
    groups: dict[int, GroupRule] = field(default_factory=dict)

    def allows(
        self,
        chat_id: int,
        user_id: int,
        is_private: bool,
        text: str,
        bot_username: str | None,
    ) -> bool:
        if is_private:
            return user_id == self.owner_id or user_id in self.dm_allow_from

        group = self.groups.get(chat_id)
        if not group:
            return False

        if group.allow_from and user_id not in group.allow_from:
            return False

        if group.require_mention:
            if not bot_username:
                return False
            mention = f"@{bot_username.lower()}"
            if mention not in (text or "").lower():
                return False

        return True

    def is_owner(self, user_id: int) -> bool:
        return user_id == self.owner_id


def load_policy_from_json(path: str) -> TelegramPolicy:
    config_path = Path(path)
    if not config_path.exists():
        return TelegramPolicy(owner_id=435926703)

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    owner_id = int(raw.get("owner_id", 435926703))
    dm_allow = frozenset(int(x) for x in raw.get("dm_allow_from", []))

    groups: dict[int, GroupRule] = {}
    for g in raw.get("groups", []):
        chat_id = int(g["chat_id"])
        groups[chat_id] = GroupRule(
            require_mention=bool(g.get("require_mention", True)),
            allow_from=frozenset(int(x) for x in g.get("allow_from", [])),
            mode=g.get("mode", "limited"),
            title=g.get("title", f"chat-{chat_id}"),
        )

    return TelegramPolicy(owner_id=owner_id, dm_allow_from=dm_allow, groups=groups)

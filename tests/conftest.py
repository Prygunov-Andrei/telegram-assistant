from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.brain.conversation import Conversation, ConversationStore
from src.memory.vault_adapter import VaultAdapter
from src.tools.registry import ToolRegistry
from src.transport.telegram_policy import TelegramPolicy, GroupRule
from src.utils.cost_tracker import CostTracker


@pytest.fixture
def tmp_vault(tmp_path: Path) -> VaultAdapter:
    task_dir = tmp_path / "life" / "ЗАДАЧИ"
    task_dir.mkdir(parents=True)
    (task_dir / "100-test-task.md").write_text(
        "---\ntask_id: 100\ntitle: Test Task\nstatus: todo\ndue: '2026-04-15'\nassignee: ''\n---\n\n# Test Task\n",
        encoding="utf-8",
    )
    (task_dir / "101-done-task.md").write_text(
        "---\ntask_id: 101\ntitle: Done Task\nstatus: done\n---\n\n# Done Task\n",
        encoding="utf-8",
    )
    (task_dir / "102-delegated.md").write_text(
        "---\ntask_id: 102\ntitle: Delegated Task\nstatus: todo\nassignee: Ирина\n---\n\n# Delegated\n",
        encoding="utf-8",
    )
    return VaultAdapter(str(tmp_path))


@pytest.fixture
def conversation() -> Conversation:
    return Conversation(chat_id=123)


@pytest.fixture
def conversation_store() -> ConversationStore:
    return ConversationStore()


@pytest.fixture
def tool_registry() -> ToolRegistry:
    return ToolRegistry()


@pytest.fixture
def policy_owner_only() -> TelegramPolicy:
    return TelegramPolicy(owner_id=435926703)


@pytest.fixture
def policy_with_group() -> TelegramPolicy:
    return TelegramPolicy(
        owner_id=435926703,
        groups={
            -12345: GroupRule(
                require_mention=True,
                allow_from=frozenset({435926703, 111222}),
                mode="interactive",
                title="Test Group",
            )
        },
    )


@pytest.fixture
def cost_tracker(tmp_path: Path) -> CostTracker:
    return CostTracker(usage_dir=str(tmp_path / "usage"), daily_limit_usd=1.0)

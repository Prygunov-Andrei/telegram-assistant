from __future__ import annotations

import asyncio

from src.memory.vault_adapter import VaultAdapter
from src.tools.registry import ToolRegistry
from src.tools.vault_tools import register_vault_tools
from src.utils.approval import ApprovalManager


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _setup(tmp_vault, tool_registry):
    approval = ApprovalManager()
    register_vault_tools(tool_registry, tmp_vault, approval)
    return approval


def test_list_tasks(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    _setup(tmp_vault, tool_registry)
    result = _run(tool_registry.execute("list_tasks", {"project": "life"}))
    assert "#100 Test Task" in result
    assert "#101" not in result  # done — не показываем
    assert "Ирина" in result  # делегировано


def test_list_tasks_unknown_project(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    _setup(tmp_vault, tool_registry)
    result = _run(tool_registry.execute("list_tasks", {"project": "nonexistent"}))
    assert "Открытых задач нет" in result


def test_get_all_projects_summary(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    _setup(tmp_vault, tool_registry)
    result = _run(tool_registry.execute("get_all_projects_summary", {}))
    assert "/life" in result
    assert "2" in result  # 2 open tasks (#100, #102)


def test_create_task(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    approval = _setup(tmp_vault, tool_registry)
    result = _run(tool_registry.execute("create_task", {
        "project": "life",
        "title": "Buy Milk",
        "task_id": 200,
        "task_type": "personal",
    }))
    # Should require approval, not create directly
    assert "подтверждени" in result.lower()
    assert "токен" in result.lower()


def test_create_task_with_approval(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    approval = _setup(tmp_vault, tool_registry)
    result = _run(tool_registry.execute("create_task", {
        "project": "life",
        "title": "Buy Milk",
        "task_id": 200,
        "task_type": "personal",
    }))
    # Extract token and approve
    token = result.split("токеном: ")[1].strip()
    result2 = _run(tool_registry.execute("approve_vault_action", {"token": token}))
    assert "создана" in result2.lower()


def test_read_task(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    _setup(tmp_vault, tool_registry)
    result = _run(tool_registry.execute("read_task", {"project": "life", "task_id": 100}))
    assert "Test Task" in result
    assert "todo" in result


def test_search_tasks(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    _setup(tmp_vault, tool_registry)
    result = _run(tool_registry.execute("search_tasks", {"query": "Delegated"}))
    assert "#102" in result


def test_update_task_status(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    approval = _setup(tmp_vault, tool_registry)
    # Should require approval
    result = _run(tool_registry.execute("update_task_status", {
        "project": "life",
        "task_id": 100,
        "new_status": "done",
    }))
    assert "подтверждени" in result.lower()
    # Approve it
    token = result.split("токеном: ")[1].strip()
    result2 = _run(tool_registry.execute("approve_vault_action", {"token": token}))
    assert "done" in result2
    # Verify file was updated
    data = tmp_vault.read_task(tmp_vault.find_task_file("/life", 100))
    assert data["frontmatter"]["status"] == "done"


def test_tools_registered_count(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    _setup(tmp_vault, tool_registry)
    assert tool_registry.tool_count() == 16  # 7 read-only + 8 modifying + 1 approve_vault_action

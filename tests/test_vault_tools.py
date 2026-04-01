from __future__ import annotations

import asyncio

from src.memory.vault_adapter import VaultAdapter
from src.tools.registry import ToolRegistry
from src.tools.vault_tools import register_vault_tools


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_list_tasks(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    register_vault_tools(tool_registry, tmp_vault)
    result = _run(tool_registry.execute("list_tasks", {"project": "life"}))
    assert "#100 Test Task" in result
    assert "#101" not in result  # done — не показываем
    assert "Ирина" in result  # делегировано


def test_list_tasks_unknown_project(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    register_vault_tools(tool_registry, tmp_vault)
    result = _run(tool_registry.execute("list_tasks", {"project": "nonexistent"}))
    assert "Открытых задач нет" in result


def test_get_all_projects_summary(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    register_vault_tools(tool_registry, tmp_vault)
    result = _run(tool_registry.execute("get_all_projects_summary", {}))
    assert "/life" in result
    assert "2" in result  # 2 open tasks (#100, #102)


def test_create_task(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    register_vault_tools(tool_registry, tmp_vault)
    result = _run(tool_registry.execute("create_task", {
        "project": "life",
        "title": "Buy Milk",
        "task_id": 200,
        "task_type": "personal",
    }))
    assert "создана" in result.lower() or "Buy Milk" in result or "200" in result


def test_read_task(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    register_vault_tools(tool_registry, tmp_vault)
    result = _run(tool_registry.execute("read_task", {"project": "life", "task_id": 100}))
    assert "Test Task" in result
    assert "todo" in result


def test_search_tasks(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    register_vault_tools(tool_registry, tmp_vault)
    result = _run(tool_registry.execute("search_tasks", {"query": "Delegated"}))
    assert "#102" in result


def test_update_task_status(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    register_vault_tools(tool_registry, tmp_vault)
    result = _run(tool_registry.execute("update_task_status", {
        "project": "life",
        "task_id": 100,
        "new_status": "done",
    }))
    assert "done" in result
    # Verify file was updated
    data = tmp_vault.read_task(tmp_vault.find_task_file("/life", 100))
    assert data["frontmatter"]["status"] == "done"


def test_tools_registered_count(tmp_vault: VaultAdapter, tool_registry: ToolRegistry):
    register_vault_tools(tool_registry, tmp_vault)
    assert tool_registry.tool_count() == 6

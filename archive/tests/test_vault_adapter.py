from __future__ import annotations

from src.memory.vault_adapter import VaultAdapter


def test_list_open_tasks(tmp_vault: VaultAdapter):
    sections = tmp_vault.list_open_tasks("/life")
    assert len(sections["С дедлайном"]) == 1
    assert "#100" in sections["С дедлайном"][0]
    assert len(sections["Делегировано"]) == 1
    assert "Ирина" in sections["Делегировано"][0]
    assert len(sections["Когда-нибудь"]) == 0


def test_done_tasks_excluded(tmp_vault: VaultAdapter):
    sections = tmp_vault.list_open_tasks("/life")
    all_items = sections["С дедлайном"] + sections["Делегировано"] + sections["Когда-нибудь"]
    assert not any("#101" in item for item in all_items)


def test_project_counts(tmp_vault: VaultAdapter):
    counts = tmp_vault.project_counts()
    assert counts.get("/life", 0) == 2


def test_create_task(tmp_vault: VaultAdapter):
    path = tmp_vault.create_task("/life", "New Task", 200)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "task_id: 200" in text
    assert "Claude Assistant" in text


def test_update_task_status(tmp_vault: VaultAdapter):
    task_file = tmp_vault.find_task_file("/life", 100)
    assert task_file is not None
    tmp_vault.update_task_status(task_file, "in_progress")
    text = task_file.read_text(encoding="utf-8")
    assert "status: in_progress" in text
    assert "Claude Assistant" in text


def test_unknown_command(tmp_vault: VaultAdapter):
    sections = tmp_vault.list_open_tasks("/unknown")
    assert all(len(v) == 0 for v in sections.values())


def test_validate_path(tmp_vault: VaultAdapter):
    from pathlib import Path
    assert tmp_vault.validate_path(Path(tmp_vault.root) / "life" / "ЗАДАЧИ" / "test.md")
    assert not tmp_vault.validate_path(Path("/etc/passwd"))

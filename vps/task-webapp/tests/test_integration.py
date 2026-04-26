"""Integration tests: full task CRUD cycle via Vault.

Tests that all vault operations work together correctly and files
end up in the expected state on disk.
"""
import os
os.environ.setdefault("BOT_TOKEN", "test:token")

from vault import VaultAdapter


def test_full_task_lifecycle(tmp_vault):
    """Create → list → update status → update tags → archive."""
    vault = VaultAdapter(str(tmp_vault))

    # Create
    task = vault.create_task(
        project="life",
        title="Интеграционный тест",
        task_type="dev",
    )
    task_id = task["task_id"]
    assert task_id > 0

    # File exists on disk
    fp = vault.find_task_file("life", task_id)
    assert fp is not None
    assert fp.exists()

    # Listed in tasks
    tasks = vault.list_tasks(project="life")
    ids = [t["task_id"] for t in tasks]
    assert task_id in ids

    # Update status
    vault.update_task("life", task_id, {"status": "in_progress"})
    text = fp.read_text(encoding="utf-8")
    assert "status: in_progress" in text

    # Update tags
    vault.update_task("life", task_id, {"tags": ["integration", "test"]})
    text = fp.read_text(encoding="utf-8")
    assert "integration" in text
    assert "test" in text

    # Archive
    assert vault.archive_task("life", task_id) is True
    assert vault.find_task_file("life", task_id) is None

    archive_dir = tmp_vault / "life" / "ЗАДАЧИ" / "archive"
    assert archive_dir.exists()
    assert len(list(archive_dir.glob(f"{task_id}-*.md"))) == 1


def test_dashboard_reflects_state(tmp_vault):
    """Regenerated dashboard shows current open tasks."""
    vault = VaultAdapter(str(tmp_vault))

    vault.create_task(project="life", title="Задача А")
    vault.create_task(project="april", title="Задача Б")

    vault.regenerate_dashboard()

    dash = (tmp_vault / "ДАШБОРД.md").read_text(encoding="utf-8")
    assert "Задача А" in dash
    assert "Задача Б" in dash


def test_project_counts_after_operations(tmp_vault):
    """Counts update correctly after create/archive."""
    vault = VaultAdapter(str(tmp_vault))

    initial = vault.project_counts()["life"]["count"]

    vault.create_task(project="life", title="New A")
    vault.create_task(project="life", title="New B")

    after_create = vault.project_counts()["life"]["count"]
    assert after_create == initial + 2

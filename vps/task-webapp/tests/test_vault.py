"""Tests for vault.py — task file I/O."""
from vault import VaultAdapter as Vault, _split_frontmatter


def test_split_frontmatter_valid():
    text = "---\nkey: value\n---\n\nBody content"
    fm, body = _split_frontmatter(text)
    assert fm == {"key": "value"}
    assert "Body content" in body


def test_split_frontmatter_no_frontmatter():
    text = "Just plain markdown"
    fm, body = _split_frontmatter(text)
    assert fm == {}
    assert body == text


def test_list_tasks_all(tmp_vault):
    vault = Vault(str(tmp_vault))
    tasks = vault.list_tasks()
    assert len(tasks) >= 2  # at least our open tasks
    titles = {t["title"] for t in tasks}
    assert "Купить молоко" in titles


def test_list_tasks_by_project(tmp_vault):
    vault = Vault(str(tmp_vault))
    life_tasks = vault.list_tasks(project="life")
    assert all(t["project"] == "life" for t in life_tasks)
    april_tasks = vault.list_tasks(project="april")
    assert all(t["project"] == "april" for t in april_tasks)


def test_list_tasks_by_status(tmp_vault):
    vault = Vault(str(tmp_vault))
    todo = vault.list_tasks(status="todo")
    assert all(t["status"] == "todo" for t in todo)
    done = vault.list_tasks(status="done")
    assert all(t["status"] == "done" for t in done)


def test_find_task_file(tmp_vault):
    vault = Vault(str(tmp_vault))
    fp = vault.find_task_file("life", 100)
    assert fp is not None
    assert "100-buy-milk.md" in str(fp)


def test_find_task_file_missing(tmp_vault):
    vault = Vault(str(tmp_vault))
    assert vault.find_task_file("life", 99999) is None


def test_create_task(tmp_vault):
    vault = Vault(str(tmp_vault))
    task = vault.create_task(
        project="life",
        title="Новая задача",
        task_type="org",
    )
    assert task["task_id"] > 0
    assert task["title"] == "Новая задача"
    fp = vault.find_task_file("life", task["task_id"])
    assert fp.exists()


def test_update_task_status(tmp_vault):
    vault = Vault(str(tmp_vault))
    vault.update_task("life", 100, {"status": "done"})
    fp = vault.find_task_file("life", 100)
    text = fp.read_text(encoding="utf-8")
    assert "status: done" in text


def test_update_task_tags(tmp_vault):
    vault = Vault(str(tmp_vault))
    vault.update_task("life", 100, {"tags": ["shopping", "urgent"]})
    fp = vault.find_task_file("life", 100)
    text = fp.read_text(encoding="utf-8")
    assert "urgent" in text


def test_archive_task(tmp_vault):
    vault = Vault(str(tmp_vault))
    assert vault.archive_task("life", 100) is True
    # Original should be gone, file should be in archive/
    assert vault.find_task_file("life", 100) is None
    archive_dir = tmp_vault / "life" / "ЗАДАЧИ" / "archive"
    assert archive_dir.exists()
    assert len(list(archive_dir.glob("100-*.md"))) == 1


def test_archive_nonexistent(tmp_vault):
    vault = Vault(str(tmp_vault))
    assert vault.archive_task("life", 99999) is False


def test_delete_task_removes_file(tmp_vault):
    vault = Vault(str(tmp_vault))
    fp = vault.find_task_file("life", 100)
    assert fp is not None and fp.exists()
    assert vault.delete_task("life", 100) is True
    assert vault.find_task_file("life", 100) is None
    assert not fp.exists()


def test_delete_nonexistent(tmp_vault):
    vault = Vault(str(tmp_vault))
    assert vault.delete_task("life", 99999) is False


def test_project_counts(tmp_vault):
    vault = Vault(str(tmp_vault))
    counts = vault.project_counts(open_only=True)
    assert "life" in counts
    assert counts["life"]["count"] >= 2  # open tasks only


def test_regenerate_dashboard(tmp_vault):
    vault = Vault(str(tmp_vault))
    assert vault.regenerate_dashboard() is True
    dash = tmp_vault / "ДАШБОРД.md"
    assert dash.exists()
    content = dash.read_text(encoding="utf-8")
    assert "Купить молоко" in content

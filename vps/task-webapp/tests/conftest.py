"""Shared fixtures."""
import sys
from pathlib import Path

# Make vault.py etc importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import tempfile
import shutil


@pytest.fixture
def tmp_vault():
    """Temp vault with realistic structure and a few tasks."""
    tmp = tempfile.mkdtemp()
    root = Path(tmp)

    # Create project dirs (новая структура: задачи/<project>/)
    projects = [
        "задачи/life",
        "задачи/april",
        "задачи/avgust",
    ]
    for p in projects:
        (root / p).mkdir(parents=True)

    # Create sample tasks
    (root / "задачи/life/100-buy-milk.md").write_text(
        "---\n"
        "task_id: 100\n"
        "title: Купить молоко\n"
        "status: todo\n"
        "type: org\n"
        "project: life\n"
        "created: 2026-04-10\n"
        "due: 2026-04-12\n"
        "assignee: null\n"
        "tags: [shopping]\n"
        "---\n"
        "# Купить молоко\n"
        "Обычное, 3.5%\n",
        encoding="utf-8",
    )
    (root / "задачи/life/101-run-7km.md").write_text(
        "---\n"
        "task_id: 101\n"
        "title: Пробежка 7 км\n"
        "status: in_progress\n"
        "type: org\n"
        "project: life\n"
        "tags: [здоровье, спорт]\n"
        "---\n"
        "# Пробежка\n",
        encoding="utf-8",
    )
    (root / "задачи/april/200-feedback-form.md").write_text(
        "---\n"
        "task_id: 200\n"
        "title: Форма обратной связи\n"
        "status: done\n"
        "project: april\n"
        "---\n",
        encoding="utf-8",
    )

    yield root

    shutil.rmtree(tmp)

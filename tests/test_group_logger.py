"""Tests for GroupLogger — log format, search, message types."""
from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path

from src.transport.group_logger import GroupLogger


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestGroupLoggerSearch:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.logger = GroupLogger(log_dir=self.tmpdir)

    def _write_log(self, chat_id: int, date: str, lines: list[str]):
        group_dir = Path(self.tmpdir) / str(chat_id)
        group_dir.mkdir(parents=True, exist_ok=True)
        log_file = group_dir / f"{date}.txt"
        log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_search_finds_text(self):
        self._write_log(-100, datetime.now().strftime("%Y-%m-%d"), [
            "[10:00] Alice (111): Hello world",
            "[10:01] Bob (222): Goodbye world",
        ])
        results = self.logger.search_logs(chat_id=-100, query="Hello", days=1)
        assert len(results) == 1
        assert "Alice" in results[0]

    def test_search_all_groups(self):
        today = datetime.now().strftime("%Y-%m-%d")
        self._write_log(-100, today, ["[10:00] Alice (111): keyword test"])
        self._write_log(-200, today, ["[11:00] Bob (222): another keyword"])
        results = self.logger.search_logs(chat_id=None, query="keyword", days=1)
        assert len(results) == 2

    def test_search_case_insensitive(self):
        self._write_log(-100, datetime.now().strftime("%Y-%m-%d"), [
            "[10:00] Alice (111): UPPER case text",
        ])
        results = self.logger.search_logs(chat_id=-100, query="upper", days=1)
        assert len(results) == 1

    def test_search_limit_50(self):
        today = datetime.now().strftime("%Y-%m-%d")
        lines = [f"[10:{i:02d}] User ({i}): match line" for i in range(60)]
        self._write_log(-100, today, lines)
        results = self.logger.search_logs(chat_id=-100, query="match", days=1)
        assert len(results) == 50

    def test_count_messages(self):
        today = datetime.now().strftime("%Y-%m-%d")
        self._write_log(-100, today, [
            "[10:00] Alice (111): msg1",
            "[10:01] Alice (111): msg2",
        ])
        self._write_log(-200, today, [
            "[11:00] Bob (222): msg3",
        ])
        counts = self.logger.count_messages(days=1)
        assert counts["-100"] == 2
        assert counts["-200"] == 1


class TestGroupLoggerCleanup:
    def test_cleanup_removes_old_files(self):
        tmpdir = tempfile.mkdtemp()
        logger = GroupLogger(log_dir=tmpdir)
        media_dir = Path(tmpdir) / "-100" / "media"
        media_dir.mkdir(parents=True)

        # Create an old file
        old_file = media_dir / "old.jpg"
        old_file.write_bytes(b"old")
        import os
        # Set mtime to 100 days ago
        old_time = datetime.now().timestamp() - (100 * 86400)
        os.utime(str(old_file), (old_time, old_time))

        # Create a recent file
        new_file = media_dir / "new.jpg"
        new_file.write_bytes(b"new")

        removed = logger.cleanup_old_media(keep_days=90)
        assert removed == 1
        assert not old_file.exists()
        assert new_file.exists()


class TestGroupLoggerSpecialTypes:
    def test_process_special_sticker(self):
        # Simulate a sticker message
        class FakeSticker:
            emoji = "😂"
        class FakeMsg:
            sticker = FakeSticker()
            location = None
            contact = None
            poll = None
            animation = None
        result = GroupLogger._process_special(FakeMsg())
        assert "[стикер — 😂]" == result

    def test_process_special_location(self):
        class FakeLoc:
            latitude = 52.52
            longitude = 13.405
        class FakeMsg:
            sticker = None
            location = FakeLoc()
            contact = None
            poll = None
            animation = None
        result = GroupLogger._process_special(FakeMsg())
        assert "52.5200" in result
        assert "13.4050" in result

    def test_process_special_contact(self):
        class FakeContact:
            phone_number = "+49123456789"
            first_name = "John"
            last_name = "Doe"
        class FakeMsg:
            sticker = None
            location = None
            contact = FakeContact()
            poll = None
            animation = None
        result = GroupLogger._process_special(FakeMsg())
        assert "+49123456789" in result
        assert "John" in result

    def test_process_special_poll(self):
        class FakePoll:
            question = "Когда удобно?"
        class FakeMsg:
            sticker = None
            location = None
            contact = None
            poll = FakePoll()
            animation = None
        result = GroupLogger._process_special(FakeMsg())
        assert "Когда удобно?" in result

    def test_process_special_none(self):
        class FakeMsg:
            sticker = None
            location = None
            contact = None
            poll = None
            animation = None
        assert GroupLogger._process_special(FakeMsg()) is None


class TestBotResponseLogging:
    def test_log_bot_response(self):
        tmpdir = tempfile.mkdtemp()
        logger = GroupLogger(log_dir=tmpdir)
        _run(logger.log_bot_response(-100, "Привет, это ответ бота"))

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = Path(tmpdir) / "-100" / f"{today}.txt"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "Claude Assistant (bot)" in content
        assert "ответ бота" in content

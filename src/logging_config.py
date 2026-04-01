from __future__ import annotations

import logging
import re
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_SECRET_RE = re.compile(r"(sk-ant-[a-zA-Z0-9_-]{6})[a-zA-Z0-9_-]+")


class SecretFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _SECRET_RE.sub(r"\1***", record.msg)
        return True


def configure_logging(log_dir: str = "logs") -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    secret_filter = SecretFilter()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(secret_filter)

    file_handler = TimedRotatingFileHandler(
        filename=f"{log_dir}/assistant.log",
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(secret_filter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console)
    root.addHandler(file_handler)

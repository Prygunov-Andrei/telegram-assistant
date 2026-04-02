from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

MEDIA_SIZE_LIMIT = 20 * 1024 * 1024  # 20MB


class GroupLogger:
    def __init__(self, log_dir: str) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        # chmod 700 for security
        try:
            os.chmod(str(self.log_dir), 0o700)
        except OSError:
            pass
        self._locks: dict[int, asyncio.Lock] = {}

    def _get_lock(self, chat_id: int) -> asyncio.Lock:
        if chat_id not in self._locks:
            self._locks[chat_id] = asyncio.Lock()
        return self._locks[chat_id]

    def _group_dir(self, chat_id: int) -> Path:
        d = self.log_dir / str(chat_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _media_dir(self, chat_id: int) -> Path:
        d = self._group_dir(chat_id) / "media"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _log_file(self, chat_id: int, date: str) -> Path:
        return self._group_dir(chat_id) / f"{date}.txt"

    async def log_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.edited_message or update.message
        if not msg or not update.effective_chat or not update.effective_user:
            return

        chat_id = update.effective_chat.id
        user = update.effective_user
        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or "Unknown"
        user_id = user.id
        ts = msg.date.strftime("%H:%M") if msg.date else datetime.now().strftime("%H:%M")
        date_str = msg.date.strftime("%Y-%m-%d") if msg.date else datetime.now().strftime("%Y-%m-%d")
        is_edit = update.edited_message is not None

        prefix = f"[{ts}] {user_name} ({user_id})"

        # Build context (reply / forward)
        context_str = ""
        if msg.reply_to_message:
            orig = msg.reply_to_message
            orig_text = (orig.text or orig.caption or "")[:50]
            context_str = f"↩️ ответ на \"{orig_text}\": "
        elif msg.forward_from:
            fwd_name = f"{msg.forward_from.first_name or ''} {msg.forward_from.last_name or ''}".strip()
            context_str = f"⤵️ переслано от {fwd_name}: "
        elif msg.forward_sender_name:
            context_str = f"⤵️ переслано от {msg.forward_sender_name}: "

        edit_prefix = "[отредактировано] " if is_edit else ""

        lines: list[str] = []

        # Media
        media_entries = await self._process_media(msg, chat_id, context)
        if media_entries:
            for entry in media_entries:
                caption = msg.caption or ""
                suffix = f" {caption}" if caption and entry == media_entries[0] else ""
                lines.append(f"{prefix}: {context_str}{edit_prefix}{entry}{suffix}")

        # Text (if no media or separate text)
        text = msg.text or ""
        if text:
            lines.append(f"{prefix}: {context_str}{edit_prefix}{text}")

        # Special message types (no text, no media)
        if not lines:
            special = self._process_special(msg)
            if special:
                lines.append(f"{prefix}: {context_str}{edit_prefix}{special}")

        if not lines:
            return

        lock = self._get_lock(chat_id)
        async with lock:
            log_file = self._log_file(chat_id, date_str)
            with open(log_file, "a", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")

    async def log_bot_response(self, chat_id: int, text: str) -> None:
        now = datetime.now()
        ts = now.strftime("%H:%M")
        date_str = now.strftime("%Y-%m-%d")
        line = f"[{ts}] Claude Assistant (bot): {text[:500]}"

        lock = self._get_lock(chat_id)
        async with lock:
            log_file = self._log_file(chat_id, date_str)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    async def _process_media(
        self, msg: Any, chat_id: int, context: ContextTypes.DEFAULT_TYPE
    ) -> list[str]:
        entries: list[str] = []
        timestamp = int(time.time() * 1000)

        try:
            if msg.photo:
                photo = msg.photo[-1]  # largest
                path = await self._download_file(
                    context, photo.file_id, chat_id, timestamp, "jpg"
                )
                entries.append(f"[фото — {path}]" if path else "[фото — ошибка скачивания]")

            if msg.video:
                size = msg.video.file_size or 0
                duration = msg.video.duration or 0
                if size <= MEDIA_SIZE_LIMIT:
                    path = await self._download_file(
                        context, msg.video.file_id, chat_id, timestamp, "mp4"
                    )
                    entries.append(
                        f"[видео — {path}] ({duration}s, {size // 1024 // 1024}MB)"
                        if path else f"[видео — ошибка скачивания] ({duration}s)"
                    )
                else:
                    entries.append(f"[видео — слишком большое: {size // 1024 // 1024}MB] ({duration}s)")

            if msg.document:
                size = msg.document.file_size or 0
                fname = msg.document.file_name or "file"
                ext = fname.rsplit(".", 1)[-1] if "." in fname else "bin"
                if size <= MEDIA_SIZE_LIMIT:
                    path = await self._download_file(
                        context, msg.document.file_id, chat_id, timestamp, ext
                    )
                    entries.append(
                        f"[документ — {path}] {fname}"
                        if path else f"[документ — ошибка скачивания] {fname}"
                    )
                else:
                    entries.append(f"[документ — слишком большой: {size // 1024 // 1024}MB] {fname}")

            if msg.voice:
                duration = msg.voice.duration or 0
                path = await self._download_file(
                    context, msg.voice.file_id, chat_id, timestamp, "ogg"
                )
                entries.append(
                    f"[голос — {path}] ({duration}s)"
                    if path else f"[голос — ошибка скачивания] ({duration}s)"
                )

            if msg.video_note:
                duration = msg.video_note.duration or 0
                path = await self._download_file(
                    context, msg.video_note.file_id, chat_id, timestamp, "mp4"
                )
                entries.append(
                    f"[видеосообщение — {path}] ({duration}s)"
                    if path else f"[видеосообщение — ошибка скачивания] ({duration}s)"
                )

        except Exception:
            logger.exception("Error processing media for chat=%d", chat_id)
            entries.append("[медиа — ошибка скачивания]")

        return entries

    async def _download_file(
        self, context: ContextTypes.DEFAULT_TYPE,
        file_id: str, chat_id: int, timestamp: int, ext: str,
    ) -> str | None:
        try:
            tg_file = await context.bot.get_file(file_id)
            filename = f"{timestamp}.{ext}"
            media_dir = self._media_dir(chat_id)
            target = media_dir / filename
            await tg_file.download_to_drive(custom_path=str(target))
            return f"media/{filename}"
        except Exception:
            logger.exception("Failed to download file %s", file_id)
            return None

    @staticmethod
    def _process_special(msg: Any) -> str | None:
        if msg.sticker:
            emoji = msg.sticker.emoji or "?"
            return f"[стикер — {emoji}]"
        if msg.location:
            return f"[локация — {msg.location.latitude:.4f}, {msg.location.longitude:.4f}]"
        if msg.contact:
            phone = msg.contact.phone_number or ""
            name = f"{msg.contact.first_name or ''} {msg.contact.last_name or ''}".strip()
            return f"[контакт — {phone} {name}]"
        if msg.poll:
            return f"[опрос — \"{msg.poll.question}\"]"
        if msg.animation:
            return "[GIF]"
        return None

    # ── Search ────────────────────────────────────────────────

    def search_logs(
        self, chat_id: int | None, query: str, days: int = 7
    ) -> list[str]:
        query_lower = query.lower()
        results: list[str] = []
        today = datetime.now()

        dirs = []
        if chat_id:
            d = self.log_dir / str(chat_id)
            if d.exists():
                dirs.append(d)
        else:
            dirs = [d for d in self.log_dir.iterdir() if d.is_dir() and d.name.lstrip("-").isdigit()]

        for d in dirs:
            for day_offset in range(days):
                date_str = (today - timedelta(days=day_offset)).strftime("%Y-%m-%d")
                log_file = d / f"{date_str}.txt"
                if not log_file.exists():
                    continue
                for line in log_file.read_text(encoding="utf-8").splitlines():
                    if query_lower in line.lower():
                        group_id = d.name
                        results.append(f"[{group_id}] {date_str} {line}")
                        if len(results) >= 50:
                            return results
        return results

    def count_messages(self, days: int = 7) -> dict[str, int]:
        counts: dict[str, int] = {}
        today = datetime.now()

        for d in self.log_dir.iterdir():
            if not d.is_dir() or not d.name.lstrip("-").isdigit():
                continue
            total = 0
            for day_offset in range(days):
                date_str = (today - timedelta(days=day_offset)).strftime("%Y-%m-%d")
                log_file = d / f"{date_str}.txt"
                if log_file.exists():
                    total += sum(1 for _ in log_file.read_text(encoding="utf-8").splitlines() if _)
            if total > 0:
                counts[d.name] = total
        return counts

    def cleanup_old_media(self, keep_days: int = 90) -> int:
        cutoff = time.time() - (keep_days * 86400)
        removed = 0
        for group_dir in self.log_dir.iterdir():
            media_dir = group_dir / "media"
            if not media_dir.exists():
                continue
            for f in media_dir.iterdir():
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
        return removed

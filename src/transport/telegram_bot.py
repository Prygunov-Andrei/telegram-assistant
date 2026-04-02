from __future__ import annotations

import asyncio
import base64
import logging
import os
import tempfile
from io import BytesIO

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from telegram.error import BadRequest

from src.brain.anthropic_engine import AnthropicEngine
from src.transport.group_logger import GroupLogger
from src.transport.telegram_policy import TelegramPolicy
from src.utils.formatting import sanitize_output, split_message

logger = logging.getLogger(__name__)

VOICE_MARKERS = ("скажи", "расскажи", "озвучь", "прочитай вслух",
                  "голосом", "аудио", "послушать", "начитай")


def _wants_voice(text: str) -> bool:
    lower = (text or "").lower()
    return any(marker in lower for marker in VOICE_MARKERS)


class TelegramBot:
    def __init__(
        self,
        token: str,
        owner_id: int,
        engine: AnthropicEngine,
        policy: TelegramPolicy,
        stt_api_key: str = "",
        stt_provider: str = "openai",
        group_logger: GroupLogger | None = None,
        tts_api_key: str = "",
        tts_voice_id: str = "",
        tts_model: str = "eleven_multilingual_v2",
    ) -> None:
        self.token = token
        self.owner_id = owner_id
        self.engine = engine
        self.policy = policy
        self.stt_api_key = stt_api_key
        self.stt_provider = stt_provider
        self.bot_username: str | None = None
        self.group_logger = group_logger
        self.tts_api_key = tts_api_key
        self.tts_voice_id = tts_voice_id
        self.tts_model = tts_model

    @staticmethod
    async def _safe_send(bot, chat_id: int, text: str) -> None:
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        except BadRequest:
            await bot.send_message(chat_id=chat_id, text=text)

    async def _send_voice_response(
        self, bot, chat_id: int, text: str, reply_to_message_id: int | None = None,
    ) -> bool:
        """Send voice message via ElevenLabs TTS. Auto-deletes after playback.

        Voice messages in Telegram auto-chain: after user taps play on one,
        all subsequent voice messages play automatically with sound.
        """
        if not self.tts_api_key:
            return False
        try:
            from src.integrations.elevenlabs_tts import text_to_speech, mp3_to_ogg_opus
            mp3_bytes = await text_to_speech(
                text=text, api_key=self.tts_api_key,
                voice_id=self.tts_voice_id, model=self.tts_model,
            )
            ogg_bytes = mp3_to_ogg_opus(mp3_bytes)
            if not ogg_bytes:
                logger.warning("OGG conversion failed, skipping voice response")
                return False

            msg = await bot.send_voice(
                chat_id=chat_id,
                voice=BytesIO(ogg_bytes),
                reply_to_message_id=reply_to_message_id,
            )
            duration = msg.voice.duration if msg.voice else 15

            # Удалить голосовое после прослушивания (+5 сек запас)
            async def _delete_later():
                await asyncio.sleep(duration + 5)
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
                except Exception:
                    pass
            asyncio.create_task(_delete_later())

            return True
        except Exception:
            logger.exception("TTS failed for chat=%d", chat_id)
            return False

    def _is_group(self, update: Update) -> bool:
        return update.effective_chat and update.effective_chat.type in ("group", "supergroup")

    def _should_respond(self, update: Update) -> bool:
        """Определяет, нужно ли отвечать на сообщение (после логирования)."""
        if not update.effective_user or not update.effective_chat:
            return False

        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        is_private = update.effective_chat.type == "private"
        text = (update.message or update.edited_message)
        msg_text = text.text if text else ""

        # Личные чаты — стандартная проверка
        if is_private:
            if user_id == self.owner_id:
                return True
            return self.policy.allows(
                chat_id=chat_id, user_id=user_id, is_private=True,
                text=msg_text, bot_username=self.bot_username,
            )

        # Группы — проверяем mode
        group = self.policy.groups.get(chat_id)
        if not group:
            return False

        if group.mode == "interactive":
            # Отвечаем всем допущенным
            return self.policy.allows(
                chat_id=chat_id, user_id=user_id, is_private=False,
                text=msg_text, bot_username=self.bot_username,
            )
        else:
            # monitoring / logging — только owner
            if user_id != self.owner_id:
                return False
            return self.policy.allows(
                chat_id=chat_id, user_id=user_id, is_private=False,
                text=msg_text, bot_username=self.bot_username,
            )

    async def _log_and_route(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Единый handler: сначала лог, потом маршрутизация."""
        msg = update.message
        if not msg or not update.effective_chat:
            return

        chat_id = update.effective_chat.id
        is_group = self._is_group(update)

        # 1. Логируем ВСЕ групповые сообщения (до проверки allow_from)
        if is_group and self.group_logger:
            group = self.policy.groups.get(chat_id)
            if group:
                try:
                    await self.group_logger.log_message(update, context)
                except Exception:
                    logger.exception("Failed to log message for chat=%d", chat_id)

        # 2. Проверяем, нужно ли отвечать
        if not self._should_respond(update):
            return

        # 3. Маршрутизация по типу
        if msg.voice:
            await self._process_voice(update, context)
        elif msg.photo:
            await self._process_photo(update, context)
        elif msg.document or msg.video:
            await self._process_media_message(update, context)
        elif msg.text:
            await self._process_text(update, context)

    async def _log_edited(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler для отредактированных сообщений — только логируем."""
        if not update.edited_message or not update.effective_chat:
            return
        chat_id = update.effective_chat.id
        if self._is_group(update) and self.group_logger:
            group = self.policy.groups.get(chat_id)
            if group:
                try:
                    await self.group_logger.log_message(update, context)
                except Exception:
                    logger.exception("Failed to log edited message for chat=%d", chat_id)

    async def _process_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        text = update.message.text or ""

        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        try:
            result = await self.engine.process_message(chat_id, text)
        except Exception:
            logger.exception("Engine error for chat=%d", chat_id)
            result = "Произошла ошибка при обработке сообщения. Попробуйте позже."

        clean = sanitize_output(result)

        # Голосовой ответ если пользователь попросил
        voice_sent = _wants_voice(text) and await self._send_voice_response(
            context.bot, chat_id, clean, reply_to_message_id=update.message.message_id,
        )

        # Текст отправляем всегда (останется после удаления голосового)
        for chunk in split_message(clean):
            await self._safe_send(context.bot, chat_id, chunk)

        if self._is_group(update) and self.group_logger:
            await self.group_logger.log_bot_response(chat_id, result[:500])

    async def _process_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        voice = update.message.voice
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            local_path = tmp.name

        try:
            tg_file = await context.bot.get_file(voice.file_id)
            await tg_file.download_to_drive(custom_path=local_path)

            transcribed = await self._transcribe(local_path)
            if not transcribed:
                await update.message.reply_text("Не удалось распознать голосовое сообщение.")
                return

            is_private = update.effective_chat.type == "private"
            if is_private:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
                except Exception:
                    logger.debug("Could not delete original voice message")
                await context.bot.send_message(chat_id=chat_id, text=f"🎤 {transcribed}")

            result = await self.engine.process_message(chat_id, transcribed)
            clean = sanitize_output(result)

            # Голосовой ответ только если пользователь попросил ("скажи", "расскажи" и т.д.)
            if _wants_voice(transcribed):
                await self._send_voice_response(
                    context.bot, chat_id, clean,
                    reply_to_message_id=update.message.message_id,
                )

            # Текст всегда
            for chunk in split_message(clean):
                await self._safe_send(context.bot, chat_id, chunk)

            if self._is_group(update) and self.group_logger:
                await self.group_logger.log_bot_response(chat_id, result[:500])
        except Exception:
            logger.exception("Voice handling failed for chat=%d", chat_id)
            await update.message.reply_text("Ошибка обработки голосового сообщения.")
        finally:
            try:
                os.remove(local_path)
            except OSError:
                pass

    async def _process_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        photo = update.message.photo[-1]
        caption = update.message.caption or ""

        try:
            tg_file = await context.bot.get_file(photo.file_id)
            photo_bytes = await tg_file.download_as_bytearray()
            image_b64 = base64.b64encode(bytes(photo_bytes)).decode("utf-8")

            result = await self.engine.process_message_with_image(chat_id, caption, image_b64)
            for chunk in split_message(sanitize_output(result)):
                await self._safe_send(context.bot, chat_id, chunk)

            if self._is_group(update) and self.group_logger:
                await self.group_logger.log_bot_response(chat_id, result[:500])
        except Exception:
            logger.exception("Photo handling failed for chat=%d", chat_id)
            await update.message.reply_text("Ошибка обработки изображения.")

    async def _process_media_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка документов и видео — описание для Claude."""
        msg = update.message
        chat_id = update.effective_chat.id
        caption = msg.caption or ""

        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        if msg.document:
            file_info = f"[Документ: {msg.document.file_name or 'unknown'}, {(msg.document.file_size or 0) // 1024}KB]"
        elif msg.video:
            file_info = f"[Видео: {msg.video.duration or 0}s, {(msg.video.file_size or 0) // 1024}KB]"
        else:
            return

        text = f"{file_info}\n{caption}" if caption else file_info

        try:
            result = await self.engine.process_message(chat_id, text)
            for chunk in split_message(sanitize_output(result)):
                await self._safe_send(context.bot, chat_id, chunk)

            if self._is_group(update) and self.group_logger:
                await self.group_logger.log_bot_response(chat_id, result[:500])
        except Exception:
            logger.exception("Media message handling failed for chat=%d", chat_id)
            await update.message.reply_text("Ошибка обработки сообщения.")

    async def _transcribe(self, file_path: str) -> str:
        if not self.stt_api_key:
            return ""
        from src.integrations.groq_stt import transcribe
        return await transcribe(file_path, self.stt_api_key, self.stt_provider)

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._should_respond(update):
            return
        await update.message.reply_text("Claude Assistant online. Чем могу помочь?")

    def run(self) -> None:
        app = Application.builder().token(self.token).build()

        async def _post_init(application: Application) -> None:
            me = await application.bot.get_me()
            self.bot_username = me.username.lower() if me.username else None
            logger.info("Bot started as @%s", self.bot_username)

        app.post_init = _post_init
        app.add_handler(CommandHandler("start", self._start))
        # Единый handler для всех типов сообщений
        app.add_handler(MessageHandler(
            filters.ALL & ~filters.COMMAND & ~filters.StatusUpdate.ALL,
            self._log_and_route,
        ))
        app.add_handler(MessageHandler(filters.COMMAND, self._log_and_route))
        # Edited messages — только логирование
        app.add_handler(MessageHandler(
            filters.UpdateType.EDITED_MESSAGE,
            self._log_edited,
        ))
        logger.info("Telegram polling started")
        app.run_polling(close_loop=False, allowed_updates=["message", "edited_message"])

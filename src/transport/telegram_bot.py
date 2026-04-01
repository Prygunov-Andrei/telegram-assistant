from __future__ import annotations

import base64
import logging
import os
import tempfile

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from telegram.error import BadRequest

from src.brain.anthropic_engine import AnthropicEngine
from src.transport.telegram_policy import TelegramPolicy
from src.utils.formatting import sanitize_output, split_message

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(
        self,
        token: str,
        owner_id: int,
        engine: AnthropicEngine,
        policy: TelegramPolicy,
        stt_api_key: str = "",
        stt_provider: str = "openai",
    ) -> None:
        self.token = token
        self.owner_id = owner_id
        self.engine = engine
        self.policy = policy
        self.stt_api_key = stt_api_key
        self.stt_provider = stt_provider
        self.bot_username: str | None = None

    @staticmethod
    async def _safe_send(bot, chat_id: int, text: str) -> None:
        """Send message with Markdown, fallback to plain text on parse error."""
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        except BadRequest:
            await bot.send_message(chat_id=chat_id, text=text)

    def _allowed(self, update: Update) -> bool:
        if not update.effective_user or not update.effective_chat:
            return False
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        is_private = update.effective_chat.type == "private"
        text = update.message.text if update.message else ""
        if user_id == self.owner_id and is_private:
            return True
        return self.policy.allows(
            chat_id=chat_id,
            user_id=user_id,
            is_private=is_private,
            text=text or "",
            bot_username=self.bot_username,
        )

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        if not self._allowed(update):
            return
        chat_id = update.effective_chat.id
        text = update.message.text or ""

        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        try:
            result = await self.engine.process_message(chat_id, text)
        except Exception:
            logger.exception("Engine error for chat=%d", chat_id)
            result = "Произошла ошибка при обработке сообщения. Попробуйте позже."

        for chunk in split_message(sanitize_output(result)):
            await self._safe_send(context.bot, chat_id, chunk)

    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message or not update.message.voice:
            return
        if not self._allowed(update):
            return

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

            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
            except Exception:
                logger.debug("Could not delete original voice message")

            await context.bot.send_message(chat_id=chat_id, text=f"🎤 {transcribed}")

            result = await self.engine.process_message(chat_id, transcribed)
            for chunk in split_message(sanitize_output(result)):
                await self._safe_send(context.bot, chat_id, chunk)
        except Exception:
            logger.exception("Voice handling failed for chat=%d", chat_id)
            await update.message.reply_text("Ошибка обработки голосового сообщения.")
        finally:
            try:
                os.remove(local_path)
            except OSError:
                pass

    async def _handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message or not update.message.photo:
            return
        if not self._allowed(update):
            return

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
        except Exception:
            logger.exception("Photo handling failed for chat=%d", chat_id)
            await update.message.reply_text("Ошибка обработки изображения.")

    async def _transcribe(self, file_path: str) -> str:
        if not self.stt_api_key:
            return ""
        from src.integrations.groq_stt import transcribe
        return await transcribe(file_path, self.stt_api_key, self.stt_provider)

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._allowed(update):
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
        app.add_handler(MessageHandler(filters.VOICE, self._handle_voice))
        app.add_handler(MessageHandler(filters.PHOTO, self._handle_photo))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))
        app.add_handler(MessageHandler(filters.COMMAND, self._handle_text))
        logger.info("Telegram polling started")
        app.run_polling(close_loop=False)

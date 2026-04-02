from __future__ import annotations

from src.integrations.google_services import GoogleServices
from src.tools.registry import ToolRegistry
from src.utils.approval import ApprovalManager

ATTACHMENT_SIZE_LIMIT = 5 * 1024 * 1024  # 5MB
TEXT_MIMETYPES = {
    "text/plain", "text/csv", "text/html", "text/xml",
    "application/json", "application/xml", "application/javascript",
}


def register_gmail_tools(
    registry: ToolRegistry,
    google: GoogleServices,
    approval: ApprovalManager,
) -> None:

    # ── Read-only tools ───────────────────────────────────────

    def search_emails(query: str, max_results: int = 10) -> str:
        rows = google.gmail_search(query=query, max_results=max_results)
        if not rows:
            return "Писем по запросу не найдено."
        lines = []
        for row in rows:
            unread = "📩 " if row.get("is_unread") else ""
            attach = " 📎" if row.get("has_attachments") else ""
            snippet = (row.get("snippet") or "")[:80]
            lines.append(
                f"- {unread}id={row['id']} | {row.get('date', '')} | "
                f"от: {row['from']} | {row['subject']}{attach}\n"
                f"  {snippet}"
            )
        return "\n".join(lines)

    registry.register(
        name="search_emails",
        description="Поиск писем в Gmail. Синтаксис: from:, to:, subject:, after:, before:, is:unread, has:attachment и т.д.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос Gmail"},
                "max_results": {"type": "integer", "description": "Макс. количество (по умолчанию 10)"},
            },
            "required": ["query"],
        },
        handler=search_emails,
    )

    def get_inbox(max_results: int = 10) -> str:
        return search_emails(query="in:inbox", max_results=max_results)

    registry.register(
        name="get_inbox",
        description="Показать последние письма во входящих (inbox).",
        input_schema={
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "Количество писем (по умолчанию 10)"},
            },
        },
        handler=get_inbox,
    )

    def read_email(message_id: str) -> str:
        msg = google.gmail_get_message(message_id)
        lines = [
            f"**{msg['subject']}**",
            f"От: {msg['from']}",
            f"Кому: {msg['to']}",
        ]
        if msg.get("cc"):
            lines.append(f"Копия: {msg['cc']}")
        lines.append(f"Дата: {msg['date']}")
        if msg.get("is_unread"):
            lines.append("Статус: непрочитано")

        attachments = msg.get("attachments", [])
        if attachments:
            lines.append(f"\n📎 Вложения ({len(attachments)}):")
            for att in attachments:
                size_kb = att.get("size", 0) // 1024
                lines.append(f"  - {att['filename']} ({att['mimeType']}, {size_kb}KB) [att_id={att['attachmentId']}]")

        lines.append(f"\n---\n{msg['body']}")
        return "\n".join(lines)

    registry.register(
        name="read_email",
        description="Прочитать полное содержимое письма: от, кому, дата, тело, вложения.",
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID письма из Gmail"},
            },
            "required": ["message_id"],
        },
        handler=read_email,
    )

    def read_attachment(message_id: str, attachment_id: str, filename: str = "") -> str:
        try:
            data = google.gmail_get_attachment(message_id, attachment_id)
        except Exception as e:
            return f"Ошибка скачивания вложения: {e}"

        if len(data) > ATTACHMENT_SIZE_LIMIT:
            return f"Файл слишком большой ({len(data) // 1024}KB). Лимит: {ATTACHMENT_SIZE_LIMIT // 1024 // 1024}MB."

        # Определяем тип по расширению
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        text_extensions = {"txt", "csv", "json", "html", "xml", "md", "yml", "yaml", "log", "py", "js", "ts"}

        if ext in text_extensions:
            try:
                return data.decode("utf-8", errors="replace")[:50_000]
            except Exception:
                return f"Не удалось прочитать как текст: {filename} ({len(data)} bytes)"

        return f"Бинарный файл: {filename} ({len(data) // 1024}KB). Содержимое нельзя отобразить как текст."

    registry.register(
        name="read_attachment",
        description="Скачать и прочитать вложение из письма. Текстовые файлы возвращаются как текст, бинарные — метаданные.",
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID письма"},
                "attachment_id": {"type": "string", "description": "ID вложения из read_email"},
                "filename": {"type": "string", "description": "Имя файла (для определения типа)"},
            },
            "required": ["message_id", "attachment_id"],
        },
        handler=read_attachment,
    )

    def mark_read(message_id: str) -> str:
        google.gmail_mark_read(message_id)
        return f"Письмо {message_id} отмечено как прочитанное."

    registry.register(
        name="mark_read",
        description="Пометить письмо как прочитанное.",
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID письма"},
            },
            "required": ["message_id"],
        },
        handler=mark_read,
    )

    def mark_unread(message_id: str) -> str:
        google.gmail_mark_unread(message_id)
        return f"Письмо {message_id} отмечено как непрочитанное."

    registry.register(
        name="mark_unread",
        description="Пометить письмо как непрочитанное.",
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID письма"},
            },
            "required": ["message_id"],
        },
        handler=mark_unread,
    )

    # ── Write tools (через подтверждение) ─────────────────────

    def send_email(to: str, subject: str, body: str) -> str:
        token = approval.register(
            action="send_email",
            payload={"to": to, "subject": subject, "body": body},
            description=f"Отправить письмо на {to}: «{subject}»",
        )
        return (
            f"Для отправки письма требуется подтверждение.\n"
            f"Кому: {to}\nТема: {subject}\n\n{body[:300]}\n\n"
            f"Для подтверждения вызови approve_action с токеном: {token}"
        )

    registry.register(
        name="send_email",
        description="Подготовить отправку email. Требует подтверждения.",
        input_schema={
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Email получателя"},
                "subject": {"type": "string", "description": "Тема письма"},
                "body": {"type": "string", "description": "Текст письма"},
            },
            "required": ["to", "subject", "body"],
        },
        handler=send_email,
    )

    def reply_email(message_id: str, body: str) -> str:
        # Получаем оригинал для описания
        try:
            original = google.gmail_get_message(message_id)
            desc = f"Ответить на письмо от {original['from']}: «{original['subject']}»"
        except Exception:
            desc = f"Ответить на письмо {message_id}"
        token = approval.register(
            action="reply_email",
            payload={"message_id": message_id, "body": body},
            description=desc,
        )
        return (
            f"Для отправки ответа требуется подтверждение.\n{desc}\n\n"
            f"Текст ответа:\n{body[:300]}\n\n"
            f"Для подтверждения вызови approve_action с токеном: {token}"
        )

    registry.register(
        name="reply_email",
        description="Ответить на письмо. Требует подтверждения. Автоматически подставляет In-Reply-To, References, Re: subject.",
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID письма, на которое отвечаем"},
                "body": {"type": "string", "description": "Текст ответа"},
            },
            "required": ["message_id", "body"],
        },
        handler=reply_email,
    )

    def forward_email(message_id: str, to: str) -> str:
        try:
            original = google.gmail_get_message(message_id)
            desc = f"Переслать письмо «{original['subject']}» на {to}"
        except Exception:
            desc = f"Переслать письмо {message_id} на {to}"
        token = approval.register(
            action="forward_email",
            payload={"message_id": message_id, "to": to},
            description=desc,
        )
        return (
            f"Для пересылки требуется подтверждение.\n{desc}\n\n"
            f"Для подтверждения вызови approve_action с токеном: {token}"
        )

    registry.register(
        name="forward_email",
        description="Переслать письмо на другой адрес. Требует подтверждения.",
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID письма для пересылки"},
                "to": {"type": "string", "description": "Email получателя"},
            },
            "required": ["message_id", "to"],
        },
        handler=forward_email,
    )

    def archive_email(message_id: str) -> str:
        token = approval.register(
            action="archive_email",
            payload={"message_id": message_id},
            description=f"Архивировать письмо {message_id}",
        )
        return (
            f"Для архивации требуется подтверждение.\n"
            f"Для подтверждения вызови approve_action с токеном: {token}"
        )

    registry.register(
        name="archive_email",
        description="Архивировать письмо (убрать из INBOX). Требует подтверждения.",
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID письма"},
            },
            "required": ["message_id"],
        },
        handler=archive_email,
    )

    def delete_email(message_id: str) -> str:
        token = approval.register(
            action="delete_email",
            payload={"message_id": message_id},
            description=f"Удалить письмо {message_id}",
        )
        return (
            f"Для удаления письма требуется подтверждение.\n"
            f"ID: {message_id}\n\n"
            f"Для подтверждения вызови approve_action с токеном: {token}"
        )

    registry.register(
        name="delete_email",
        description="Удалить письмо. Требует подтверждения.",
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID письма"},
            },
            "required": ["message_id"],
        },
        handler=delete_email,
    )

    # ── Approval execution ────────────────────────────────────

    def approve_action(token: str) -> str:
        pending = approval.approve(token)
        if not pending:
            return f"Токен {token} не найден или уже использован."

        p = pending.payload

        if pending.action == "send_email":
            msg_id = google.gmail_send(p["to"], p["subject"], p["body"])
            return f"Письмо отправлено на {p['to']} (id={msg_id})."

        if pending.action == "reply_email":
            msg_id = google.gmail_reply(p["message_id"], p["body"])
            return f"Ответ отправлен (id={msg_id})."

        if pending.action == "forward_email":
            msg_id = google.gmail_forward(p["message_id"], p["to"])
            return f"Письмо переслано на {p['to']} (id={msg_id})."

        if pending.action == "archive_email":
            google.gmail_archive(p["message_id"])
            return f"Письмо {p['message_id']} архивировано."

        if pending.action == "delete_email":
            google.gmail_delete(p["message_id"])
            return f"Письмо {p['message_id']} удалено."

        return f"Неизвестное действие: {pending.action}"

    registry.register(
        name="approve_action",
        description=(
            "Подтвердить и выполнить отложенное действие (отправка/ответ/пересылка/архивация/удаление email). "
            "Вызывай ТОЛЬКО после явного согласия пользователя."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "token": {"type": "string", "description": "Токен подтверждения"},
            },
            "required": ["token"],
        },
        handler=approve_action,
    )

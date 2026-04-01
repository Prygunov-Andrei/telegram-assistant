from __future__ import annotations

from src.integrations.google_services import GoogleServices
from src.tools.registry import ToolRegistry
from src.utils.approval import ApprovalManager


def register_gmail_tools(
    registry: ToolRegistry,
    google: GoogleServices,
    approval: ApprovalManager,
) -> None:

    def search_emails(query: str, max_results: int = 10) -> str:
        rows = google.gmail_search(query=query, max_results=max_results)
        if not rows:
            return "Писем по запросу не найдено."
        lines = []
        for row in rows:
            lines.append(f"- id={row['id']} | {row['subject']} | от: {row['from']}")
        return "\n".join(lines)

    registry.register(
        name="search_emails",
        description="Поиск писем в Gmail. Поддерживает синтаксис Gmail: from:, to:, subject:, after:, before:, is:unread и т.д.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос Gmail"},
                "max_results": {"type": "integer", "description": "Макс. количество результатов (по умолчанию 10)"},
            },
            "required": ["query"],
        },
        handler=search_emails,
    )

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
        description=(
            "Подготовить отправку email. Возвращает токен подтверждения — "
            "письмо НЕ отправляется сразу. Покажи пользователю текст письма "
            "и вызови approve_action после его согласия."
        ),
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

    def archive_email(message_id: str) -> str:
        google.gmail_archive(message_id)
        return f"Письмо {message_id} архивировано."

    registry.register(
        name="archive_email",
        description="Архивировать письмо (убрать из INBOX).",
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID письма из Gmail"},
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
        description=(
            "Подготовить удаление письма. Возвращает токен подтверждения — "
            "письмо НЕ удаляется сразу. Вызови approve_action после согласия пользователя."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID письма из Gmail"},
            },
            "required": ["message_id"],
        },
        handler=delete_email,
    )

    # --- Approval execution tool ---

    def approve_action(token: str) -> str:
        pending = approval.approve(token)
        if not pending:
            return f"Токен {token} не найден или уже использован."

        if pending.action == "send_email":
            p = pending.payload
            msg_id = google.gmail_send(p["to"], p["subject"], p["body"])
            return f"Письмо отправлено на {p['to']} (id={msg_id})."

        if pending.action == "delete_email":
            google.gmail_delete(pending.payload["message_id"])
            return f"Письмо {pending.payload['message_id']} удалено."

        return f"Неизвестное действие: {pending.action}"

    registry.register(
        name="approve_action",
        description=(
            "Подтвердить и выполнить отложенное опасное действие (отправка/удаление email). "
            "Вызывай ТОЛЬКО после явного согласия пользователя."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "token": {"type": "string", "description": "Токен подтверждения из send_email или delete_email"},
            },
            "required": ["token"],
        },
        handler=approve_action,
    )

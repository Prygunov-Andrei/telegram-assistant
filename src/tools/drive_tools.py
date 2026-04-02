from __future__ import annotations

from src.integrations.google_services import GoogleServices
from src.tools.registry import ToolRegistry
from src.utils.approval import ApprovalManager


def register_drive_tools(
    registry: ToolRegistry, google: GoogleServices, approval: ApprovalManager,
) -> None:

    # ── Read-only tools ───────────────────────────────────────

    def search_drive(query: str, max_results: int = 10) -> str:
        drive_query = f"fullText contains '{query}' and trashed = false"
        files = google.drive_search(query=drive_query, max_results=max_results)
        if not files:
            return f"Файлов по запросу «{query}» не найдено."
        lines = []
        for f in files:
            mime = f.get("mimeType", "")
            short_type = _mime_to_label(mime)
            name = f.get("name", "")
            lines.append(f"- [{short_type}] {name} (id={f['id']})")
        return "\n".join(lines)

    registry.register(
        name="search_drive",
        description="Поиск файлов в Google Drive по текстовому запросу.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос"},
                "max_results": {"type": "integer", "description": "Макс. результатов (по умолчанию 10)"},
            },
            "required": ["query"],
        },
        handler=search_drive,
    )

    def read_drive_file(file_id: str) -> str:
        return google.drive_get_file_content(file_id)

    registry.register(
        name="read_drive_file",
        description="Прочитать содержимое файла из Google Drive. Поддерживает Google Docs, Sheets, текстовые файлы.",
        input_schema={
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "ID файла"},
            },
            "required": ["file_id"],
        },
        handler=read_drive_file,
    )

    def list_drive_folder(folder_id: str = "root", max_results: int = 20) -> str:
        files = google.drive_list_folder(folder_id=folder_id, max_results=max_results)
        if not files:
            return "Папка пуста."
        lines = []
        for f in files:
            mime = f.get("mimeType", "")
            short_type = _mime_to_label(mime)
            name = f.get("name", "")
            lines.append(f"- [{short_type}] {name} (id={f['id']})")
        return "\n".join(lines)

    registry.register(
        name="list_drive_folder",
        description="Показать содержимое папки в Google Drive.",
        input_schema={
            "type": "object",
            "properties": {
                "folder_id": {"type": "string", "description": "ID папки ('root' для корня)"},
                "max_results": {"type": "integer", "description": "Макс. количество (по умолчанию 20)"},
            },
        },
        handler=list_drive_folder,
    )

    def get_drive_link(file_id: str) -> str:
        link = google.drive_get_link(file_id)
        return link if link else f"Ссылка для файла {file_id} не найдена."

    registry.register(
        name="get_drive_link",
        description="Получить ссылку на файл в Google Drive.",
        input_schema={
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "ID файла"},
            },
            "required": ["file_id"],
        },
        handler=get_drive_link,
    )

    # ── Write tools (через подтверждение) ─────────────────────

    def upload_to_drive(filename: str, folder_id: str = "root") -> str:
        token = approval.register(
            action="upload_to_drive",
            payload={"filename": filename, "folder_id": folder_id},
            description=f"Загрузить файл «{filename}» на Google Drive",
        )
        return (
            f"Для загрузки файла на Drive требуется подтверждение.\n"
            f"Файл: {filename}\n\n"
            f"Для подтверждения вызови approve_drive_action с токеном: {token}"
        )

    registry.register(
        name="upload_to_drive",
        description="Загрузить файл на Google Drive. Требует подтверждения.",
        input_schema={
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Имя файла"},
                "folder_id": {"type": "string", "description": "ID папки (по умолчанию корень)"},
            },
            "required": ["filename"],
        },
        handler=upload_to_drive,
    )

    def create_drive_folder(name: str, parent_id: str = "root") -> str:
        token = approval.register(
            action="create_drive_folder",
            payload={"name": name, "parent_id": parent_id},
            description=f"Создать папку «{name}» на Google Drive",
        )
        return (
            f"Для создания папки требуется подтверждение.\n"
            f"Папка: {name}\n\n"
            f"Для подтверждения вызови approve_drive_action с токеном: {token}"
        )

    registry.register(
        name="create_drive_folder",
        description="Создать папку на Google Drive. Требует подтверждения.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Название папки"},
                "parent_id": {"type": "string", "description": "ID родительской папки ('root' для корня)"},
            },
            "required": ["name"],
        },
        handler=create_drive_folder,
    )

    def move_drive_file(file_id: str, folder_id: str) -> str:
        token = approval.register(
            action="move_drive_file",
            payload={"file_id": file_id, "folder_id": folder_id},
            description=f"Переместить файл {file_id} в папку {folder_id}",
        )
        return (
            f"Для перемещения файла требуется подтверждение.\n\n"
            f"Для подтверждения вызови approve_drive_action с токеном: {token}"
        )

    registry.register(
        name="move_drive_file",
        description="Переместить файл в другую папку на Google Drive. Требует подтверждения.",
        input_schema={
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "ID файла"},
                "folder_id": {"type": "string", "description": "ID целевой папки"},
            },
            "required": ["file_id", "folder_id"],
        },
        handler=move_drive_file,
    )

    def delete_drive_file(file_id: str) -> str:
        token = approval.register(
            action="delete_drive_file",
            payload={"file_id": file_id},
            description=f"Удалить файл {file_id} с Google Drive (в корзину)",
        )
        return (
            f"Для удаления файла требуется подтверждение.\n\n"
            f"Для подтверждения вызови approve_drive_action с токеном: {token}"
        )

    registry.register(
        name="delete_drive_file",
        description="Удалить файл с Google Drive (в корзину). Требует подтверждения.",
        input_schema={
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "ID файла"},
            },
            "required": ["file_id"],
        },
        handler=delete_drive_file,
    )

    def save_email_attachment_to_drive(
        message_id: str, attachment_id: str, filename: str, folder_id: str = "root",
    ) -> str:
        token = approval.register(
            action="save_email_attachment_to_drive",
            payload={
                "message_id": message_id, "attachment_id": attachment_id,
                "filename": filename, "folder_id": folder_id,
            },
            description=f"Сохранить вложение «{filename}» из письма на Google Drive",
        )
        return (
            f"Для сохранения вложения на Drive требуется подтверждение.\n"
            f"Файл: {filename}\n\n"
            f"Для подтверждения вызови approve_drive_action с токеном: {token}"
        )

    registry.register(
        name="save_email_attachment_to_drive",
        description=(
            "Сохранить вложение из письма Gmail на Google Drive. Требует подтверждения. "
            "Атомарная операция: скачивает из Gmail → загружает на Drive → возвращает ссылку."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID письма Gmail"},
                "attachment_id": {"type": "string", "description": "ID вложения из read_email"},
                "filename": {"type": "string", "description": "Имя файла"},
                "folder_id": {"type": "string", "description": "ID папки на Drive ('root' для корня)"},
            },
            "required": ["message_id", "attachment_id", "filename"],
        },
        handler=save_email_attachment_to_drive,
    )

    # ── Approval execution ────────────────────────────────────

    def approve_drive_action(token: str) -> str:
        pending = approval.approve(token)
        if not pending:
            return f"Токен {token} не найден или уже использован."

        p = pending.payload

        if pending.action == "create_drive_folder":
            result = google.drive_create_folder(p["name"], p.get("parent_id", "root"))
            return f"Папка «{p['name']}» создана.\nID: {result['id']}\nСсылка: {result['webViewLink']}"

        if pending.action == "move_drive_file":
            google.drive_move_file(p["file_id"], p["folder_id"])
            return f"Файл {p['file_id']} перемещён."

        if pending.action == "delete_drive_file":
            google.drive_delete_file(p["file_id"])
            return f"Файл {p['file_id']} удалён (в корзину)."

        if pending.action == "save_email_attachment_to_drive":
            content = google.gmail_get_attachment(p["message_id"], p["attachment_id"])
            # Определяем MIME по расширению
            ext = p["filename"].rsplit(".", 1)[-1].lower() if "." in p["filename"] else ""
            mime_map = {
                "pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "doc": "application/msword",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "xls": "application/vnd.ms-excel",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
            mime = mime_map.get(ext, "application/octet-stream")
            result = google.drive_upload_file(content, p["filename"], mime, p.get("folder_id", "root"))
            return (
                f"Файл «{p['filename']}» сохранён на Drive.\n"
                f"ID: {result['id']}\nСсылка: {result['webViewLink']}"
            )

        return f"Неизвестное действие: {pending.action}"

    registry.register(
        name="approve_drive_action",
        description="Подтвердить и выполнить отложенное действие с Google Drive по токену.",
        input_schema={
            "type": "object",
            "properties": {
                "token": {"type": "string", "description": "Токен подтверждения"},
            },
            "required": ["token"],
        },
        handler=approve_drive_action,
    )


def _mime_to_label(mime: str) -> str:
    mapping = {
        "application/vnd.google-apps.folder": "Папка",
        "application/vnd.google-apps.document": "Документ",
        "application/vnd.google-apps.spreadsheet": "Таблица",
        "application/vnd.google-apps.presentation": "Презентация",
        "application/vnd.google-apps.form": "Форма",
        "application/pdf": "PDF",
        "image/": "Изображение",
        "video/": "Видео",
        "audio/": "Аудио",
    }
    for key, label in mapping.items():
        if mime.startswith(key) or mime == key:
            return label
    return "Файл"

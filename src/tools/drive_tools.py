from __future__ import annotations

from src.integrations.google_services import GoogleServices
from src.tools.registry import ToolRegistry


def register_drive_tools(registry: ToolRegistry, google: GoogleServices) -> None:

    def search_drive(query: str, max_results: int = 10) -> str:
        # Build Drive search query from natural language
        drive_query = f"fullText contains '{query}' and trashed = false"
        files = google.drive_search(query=drive_query, max_results=max_results)
        if not files:
            return f"Файлов по запросу «{query}» не найдено."
        lines = []
        for f in files:
            mime = f.get("mimeType", "")
            short_type = _mime_to_label(mime)
            name = f.get("name", "")
            link = f.get("webViewLink", "")
            lines.append(f"- [{short_type}] {name} (id={f['id']})")
        return "\n".join(lines)

    registry.register(
        name="search_drive",
        description="Поиск файлов в Google Drive по текстовому запросу.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос (название или содержимое файла)"},
                "max_results": {"type": "integer", "description": "Макс. количество результатов (по умолчанию 10)"},
            },
            "required": ["query"],
        },
        handler=search_drive,
    )

    def read_drive_file(file_id: str) -> str:
        return google.drive_get_file_content(file_id)

    registry.register(
        name="read_drive_file",
        description="Прочитать содержимое файла из Google Drive по ID. Поддерживает Google Docs, Sheets, текстовые файлы.",
        input_schema={
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "ID файла из Google Drive (из результатов search_drive)"},
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
                "folder_id": {"type": "string", "description": "ID папки (по умолчанию — корень диска). Используй 'root' для корня."},
                "max_results": {"type": "integer", "description": "Макс. количество (по умолчанию 20)"},
            },
        },
        handler=list_drive_folder,
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

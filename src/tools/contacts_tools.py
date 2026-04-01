from __future__ import annotations

from src.integrations.google_services import GoogleServices
from src.tools.registry import ToolRegistry


def register_contacts_tools(registry: ToolRegistry, google: GoogleServices) -> None:

    def search_contacts(query: str, max_results: int = 10) -> str:
        results = google.contacts_search(query=query, page_size=max_results)
        if not results:
            return f"Контактов по запросу «{query}» не найдено."
        lines = []
        for item in results:
            person = item.get("person", {})
            names = person.get("names", [{}])
            name = names[0].get("displayName", "(без имени)") if names else "(без имени)"
            emails = person.get("emailAddresses", [])
            phones = person.get("phoneNumbers", [])
            parts = [f"- {name}"]
            if emails:
                parts.append(f"email: {emails[0].get('value', '')}")
            if phones:
                parts.append(f"тел: {phones[0].get('value', '')}")
            lines.append(" | ".join(parts))
        return "\n".join(lines)

    registry.register(
        name="search_contacts",
        description="Поиск контактов в Google Contacts по имени.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Имя или часть имени для поиска"},
                "max_results": {"type": "integer", "description": "Макс. количество результатов (по умолчанию 10)"},
            },
            "required": ["query"],
        },
        handler=search_contacts,
    )

    def create_contact(
        first_name: str,
        last_name: str = "",
        email: str = "",
        phone: str = "",
    ) -> str:
        resource = google.contacts_create(first_name, last_name, email, phone)
        return f"Контакт {first_name} {last_name} создан (resource={resource})."

    registry.register(
        name="create_contact",
        description="Создать новый контакт в Google Contacts.",
        input_schema={
            "type": "object",
            "properties": {
                "first_name": {"type": "string", "description": "Имя"},
                "last_name": {"type": "string", "description": "Фамилия (необязательно)"},
                "email": {"type": "string", "description": "Email (необязательно)"},
                "phone": {"type": "string", "description": "Телефон (необязательно)"},
            },
            "required": ["first_name"],
        },
        handler=create_contact,
    )

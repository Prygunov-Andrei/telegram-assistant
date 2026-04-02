from __future__ import annotations

import httpx

from src.tools.registry import ToolRegistry
from src.utils.formatting import strip_html


def register_web_tools(registry: ToolRegistry, serper_api_key: str) -> None:

    def web_search(query: str, num: int = 5) -> str:
        if not serper_api_key:
            return "Поиск недоступен: API key не настроен."
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": serper_api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num, "hl": "ru"},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

        lines = []
        # Answer box
        if data.get("answerBox"):
            ab = data["answerBox"]
            lines.append(f"**{ab.get('title', '')}**: {ab.get('answer', ab.get('snippet', ''))}\n")

        # Organic results
        for item in data.get("organic", []):
            title = item.get("title", "")
            link = item.get("link", "")
            snippet = item.get("snippet", "")[:150]
            lines.append(f"- **{title}**\n  {link}\n  {snippet}")

        return "\n\n".join(lines) if lines else "Ничего не найдено."

    registry.register(
        name="web_search",
        description="Поиск в Google. Используй для любых вопросов требующих актуальной информации из интернета.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос"},
                "num": {"type": "integer", "description": "Количество результатов (по умолчанию 5)"},
            },
            "required": ["query"],
        },
        handler=web_search,
    )

    def web_read(url: str) -> str:
        try:
            resp = httpx.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                follow_redirects=True,
                timeout=15.0,
            )
            resp.raise_for_status()
        except Exception as e:
            return f"Ошибка загрузки: {e}"

        text = strip_html(resp.text)

        if len(text) > 10000:
            text = text[:10000] + "\n\n[обрезано — слишком длинная страница]"

        return text if text else "Не удалось извлечь текст со страницы."

    registry.register(
        name="web_read",
        description="Открыть и прочитать веб-страницу по URL. Возвращает текст страницы (HTML очищен).",
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL страницы для чтения"},
            },
            "required": ["url"],
        },
        handler=web_read,
    )

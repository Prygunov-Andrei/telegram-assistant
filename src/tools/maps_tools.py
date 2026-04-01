from __future__ import annotations

import httpx

from src.tools.registry import ToolRegistry

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
PLACES_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"


def register_maps_tools(registry: ToolRegistry, api_key: str) -> None:
    if not api_key:
        return

    def search_places(query: str, max_results: int = 5) -> str:
        resp = httpx.get(
            PLACES_URL,
            params={"query": query, "key": api_key, "language": "ru"},
            timeout=10.0,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])[:max_results]
        if not results:
            return f"Мест по запросу «{query}» не найдено."
        lines = []
        for r in results:
            name = r.get("name", "")
            addr = r.get("formatted_address", "")
            rating = r.get("rating", "")
            rating_str = f" ({rating}★)" if rating else ""
            lines.append(f"- {name}{rating_str}\n  {addr}")
        return "\n".join(lines)

    registry.register(
        name="search_places",
        description="Поиск мест на карте: рестораны, магазины, достопримечательности и т.д.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос (например: 'итальянский ресторан в Берлине')"},
                "max_results": {"type": "integer", "description": "Макс. количество (по умолчанию 5)"},
            },
            "required": ["query"],
        },
        handler=search_places,
    )

    def get_directions(origin: str, destination: str, mode: str = "driving") -> str:
        resp = httpx.get(
            DIRECTIONS_URL,
            params={
                "origin": origin,
                "destination": destination,
                "mode": mode,
                "key": api_key,
                "language": "ru",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        routes = data.get("routes", [])
        if not routes:
            return f"Маршрут из «{origin}» в «{destination}» не найден."
        leg = routes[0].get("legs", [{}])[0]
        distance = leg.get("distance", {}).get("text", "?")
        duration = leg.get("duration", {}).get("text", "?")
        start = leg.get("start_address", origin)
        end = leg.get("end_address", destination)
        mode_ru = {"driving": "На машине", "walking": "Пешком", "bicycling": "На велосипеде", "transit": "Общ. транспорт"}
        lines = [
            f"**{mode_ru.get(mode, mode)}:** {start} → {end}",
            f"Расстояние: {distance}",
            f"Время в пути: {duration}",
        ]
        steps = leg.get("steps", [])
        if steps and len(steps) <= 10:
            lines.append("\n**Маршрут:**")
            for i, step in enumerate(steps, 1):
                instruction = step.get("html_instructions", "")
                # Strip HTML tags
                import re
                clean = re.sub(r"<[^>]+>", " ", instruction).strip()
                dist = step.get("distance", {}).get("text", "")
                lines.append(f"{i}. {clean} ({dist})")
        return "\n".join(lines)

    registry.register(
        name="get_directions",
        description="Построить маршрут между двумя точками. Показывает расстояние, время в пути и пошаговые инструкции.",
        input_schema={
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Откуда (адрес или название места)"},
                "destination": {"type": "string", "description": "Куда (адрес или название места)"},
                "mode": {
                    "type": "string",
                    "enum": ["driving", "walking", "bicycling", "transit"],
                    "description": "Способ: driving (авто), walking (пешком), bicycling (вело), transit (общ. транспорт)",
                },
            },
            "required": ["origin", "destination"],
        },
        handler=get_directions,
    )

    def geocode(address: str) -> str:
        resp = httpx.get(
            GEOCODE_URL,
            params={"address": address, "key": api_key, "language": "ru"},
            timeout=10.0,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return f"Адрес «{address}» не найден."
        r = results[0]
        formatted = r.get("formatted_address", "")
        loc = r.get("geometry", {}).get("location", {})
        lat = loc.get("lat", "?")
        lng = loc.get("lng", "?")
        return f"{formatted}\nКоординаты: {lat}, {lng}"

    registry.register(
        name="geocode",
        description="Найти координаты и полный адрес по названию места или адресу.",
        input_schema={
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "Адрес или название места"},
            },
            "required": ["address"],
        },
        handler=geocode,
    )

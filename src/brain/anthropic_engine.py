from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import anthropic

from src.brain.conversation import ConversationStore
from src.brain.model_router import choose_model
from src.brain.system_prompt import build_system_prompt
from src.memory.memory_store import MemoryContext
from src.tools.registry import ToolRegistry
from src.utils.cost_tracker import CostTracker

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 10
MAX_RETRIES = 3


@dataclass
class AnthropicEngine:
    api_key: str
    main_model: str
    routine_model: str
    tool_registry: ToolRegistry
    memory: MemoryContext
    timezone: str
    cost_tracker: CostTracker
    conversations: ConversationStore

    def __post_init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=self.api_key)

    async def process_message(self, chat_id: int, user_text: str) -> str:
        if self.cost_tracker.is_over_limit():
            cost = self.cost_tracker.today_cost()
            limit = self.cost_tracker.daily_limit_usd
            return (
                f"Дневной лимит расхода (${limit:.2f}) достигнут. "
                f"Использовано: ${cost:.2f}. Жду завтра или измени лимит в .env."
            )

        conv = self.conversations.get_or_create(chat_id)
        conv.add_user_message(user_text)

        route = choose_model(user_text, self.main_model, self.routine_model)
        logger.info("model_route=%s reason=%s chat=%d", route.model, route.reason, chat_id)

        system = build_system_prompt(self.memory, self.timezone)
        tools = self.tool_registry.get_definitions()

        for round_num in range(MAX_TOOL_ROUNDS):
            response = await self._call_api_with_retry(
                model=route.model,
                max_tokens=16000,
                system=system,
                tools=tools or anthropic.NOT_GIVEN,
                messages=conv.get_messages(),
            )

            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
            }
            record = self.cost_tracker.record(route.model, usage)
            logger.info(
                "api_call round=%d tokens_in=%d tokens_out=%d cached=%d cost=$%.4f",
                round_num, usage["input_tokens"], usage["output_tokens"],
                usage["cache_read_input_tokens"], record.cost_usd,
            )

            conv.add_assistant_response(response.content)

            if response.stop_reason == "end_turn":
                return self._extract_text(response)

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        logger.info("tool_call name=%s input=%s", block.name, block.input)
                        result = await self.tool_registry.execute(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })
                conv.add_tool_results(tool_results)
                continue

            logger.warning("unexpected stop_reason=%s", response.stop_reason)
            return self._extract_text(response)

        return "Превышено максимальное количество вызовов инструментов. Попробуйте упростить запрос."

    async def process_message_with_image(
        self, chat_id: int, text: str, image_base64: str, media_type: str = "image/jpeg"
    ) -> str:
        if self.cost_tracker.is_over_limit():
            return "Дневной лимит расхода достигнут."

        conv = self.conversations.get_or_create(chat_id)
        conv.add_user_message_with_image(text, image_base64, media_type)

        route = choose_model(text or "image", self.main_model, self.routine_model)
        system = build_system_prompt(self.memory, self.timezone)
        tools = self.tool_registry.get_definitions()

        for round_num in range(MAX_TOOL_ROUNDS):
            response = await self._call_api_with_retry(
                model=route.model,
                max_tokens=16000,
                system=system,
                tools=tools or anthropic.NOT_GIVEN,
                messages=conv.get_messages(),
            )

            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
            }
            record = self.cost_tracker.record(route.model, usage)
            logger.info(
                "api_call(image) round=%d tokens_in=%d tokens_out=%d cost=$%.4f",
                round_num, usage["input_tokens"], usage["output_tokens"], record.cost_usd,
            )

            conv.add_assistant_response(response.content)

            if response.stop_reason == "end_turn":
                return self._extract_text(response)

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        logger.info("tool_call(image) name=%s", block.name)
                        result = await self.tool_registry.execute(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })
                conv.add_tool_results(tool_results)
                continue

            return self._extract_text(response)

        return "Превышено максимальное количество вызовов инструментов."

    async def _call_api_with_retry(self, **kwargs: Any) -> Any:
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return await asyncio.to_thread(self._client.messages.create, **kwargs)
            except anthropic.RateLimitError as e:
                retry_after = 2 ** attempt
                if hasattr(e, "response") and e.response is not None:
                    retry_after = float(e.response.headers.get("retry-after", retry_after))
                logger.warning("Rate limited, retrying in %.1fs (attempt %d)", retry_after, attempt + 1)
                await asyncio.sleep(retry_after)
                last_error = e
            except anthropic.APIConnectionError as e:
                wait = 2 ** attempt
                logger.warning("Connection error, retrying in %ds (attempt %d)", wait, attempt + 1)
                await asyncio.sleep(wait)
                last_error = e
            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    wait = 2 ** attempt
                    logger.warning("Server error %d, retrying in %ds", e.status_code, wait)
                    await asyncio.sleep(wait)
                    last_error = e
                else:
                    raise
        raise RuntimeError(f"Anthropic API unavailable after {MAX_RETRIES} retries: {last_error}")

    @staticmethod
    def _extract_text(response: Any) -> str:
        parts = []
        for block in response.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts) if parts else "Не удалось сформировать ответ."

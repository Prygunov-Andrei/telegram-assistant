from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)


async def transcribe(file_path: str, api_key: str, provider: str = "openai") -> str:
    """Transcribe audio file using OpenAI or Groq Whisper API.

    provider: "openai" (default) or "groq"
    """

    if provider == "openai":
        url = "https://api.openai.com/v1/audio/transcriptions"
        model = "gpt-4o-mini-transcribe"
    else:
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        model = "whisper-large-v3-turbo"

    def _do() -> str:
        with open(file_path, "rb") as f:
            response = httpx.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": ("audio.ogg", f, "audio/ogg")},
                data={"model": model},
                timeout=60.0,
            )
        response.raise_for_status()
        return response.json().get("text", "").strip()

    try:
        return await asyncio.to_thread(_do)
    except Exception:
        logger.exception("STT transcription failed (provider=%s)", provider)
        return ""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str
    anthropic_model_main: str = "claude-opus-4-6"
    anthropic_model_routine: str = "claude-haiku-4-5-20251001"

    # Telegram
    telegram_bot_token: str
    telegram_owner_id: int = 435926703

    # Obsidian
    obsidian_root: str = "/Users/andrei_prygunov/obsidian"

    # Google
    gmail_token_path: str = Field(default="~/.gmail-mcp/credentials.json")
    google_calendar_token_path: str = Field(default="~/.gmail-mcp/calendar_credentials.json")
    google_calendar_id: str = "primary"
    google_contacts_resource_name: str = "people/me"

    # Voice (STT)
    stt_provider: str = "openai"  # "openai" or "groq"
    stt_api_key: str = ""  # OpenAI or Groq API key for STT
    groq_api_key: str = ""  # Legacy, used if stt_api_key is empty

    # Google Maps
    google_maps_api_key: str = ""

    # GitHub
    github_token: str = ""

    # General
    timezone: str = "Europe/Berlin"

    # Cost control
    daily_cost_limit_usd: float = 5.0

    # Memory
    assistant_memory_dir: str = "memory"

    model_config = {"env_file": "config/.env", "env_file_encoding": "utf-8"}

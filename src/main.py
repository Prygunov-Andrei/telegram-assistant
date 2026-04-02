from __future__ import annotations

import atexit
import logging
import os
import signal
import sys
from pathlib import Path

from src.brain.anthropic_engine import AnthropicEngine
from src.brain.conversation import ConversationStore
from src.config import Settings
from src.integrations.google_services import GoogleServices
from src.logging_config import configure_logging
from src.memory.memory_store import load_memory_context
from src.memory.vault_adapter import VaultAdapter
from src.tools.admin_tools import register_admin_tools
from src.tools.calendar_tools import register_calendar_tools
from src.tools.contacts_tools import register_contacts_tools
from src.tools.deutsch_tools import register_deutsch_tools
from src.tools.drive_tools import register_drive_tools
from src.tools.maps_tools import register_maps_tools
from src.brain.context_gatherer import ContextGatherer
from src.integrations.apple_health import HealthDataReader
from src.tools.fitness_tools import register_fitness_tools
from src.tools.github_tools import register_github_tools
from src.tools.gmail_tools import register_gmail_tools
from src.tools.group_tools import register_group_tools
from src.tools.registry import ToolRegistry
from src.tools.vault_tools import register_vault_tools
from src.tools.web_tools import register_web_tools
from src.transport.group_logger import GroupLogger
from src.transport.telegram_bot import TelegramBot
from src.transport.telegram_policy import load_policy_from_json
from src.utils.approval import ApprovalManager
from src.utils.cost_tracker import CostTracker

logger = logging.getLogger(__name__)

LOCK_FILE = "/tmp/telegram-assistant.lock"


def _acquire_lock() -> None:
    if os.path.exists(LOCK_FILE):
        try:
            old_pid = int(Path(LOCK_FILE).read_text().strip())
            os.kill(old_pid, 0)
            print(f"Already running (PID={old_pid}). Exiting.", file=sys.stderr)
            sys.exit(1)
        except (OSError, ValueError):
            pass
    Path(LOCK_FILE).write_text(str(os.getpid()))


def _release_lock() -> None:
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)

    configure_logging(log_dir=str(project_root / "logs"))

    _acquire_lock()
    atexit.register(_release_lock)

    def _signal_handler(signum: int, frame) -> None:
        logger.info("Received signal %d, shutting down...", signum)
        _release_lock()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    settings = Settings()
    logger.info("Settings loaded. obsidian_root=%s", settings.obsidian_root)

    memory_dir = project_root / settings.assistant_memory_dir
    memory = load_memory_context(str(memory_dir))
    logger.info("Memory loaded: %d blocks", len(memory.blocks))

    cost_tracker = CostTracker(
        usage_dir=str(project_root / "memory" / "usage"),
        daily_limit_usd=settings.daily_cost_limit_usd,
    )

    tool_registry = ToolRegistry()
    conversations = ConversationStore(persist_dir=str(project_root / "memory" / "conversations"))

    # --- Зависимости для tools ---
    vault = VaultAdapter(settings.obsidian_root)
    logger.info("VaultAdapter created. root=%s", settings.obsidian_root)

    google = GoogleServices(
        token_path=os.path.expanduser(settings.gmail_token_path),
        calendar_id=settings.google_calendar_id,
        contacts_resource_name=settings.google_contacts_resource_name,
        calendar_token_path=os.path.expanduser(settings.google_calendar_token_path),
    )

    approval = ApprovalManager()

    # --- Регистрация всех tools ---
    register_vault_tools(tool_registry, vault, approval, settings.timezone)
    register_calendar_tools(tool_registry, google, settings.timezone)
    register_gmail_tools(tool_registry, google, approval)
    register_contacts_tools(tool_registry, google)
    register_drive_tools(tool_registry, google, approval)
    register_maps_tools(tool_registry, settings.google_maps_api_key)
    register_github_tools(tool_registry, settings.github_token)
    health_reader = HealthDataReader(os.path.expanduser(settings.apple_health_export_dir))
    register_fitness_tools(tool_registry, settings.obsidian_root, settings.timezone, health_reader)
    register_deutsch_tools(tool_registry, settings.obsidian_root)
    register_admin_tools(tool_registry, cost_tracker, conversations)
    register_web_tools(tool_registry, settings.serper_api_key)

    policy = load_policy_from_json(str(project_root / "config" / "policy.json"))
    logger.info("Policy loaded. owner=%d, groups=%d", policy.owner_id, len(policy.groups))

    group_logger = GroupLogger(log_dir=str(project_root / "logs" / "groups"))
    register_group_tools(tool_registry, group_logger, policy)
    logger.info("Tools registered: %d", tool_registry.tool_count())

    context_gatherer = ContextGatherer(
        fitness_dir=str(project_root / "memory" / "fitness"),
        dashboard_path=str(Path(settings.obsidian_root) / "ДАШБОРД.md"),
        health_reader=health_reader,
    )

    engine = AnthropicEngine(
        api_key=settings.anthropic_api_key,
        main_model=settings.anthropic_model_main,
        routine_model=settings.anthropic_model_routine,
        tool_registry=tool_registry,
        memory=memory,
        timezone=settings.timezone,
        cost_tracker=cost_tracker,
        conversations=conversations,
        context_gatherer=context_gatherer,
    )

    stt_key = settings.stt_api_key or settings.groq_api_key
    bot = TelegramBot(
        token=settings.telegram_bot_token,
        owner_id=settings.telegram_owner_id,
        engine=engine,
        policy=policy,
        stt_api_key=stt_key,
        stt_provider=settings.stt_provider,
        group_logger=group_logger,
        tts_api_key=settings.elevenlabs_api_key,
        tts_voice_id=settings.elevenlabs_voice_id,
        tts_model=settings.elevenlabs_model,
    )

    logger.info("Starting Telegram bot... (tools=%d)", tool_registry.tool_count())
    bot.run()


if __name__ == "__main__":
    main()

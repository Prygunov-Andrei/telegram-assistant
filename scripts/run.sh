#!/bin/bash
set -euo pipefail

PROJECT_ROOT="/Users/andrei_prygunov/obsidian/telegram-assistant"
ENV_FILE="$PROJECT_ROOT/config/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Create it from config/.env.example"
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

cd "$PROJECT_ROOT"
exec python3 -m src.main

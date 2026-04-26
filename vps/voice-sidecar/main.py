#!/usr/bin/env python3
"""Voice sidecar v2: instant transcription + echo + delete.

Watches /root/.openclaw/media/inbound/ for new .ogg files.
When one appears, immediately transcribes via Groq Whisper (0.3s),
sends transcript to Telegram, and deletes the original voice message.
Does NOT wait for OpenClaw's slow transcription pipeline.
"""

import subprocess
import time
import json
import logging
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

BOT_TOKEN = os.environ.get(
    "BOT_TOKEN", ""
)
GROQ_API_KEY = os.environ.get(
    "GROQ_API_KEY", ""
)
CHAT_ID = int(os.environ.get("CHAT_ID", "435926703"))
MEDIA_DIR = "/root/.openclaw/media/inbound"
PROCESSED_FILE = "/root/voice-sidecar/.processed"
GROQ_MODEL = "whisper-large-v3-turbo"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [voice-sidecar] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("voice-sidecar")


def load_processed():
    try:
        with open(PROCESSED_FILE) as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()


def save_processed(name):
    with open(PROCESSED_FILE, "a") as f:
        f.write(name + "\n")


def telegram_api(method, data):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    payload = json.dumps(data).encode()
    req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except URLError as e:
        log.error(f"Telegram API error ({method}): {e}")
        return {"ok": False, "description": str(e)}


def transcribe_ogg(ogg_path):
    """Transcribe OGG via Groq Whisper. Returns text or None."""
    import io
    from urllib.request import urlopen as _urlopen

    boundary = "----VoiceSidecar"
    filename = ogg_path.name

    with open(ogg_path, "rb") as f:
        file_data = f.read()

    body = b""
    # model field
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="model"\r\n\r\n'
    body += f"{GROQ_MODEL}\r\n".encode()
    # file field (no language hint — Whisper auto-detects)
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    body += b"Content-Type: audio/ogg\r\n\r\n"
    body += file_data
    body += b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    req = Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "voice-sidecar/2.0",
        },
    )

    try:
        t0 = time.monotonic()
        with urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        elapsed = time.monotonic() - t0
        text = result.get("text", "").strip()
        log.info(f"Groq transcription: {elapsed:.2f}s, {len(text)} chars")
        return text if text else None
    except Exception as e:
        log.error(f"Groq transcription failed: {e}")
        return None


def send_transcript(text):
    """Send transcript to chat, return message_id."""
    result = telegram_api(
        "sendMessage",
        {"chat_id": CHAT_ID, "text": "\U0001f3a4 " + text},
    )
    if result.get("ok"):
        msg_id = result["result"]["message_id"]
        log.info(f"Transcript sent, message_id={msg_id}")
        return msg_id
    log.error(f"Failed to send: {result}")
    return None


def delete_message(message_id):
    """Delete a message from chat."""
    result = telegram_api(
        "deleteMessage", {"chat_id": CHAT_ID, "message_id": message_id}
    )
    if result.get("ok"):
        log.info(f"Deleted voice message_id={message_id}")
        return True
    desc = result.get("description", "?")
    if "not found" in desc.lower() or "can't be deleted" in desc.lower():
        log.info(f"Skip delete message_id={message_id}: {desc}")
    else:
        log.warning(f"Could not delete message_id={message_id}: {desc}")
    return False


def process_ogg(ogg_path):
    """Process a new OGG file: transcribe + send + delete original."""
    name = ogg_path.stem
    processed = load_processed()
    if name in processed:
        return

    # Small delay to ensure file is fully written
    time.sleep(0.2)

    # Check file size — skip tiny files (< 1KB, likely not voice)
    size = ogg_path.stat().st_size
    if size < 1024:
        log.info(f"Skipping tiny file ({size} bytes): {ogg_path.name}")
        save_processed(name)
        return

    log.info(f"New OGG detected ({size} bytes): {ogg_path.name}")

    # Transcribe directly via Groq (bypasses OpenClaw's slow pipeline)
    text = transcribe_ogg(ogg_path)
    if not text:
        log.warning(f"No transcript for {ogg_path.name}")
        telegram_api(
            "sendMessage",
            {"chat_id": CHAT_ID, "text": "\u26a0\ufe0f Не удалось распознать голосовое"},
        )
        save_processed(name)
        return

    # Write .txt sibling so OpenClaw reuses our transcript instead of
    # calling its own (slower) whisper pipeline.
    txt_path = ogg_path.with_suffix(".txt")
    if not txt_path.exists():
        try:
            txt_path.write_text(text, encoding="utf-8")
        except OSError as e:
            log.warning(f"Could not write {txt_path}: {e}")

    # Send transcript to Telegram
    echo_id = send_transcript(text)

    if echo_id:
        # In DM, messages are sequential.
        # User's voice message_id = our echo_id - 1
        voice_msg_id = echo_id - 1
        delete_message(voice_msg_id)

    save_processed(name)


def watch_with_inotifywait():
    """Monitor via inotifywait (efficient, event-driven)."""
    log.info(f"Watching {MEDIA_DIR} via inotifywait")

    cmd = [
        "inotifywait", "-m", "-e", "close_write",
        "--format", "%f", MEDIA_DIR,
    ]

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    try:
        for line in proc.stdout:
            filename = line.strip()
            if filename.endswith(".ogg"):
                ogg_path = Path(MEDIA_DIR) / filename
                if ogg_path.exists():
                    process_ogg(ogg_path)
    except KeyboardInterrupt:
        log.info("Shutting down")
    finally:
        proc.terminate()


def watch_with_polling():
    """Fallback: poll every 0.3 seconds."""
    log.info(f"Watching {MEDIA_DIR} via polling (fallback)")
    known_files = set(p.name for p in Path(MEDIA_DIR).glob("*.ogg"))

    while True:
        try:
            current = set(p.name for p in Path(MEDIA_DIR).glob("*.ogg"))
            new_files = current - known_files
            for name in sorted(new_files):
                ogg_path = Path(MEDIA_DIR) / name
                process_ogg(ogg_path)
            known_files = current
        except Exception as e:
            log.error(f"Polling error: {e}")
        time.sleep(0.3)


def main():
    log.info("Voice sidecar v2 starting")
    log.info(f"Chat ID: {CHAT_ID}")
    log.info(f"Groq model: {GROQ_MODEL}")

    os.makedirs(MEDIA_DIR, exist_ok=True)

    # Mark existing OGG files as processed
    processed = load_processed()
    for ogg in Path(MEDIA_DIR).glob("*.ogg"):
        name = ogg.stem
        if name not in processed:
            save_processed(name)

    existing = len(list(Path(MEDIA_DIR).glob("*.ogg")))
    log.info(f"Initialized, {existing} existing OGGs marked")

    try:
        subprocess.run(["which", "inotifywait"], capture_output=True, check=True)
        watch_with_inotifywait()
    except (FileNotFoundError, subprocess.CalledProcessError):
        log.warning("inotifywait not found, falling back to polling")
        watch_with_polling()


if __name__ == "__main__":
    main()

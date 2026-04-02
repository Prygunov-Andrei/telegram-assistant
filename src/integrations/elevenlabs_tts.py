"""ElevenLabs Text-to-Speech integration.

Converts text to speech via ElevenLabs API, returns audio bytes.
Uses httpx (already a dependency) instead of the elevenlabs SDK.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
MAX_TEXT_LENGTH = 5000  # Safety limit to avoid surprise costs


async def text_to_speech(
    text: str,
    api_key: str,
    voice_id: str = "cgSgspJ2msm6clMCkdW9",  # Ivan
    model: str = "eleven_multilingual_v2",
) -> bytes:
    """Convert text to speech via ElevenLabs API. Returns mp3 bytes."""
    if not api_key:
        raise ValueError("ElevenLabs API key not configured")

    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
        logger.warning("TTS text truncated to %d chars", MAX_TEXT_LENGTH)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TTS_URL}/{voice_id}",
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": model,
                "language_code": "ru",
            },
            timeout=60.0,
        )
        response.raise_for_status()
        return response.content


def mp3_to_ogg_opus(mp3_bytes: bytes) -> bytes | None:
    """Convert mp3 to ogg/opus for Telegram voice messages. Returns None if ffmpeg unavailable."""
    if not shutil.which("ffmpeg"):
        return None

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_file:
        mp3_file.write(mp3_bytes)
        mp3_path = mp3_file.name

    ogg_path = mp3_path.replace(".mp3", ".ogg")

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-i", mp3_path,
                "-c:a", "libopus", "-b:a", "64k",
                "-y", ogg_path,
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning("ffmpeg conversion failed: %s", result.stderr.decode()[:200])
            return None

        return Path(ogg_path).read_bytes()
    except Exception:
        logger.exception("mp3 to ogg conversion failed")
        return None
    finally:
        Path(mp3_path).unlink(missing_ok=True)
        Path(ogg_path).unlink(missing_ok=True)


def mp3_to_video_note(mp3_bytes: bytes) -> bytes | None:
    """Convert mp3 to square MP4 video note (circle in Telegram). Auto-plays on receive.

    Creates a 640x640 black video with the audio track.
    Files under 1MB are guaranteed to autoplay in Telegram.
    """
    if not shutil.which("ffmpeg"):
        return None

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_file:
        mp3_file.write(mp3_bytes)
        mp3_path = mp3_file.name

    mp4_path = mp3_path.replace(".mp3", ".mp4")

    try:
        # Get audio duration first
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", mp3_path],
            capture_output=True, text=True, timeout=10,
        )
        duration = float(probe.stdout.strip()) if probe.stdout.strip() else 30

        result = subprocess.run(
            [
                "ffmpeg",
                "-f", "lavfi", "-i", f"color=c=0x1a1a2e:s=640x640:d={duration}",
                "-i", mp3_path,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "32",
                "-c:a", "aac", "-b:a", "96k",
                "-shortest", "-movflags", "+faststart",
                "-y", mp4_path,
            ],
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning("ffmpeg video_note conversion failed: %s", result.stderr.decode()[:200])
            return None

        data = Path(mp4_path).read_bytes()
        logger.info("Video note created: %d KB (duration %.1fs)", len(data) // 1024, duration)
        return data
    except Exception:
        logger.exception("mp3 to video_note conversion failed")
        return None
    finally:
        Path(mp3_path).unlink(missing_ok=True)
        Path(mp4_path).unlink(missing_ok=True)

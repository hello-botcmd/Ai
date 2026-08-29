#!/usr/bin/env python3
"""
Userbot — Central Configuration

All secrets are loaded from environment variables or the local `.env` file
(the `.env` file is gitignored — never commit it).
"""

import os
from pathlib import Path
from typing import List

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:  # pragma: no cover
    pass


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


# ═══════════════════════════════════════════════════════════════
#  OWNER SETTINGS
# ═══════════════════════════════════════════════════════════════

OWNER_IDS: List[int] = [
    int(x.strip())
    for x in os.getenv("OWNER_IDS", "8580367479").split(",")
    if x.strip()
]

# ═══════════════════════════════════════════════════════════════
#  PYROGRAM BOT CREDENTIALS
# ═══════════════════════════════════════════════════════════════

API_ID: int = _env_int("API_ID", 0)
API_HASH: str = os.getenv("API_HASH", "")
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# ═══════════════════════════════════════════════════════════════
#  OPENROUTER CONFIG — AI CHAT
# ═══════════════════════════════════════════════════════════════

OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
# Your preferred model — unchanged.
OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-chat-latest")
# Backup models — ONLY tried if the primary is down/rate-limited.
# Set OPENROUTER_FALLBACK_MODELS to "" in .env to disable fallbacks entirely.
OPENROUTER_FALLBACK_MODELS: List[str] = [
    m.strip()
    for m in os.getenv(
        "OPENROUTER_FALLBACK_MODELS",
        "meta-llama/llama-3.3-70b-instruct:free,deepseek/deepseek-chat-v3-0324:free",
    ).split(",")
    if m.strip()
]
OPENROUTER_URL: str = os.getenv(
    "OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions"
)
OPENROUTER_REFERER: str = os.getenv("OPENROUTER_REFERER", "https://t.me/sexyiwowu")
OPENROUTER_TITLE: str = os.getenv("OPENROUTER_TITLE", "Userbot")

# Fewer history turns = shorter prompt = faster & cheaper replies
MAX_HISTORY_TURNS: int = _env_int("MAX_HISTORY_TURNS", 4)
AI_COOLDOWN_SECONDS: int = _env_int("AI_COOLDOWN_SECONDS", 3)
# Hard cap for the whole AI call (all model attempts combined).
# Generous enough for gpt-chat-latest, but never lets a reply hang forever.
AI_TOTAL_TIMEOUT: float = _env_float("AI_TOTAL_TIMEOUT", 50.0)

# ── Credit protection ──
# AI auto-reply pauses for the day once this many AI calls were made.
MAX_DAILY_AI_CALLS: int = _env_int("MAX_DAILY_AI_CALLS", 100)
# AI auto-reply pauses when remaining OpenRouter credits drop to/below this ($).
LOW_CREDITS_THRESHOLD: float = _env_float("LOW_CREDITS_THRESHOLD", 0.05)

# ═══════════════════════════════════════════════════════════════
#  WELCOME / CONTACT SETTINGS
# ═══════════════════════════════════════════════════════════════

# Direct URL to a welcome image (JPEG/PNG). The bot downloads it on startup.
WELCOME_IMAGE_URL: str = os.getenv(
    "WELCOME_IMAGE_URL", "https://i.ibb.co/nhQQLxK/894e3a6da2af.jpg"
)

# Your contact link — shown when the Support button is pressed.
CONTACT_LINK: str = os.getenv("CONTACT_LINK", "t.me/sexyiwowu")

# ═══════════════════════════════════════════════════════════════
#  PAID MEDIA DEFAULTS
# ═══════════════════════════════════════════════════════════════

DEFAULT_PAID_STARS: int = _env_int("DEFAULT_PAID_STARS", 10)

# ═══════════════════════════════════════════════════════════════
#  AI PERSONA (Hinglish — keep as-is)
# ═══════════════════════════════════════════════════════════════

DEFAULT_PERSONA: str = os.getenv(
    "DEFAULT_PERSONA",
    "Tum ek friendly Telegram assistant ho. Hinglish (Hindi + English mix) "
    "me, chhoti aur natural baaton me reply karo, jaise ek dost baat karta hai.",
)

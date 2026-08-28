#!/usr/bin/env python3
"""
RAUSHAN Userbot — Central Configuration
Edit only this file to configure everything.
"""

from typing import List

# ═══════════════════════════════════════════════════════════════
#  OWNER SETTINGS
# ═══════════════════════════════════════════════════════════════

OWNER_IDS: List[int] = [123456789]         # ← Your Telegram user ID(s)

# ═══════════════════════════════════════════════════════════════
#  PYROGRAM BOT CREDENTIALS
# ═══════════════════════════════════════════════════════════════

API_ID: int = 123456                       # ← From my.telegram.org
API_HASH: str = "your_api_hash_here"       # ← From my.telegram.org
BOT_TOKEN: str = "your_bot_token_here"     # ← From @BotFather

# ═══════════════════════════════════════════════════════════════
#  OPENROUTER CONFIG — AI CHAT
# ═══════════════════════════════════════════════════════════════

OPENROUTER_API_KEY: str = "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"
OPENROUTER_MODEL: str = "openai/gpt-chat-latest"
OPENROUTER_URL: str = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_REFERER: str = "https://t.me/nonsecularman"
OPENROUTER_TITLE: str = "RAUSHAN Userbot"

MAX_HISTORY_TURNS: int = 6
AI_COOLDOWN_SECONDS: int = 5

# ═══════════════════════════════════════════════════════════════
#  WELCOME / CONTACT SETTINGS
# ═══════════════════════════════════════════════════════════════

# Direct URL to a welcome image (JPEG/PNG). The bot downloads it on startup.
WELCOME_IMAGE_URL: str = ""
# Example:
# WELCOME_IMAGE_URL = "https://example.com/welcome.jpg"

# Your contact link — shown when the Contact button is pressed.
CONTACT_LINK: str = "t.me/nonsecularman"
# Example:
# CONTACT_LINK = "t.me/your_username"

# ═══════════════════════════════════════════════════════════════
#  PAID MEDIA DEFAULTS
# ═══════════════════════════════════════════════════════════════

DEFAULT_PAID_STARS: int = 10

# ═══════════════════════════════════════════════════════════════
#  AI PERSONA (Hinglish — keep as-is)
# ═══════════════════════════════════════════════════════════════

DEFAULT_PERSONA: str = (
    "Tum ek friendly Telegram assistant ho. Hinglish (Hindi + English mix) "
    "me, chhoti aur natural baaton me reply karo, jaise ek dost baat karta hai."
)

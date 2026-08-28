#!/usr/bin/env python3
"""
RAUSHAN Userbot — Central Configuration
Edit only this file to configure everything.
"""

from typing import List

# ═══════════════════════════════════════════════════════════════
#  OWNER SETTINGS
# ═══════════════════════════════════════════════════════════════

OWNER_IDS: List[int] = [8580367479]         # ← Your Telegram user ID(s)

# ═══════════════════════════════════════════════════════════════
#  PYROGRAM BOT CREDENTIALS
# ═══════════════════════════════════════════════════════════════

API_ID: int = 36134104                    # ← From my.telegram.org
API_HASH: str = "7e85000983efb86b5d4739b6680016b2"       # ← From my.telegram.org
BOT_TOKEN: str = "8607223226:AAFDLuUGKeofa8pTV9qiSPPqDhz1nCVUngI"     # ← From @BotFather

# ═══════════════════════════════════════════════════════════════
#  OPENROUTER CONFIG — AI CHAT
# ═══════════════════════════════════════════════════════════════

OPENROUTER_API_KEY: str = "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"
OPENROUTER_MODEL: str = "openai/gpt-chat-latest"
OPENROUTER_URL: str = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_REFERER: str = "https://t.me/sexyiwowu"
OPENROUTER_TITLE: str = "Userbot"

MAX_HISTORY_TURNS: int = 6
AI_COOLDOWN_SECONDS: int = 5

# ═══════════════════════════════════════════════════════════════
#  WELCOME / CONTACT SETTINGS
# ═══════════════════════════════════════════════════════════════

# Direct URL to a welcome image (JPEG/PNG). The bot downloads it on startup.
WELCOME_IMAGE_URL: str = "https://i.ibb.co/nhQQLxK/894e3a6da2af.jpg"
# Example:
# WELCOME_IMAGE_URL = "https://example.com/welcome.jpg"

# Your contact link — shown when the Contact button is pressed.
CONTACT_LINK: str = "t.me/sexyiwowu"
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

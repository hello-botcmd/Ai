#!/usr/bin/env python3
"""
Userbot Manager — Main Entry Point
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

import requests
from pyrogram import Client
from pyrogram import filters

import config
import database as db
from bot import manager as bot_manager, callback_router, handle_owner_text, handle_owner_photo, start_cmd
from manager import UserbotManager

# ── Logging ──

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("raushan")

WELCOME_IMAGE_PATH = Path(__file__).resolve().parent / "data" / "welcome.jpg"


def download_welcome_image() -> bool:
    """Download the welcome image from the configured URL."""
    url = config.WELCOME_IMAGE_URL
    if not url:
        logger.info("No WELCOME_IMAGE_URL set, skipping download.")
        return False
    try:
        logger.info(f"Downloading welcome image from {url}")
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(WELCOME_IMAGE_PATH, "wb") as f:
            f.write(r.content)
        logger.info(f"Welcome image saved to {WELCOME_IMAGE_PATH}")
        return True
    except Exception as e:
        logger.warning(f"Failed to download welcome image: {e}")
        return False


async def main():
    print("=" * 50)
    print("🚀  RAUSHAN Userbot Manager")
    print("=" * 50)

    # 1. Init database
    db.init_db()
    logger.info("Database ready.")

    # 2. Download welcome image from URL
    if not WELCOME_IMAGE_PATH.exists():
        download_welcome_image()
    else:
        logger.info("Welcome image already exists locally.")

    # 3. Create and wire up the manager
    mgr = UserbotManager()

    # Inject into bot module so the handlers can use it
    import bot
    bot.manager = mgr

    logger.info("Loading existing accounts...")
    await mgr.load_all()
    logger.info(f"Loaded {len(mgr.instances)} account(s).")

    # 4. Build and start Pyrogram bot
    app = Client(
        "raushan_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        workers=8,
    )

    # Register handlers
    app.on_message(filters.command("start"))(start_cmd)
    app.on_callback_query()(callback_router)
    app.on_message(filters.private & filters.text & ~filters.command("start"))(handle_owner_text)
    app.on_message(filters.private & filters.photo & ~filters.command("start"))(handle_owner_photo)

    logger.info("Starting Pyrogram bot...")
    await app.start()
    logger.info(f"Bot started! @{app.me.username}")

    # Keep running
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.exception("Fatal error")
        sys.exit(1)

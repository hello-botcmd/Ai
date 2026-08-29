#!/usr/bin/env python3
"""
Userbot Manager — Main Entry Point
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

import requests
from pyrogram import Client

import config
import database as db
from bot import register_handlers
from manager import UserbotManager, fetch_openrouter_credits

# ── Logging ──

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("userbot.main")

WELCOME_IMAGE_PATH = Path(__file__).resolve().parent / "data" / "welcome.jpg"

CREDITS_REFRESH_SECONDS = 300


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


async def credits_watchdog(app: Client) -> None:
    """Periodically refresh credit info; alert the owner once a day when low."""
    while True:
        await asyncio.sleep(CREDITS_REFRESH_SECONDS)
        try:
            limit, _usage, remaining, _free = await fetch_openrouter_credits(force=True)
            if limit > 0 and remaining <= config.LOW_CREDITS_THRESHOLD:
                today = time.strftime("%Y-%m-%d")
                if db.setting_get(f"credits_alert_{today}", "0") != "1":
                    db.setting_set(f"credits_alert_{today}", "1")
                    for owner in config.OWNER_IDS:
                        try:
                            await app.send_message(
                                owner,
                                f"⚠️ **Low credits:** `${remaining:,.2f}` left. "
                                "AI auto-reply is paused until credits are topped up.",
                            )
                        except Exception:
                            pass
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Credits watchdog error: {e}")


async def main():
    print("=" * 50)
    print("🚀  Userbot Manager")
    print("=" * 50)

    # 1. Config sanity check
    if not (config.API_ID and config.API_HASH and config.BOT_TOKEN):
        logger.error("API_ID / API_HASH / BOT_TOKEN missing — fill in the .env file.")
        sys.exit(1)

    # 2. Init database
    db.init_db()
    logger.info("Database ready.")

    # 3. Download welcome image from URL (if missing or broken)
    if not WELCOME_IMAGE_PATH.exists() or WELCOME_IMAGE_PATH.stat().st_size < 1024:
        download_welcome_image()
    else:
        logger.info("Welcome image already exists locally.")

    # 4. Create and wire up the manager
    mgr = UserbotManager()

    import bot

    bot.manager = mgr

    logger.info("Loading existing accounts...")
    await mgr.load_all()
    logger.info(f"Loaded {len(mgr.instances)} account(s).")

    # 5. Build and start Pyrogram bot
    app = Client(
        "userbot_control",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        workers=8,
    )
    register_handlers(app)

    logger.info("Starting Pyrogram bot...")
    await app.start()
    logger.info(f"Bot started! @{app.me.username}")

    # 6. Warm the credits cache + start the watchdog
    await fetch_openrouter_credits(force=True)
    refresh_task = asyncio.create_task(credits_watchdog(app))

    # Keep running until interrupted, then shut everything down cleanly
    try:
        await asyncio.Event().wait()
    finally:
        refresh_task.cancel()
        logger.info("Stopping userbots...")
        await mgr.stop_all()
        await app.stop()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.exception("Fatal error")
        sys.exit(1)

#!/usr/bin/env python3
"""
Userbot Manager — Main Entry Point

Resilient startup: userbots are the core feature and keep running even if
the optional control-panel bot fails. Every failure is logged loudly.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

import requests
from pyrogram import Client
from telethon import TelegramClient as TClient
from telethon.sessions import StringSession

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
STATUS_INTERVAL_SECONDS = 60


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


async def check_api_credentials() -> str:
    """Bare MTProto connect test. Returns '' on success or an error message."""
    client = TClient(StringSession(), config.API_ID, config.API_HASH)
    try:
        await asyncio.wait_for(client.connect(), timeout=25)
        await client.disconnect()
        return ""
    except asyncio.TimeoutError:
        return "TIMEOUT — Telegram unreachable (network problem?)"
    except Exception as e:
        return f"{type(e).__name__}: {e}"


async def status_reporter(mgr: UserbotManager) -> None:
    """Print a heartbeat line every minute so health is visible in the console."""
    while True:
        await asyncio.sleep(STATUS_INTERVAL_SECONDS)
        total = len(mgr.instances)
        conn = mgr.connected_count
        logger.info(
            f"HEARTBEAT: {conn}/{total} userbot(s) connected | "
            f"AI master switch: {'ON' if mgr.global_enabled else 'OFF'}"
        )


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
        logger.error("API_ID / API_HASH / BOT_TOKEN are missing.")
        logger.error(
            "Create a file named `.env` in this folder with your values, e.g.:\n"
            "  API_ID=123456\n"
            "  API_HASH=abcdef...\n"
            "  BOT_TOKEN=123456:ABCDEF...\n"
            "  OWNER_IDS=123456789\n"
            "  OPENROUTER_API_KEY=sk-or-v1-..."
        )
        sys.exit(1)

    # 2. Init database
    db.init_db()
    logger.info("Database ready.")

    # 3. Download welcome image from URL (if missing or broken)
    if not WELCOME_IMAGE_PATH.exists() or WELCOME_IMAGE_PATH.stat().st_size < 1024:
        download_welcome_image()
    else:
        logger.info("Welcome image already exists locally.")

    # 4. Preflight: verify API_ID/API_HASH reach Telegram
    api_error = await check_api_credentials()
    if api_error:
        logger.error(f"⚠️  Telegram connection test FAILED: {api_error}")
        logger.error(
            "Possible causes:\n"
            "  - API_ID / API_HASH are wrong or the app was deleted "
            "(check https://my.telegram.org)\n"
            "  - No internet / Telegram blocked on this network"
        )
    else:
        logger.info("Telegram connection test passed (API_ID/API_HASH OK).")

    # 5. Create and wire up the manager
    mgr = UserbotManager()

    import bot

    bot.manager = mgr

    # 6. Start all userbot accounts (core feature — must survive everything)
    logger.info("Loading existing accounts...")
    await mgr.load_all()
    logger.info(f"Loaded {len(mgr.instances)} account(s) — {mgr.connected_count} connected.")

    # 7. Start the optional control-panel bot (does NOT kill userbots if it fails)
    app = Client(
        "userbot_control",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        workers=8,
    )
    register_handlers(app)

    panel_ok = False
    try:
        logger.info("Starting control-panel bot...")
        await app.start()
        logger.info(f"Control-panel bot online: @{app.me.username}")
        panel_ok = True
    except Exception as e:
        logger.error(f"❌ Control-panel bot FAILED to start: {type(e).__name__}: {e}")
        logger.error(
            "   The userbots keep running without the panel.\n"
            "   Likely cause: BOT_TOKEN is invalid/revoked — "
            "recreate it with @BotFather /revoke."
        )

    # 8. Background tasks
    try:
        await fetch_openrouter_credits(force=True)
    except Exception as e:
        logger.warning(f"Initial credits fetch failed: {e}")

    refresh_task = None
    if panel_ok:
        refresh_task = asyncio.create_task(credits_watchdog(app))
    status_task = asyncio.create_task(status_reporter(mgr))

    # Keep running until interrupted, then shut everything down cleanly
    try:
        await asyncio.Event().wait()
    finally:
        if refresh_task:
            refresh_task.cancel()
        status_task.cancel()
        logger.info("Stopping userbots...")
        await mgr.stop_all()
        if panel_ok and app.is_connected:
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

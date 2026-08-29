#!/usr/bin/env python3
"""
Diagnose — health check for the whole system.

Run this when "nothing works":
    python diagnose.py

It checks, in order:
  1. config (.env) loaded?
  2. database + accounts present?
  3. API_ID/API_HASH accepted by Telegram? (MTProto connect test)
  4. BOT_TOKEN valid? (control-panel bot login test)
  5. each saved userbot session actually connects?
"""

import asyncio
import sys

import config
import database as db
from pyrogram import Client as PyroClient
from telethon import TelegramClient as TClient
from telethon.sessions import StringSession


def mask(value: str, show: int = 6) -> str:
    if not value:
        return "(empty)"
    if len(value) <= show:
        return value
    return value[:show] + "…" + value[-2:]


async def check_mtproto() -> str:
    """Bare connect test for API_ID/API_HASH."""
    client = TClient(StringSession(), config.API_ID, config.API_HASH)
    try:
        await asyncio.wait_for(client.connect(), timeout=25)
        await client.disconnect()
        return "✅ OK — Telegram accepts API_ID/API_HASH"
    except asyncio.TimeoutError:
        return "❌ TIMEOUT — cannot reach Telegram (check internet/firewall)"
    except Exception as e:
        return f"❌ {type(e).__name__}: {e}"


async def check_bot_token() -> str:
    """Login test for the control-panel bot."""
    app = PyroClient(
        "diag_session",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        in_memory=True,
    )
    try:
        await asyncio.wait_for(app.start(), timeout=40)
        me = await app.get_me()
        await app.stop()
        return f"✅ OK — bot @{me.username} logged in"
    except asyncio.TimeoutError:
        return "❌ TIMEOUT — cannot reach Telegram"
    except Exception as e:
        return f"❌ {type(e).__name__}: {e}"


async def check_userbot_sessions() -> list:
    """Try to start every saved userbot account and report the result."""
    results = []
    accounts = db.account_get_all()
    if not accounts:
        results.append("❌ No accounts in the database — add one from the panel.")
        return results
    for acc in accounts:
        sess = db.account_get_session(acc["user_id"])
        if not sess:
            results.append(f"⚠️ {acc['first_name']} ({acc['user_id']}): no session string stored")
            continue
        client = TClient(StringSession(sess), config.API_ID, config.API_HASH)
        try:
            await asyncio.wait_for(client.connect(), timeout=25)
            connected = client.is_connected()
            await client.disconnect()
            if connected:
                results.append(f"✅ {acc['first_name']} ({acc['user_id']}): connects fine")
            else:
                results.append(f"❌ {acc['first_name']} ({acc['user_id']}): connect returned but not connected")
        except asyncio.TimeoutError:
            results.append(f"❌ {acc['first_name']} ({acc['user_id']}): TIMEOUT — network issue")
        except Exception as e:
            results.append(
                f"❌ {acc['first_name']} ({acc['user_id']}): {type(e).__name__}: {e}\n"
                f"      → generate a fresh session string and add it again"
            )
    return results


async def main():
    print("=" * 56)
    print("🔍  DIAGNOSE")
    print("=" * 56)

    # 1. Config
    print("\n[1] Config")
    print(f"    API_ID       : {config.API_ID or 'MISSING'}")
    print(f"    API_HASH     : {mask(config.API_HASH)}")
    print(f"    BOT_TOKEN    : {mask(config.BOT_TOKEN, 10)}")
    print(f"    OWNER_IDS    : {config.OWNER_IDS}")
    print(f"    OPENROUTER   : {mask(config.OPENROUTER_API_KEY)}")
    if not (config.API_ID and config.API_HASH and config.BOT_TOKEN):
        print("\n❌ Config incomplete! Create a `.env` file next to main.py, e.g.:")
        print("   API_ID=123456")
        print("   API_HASH=abcdef...")
        print("   BOT_TOKEN=123456:ABCDEF...")
        print("   OWNER_IDS=123456789")
        print("   OPENROUTER_API_KEY=sk-or-v1-...")
        return

    # 2. Database
    print("\n[2] Database")
    try:
        db.init_db()
        accounts = db.account_get_all()
        print(f"    DB file      : {db.DB_PATH}")
        print(f"    Accounts     : {len(accounts)}")
        for a in accounts:
            print(f"      - {a['first_name']} ({a['user_id']}) active={a['is_active']}")
    except Exception as e:
        print(f"    ❌ DB error: {e}")
        return

    # 3. MTProto
    print("\n[3] Telegram API check (API_ID/API_HASH)")
    print(f"    {await check_mtproto()}")

    # 4. Bot token
    print("\n[4] Control-panel bot check (BOT_TOKEN)")
    print(f"    {await check_bot_token()}")

    # 5. Userbot sessions
    print("\n[5] Userbot sessions")
    for line in await check_userbot_sessions():
        print(f"    {line}")

    print("\n" + "=" * 56)
    print("If [3] fails: fix API_ID/API_HASH at https://my.telegram.org")
    print("If [4] fails: /revoke + recreate the token in @BotFather")
    print("If [5] fails: generate a new session string for that account")
    print("If everything passes: run `python main.py` and watch the console")
    print("=" * 56)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)

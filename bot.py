#!/usr/bin/env python3
"""
RAUSHAN Userbot — Pyrogram Bot (Owner Control Panel)
"""

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
import database as db
from manager import UserbotManager

logger = logging.getLogger("raushan.bot")

# Global manager reference (set from main.py)
manager: UserbotManager = None  # type: ignore[assignment]

PAID_PHOTO_PATH = str(Path(__file__).resolve().parent / "data" / "paid_media.jpg")
WELCOME_IMAGE_PATH = str(Path(__file__).resolve().parent / "data" / "welcome.jpg")


# ── Helpers ──

def owner_only(func):
    async def wrapper(client: Client, message: Message):
        if message.from_user and message.from_user.id in config.OWNER_IDS:
            return await func(client, message)
        if message.chat.type == enums.ChatType.PRIVATE:
            await message.reply("⛔ This bot is for authorized owners only.")
    return wrapper


def cback_owner_only(func):
    async def wrapper(client: Client, cb: CallbackQuery):
        if cb.from_user and cb.from_user.id in config.OWNER_IDS:
            return await func(client, cb)
        await cb.answer("⛔ Unauthorized", show_alert=True)
    return wrapper


# ── Keyboard builders ──

def main_markup() -> InlineKeyboardMarkup:
    """Two buttons: Dashboard & Contact."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Dashboard", callback_data="dashboard"),
            InlineKeyboardButton("📞 Contact", callback_data="contact"),
        ],
    ])


def dashboard_markup() -> InlineKeyboardMarkup:
    """2×2 grid + bottom row."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add Account", callback_data="add_account"),
            InlineKeyboardButton("📋 Manage Accounts", callback_data="manage_accounts"),
        ],
        [
            InlineKeyboardButton("🔄 Toggle AI", callback_data="toggle_ai"),
            InlineKeyboardButton("📊 Stats", callback_data="stats"),
        ],
        [
            InlineKeyboardButton("🖼 Set Paid Photo", callback_data="set_paid_photo"),
            InlineKeyboardButton("🏠 Back to Main", callback_data="back_main"),
        ],
    ])


def back_dashboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Back to Dashboard", callback_data="dashboard")],
    ])


def build_welcome_text() -> str:
    enabled = "ON ✅" if manager.global_enabled else "OFF ❌"
    return (
        "🌟 **Welcome to RAUSHAN Userbot Manager**\n\n"
        "Your personal Telegram userbot control panel. Manage accounts, "
        "configure AI auto-reply, paid media, and more — all from here.\n\n"
        f"📌 **Connected accounts:** `{manager.connected_count}`\n"
        f"⏱ **Uptime:** `{manager.uptime}`\n"
        f"🤖 **AI Auto-Reply:** `{enabled}`\n\n"
        "_Use the buttons below to get started._"
    )


# ── /start ──

@Client.on_message(filters.command("start"))
@owner_only
async def start_cmd(client: Client, message: Message):
    welcome = build_welcome_text()

    if os.path.exists(WELCOME_IMAGE_PATH):
        try:
            await message.reply_photo(
                photo=WELCOME_IMAGE_PATH,
                caption=welcome,
                reply_markup=main_markup(),
            )
            return
        except Exception as e:
            logger.warning(f"Welcome image failed: {e}")

    await message.reply_text(welcome, reply_markup=main_markup())


# ── Callback router ──

@Client.on_callback_query()
@cback_owner_only
async def callback_router(client: Client, cb: CallbackQuery):
    data = cb.data
    uid = cb.from_user.id

    # ── BACK TO MAIN ──
    if data == "back_main":
        welcome = build_welcome_text()
        if os.path.exists(WELCOME_IMAGE_PATH):
            try:
                await cb.message.delete()
                await client.send_photo(
                    chat_id=cb.message.chat.id,
                    photo=WELCOME_IMAGE_PATH,
                    caption=welcome,
                    reply_markup=main_markup(),
                )
                return
            except Exception:
                pass
        await cb.message.edit_text(welcome, reply_markup=main_markup())
        return

    # ── DASHBOARD ──
    if data == "dashboard":
        await cb.message.edit_text(
            "📊 **Dashboard**\n\nChoose an option below:",
            reply_markup=dashboard_markup(),
        )
        return

    # ── CONTACT ──
    if data == "contact":
        link = config.CONTACT_LINK
        if not link.startswith("https://"):
            link = f"https://{link}"
        text = (
            "📞 **Contact Owner**\n\n"
            f"Reach out via Telegram:\n"
            f"👉 [{link}]({link})\n\n"
            "_Developed by NonSecularMan_"
        )
        await cb.message.edit_text(
            text,
            reply_markup=back_dashboard(),
            disable_web_page_preview=True,
        )
        return

    # ── ADD ACCOUNT ──
    if data == "add_account":
        await cb.message.edit_text(
            "➕ **Add a Userbot Account**\n\n"
            "Please send me the **Telethon session string** for the account.\n\n"
            "```\n"
            "from telethon.sessions import StringSession\n"
            "from telethon import TelegramClient\n"
            "client = TelegramClient(StringSession(), API_ID, API_HASH)\n"
            "await client.start()\n"
            "print(client.session.save())\n"
            "```\n\n"
            "Reply to this message with the session string.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Cancel", callback_data="dashboard")]
            ]),
            parse_mode=enums.ParseMode.MARKDOWN,
        )
        db.setting_set(f"awaiting_session_{uid}", "1")
        return

    # ── MANAGE ACCOUNTS ──
    if data == "manage_accounts":
        accounts = db.account_get_all()
        if not accounts:
            await cb.message.edit_text(
                "📋 **Manage Accounts**\n\nNo accounts connected yet.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Back to Dashboard", callback_data="dashboard")]
                ]),
            )
            return

        buttons = []
        for acc in accounts:
            connected = acc["user_id"] in manager.instances and manager.instances[acc["user_id"]].is_connected
            status = "🟢" if connected else "🔴"
            label = f"{status} {acc['first_name'][:20]}"
            buttons.append([
                InlineKeyboardButton(label, callback_data=f"account_{acc['user_id']}")
            ])
        buttons.append([InlineKeyboardButton("🏠 Back to Dashboard", callback_data="dashboard")])
        await cb.message.edit_text(
            "📋 **Manage Accounts**\n\nTap an account to manage it:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    # ── ACCOUNT DETAIL ──
    if data.startswith("account_"):
        try:
            # could be "account_123" or "account_detail_123"
            parts = data.split("_")
            if parts[1] == "detail":
                uid_acc = int(parts[2])
            else:
                uid_acc = int(parts[1])
        except (IndexError, ValueError):
            await cb.answer("Invalid account.", show_alert=True)
            return

        accs = db.account_get_all()
        acc = next((a for a in accs if a["user_id"] == uid_acc), None)
        if not acc:
            await cb.answer("Account not found.", show_alert=True)
            return

        conn = uid_acc in manager.instances and manager.instances[uid_acc].is_connected
        status = "🟢 Connected" if conn else "🔴 Disconnected"
        active = "✅ Active" if acc["is_active"] else "❌ Inactive"

        text = (
            f"👤 **Account:** {acc['first_name']}\n"
            f"🆔 **ID:** `{uid_acc}`\n"
            f"📡 **Status:** {status}\n"
            f"⚙️ **Active:** {active}\n\n"
            "Choose an action:"
        )
        buttons = [
            [
                InlineKeyboardButton("❌ Terminate", callback_data=f"terminate_{uid_acc}"),
                InlineKeyboardButton("🔙 Back", callback_data="manage_accounts"),
            ]
        ]
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        return

    # ── TERMINATE ──
    if data.startswith("terminate_"):
        try:
            uid_acc = int(data.split("_")[1])
        except (IndexError, ValueError):
            await cb.answer("Invalid ID.", show_alert=True)
            return

        ok = await manager.remove_account(uid_acc)
        if ok:
            await cb.message.edit_text(
                f"✅ **Account `{uid_acc}`** terminated and removed.",
                reply_markup=back_dashboard(),
            )
        else:
            await cb.answer("Failed to remove.", show_alert=True)
        return

    # ── TOGGLE AI ──
    if data == "toggle_ai":
        new_state = manager.toggle_global()
        status = "ON ✅" if new_state else "OFF ❌"
        await cb.message.edit_text(
            f"🔄 **AI Auto-Reply is now: {status}**\n\n"
            "_Affects all connected accounts._",
            reply_markup=back_dashboard(),
        )
        return

    # ── STATS ──
    if data == "stats":
        accounts = db.account_get_all()
        total = len(accounts)
        active = sum(1 for a in accounts if a["is_active"])
        connected = manager.connected_count

        total_c, usage_c, remaining_c = await manager.get_openrouter_credits()
        ai_st = "ON ✅" if manager.global_enabled else "OFF ❌"

        text = (
            "📊 **Bot Statistics**\n\n"
            f"👥 **Accounts:**\n"
            f"   • Total: `{total}`\n"
            f"   • Active: `{active}`\n"
            f"   • Connected: `{connected}`\n\n"
            f"🤖 **AI:**\n"
            f"   • Status: `{ai_st}`\n"
            f"   • Model: `{config.OPENROUTER_MODEL}`\n\n"
            f"💰 **OpenRouter Credits:**\n"
            f"   • Total: `{total_c:.2f}$`\n"
            f"   • Used: `{usage_c:.2f}$`\n"
            f"   • Remaining: `{remaining_c:.2f}$`\n\n"
            f"⏱ **Uptime:** `{manager.uptime}`\n"
            f"🕐 **Start:** `{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(manager._start_time))}`"
        )
        await cb.message.edit_text(text, reply_markup=back_dashboard())
        return

    # ── SET PAID PHOTO ──
    if data == "set_paid_photo":
        current_stars = db.setting_get("paid_stars", str(config.DEFAULT_PAID_STARS))
        await cb.message.edit_text(
            "🖼 **Set Paid Photo**\n\n"
            "When someone types `send` to any connected userbot, "
            "it will reply with this photo as paid media.\n\n"
            f"⭐ **Current stars cost:** `{current_stars}`\n\n"
            "**Step 1:** Send me the **photo**.\n"
            "**Step 2:** Tell me how many **Telegram Stars** to charge.\n\n"
            "_Reply to this message with the photo._",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Cancel", callback_data="dashboard")]
            ]),
        )
        db.setting_set(f"awaiting_photo_{uid}", "1")
        return


# ── Handle session-string text ──

@Client.on_message(filters.private & filters.text & ~filters.command("start"))
async def handle_owner_text(client: Client, message: Message):
    uid = message.from_user.id
    if uid not in config.OWNER_IDS:
        return

    text = message.text.strip()

    # Awaiting session string?
    awaiting = db.setting_get(f"awaiting_session_{uid}", "0")
    if awaiting == "1":
        db.setting_set(f"awaiting_session_{uid}", "0")
        await message.reply_text("⏳ **Testing session string...**")
        ok, msg = await manager.add_account(text)
        if ok:
            await message.reply_text(
                f"✅ **Success!**\n{msg}",
                reply_markup=back_dashboard(),
            )
        else:
            await message.reply_text(
                f"❌ **Failed:** {msg}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Try Again", callback_data="add_account")]
                ]),
            )
        return

    # Awaiting stars amount?
    awaiting_stars = db.setting_get(f"awaiting_stars_{uid}", "0")
    if awaiting_stars == "1":
        db.setting_set(f"awaiting_stars_{uid}", "0")
        try:
            stars = int(text)
            if stars <= 0:
                raise ValueError
        except ValueError:
            await message.reply_text(
                "❌ Invalid number. Please send a positive integer (e.g., `10`).",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Cancel", callback_data="set_paid_photo")]
                ]),
            )
            db.setting_set(f"awaiting_stars_{uid}", "1")
            return

        db.setting_set("paid_stars", str(stars))
        if os.path.exists(PAID_PHOTO_PATH):
            await message.reply_text(
                f"✅ **Paid photo configured!**\n\n"
                f"⭐ Stars cost: `{stars}`\n\n"
                "_When someone types \"send\", the userbot will send this photo._",
                reply_markup=back_dashboard(),
            )
        else:
            await message.reply_text(
                "⚠️ Stars saved, but no photo was stored. Set the photo again.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🖼 Set Photo", callback_data="set_paid_photo")]
                ]),
            )
        return


# ── Handle photo for paid media ──

@Client.on_message(filters.private & filters.photo & ~filters.command("start"))
async def handle_owner_photo(client: Client, message: Message):
    uid = message.from_user.id
    if uid not in config.OWNER_IDS:
        return

    awaiting = db.setting_get(f"awaiting_photo_{uid}", "0")
    if awaiting != "1":
        return

    db.setting_set(f"awaiting_photo_{uid}", "0")  # clear photo flag

    try:
        file_path = await client.download_media(message.photo, file_name=PAID_PHOTO_PATH)
        # Ensure it's at the correct path
        if file_path and file_path != PAID_PHOTO_PATH:
            shutil.move(file_path, PAID_PHOTO_PATH)
    except Exception as e:
        await message.reply_text(f"❌ Download failed: {e}")
        return

    # Now ask for stars
    db.setting_set(f"awaiting_stars_{uid}", "1")
    await message.reply_text(
        "✅ **Photo saved!**\n\n"
        "Now send me the **Telegram Stars** cost (e.g., `5`, `10`, `50`):",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Cancel", callback_data="dashboard")]
        ]),
    )

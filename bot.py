#!/usr/bin/env python3
"""
Userbot Control Panel — Pyrogram Bot (Owner Control Panel)

Handlers are defined here and wired onto the client via register_handlers(app).
"""

import logging
import os
import shutil
import time
from pathlib import Path

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

logger = logging.getLogger("userbot.bot")

# Global manager reference (injected from main.py)
manager: UserbotManager = None  # type: ignore[assignment]

PAID_PHOTO_PATH = str(Path(__file__).resolve().parent / "data" / "paid_media.jpg")
WELCOME_IMAGE_PATH = str(Path(__file__).resolve().parent / "data" / "welcome.jpg")

DIVIDER = "━━━━━━━━━━━━━━━━━"


# ── Premium label helper (small-caps) ──

def small(text: str) -> str:
    table = str.maketrans(
        "abcdefghijklmnopqrstuvwxyz",
        "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
    )
    return text.translate(table)


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


def flow_get(uid: int) -> str:
    return db.setting_get(f"flow_{uid}", "none")


def flow_set(uid: int, state: str) -> None:
    db.setting_set(f"flow_{uid}", state)


def flow_clear(uid: int) -> None:
    db.setting_set(f"flow_{uid}", "none")


# ── Keyboard builders ──

def main_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"✦  {small('open dashboard')}  ✦", callback_data="dashboard")],
            [InlineKeyboardButton(f"📞  {small('support')}", callback_data="contact")],
        ]
    )


def dashboard_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"➕ {small('add account')}", callback_data="add_account"),
                InlineKeyboardButton(f"👥 {small('accounts')}", callback_data="manage_accounts"),
            ],
            [
                InlineKeyboardButton(f"🤖 {small('toggle ai')}", callback_data="toggle_ai"),
                InlineKeyboardButton(f"📊 {small('stats')}", callback_data="stats"),
            ],
            [
                InlineKeyboardButton(f"🖼 {small('paid photo')}", callback_data="set_paid_photo"),
                InlineKeyboardButton(f"💰 {small('credits')}", callback_data="credits"),
            ],
            [InlineKeyboardButton(f"🏠  {small('back to main')}", callback_data="back_main")],
        ]
    )


def back_dashboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"🏠  {small('back to dashboard')}", callback_data="dashboard")],
        ]
    )


def cancel_flow_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"✖  {small('cancel')}", callback_data="cancel_flow")],
        ]
    )


# ── Premium texts ──

def build_welcome_text() -> str:
    ai = "ON ✅" if manager.global_enabled else "OFF ❌"
    return (
        "**✦ ᴜsᴇʀʙᴏᴛ ✦**\n\n"
        "_Your personal AI companion is up and running._\n\n"
        f"{DIVIDER}\n"
        f"🤖 AI Auto-Reply  : `{ai}`\n"
        f"👥 Accounts       : `{manager.connected_count} connected`\n"
        f"💰 Credits Left   : `{manager.credits_summary()}`\n"
        f"⏱ Uptime          : `{manager.uptime}`\n"
        f"{DIVIDER}\n\n"
        "_Tap below to manage everything._"
    )


def build_dashboard_text() -> str:
    ai = "ON ✅" if manager.global_enabled else "OFF ❌"
    return (
        "**✦ ᴄᴏɴᴛʀᴏʟ ᴘᴀɴᴇʟ ✦**\n\n"
        "_Manage everything from one place._\n\n"
        f"{DIVIDER}\n"
        f"🤖 AI Engine  : `{ai}`\n"
        f"👥 Accounts   : `{manager.connected_count} connected`\n"
        f"💰 Credits    : `{manager.credits_summary()}`\n"
        f"{DIVIDER}\n\n"
        "_Choose an option below:_"
    )


# ── Handler registration ──

def register_handlers(app: Client) -> None:
    """Single source of truth for wiring handlers onto the bot client."""
    app.on_message(filters.command("start"))(start_cmd)
    app.on_callback_query()(callback_router)
    app.on_message(filters.private & filters.text & ~filters.command("start"))(handle_owner_text)
    app.on_message(filters.private & filters.photo & ~filters.command("start"))(handle_owner_photo)


# ── /start ──

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

@cback_owner_only
async def callback_router(client: Client, cb: CallbackQuery):
    data = cb.data
    uid = cb.from_user.id

    # ── BACK TO MAIN ──
    if data == "back_main":
        flow_clear(uid)
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
                await cb.answer()
                return
            except Exception:
                pass
        await cb.message.edit_text(welcome, reply_markup=main_markup())
        await cb.answer()
        return

    # ── DASHBOARD ──
    if data == "dashboard":
        flow_clear(uid)
        await cb.message.edit_text(build_dashboard_text(), reply_markup=dashboard_markup())
        await cb.answer()
        return

    # ── CANCEL FLOW ──
    if data == "cancel_flow":
        flow_clear(uid)
        await cb.message.edit_text(build_dashboard_text(), reply_markup=dashboard_markup())
        await cb.answer()
        return

    # ── CONTACT ──
    if data == "contact":
        flow_clear(uid)
        link = config.CONTACT_LINK
        if not link.startswith(("https://", "http://")):
            link = f"https://{link}"
        text = (
            "**📞 sᴜᴘᴘᴏʀᴛ**\n\n"
            f"{DIVIDER}\n"
            f"Reach the owner on Telegram:\n👉 [{link}]({link})\n"
            f"{DIVIDER}\n\n"
            "_Developed by NonSecularMan_"
        )
        await cb.message.edit_text(
            text,
            reply_markup=back_dashboard(),
            disable_web_page_preview=True,
        )
        await cb.answer()
        return

    # ── ADD ACCOUNT ──
    if data == "add_account":
        flow_set(uid, "session")
        await cb.message.edit_text(
            "**➕ ᴀᴅᴅ ᴀᴄᴄᴏᴜɴᴛ**\n\n"
            "_Send me the Telethon session string for the account._\n\n"
            "```\n"
            "from telethon.sessions import StringSession\n"
            "from telethon import TelegramClient\n"
            "client = TelegramClient(StringSession(), API_ID, API_HASH)\n"
            "await client.start()\n"
            "print(client.session.save())\n"
            "```\n\n"
            "_Reply to this message with the session string._",
            reply_markup=cancel_flow_markup(),
            parse_mode=enums.ParseMode.MARKDOWN,
        )
        await cb.answer()
        return

    # ── MANAGE ACCOUNTS ──
    if data == "manage_accounts":
        flow_clear(uid)
        accounts = db.account_get_all()
        if not accounts:
            await cb.message.edit_text(
                "**👥 ᴀᴄᴄᴏᴜɴᴛs**\n\n"
                "_No accounts connected yet._\n\n"
                "_Add one from the dashboard._",
                reply_markup=back_dashboard(),
            )
            await cb.answer()
            return

        buttons = []
        for acc in accounts:
            connected = (
                acc["user_id"] in manager.instances
                and manager.instances[acc["user_id"]].is_connected
            )
            status = "🟢" if connected else "🔴"
            label = f"{status} {acc['first_name'][:20]}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"account_{acc['user_id']}")])
        buttons.append(
            [InlineKeyboardButton(f"🏠 {small('back to dashboard')}", callback_data="dashboard")]
        )
        await cb.message.edit_text(
            "**👥 ᴀᴄᴄᴏᴜɴᴛs**\n\n"
            f"{DIVIDER}\n"
            "_Tap an account to manage it:_",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        await cb.answer()
        return

    # ── ACCOUNT DETAIL ──
    if data.startswith("account_"):
        try:
            parts = data.split("_")
            uid_acc = int(parts[2] if len(parts) > 2 and parts[1] == "detail" else parts[1])
        except (IndexError, ValueError):
            await cb.answer("Invalid account.", show_alert=True)
            return
        await render_account_detail(cb, uid_acc)
        return

    # ── PAUSE / RESUME ACCOUNT ──
    if data.startswith("pause_"):
        try:
            uid_acc = int(data.split("_")[1])
        except (IndexError, ValueError):
            await cb.answer("Invalid ID.", show_alert=True)
            return
        new_active = await manager.toggle_account(uid_acc)
        if new_active is None:
            await cb.answer("Account not found.", show_alert=True)
            return
        await cb.answer("Account activated ✅" if new_active else "Account paused ⏸")
        await render_account_detail(cb, uid_acc)
        return

    # ── REMOVE ACCOUNT ──
    if data.startswith("remove_"):
        try:
            uid_acc = int(data.split("_")[1])
        except (IndexError, ValueError):
            await cb.answer("Invalid ID.", show_alert=True)
            return

        ok = await manager.remove_account(uid_acc)
        if ok:
            await cb.message.edit_text(
                f"✅ **Account `{uid_acc}`** removed.",
                reply_markup=back_dashboard(),
            )
            await cb.answer("Removed 🗑")
        else:
            await cb.answer("Failed to remove.", show_alert=True)
        return

    # ── TOGGLE AI ──
    if data == "toggle_ai":
        new_state = manager.toggle_global()
        status = "ON ✅" if new_state else "OFF ❌"
        await cb.message.edit_text(
            "**🤖 AI Auto-Reply**\n\n"
            f"{DIVIDER}\n"
            f"Status : `{status}`\n"
            f"{DIVIDER}\n\n"
            "_Applies to all connected accounts._",
            reply_markup=back_dashboard(),
        )
        await cb.answer()
        return

    # ── STATS ──
    if data == "stats":
        accounts = db.account_get_all()
        total = len(accounts)
        active = sum(1 for a in accounts if a["is_active"])
        connected = manager.connected_count

        total_c, usage_c, remaining_c, free_tier = await manager.get_openrouter_credits()
        ai_st = "ON ✅" if manager.global_enabled else "OFF ❌"
        today = time.strftime("%Y-%m-%d")
        calls_today = db.setting_get(f"ai_calls_{today}", "0")

        if total_c > 0:
            credits_lines = (
                f"   • Plan      : `{'🎁 free' if free_tier else '💎 paid'}`\n"
                f"   • Total     : `${total_c:,.2f}`\n"
                f"   • Used      : `${usage_c:,.2f}`\n"
                f"   • Remaining : `${remaining_c:,.2f}`\n"
            )
        else:
            credits_lines = "   • _Unavailable — check later_\n"

        text = (
            "**📊 sᴛᴀᴛɪsᴛɪᴄs**\n\n"
            f"{DIVIDER}\n"
            "👥 **Accounts**\n"
            f"   • Total     : `{total}`\n"
            f"   • Active    : `{active}`\n"
            f"   • Connected : `{connected}`\n\n"
            "🤖 **AI**\n"
            f"   • Status    : `{ai_st}`\n"
            f"   • Model     : `{config.OPENROUTER_MODEL}`\n"
            f"   • Today     : `{calls_today} / {config.MAX_DAILY_AI_CALLS}`\n\n"
            "💰 **OpenRouter**\n"
            f"{credits_lines}"
            f"⏱ **Uptime** : `{manager.uptime}`\n"
            f"🕐 **Start**  : `{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(manager._start_time))}`"
        )
        await cb.message.edit_text(text, reply_markup=back_dashboard())
        await cb.answer()
        return

    # ── CREDITS ──
    if data == "credits":
        await cb.message.edit_text("⏳ _Fetching live credit data…_")
        limit, usage, remaining, free_tier = await manager.get_openrouter_credits(force=True)
        today = time.strftime("%Y-%m-%d")
        calls_today = db.setting_get(f"ai_calls_{today}", "0")

        if limit > 0:
            if remaining <= 0:
                status = "🪫 EMPTY"
            elif remaining <= config.LOW_CREDITS_THRESHOLD:
                status = "⚠️ LOW"
            else:
                status = "✅ HEALTHY"
            body = (
                f"• Plan      : `{'🎁 free tier' if free_tier else '💎 paid'}`\n"
                f"• Total     : `${limit:,.2f}`\n"
                f"• Used      : `${usage:,.2f}`\n"
                f"• Remaining : `${remaining:,.2f}`\n"
            )
        else:
            status = "❔ UNKNOWN"
            body = "_Could not reach OpenRouter right now._\n"

        text = (
            "**💰 ᴄʀᴇᴅɪᴛs**\n\n"
            f"{DIVIDER}\n"
            f"Status : `{status}`\n"
            f"{body}"
            f"{DIVIDER}\n"
            f"🤖 AI calls today : `{calls_today} / {config.MAX_DAILY_AI_CALLS}`\n"
            f"🛡 Auto-off below : `${config.LOW_CREDITS_THRESHOLD:,.2f}`\n\n"
            "_AI pauses automatically when credits run low._"
        )
        await cb.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(f"🔄 {small('refresh')}", callback_data="credits"),
                        InlineKeyboardButton(f"🏠 {small('back')}", callback_data="dashboard"),
                    ],
                ]
            ),
        )
        await cb.answer()
        return

    # ── SET PAID PHOTO ──
    if data == "set_paid_photo":
        flow_set(uid, "photo")
        current_stars = db.setting_get("paid_stars", str(config.DEFAULT_PAID_STARS))
        await cb.message.edit_text(
            "**🖼 ᴘᴀɪᴅ ᴘʜᴏᴛᴏ**\n\n"
            "_Whenever someone messages any connected userbot a sentence containing "
            "the word “send”, the bot replies with this photo as paid media._\n\n"
            f"{DIVIDER}\n"
            f"⭐ Current price : `{current_stars} stars`\n"
            f"{DIVIDER}\n\n"
            "**Step 1** — send the photo.\n"
            "**Step 2** — send the star price.\n\n"
            "_Reply to this message with the photo._",
            reply_markup=cancel_flow_markup(),
        )
        await cb.answer()
        return

async def render_account_detail(cb: CallbackQuery, uid_acc: int) -> None:
    accs = db.account_get_all()
    acc = next((a for a in accs if a["user_id"] == uid_acc), None)
    if not acc:
        await cb.answer("Account not found.", show_alert=True)
        return

    conn = uid_acc in manager.instances and manager.instances[uid_acc].is_connected
    status = "🟢 Connected" if conn else "🔴 Disconnected"
    active = "✅ Active" if acc["is_active"] else "⏸ Paused"
    ai_on = db.setting_get(f"enabled_{uid_acc}", "true") == "true"

    err_line = ""
    inst = manager.instances.get(uid_acc)
    if inst and inst.last_error:
        err_line = f"⚠️ Last error : `{inst.last_error[:80]}`\n"

    text = (
        f"**👤 {acc['first_name']}**\n\n"
        f"{DIVIDER}\n"
        f"🆔 ID     : `{uid_acc}`\n"
        f"📡 Status : {status}\n"
        f"⚙️ State  : {active}\n"
        f"🤖 AI     : {'✅ On' if ai_on else '❌ Off'}\n"
        f"{err_line}"
        f"{DIVIDER}\n\n"
        "_Choose an action:_"
    )
    pause_label = (
        f"⏸ {small('pause')}" if acc["is_active"] else f"▶️ {small('resume')}"
    )
    buttons = [
        [
            InlineKeyboardButton(pause_label, callback_data=f"pause_{uid_acc}"),
            InlineKeyboardButton(f"🗑 {small('remove')}", callback_data=f"remove_{uid_acc}"),
        ],
        [InlineKeyboardButton(f"🔙 {small('back')}", callback_data="manage_accounts")],
    ]
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await cb.answer()

# ── Owner text input (flow-based) ──

async def handle_owner_text(client: Client, message: Message):
    uid = message.from_user.id
    if uid not in config.OWNER_IDS:
        return

    flow = flow_get(uid)
    if flow == "none":
        return  # no pending flow — ignore

    text = message.text.strip()

    # ── Awaiting session string ──
    if flow == "session":
        flow_clear(uid)
        await message.reply_text("⏳ _Testing session string…_")
        ok, msg = await manager.add_account(text)
        if ok:
            await message.reply_text(f"✅ **Success!**\n{msg}", reply_markup=back_dashboard())
        else:
            await message.reply_text(
                f"❌ **Failed:** {msg}",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(f"🔄 {small('try again')}", callback_data="add_account"),
                            InlineKeyboardButton(f"🏠 {small('cancel')}", callback_data="cancel_flow"),
                        ],
                    ]
                ),
            )
        return

    # ── Awaiting stars amount ──
    if flow == "stars":
        flow_clear(uid)
        try:
            stars = int(text)
            if stars <= 0:
                raise ValueError
        except ValueError:
            flow_set(uid, "stars")
            await message.reply_text(
                "❌ _Please send a positive number of stars (e.g. `10`)._\n"
                "_Or cancel below._",
                reply_markup=cancel_flow_markup(),
            )
            return

        db.setting_set("paid_stars", str(stars))
        if os.path.exists(PAID_PHOTO_PATH):
            await message.reply_text(
                f"✅ **Paid photo configured!**\n\n"
                f"⭐ Price : `{stars} stars`\n\n"
                "_Any sentence containing “send” now triggers the paid photo._",
                reply_markup=back_dashboard(),
            )
        else:
            await message.reply_text(
                "⚠️ _Stars saved, but no photo was stored. Set the photo again._",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton(f"🖼 {small('set photo')}", callback_data="set_paid_photo")],
                    ]
                ),
            )
        return


# ── Owner photo input (paid media) ──

async def handle_owner_photo(client: Client, message: Message):
    uid = message.from_user.id
    if uid not in config.OWNER_IDS:
        return

    if flow_get(uid) != "photo":
        return

    flow_set(uid, "stars")  # next step: star price

    try:
        file_path = await client.download_media(message.photo, file_name=PAID_PHOTO_PATH)
        if file_path and file_path != PAID_PHOTO_PATH:
            shutil.move(file_path, PAID_PHOTO_PATH)
    except Exception as e:
        logger.warning(f"Paid photo download failed: {e}")
        flow_clear(uid)
        await message.reply_text(
            "❌ _Download failed. Try again from the dashboard._",
            reply_markup=back_dashboard(),
        )
        return

    await message.reply_text(
        "✅ **Photo saved!**\n\n"
        "_Now send the star price (e.g. `10`):_",
        reply_markup=cancel_flow_markup(),
    )

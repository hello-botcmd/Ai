#!/usr/bin/env python3
"""
RAUSHAN Userbot — Telethon Userbot Instance & Manager
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from telethon import TelegramClient as TClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.messages import SendMediaRequest
from telethon.tl.types import InputMediaPaidMedia, InputMediaUploadedPhoto

import config
import database as db

logger = logging.getLogger("raushan.manager")
PAID_PHOTO_PATH: str = str(Path(__file__).resolve().parent / "data" / "paid_media.jpg")


class UserbotInstance:
    """One connected Telethon userbot instance."""

    def __init__(self, user_id: int, session_string: str, first_name: str = ""):
        self.user_id = user_id
        self.session_string = session_string
        self.first_name = first_name
        self.client: Optional[TClient] = None
        self._task: Optional[asyncio.Task] = None
        self._ready = asyncio.Event()

    # ── Lifecycle ──

    async def start(self) -> bool:
        try:
            self.client = TClient(
                StringSession(self.session_string),
                config.API_ID, config.API_HASH,
                connection_retries=3,
                auto_reconnect=True,
            )
            await self.client.start()
            me = await self.client.get_me()
            self.user_id = me.id
            self.first_name = me.first_name or ""

            # Register incoming message handler
            @self.client.on(events.NewMessage(incoming=True))
            async def handler(event):
                await self._on_message(event)

            self._task = asyncio.create_task(self._run())
            self._ready.set()
            logger.info(f"Userbot {self.user_id} ({self.first_name}) started")
            return True
        except Exception as e:
            logger.error(f"Start failed for {self.user_id}: {e}")
            return False

    async def stop(self) -> None:
        if self.client:
            await self.client.disconnect()
            self.client = None
        if self._task and not self._task.done():
            self._task.cancel()
        self._ready.clear()

    async def _run(self) -> None:
        try:
            await self.client.run_until_disconnected()
        except Exception as e:
            logger.warning(f"Userbot {self.user_id} disconnected: {e}")

    @property
    def is_connected(self) -> bool:
        return bool(self.client and self.client.is_connected())

    async def wait_ready(self, timeout: float = 15) -> bool:
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    # ── Message handler ──

    async def _on_message(self, event) -> None:
        if not event.is_private:
            return
        if not event.message or not event.message.text:
            return
        sender = await event.get_sender()
        if not sender or sender.bot:
            return

        sender_id = sender.id
        text = event.message.text.strip().lower()

        # ── Global enabled check ──
        if db.setting_get("enabled", "true") != "true":
            return

        # ── Blocked check ──
        if db.blocked_is(self.user_id, sender_id):
            return

        now = time.time()

        # ── Rate-limit check ──
        if now < float(db.setting_get("rate_limited_until", "0")):
            return

        # ── Cooldown per sender ──
        last_key = f"last_msg_{self.user_id}_{sender_id}"
        last = float(db.setting_get(last_key, "0"))
        if now - last < config.AI_COOLDOWN_SECONDS:
            return
        db.setting_set(last_key, str(now))

        # ── Paid media trigger (exact "send") ──
        if text == "send":
            await self._send_paid_media(event)
            return

        # ── AI reply ──
        try:
            await self.client.send_chat_action(event.chat_id, "typing")
        except Exception:
            pass

        history = db.history_get(self.user_id, sender_id)
        reply_text, retry_after = self._generate_ai_reply(history, event.message.text)

        if retry_after:
            db.setting_set("rate_limited_until", str(time.time() + retry_after))
            try:
                await event.reply(reply_text)
            except Exception:
                pass
            return

        try:
            await event.reply(reply_text)
        except Exception as e:
            logger.error(f"Reply error on {self.user_id}: {e}")
            return

        db.history_append(self.user_id, sender_id, "user", event.message.text)
        db.history_append(self.user_id, sender_id, "assistant", reply_text)

    async def _send_paid_media(self, event) -> None:
        if not os.path.exists(PAID_PHOTO_PATH):
            await event.reply("Paid photo is not configured yet.")
            return

        stars_str = db.setting_get("paid_stars", "10")
        try:
            stars_amount = int(stars_str)
        except ValueError:
            stars_amount = 10

        try:
            uploaded = await self.client.upload_file(PAID_PHOTO_PATH)
            await self.client(
                SendMediaRequest(
                    peer=event.chat_id,
                    media=InputMediaPaidMedia(
                        stars_amount=stars_amount,
                        extended_media=[InputMediaUploadedPhoto(file=uploaded)],
                        payload=None,
                    ),
                    message="⭐ Paid Photo — send stars to view",
                )
            )
            logger.info(f"Paid media sent by {self.user_id} to {event.chat_id}")
        except Exception as e:
            logger.error(f"Paid media error on {self.user_id}: {e}")
            await event.reply(f"Failed to send paid media: {e}")

    # ── AI call ──

    def _generate_ai_reply(
        self, history: List[Dict[str, str]], user_message: str
    ) -> Tuple[str, Optional[int]]:
        if not config.OPENROUTER_API_KEY:
            return ("AI is not configured.", None)

        persona = db.setting_get("persona", config.DEFAULT_PERSONA)

        messages = [{"role": "system", "content": persona}]
        for turn in history:
            role = "assistant" if turn.get("role") in ("model", "assistant") else "user"
            messages.append({"role": role, "content": turn["text"]})
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": config.OPENROUTER_MODEL,
            "messages": messages,
            "max_tokens": 200,
            "temperature": 0.9,
        }
        headers = {
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": config.OPENROUTER_REFERER,
            "X-Title": config.OPENROUTER_TITLE,
        }

        last_error = None
        for attempt in range(2):
            try:
                resp = requests.post(
                    config.OPENROUTER_URL, json=payload, headers=headers, timeout=45
                )
                if resp.status_code == 429:
                    retry_after = 60
                    try:
                        retry_after = int(resp.headers.get("Retry-After", retry_after))
                    except (TypeError, ValueError):
                        pass
                    logger.warning(f"429 rate-limited, retry after {retry_after}s")
                    return (
                        "I'm out of API credits right now. Please try again later.",
                        retry_after,
                    )
                resp.raise_for_status()
                data = resp.json()
                return (data["choices"][0]["message"]["content"].strip(), None)
            except requests.Timeout as e:
                last_error = e
                logger.warning(f"AI timeout attempt {attempt+1}: {e}")
                continue
            except requests.HTTPError as e:
                logger.error(f"AI HTTP error: {e}\n{e.response.text}")
                return ("I'm a bit busy right now, talk later!", None)
            except (KeyError, IndexError) as e:
                logger.error(f"AI parse error: {e}")
                return ("I didn't understand that. Try again.", None)
            except requests.RequestException as e:
                logger.error(f"AI request error: {e}")
                return ("I'm a bit busy right now, talk later!", None)

        logger.error(f"AI failed after retries: {last_error}")
        return ("It's running a bit slow. Send again please.", None)


class UserbotManager:
    """Manages all running Telethon userbots."""

    def __init__(self):
        self.instances: Dict[int, UserbotInstance] = {}
        self._start_time = time.time()

    # ── Properties ──

    @property
    def uptime(self) -> str:
        delta = timedelta(seconds=int(time.time() - self._start_time))
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        return " ".join(parts)

    @property
    def connected_count(self) -> int:
        return sum(1 for i in self.instances.values() if i.is_connected)

    # ── Load all accounts from DB ──

    async def load_all(self) -> None:
        accounts = db.account_get_all()
        for acc in accounts:
            if not acc["is_active"]:
                continue
            sess = db.account_get_session(acc["user_id"])
            if not sess:
                continue
            inst = UserbotInstance(acc["user_id"], sess, acc["first_name"])
            ok = await inst.start()
            if ok:
                self.instances[acc["user_id"]] = inst
                logger.info(f"Loaded account {acc['first_name']} ({acc['user_id']})")
            else:
                logger.warning(f"Failed to load account {acc['user_id']}")

    # ── Add account ──

    async def add_account(self, session_string: str) -> Tuple[bool, str]:
        # Quick test
        temp = TClient(StringSession(session_string), config.API_ID, config.API_HASH)
        try:
            await temp.start()
            me = await temp.get_me()
            await temp.disconnect()
        except Exception as e:
            return False, f"Invalid session string: {e}"

        # Duplicate check
        existing = db.account_get_all()
        if any(a["user_id"] == me.id for a in existing):
            return False, f"Account @{me.username or me.first_name} already exists."

        # Save
        uid = me.id
        fname = me.first_name or "Unknown"
        uname = me.username or ""
        phone = me.phone or ""
        db.account_add(session_string, uid, fname, uname, phone)

        # Start
        inst = UserbotInstance(uid, session_string, fname)
        ok = await inst.start()
        if ok:
            self.instances[uid] = inst
            return True, f"✅ Connected as @{uname or fname}!"
        else:
            return False, "Saved but failed to start the userbot."

    # ── Remove account ──

    async def remove_account(self, user_id: int) -> bool:
        if user_id in self.instances:
            await self.instances[user_id].stop()
            del self.instances[user_id]
        db.account_remove(user_id)
        return True

    # ── Toggle single account ──

    async def toggle_account(self, user_id: int) -> bool:
        accs = db.account_get_all()
        acc = next((a for a in accs if a["user_id"] == user_id), None)
        if not acc:
            return False

        new_active = not acc["is_active"]
        db.account_set_active(user_id, new_active)

        if not new_active:
            # Deactivate
            if user_id in self.instances:
                await self.instances[user_id].stop()
                del self.instances[user_id]
        else:
            # Reactivate
            sess = db.account_get_session(user_id)
            if sess:
                inst = UserbotInstance(user_id, sess, acc["first_name"])
                ok = await inst.start()
                if ok:
                    self.instances[user_id] = inst
        return True

    # ── Global toggle ──

    def toggle_global(self) -> bool:
        current = db.setting_get("enabled", "true")
        new = "false" if current == "true" else "true"
        db.setting_set("enabled", new)
        return new == "true"

    @property
    def global_enabled(self) -> bool:
        return db.setting_get("enabled", "true") == "true"

    # ── OpenRouter credits ──

    async def get_openrouter_credits(self) -> Tuple[float, float, float]:
        try:
            resp = requests.get(
                "https://openrouter.ai/api/v1/key",
                headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                remaining = float(data.get("limit_remaining", 0) or 0)
                limit = float(data.get("limit", 0) or 0)
                usage = float(data.get("usage", 0) or 0)
                return (limit, usage, remaining)
        except Exception as e:
            logger.error(f"Credits fetch error: {e}")
        return (0, 0, 0)

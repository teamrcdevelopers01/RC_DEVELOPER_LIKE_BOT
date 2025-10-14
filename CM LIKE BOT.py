#!/usr/bin/env python3
# advanced_ff_group_like_bot_final.py
# Requires: python-telegram-bot>=20.0 (async)

import asyncio
import json
import logging
import os
from datetime import datetime
from functools import wraps
from typing import Any, Dict, Optional

from telegram import __version__ as ptb_version, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode, ChatType
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    Defaults,
)

# -----------------------------
# Basic logging
# -----------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("advanced_ff_like_bot")

# -----------------------------
# Persistence files & default config
# -----------------------------
DATA_FILE = "data.json"
CONFIG_FILE = "config.json"
COOLDOWN_SECONDS = 3

DEFAULT_CONFIG = {
    "bot_token": "8460634349:AAFOLyhQmy1aSQ5su2y42td4kk5bYu43ssE",
    "channel_link": "https://t.me/+3JG3Dc0VOqs4Y2Y1",
    "owner_username": "@rc_team_01",
    "allowed_group_id": "-1003127041373",
}

# -----------------------------
# Helpers
# -----------------------------
def load_json_file(path: str, default: Any):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json_file(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

config = load_json_file(CONFIG_FILE, DEFAULT_CONFIG)
data_store: Dict[str, Any] = load_json_file(DATA_FILE, {"groups": {}})

env_token = os.getenv("BOT_TOKEN")
if env_token:
    config["bot_token"] = env_token

for k, v in DEFAULT_CONFIG.items():
    config.setdefault(k, v)

def ensure_group_record(chat_id: int, title: Optional[str] = "") -> Dict[str, Any]:
    gid = str(chat_id)
    if gid not in data_store["groups"]:
        data_store["groups"][gid] = {
            "chat_id": chat_id,
            "title": title or "",
            "owner_id": None,
            "api_url": "https://28-0.vercel.app",
            "users": {},
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        save_json_file(DATA_FILE, data_store)
    return data_store["groups"][gid]

def ensure_user(chat_id: int, tg_user) -> Dict[str, Any]:
    group = ensure_group_record(chat_id)
    uid = str(tg_user.id)
    if uid not in group["users"]:
        group["users"][uid] = {
            "tg_id": tg_user.id,
            "username": tg_user.username or "",
            "first_name": tg_user.first_name or "",
            "ff_name": "",
            "ff_uid": "",
            "likes_received": 0,
            "liked_by": [],
            "level": None,
            "registered_at": datetime.utcnow().isoformat() + "Z",
        }
        save_json_file(DATA_FILE, data_store)
    return group["users"][uid]

def is_group_allowed(chat_id: int) -> bool:
    allowed = config.get("allowed_group_id")
    if allowed is None:
        return True
    if isinstance(allowed, str):
        if allowed.strip().lower() in ("", "group id dalo"):
            return True
    try:
        return int(allowed) == int(chat_id)
    except Exception:
        return False

_last_cmd_ts: Dict[int, datetime] = {}

def cooldown_check(user_id: int) -> bool:
    now = datetime.utcnow()
    last = _last_cmd_ts.get(user_id)
    if last and (now - last).total_seconds() < COOLDOWN_SECONDS:
        return False
    _last_cmd_ts[user_id] = now
    return True

# -----------------------------
# Decorators
# -----------------------------
def group_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat is None or update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await update.effective_message.reply_text("Ye bot sirf group chats ke liye bana hai.")
            return
        if not is_group_allowed(update.effective_chat.id):
            await update.effective_message.reply_text("Yahan bot allowed nahi hai (GROUP ID DALO set nahi hua).")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# -----------------------------
# Commands
# -----------------------------
@group_only
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show banner + user info"""
    chat = update.effective_chat
    user = update.effective_user
    cfg_channel = config.get("channel_link") or DEFAULT_CONFIG["channel_link"]
    owner_un = config.get("owner_username") or DEFAULT_CONFIG["owner_username"]

    banner = "👑 MODDING BY CM 👑"
    text = (
        f"{banner}\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🙋‍♂️ User: @{user.username or user.first_name}\n"
        f"🆔 User ID: `{user.id}`\n\n"
        "👋 FreeFire-Like Bot active in this group (simulated likes only).\n\n"
        "🔹 /register <FF_UID> <FF_NAME> [level]\n"
        "🔹 /like @username — like user\n"
        "🔹 /addlike @username <n> — admin/owner only\n"
        "🔹 /set_api, /set_group, /config\n\n"
        "Note:\n"
        "- Group API default: 'API URL YAHA DALO'\n"
        "- Global allowed_group_id: 'GROUP ID DALO'\n"
        "- bot_token: '8460634349:AAFOLyhQmy1aSQ5su2y42td4kk5bYu43ssE'\n"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Channel", url=cfg_channel),
         InlineKeyboardButton("Owner", url=f"https://t.me/{owner_un.lstrip('@')}")],
    ])
    await update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

@group_only
async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.effective_message.reply_text("Usage: /register <FF_UID> <FF_NAME> [level]")
        return
    chat = update.effective_chat
    user = update.effective_user
    ff_uid, ff_name = context.args[0], context.args[1]
    level = int(context.args[2]) if len(context.args) > 2 and context.args[2].isdigit() else None
    rec = ensure_user(chat.id, user)
    rec.update({"ff_uid": ff_uid, "ff_name": ff_name, "level": level})
    save_json_file(DATA_FILE, data_store)
    await update.effective_message.reply_text(f"✅ Registered {ff_name} (UID {ff_uid}) Level: {level or '(none)'}")

@group_only
async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    target = user
    if context.args:
        uname = context.args[0].lstrip("@").lower()
        for rec in data_store["groups"].get(str(chat.id), {}).get("users", {}).values():
            if (rec.get("username") or "").lower() == uname or (rec.get("ff_name") or "").lower() == uname:
                target = rec
                break
    rec = ensure_user(chat.id, target)
    text = (
        f"👤 *{rec.get('username') or rec.get('first_name')}*\n"
        f"• Game name: *{rec.get('ff_name') or '(not set)'}*\n"
        f"• Game UID: `{rec.get('ff_uid') or '(not set)'}`\n"
        f"• Likes: *{rec.get('likes_received', 0)}*\n"
        f"• Level: *{rec.get('level') or '(not set)'}*\n"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

@group_only
async def like_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Usage: /like @username")
        return
    if not cooldown_check(update.effective_user.id):
        await update.effective_message.reply_text("Thoda ruk jao — cooldown chal raha hai.")
        return
    chat = update.effective_chat
    giver = update.effective_user
    gid = str(chat.id)
    uname = context.args[0].lstrip("@").lower()
    group = data_store["groups"].get(gid, {})
    for uid, rec in group.get("users", {}).items():
        if (rec.get("username") or "").lower() == uname or (rec.get("ff_name") or "").lower() == uname:
            if str(giver.id) == str(rec["tg_id"]):
                await update.effective_message.reply_text("Khud ko like nahi de sakte.")
                return
            if str(giver.id) in rec.get("liked_by", []):
                await update.effective_message.reply_text("Aap pehle hi like de chuke ho.")
                return
            rec["likes_received"] += 1
            rec.setdefault("liked_by", []).append(str(giver.id))
            save_json_file(DATA_FILE, data_store)
            await update.effective_message.reply_text(f"❤️ Like added for @{rec.get('username') or rec.get('ff_name')}")
            return
    await update.effective_message.reply_text("User not found or not registered.")

# -----------------------------
# Error Handler
# -----------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Error: %s", context.error)

# -----------------------------
# Main
# -----------------------------
def main():
    token = config.get("bot_token")
    if "8460634349:AAFOLyhQmy1aSQ5su2y42td4kk5bYu43ssE" in (token or ""):
        logger.error("❌ Bot token placeholder detected. Please replace it with your real token.")
        return

    logger.info("Starting bot... PTB v%s", ptb_version)
    app = ApplicationBuilder().token(token).defaults(Defaults(parse_mode=ParseMode.HTML)).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("register", register_handler))
    app.add_handler(CommandHandler("profile", profile_handler))
    app.add_handler(CommandHandler("like", like_handler))
    app.add_error_handler(error_handler)

    app.run_polling()

if __name__ == "__main__":
    main()

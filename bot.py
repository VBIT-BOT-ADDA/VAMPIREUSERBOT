import logging
import os
import re
import asyncio

from motor.motor_asyncio import AsyncIOMotorClient
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatType
from telegram.error import TelegramError, RetryAfter
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import (
    BOT_TOKEN,
    MONGO_DB_URI,
    OWNER_USERNAME,
    UPDATE_CHANNEL,
    SUPPORT_GROUP,
    START_IMAGE_URL,
)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("VampireUserbot")

mongo = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo["vampire_userbot_db"]

warnings_db = db["warnings"]
exempt_db = db["moderation_exemptions"]
optin_db = db["broadcast_optin"]
settings_db = db["chat_settings"]

# Small Unicode font. Keep digits unchanged for OTPs and IDs.
SMALL_FONT_MAP = {
    "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ",
    "f": "ꜰ", "g": "ɢ", "h": "ʜ", "i": "ɪ", "j": "ᴊ",
    "k": "ᴋ", "l": "ʟ", "m": "ᴍ", "n": "ɴ", "o": "ᴏ",
    "p": "ᴘ", "q": "ǫ", "r": "ʀ", "s": "s", "t": "ᴛ",
    "u": "ᴜ", "v": "ᴠ", "w": "ᴡ", "x": "x", "y": "ʏ",
    "z": "ᴢ",
}


def small(text):
    return "".join(SMALL_FONT_MAP.get(c.lower(), c) for c in text)


def home_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👑 ᴏᴡɴᴇʀ", url=f"https://t.me/{OWNER_USERNAME.lstrip('@')}"),
        ],
        [
            InlineKeyboardButton("📢 ᴜᴘᴅᴀᴛᴇs", url=UPDATE_CHANNEL),
            InlineKeyboardButton("🛠 sᴜᴘᴘᴏʀᴛ", url=SUPPORT_GROUP),
        ],
        [
            InlineKeyboardButton("📖 ʜᴇʟᴘ", callback_data="help"),
            InlineKeyboardButton("⌨️ ᴄᴏᴍᴍᴀɴᴅs", callback_data="commands"),
        ],
        [
            InlineKeyboardButton("📨 ʙʀᴏᴀᴅᴄᴀsᴛ ᴏᴘᴛ-ɪɴ", callback_data="broadcast_info"),
        ],
    ])


def navigation_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="home")]
    ])


WELCOME = (
    "🦇 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴠᴀᴍᴘɪʀᴇ ʙᴏᴛ 🦇\n\n"
    "✨ ʏᴏᴜʀ ᴄᴏᴍᴍᴜɴɪᴛʏ, ʏᴏᴜʀ ʀᴜʟᴇs\n"
    "🛡 ɢʀᴏᴜᴘ ᴍᴏᴅᴇʀᴀᴛɪᴏɴ\n"
    "⚠️ ᴡᴀʀɴɪɴɢ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ\n"
    "⚙️ ᴍᴏɴɢᴏᴅʙ sᴇᴛᴛɪɴɢs\n\n"
    "👇 ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ʙᴇʟᴏᴡ."
)

HELP_TEXT = (
    "📖 ʜᴇʟᴘ ᴍᴇɴᴜ\n\n"
    "➤ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ\n"
    "➤ ᴍᴀᴋᴇ ᴍᴇ ᴀᴅᴍɪɴ\n"
    "➤ ᴇɴᴀʙʟᴇ ᴅᴇʟᴇᴛᴇ ᴍᴇssᴀɢᴇs ᴀɴᴅ ʙᴀɴ ᴜsᴇʀs\n\n"
    "ᴛʜᴇ ʙᴏᴛ ᴡɪʟʟ ᴡᴀʀɴ ᴜsᴇʀs ғᴏʀ ᴍᴀᴛᴄʜɪɴɢ "
    "ʀᴜʟᴇ-ᴠɪᴏʟᴀᴛɪɴɢ ᴛᴇxᴛ. ᴀғᴛᴇʀ 3 ᴡᴀʀɴɪɴɢs, "
    "ɪᴛ ᴡɪʟʟ ᴀᴛᴛᴇᴍᴘᴛ ᴀ ʙᴀɴ ɪғ ᴘᴇʀᴍɪssɪᴏɴs ᴀʟʟᴏᴡ ɪᴛ."
)

COMMANDS_TEXT = (
    "⌨️ ᴄᴏᴍᴍᴀɴᴅs\n\n"
    "/start — ᴏᴘᴇɴ ᴍᴇɴᴜ\n"
    "/help — ʜᴇʟᴘ\n"
    "/commands — ᴄᴏᴍᴍᴀɴᴅ ʟɪsᴛ\n"
    "/warnings — ᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴡᴀʀɴɪɴɢs\n"
    "/approve — ᴇxᴇᴍᴘᴛ ᴀ ʀᴇᴘʟɪᴇᴅ ᴜsᴇʀ\n"
    "/unapprove — ʀᴇᴍᴏᴠᴇ ᴇxᴇᴍᴘᴛɪᴏɴ\n"
    "/broadcast_optin — ᴏᴘᴛ ɪɴ ᴛᴏ ᴏᴡɴᴇʀ ᴜᴘᴅᴀᴛᴇs\n"
    "/broadcast_optout — ᴏᴘᴛ ᴏᴜᴛ ᴏғ ᴏᴡɴᴇʀ ᴜᴘᴅᴀᴛᴇs\n\n"
    "ᴀᴘᴘʀᴏᴠᴇ ᴀɴᴅ ᴜɴᴀᴘᴘʀᴏᴠᴇ ᴡᴏʀᴋ ᴏɴ ᴀ ʀᴇᴘʟɪᴇᴅ "
    "ᴍᴇssᴀɢᴇ ɪɴ ᴀ ɢʀᴏᴜᴘ."
)

BROADCAST_INFO = (
    "📨 ʙʀᴏᴀᴅᴄᴀsᴛ ᴘʀɪᴠᴀᴄʏ\n\n"
    "ᴜsᴇ /broadcast_optin ɪɴ ᴘʀɪᴠᴀᴛᴇ ᴛᴏ ʀᴇᴄᴇɪᴠᴇ "
    "ᴜᴘᴅᴀᴛᴇs ғʀᴏᴍ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ.\n"
    "ᴜsᴇ /broadcast_optout ᴀɴʏᴛɪᴍᴇ ᴛᴏ sᴛᴏᴘ.\n"
    "ᴏɴʟʏ ᴜsᴇʀs ᴡʜᴏ ᴏᴘᴛᴇᴅ ɪɴ ᴡɪʟʟ ʀᴇᴄᴇɪᴠᴇ "
    "ᴍᴇssᴀɢᴇs."
)

# Starter text filters only. Review and customize these words for your group.
# Keyword matching is not a reliable way to determine whether content is pornographic.
BAD_WORDS = {
    "fuck", "fucking", "motherfucker",
    "bitch", "bastard", "asshole",
}

# Keep the list small and avoid matching harmless words accidentally.
BAD_PATTERNS = [
    re.compile(r"\bpornography\b", re.IGNORECASE),
    re.compile(r"\bporn\b", re.IGNORECASE),
    re.compile(r"\bxxx\b", re.IGNORECASE),
    re.compile(r"\bsex\s*video\b", re.IGNORECASE),
    *[
        re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        for word in BAD_WORDS
    ],
]


def violates_rules(text):
    if not text:
        return False
    return any(pattern.search(text) for pattern in BAD_PATTERNS)


async def is_group_admin(context, chat_id, user_id):
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator", "owner")
    except TelegramError:
        return False


async def show_home(message, context):
    try:
        await message.reply_photo(
            photo=START_IMAGE_URL,
            caption=WELCOME,
            reply_markup=home_keyboard(),
        )
    except Exception:
        await message.reply_text(WELCOME, reply_markup=home_keyboard())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message:
        await show_home(update.effective_message, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        HELP_TEXT, reply_markup=navigation_keyboard()
    )


async def commands_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        COMMANDS_TEXT, reply_markup=navigation_keyboard()
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "home":
        try:
            await query.message.edit_caption(
                caption=WELCOME, reply_markup=home_keyboard()
            )
        except TelegramError:
            try:
                await query.message.edit_text(
                    WELCOME, reply_markup=home_keyboard()
                )
            except TelegramError:
                pass

    elif query.data in ("help", "commands", "broadcast_info"):
        text = {
            "help": HELP_TEXT,
            "commands": COMMANDS_TEXT,
            "broadcast_info": BROADCAST_INFO,
        }[query.data]

        try:
            await query.message.edit_caption(
                caption=text, reply_markup=navigation_keyboard()
            )
        except TelegramError:
            try:
                await query.message.edit_text(
                    text, reply_markup=navigation_keyboard()
                )
            except TelegramError:
                pass


async def warnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if chat.type == ChatType.PRIVATE:
        await update.effective_message.reply_text(
            "ᴜsᴇ /warnings ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ ᴡʜᴇʀᴇ ʏᴏᴜ ᴡᴀɴᴛ "
            "ᴛᴏ ᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴡᴀʀɴɪɴɢs."
        )
        return

    record = await warnings_db.find_one({
        "chat_id": chat.id,
        "user_id": user.id,
    })
    count = record.get("count", 0) if record else 0

    await update.effective_message.reply_text(
        f"⚠️ {user.first_name}: {count}/3 ᴡᴀʀɴɪɴɢs"
    )


async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    caller = update.effective_user

    if chat.type == ChatType.PRIVATE:
        await message.reply_text(
            "ᴜsᴇ /approve ᴀs ᴀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ's ᴍᴇssᴀɢᴇ ɪɴ ᴀ ɢʀᴏᴜᴘ."
        )
        return

    if not await is_group_admin(context, chat.id, caller.id):
        await message.reply_text("❌ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴs ᴄᴀɴ ᴜsᴇ ᴛʜɪs.")
        return

    if not message.reply_to_message:
        await message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴛʜᴇ ᴜsᴇʀ's ᴍᴇssᴀɢᴇ ᴛᴏ ᴀᴘᴘʀᴏᴠᴇ ᴛʜᴇᴍ.")
        return

    target = message.reply_to_message.from_user
    if target.is_bot:
        await message.reply_text("ʙᴏᴛs ᴅᴏ ɴᴏᴛ ɴᴇᴇᴅ ᴇxᴇᴍᴘᴛɪᴏɴs.")
        return

    await exempt_db.update_one(
        {"chat_id": chat.id, "user_id": target.id},
        {"$set": {"approved_by": caller.id}},
        upsert=True,
    )
    await message.reply_text(
        f"✅ {target.first_name} ɪs ɴᴏᴡ ᴇxᴇᴍᴘᴛ ғʀᴏᴍ ᴛᴇxᴛ ᴍᴏᴅᴇʀᴀᴛɪᴏɴ."
    )


async def unapprove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    caller = update.effective_user

    if chat.type == ChatType.PRIVATE:
        await message.reply_text("ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴡᴏʀᴋs ɪɴ ɢʀᴏᴜᴘs.")
        return

    if not await is_group_admin(context, chat.id, caller.id):
        await message.reply_text("❌ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴs ᴄᴀɴ ᴜsᴇ ᴛʜɪs.")
        return

    if not message.reply_to_message:
        await message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴛʜᴇ ᴜsᴇʀ's ᴍᴇssᴀɢᴇ.")
        return

    target = message.reply_to_message.from_user
    await exempt_db.delete_one({"chat_id": chat.id, "user_id": target.id})
    await message.reply_text(
        f"✅ ᴇxᴇᴍᴘᴛɪᴏɴ ʀᴇᴍᴏᴠᴇᴅ ғᴏʀ {target.first_name}."
    )


async def broadcast_optin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.effective_message.reply_text(
            "ᴘʟᴇᴀsᴇ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ɪɴ ᴘʀɪᴠᴀᴛᴇ."
        )
        return

    await optin_db.update_one(
        {"user_id": user.id},
        {"$set": {"opted_in": True}},
        upsert=True,
    )
    await update.effective_message.reply_text(
        "✅ ʏᴏᴜ ᴀʀᴇ ᴏᴘᴛᴇᴅ ɪɴ ᴛᴏ ᴏᴡɴᴇʀ ᴜᴘᴅᴀᴛᴇs. "
        "ᴜsᴇ /broadcast_optout ᴀɴʏᴛɪᴍᴇ ᴛᴏ ᴏᴘᴛ ᴏᴜᴛ."
    )


async def broadcast_optout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await optin_db.delete_one({"user_id": update.effective_user.id})
    await update.effective_message.reply_text(
        "✅ ʏᴏᴜ ʜᴀᴠᴇ ᴏᴘᴛᴇᴅ ᴏᴜᴛ ᴏғ ᴏᴡɴᴇʀ ᴜᴘᴅᴀᴛᴇs."
    )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner-only: /broadcast your message. Only opted-in users receive it."""
    user = update.effective_user
    owner = OWNER_USERNAME.lstrip("@").lower()

    if not user.username or user.username.lower() != owner:
        await update.effective_message.reply_text("❌ ᴏᴡɴᴇʀ ᴏɴʟʏ.")
        return

    if not context.args:
        await update.effective_message.reply_text(
            "ᴜsᴀɢᴇ: /broadcast ʏᴏᴜʀ ᴍᴇssᴀɢᴇ"
        )
        return

    body = " ".join(context.args)
    cursor = optin_db.find({"opted_in": True})
    sent = 0
    failed = 0

    async for record in cursor:
        try:
            await context.bot.send_message(
                chat_id=record["user_id"],
                text=body,
            )
            sent += 1
            await asyncio.sleep(0.08)
        except RetryAfter as exc:
            await asyncio.sleep(float(exc.retry_after) + 1)
            try:
                await context.bot.send_message(
                    chat_id=record["user_id"], text=body
                )
                sent += 1
            except TelegramError:
                failed += 1
        except TelegramError:
            failed += 1

    await update.effective_message.reply_text(
        f"📨 ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇ\n"
        f"✅ sᴇɴᴛ: {sent}\n❌ ғᴀɪʟᴇᴅ: {failed}"
    )


async def moderate_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not user or user.is_bot:
        return
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    # Do not moderate group administrators.
    if await is_group_admin(context, chat.id, user.id):
        return

    # Explicit per-group exemption.
    if await exempt_db.find_one({"chat_id": chat.id, "user_id": user.id}):
        return

    text = message.text or message.caption or ""
    if not violates_rules(text):
        return

    # Delete the matching message if the bot has permission.
    try:
        await message.delete()
    except TelegramError:
        logger.warning("Cannot delete message in chat %s", chat.id)

    key = {"chat_id": chat.id, "user_id": user.id}
    record = await warnings_db.find_one_and_update(
        key,
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=True,
    )

    count = min(record.get("count", 1), 3)

    if count < 3:
        await message.reply_text(
            f"⚠️ {user.first_name}, ᴡᴀʀɴɪɴɢ {count}/3\n\n"
            "ᴘᴏʀɴᴏɢʀᴀᴘʜʏ ᴀɴᴅ ᴀʙᴜsɪᴠᴇ ʟᴀɴɢᴜᴀɢᴇ ᴀʀᴇ ɴᴏᴛ "
            "ᴀʟʟᴏᴡᴇᴅ ʜᴇʀᴇ. ᴘʟᴇᴀsᴇ sᴛᴏᴘ."
        )
        return

    try:
        await context.bot.ban_chat_member(
            chat_id=chat.id,
            user_id=user.id,
        )
        await message.reply_text(
            f"⛔ {user.first_name} ʀᴇᴀᴄʜᴇᴅ 3 ᴡᴀʀɴɪɴɢs ᴀɴᴅ ᴡᴀs ʙᴀɴɴᴇᴅ."
        )
    except TelegramError as exc:
        logger.warning("Ban failed for %s in %s: %s", user.id, chat.id, exc)
        await message.reply_text(
            f"⚠️ {user.first_name} ʀᴇᴀᴄʜᴇᴅ 3 ᴡᴀʀɴɪɴɢs, "
            "ʙᴜᴛ ɪ ᴄᴏᴜʟᴅ ɴᴏᴛ ʙᴀɴ ᴛʜᴇᴍ. "
            "ᴄʜᴇᴄᴋ ᴍʏ ᴀᴅᴍɪɴ ᴘᴇʀᴍɪssɪᴏɴs."
        )


async def error_handler(update, context):
    logger.error("Update failed", exc_info=context.error)


def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("commands", commands_command))
    app.add_handler(CommandHandler("warnings", warnings_command))
    app.add_handler(CommandHandler("approve", approve_command))
    app.add_handler(CommandHandler("unapprove", unapprove_command))
    app.add_handler(CommandHandler("broadcast_optin", broadcast_optin))
    app.add_handler(CommandHandler("broadcast_optout", broadcast_optout))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.CAPTION)
            & ~filters.COMMAND
            & filters.ChatType.GROUPS,
            moderate_message,
        )
    )

    app.add_error_handler(error_handler)
    logger.info("Vampire moderation bot starting")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()

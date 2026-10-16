import asyncio
import logging
import random

from motor.motor_asyncio import AsyncIOMotorClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import MemorySession

from config import (
    API_HASH,
    API_ID,
    BOT_TOKEN,
    MONGO_DB_URI,
    OWNER_USERNAME,
    START_IMAGE_URL,
    SUPPORT_GROUP,
    UPDATE_CHANNEL,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("VampireUserbot")

# MongoDB Database Connection
mongo = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo["vampire_userbot_db"]
opted_in = db["tag_optin"]
sessions_collection = db["hosted_sessions"]

P_EMOJI_FIRE = "🔥"
P_EMOJI_STAR = "⭐"
P_EMOJI_CHECK = "✅"

SMALL_FONT_MAP = {
    "a": "ᵃ",
    "b": "ᵇ",
    "c": "ᶜ",
    "d": "ᵈ",
    "e": "ᵉ",
    "f": "ᶠ",
    "g": "ᵍ",
    "h": "ʰ",
    "i": "ⁱ",
    "j": "ʲ",
    "k": "ᵏ",
    "l": "ˡ",
    "m": "ᵐ",
    "n": "ⁿ",
    "o": "ᵒ",
    "p": "ᵖ",
    "q": "𐞥",
    "r": "ʳ",
    "s": "ˢ",
    "t": "ᵗ",
    "u": "ᵘ",
    "v": "ᵛ",
    "w": "ʷ",
    "x": "ˣ",
    "y": "ʸ",
    "z": "ᶻ",
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
}


def to_small_font(text):
  return "".join(SMALL_FONT_MAP.get(c.lower(), c) for c in text)


HELP = (
    "🦇 ᴠᴀᴍᴘɪʀᴇ ᴜsᴇʀʙᴏᴛ\n\n"
    ".help — ᴄᴏᴍᴍᴀɴᴅ ʜᴇʟᴘ\n"
    ".optin — ᴛᴀɢɢɪɴɢ ᴏᴘᴛ-ɪɴ\n"
    ".optout — ᴛᴀɢɢɪɴɢ ᴏᴘᴛ-ᴏᴜᴛ\n"
    ".tagall <message> — ᴜᴘ ᴛᴏ 5 ᴏᴘᴛᴇᴅ-ɪɴ ᴍᴇᴍʙᴇʀs\n"
    ".randomtag — ʀᴀɴᴅᴏᴍ ᴏᴘᴛᴇᴅ-ɪɴ ᴍᴇᴍʙᴇʀ\n\n"
    "ᴛᴀɢɢɪɴɢ ɪs ʟɪᴍɪᴛᴇᴅ ᴛᴏ ᴍᴇᴍʙᴇʀs ᴡʜᴏ "
    "ᴇxᴘʟɪᴄɪᴛʟʏ ᴏᴘᴛ ɪɴ."
)


def mention(user, label=None):
  name = label or user.first_name or "Member"
  return f"[{name}](tg://user?id={user.id})"


async def group_only(event):
  return bool(event.is_group or event.is_channel)


# Temporary storage for interactive host steps
user_temp_data = {}


# --- Telegram Host Bot Start & Panel Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  keyboard = [
      [InlineKeyboardButton("👑 owner profile", url=f"https://t.me/{OWNER_USERNAME}")],
      [
          InlineKeyboardButton("📢 update channel", url=UPDATE_CHANNEL),
          InlineKeyboardButton("🛠️ support group", url=SUPPORT_GROUP),
      ],
      [InlineKeyboardButton("🚀 click to host userbot", callback_data="click_to_host")],
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  welcome_text = (
      f"{P_EMOJI_STAR} {to_small_font('welcome to vampire userbot hosting bot')} {P_EMOJI_STAR}\n\n"
      f"{to_small_font('click the button below to host your userbot directly on your account.')}"
  )

  if update.message:
    try:
      await update.message.reply_photo(
          photo=START_IMAGE_URL, caption=welcome_text, reply_markup=reply_markup
      )
    except Exception:
      await update.message.reply_text(text=welcome_text, reply_markup=reply_markup)
  elif update.callback_query:
    query = update.callback_query
    await query.answer()
    try:
      await query.message.edit_caption(caption=welcome_text, reply_markup=reply_markup)
    except Exception:
      try:
        await query.edit_message_text(text=welcome_text, reply_markup=reply_markup)
      except Exception:
        pass


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()

  if query.data == "click_to_host":
    user_temp_data[query.from_user.id] = {"step": "waiting_phone"}
    prompt_text = f"{to_small_font('📱 please send your telegram phone number with country code (e.g., +919876543210):')}"
    try:
      await query.message.edit_caption(caption=prompt_text)
    except Exception:
      try:
        await query.edit_message_text(text=prompt_text)
      except Exception:
        pass


async def handle_hosting_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if not update.message or not update.message.text:
    return

  user_id = update.message.from_user.id
  text = update.message.text.strip()

  if user_id not in user_temp_data:
    return

  current_step = user_temp_data[user_id].get("step")

  if current_step == "waiting_phone":
    phone = text
    user_temp_data[user_id]["phone"] = phone
    user_temp_data[user_id]["step"] = "waiting_otp"

    try:
      # Use MemorySession temporarily during login process
      client_temp = TelegramClient(MemorySession(), API_ID, API_HASH)
      await client_temp.connect()
      sent_code = await client_temp.send_code_request(phone)
      user_temp_data[user_id]["client"] = client_temp
      user_temp_data[user_id]["phone_code_hash"] = sent_code.phone_code_hash

      await update.message.reply_text(
          text=f"{P_EMOJI_CHECK} {to_small_font('otp sent successfully!')}\n"
          f"{to_small_font('please enter your otp with spaces (example: 1 2 3 4 5):')}"
      )
    except Exception as e:
      await update.message.reply_text(
          text=f"{to_small_font(f'❌ error: {str(e)}')}\n"
          f"{to_small_font('please restart using /start')}"
      )
      user_temp_data.pop(user_id, None)

  elif current_step == "waiting_otp":
    otp = text.replace(" ", "")
    client_temp = user_temp_data[user_id]["client"]
    phone = user_temp_data[user_id]["phone"]
    phone_code_hash = user_temp_data[user_id]["phone_code_hash"]

    try:
      await client_temp.sign_in(phone, otp, phone_code_hash=phone_code_hash)
      
      # Extract raw session bytes / session data to store in MongoDB securely without strings
      session_data = client_temp.session.save()

      # Save session into MongoDB mapped to user_id
      await sessions_collection.update_one(
          {"user_id": user_id},
          {"$set": {"session": session_data, "phone": phone}},
          upsert=True,
      )

      await update.message.reply_text(
          text=f"{P_EMOJI_FIRE} {to_small_font('login successful & userbot activated!')}\n"
          f"{to_small_font('your account is now successfully hosted and running.')}"
      )
      
      # Keep reference and start background userbot instance
      asyncio.create_task(run_active_userbot(client_temp, user_id))
      user_temp_data.pop(user_id, None)

    except SessionPasswordNeededError:
      user_temp_data[user_id]["step"] = "waiting_password"
      await update.message.reply_text(
          text=f"{to_small_font('🔒 2-step verification detected!')}\n"
          f"{to_small_font('please enter your cloud password:')}"
      )
    except Exception as e:
      await update.message.reply_text(
          text=f"{to_small_font(f'❌ login failed: {str(e)}')}\n"
          f"{to_small_font('please restart using /start')}"
      )
      user_temp_data.pop(user_id, None)

  elif current_step == "waiting_password":
    password = text
    client_temp = user_temp_data[user_id]["client"]

    try:
      await client_temp.sign_in(password=password)
      session_data = client_temp.session.save()

      # Save 2-step session securely into MongoDB
      await sessions_collection.update_one(
          {"user_id": user_id},
          {
              "$set": {
                  "session": session_data,
                  "phone": user_temp_data[user_id]["phone"],
              }
          },
          upsert=True,
      )

      await update.message.reply_text(
          text=f"{P_EMOJI_FIRE} {to_small_font('2-step login successful & userbot activated!')}\n"
          f"{to_small_font('your account is now successfully hosted and running.')}"
      )
      
      # Keep reference and start background userbot instance
      asyncio.create_task(run_active_userbot(client_temp, user_id))
      user_temp_data.pop(user_id, None)

    except Exception as e:
      await update.message.reply_text(
          text=f"{to_small_font(f'❌ wrong password: {str(e)}')}\n"
          f"{to_small_font('please restart using /start')}"
      )
      user_temp_data.pop(user_id, None)


# --- Userbot Core Event Handlers ---
def register_userbot_events(ubot_client):

  @ubot_client.on(events.NewMessage(pattern=r"^\.help$"))
  async def help_handler(event):
    await event.reply(HELP, parse_mode="md")

  @ubot_client.on(events.NewMessage(pattern=r"^\.optin$"))
  async def optin_handler(event):
    if not await group_only(event):
      await event.reply("ᴜsᴇ ᴛʜɪs ɪɴ ᴀ ɢʀᴏᴜᴘ.")
      return

    sender = await event.get_sender()
    await opted_in.update_one(
        {"chat_id": event.chat_id, "user_id": sender.id},
        {"$set": {"enabled": True}},
        upsert=True,
    )
    await event.reply("✅ ʏᴏᴜ ᴏᴘᴛᴇᴅ ɪɴ ᴛᴏ ɢʀᴏᴜᴘ ᴛᴀɢɢɪɴɢ.")

  @ubot_client.on(events.NewMessage(pattern=r"^\.optout$"))
  async def optout_handler(event):
    sender = await event.get_sender()
    await opted_in.delete_one({"chat_id": event.chat_id, "user_id": sender.id})
    await event.reply("✅ ʏᴏᴜ ᴏᴘᴛᴇᴅ ᴏᴜᴛ.")

  @ubot_client.on(events.NewMessage(pattern=r"^\.tagall(?:\s+(.+))?$"))
  async def tagall_handler(event):
    if not await group_only(event):
      await event.reply("ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴡᴏʀᴋs ɪɴ ɢʀᴏᴜᴘs.")
      return

    sender = await event.get_sender()
    try:
      permissions = await ubot_client.get_permissions(event.chat_id, sender)
      if not (permissions.is_admin or permissions.is_creator):
        await event.reply("❌ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴs ᴏɴʟʏ.")
        return
    except Exception:
      await event.reply("ᴄᴏᴜʟᴅ ɴᴏᴛ ᴠᴇʀɪғʏ ᴀᴅᴍɪɴ ᴘᴇʀᴍɪssɪᴏɴs.")
      return

    custom_message = event.pattern_match.group(1) or "Hello!"

    records = await opted_in.find({
        "chat_id": event.chat_id,
        "enabled": True,
    }).to_list(length=1000)

    chosen = random.sample(records, min(5, len(records)))

    if not chosen:
      await event.reply(
          "ɴᴏ ᴍᴇᴍʙᴇʀs ʜᴀᴠᴇ ᴏᴘᴛᴇᴅ ɪɴ ʏᴇᴛ. " "ᴍᴇᴍʙᴇʀs ᴄᴀɴ ᴜsᴇ .optin."
      )
      return

    tags = []
    for record in chosen:
      try:
        user = await ubot_client.get_entity(record["user_id"])
        tags.append(mention(user))
      except Exception:
        continue

    if tags:
      await event.reply(
          custom_message + "\n\n" + " ".join(tags),
          parse_mode="md",
      )

  @ubot_client.on(events.NewMessage(pattern=r"^\.randomtag$"))
  async def randomtag_handler(event):
    if not await group_only(event):
      await event.reply("ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴡᴏʀᴋs ɪɴ ɢʀᴏᴜᴘs.")
      return

    records = await opted_in.find({
        "chat_id": event.chat_id,
        "enabled": True,
    }).to_list(length=1000)

    if not records:
      await event.reply("ɴᴏ ᴍᴇᴍʙᴇʀs ʜᴀᴠᴇ ᴏᴘᴛᴇ_ɪɴ.")
      return

    record = random.choice(records)
    try:
      user = await ubot_client.get_entity(record["user_id"])
      await event.reply(
          "🎯 " + mention(user),
          parse_mode="md",
      )
    except Exception:
      await event.reply("ᴄᴏᴜʟᴅ ɴᴏᴛ ᴛᴀɢ ᴛʜɪs ᴍᴇᴍʙᴇʀ.")


async def run_active_userbot(ubot_client, user_id):
  try:
    register_userbot_events(ubot_client)
    if not ubot_client.is_connected():
      await ubot_client.connect()
    me = await ubot_client.get_me()
    log.info("Userbot active & running for: %s (%s)", me.first_name, me.id)
    await ubot_client.run_until_disconnected()
  except Exception as e:
    log.error("Userbot disconnected for user %s due to: %s", user_id, e)


async def restart_saved_sessions():
  async for doc in sessions_collection.find({}):
    if "session" in doc:
      try:
        # Load session back from database storage
        session_data = doc["session"]
        session_obj = MemorySession()
        session_obj.load_session(session_data)
        
        ubot_client = TelegramClient(session_obj, API_ID, API_HASH)
        asyncio.create_task(run_active_userbot(ubot_client, doc["user_id"]))
      except Exception as e:
        log.error("Failed to restart hosted session for user: %s", e)


async def main():
  # 1. Start Python Telegram Bot for Hosting Panel
  app = (
      ApplicationBuilder()
      .token(BOT_TOKEN)
      .connect_timeout(30.0)
      .read_timeout(30.0)
      .write_timeout(30.0)
      .build()
  )

  app.add_handler(CommandHandler("start", start))
  app.add_handler(CallbackQueryHandler(button_handler))
  app.add_handler(
      MessageHandler(filters.TEXT & (~filters.COMMAND), handle_hosting_messages)
  )

  await app.initialize()
  await app.start()
  await app.updater.start_polling()

  log.info("bot started successfully with click-to-host and mongodb support...")
  print("bot started successfully with click-to-host and mongodb support...")

  # 2. Restart all existing userbot sessions saved in database automatically on boot
  await restart_saved_sessions()

  # Keep running forever
  await asyncio.Event().wait()


if __name__ == "__main__":
  asyncio.run(main())

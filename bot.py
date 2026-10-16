import asyncio
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from motor.motor_asyncio import AsyncIOMotorClient
from config import (
    BOT_TOKEN,
    API_ID,
    API_HASH,
    MONGO_DB_URI,
    OWNER_USERNAME,
    UPDATE_CHANNEL,
    SUPPORT_GROUP,
    START_IMAGE_URL,
)

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# MongoDB Database Connection
db_client = AsyncIOMotorClient(MONGO_DB_URI)
db = db_client["vampire_userbot_db"]
users_collection = db["hosted_sessions"]

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


user_temp_data = {}


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
      f"{P_EMOJI_STAR} {to_small_font('welcome to premium userbot hosting bot')} {P_EMOJI_STAR}\n\n"
      f"{to_small_font('click the primary button below to host your bot safely & securely with mongodb support.')}"
  )

  if update.message:
    await update.message.reply_photo(
        photo=START_IMAGE_URL, caption=welcome_text, reply_markup=reply_markup
    )
  elif update.callback_query:
    query = update.callback_query
    await query.answer()
    try:
      await query.message.edit_caption(caption=welcome_text, reply_markup=reply_markup)
    except Exception:
      await query.edit_message_text(text=welcome_text, reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()

  if query.data == "click_to_host":
    user_temp_data[query.from_user.id] = {"step": "waiting_phone"}
    prompt_text = f"{to_small_font('📱 please send your telegram phone number with country code (e.g., +919876543210):')}"
    try:
      await query.message.edit_caption(caption=prompt_text)
    except Exception:
      await query.edit_message_text(text=prompt_text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
      client = TelegramClient(StringSession(), API_ID, API_HASH)
      await client.connect()
      sent_code = await client.send_code_request(phone)
      user_temp_data[user_id]["client"] = client
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
    client = user_temp_data[user_id]["client"]
    phone = user_temp_data[user_id]["phone"]
    phone_code_hash = user_temp_data[user_id]["phone_code_hash"]

    try:
      await client.sign_in(phone, otp, phone_code_hash=phone_code_hash)
      string_session = client.session.save()

      # Save session securely into MongoDB
      await users_collection.update_one(
          {"user_id": user_id},
          {"$set": {"session": string_session, "phone": phone}},
          upsert=True,
      )

      await update.message.reply_text(
          text=f"{P_EMOJI_FIRE} {to_small_font('login successful & saved in database!')}\n"
          f"{to_small_font('your string session is active and securely stored:')}\n\n"
          f"`{string_session}`"
      )
      user_temp_data.pop(user_id, None)
      await client.disconnect()

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
    client = user_temp_data[user_id]["client"]

    try:
      await client.sign_in(password=password)
      string_session = client.session.save()

      # Save 2-step session securely into MongoDB
      await users_collection.update_one(
          {"user_id": user_id},
          {
              "$set": {
                  "session": string_session,
                  "phone": user_temp_data[user_id]["phone"],
              }
          },
          upsert=True,
      )

      await update.message.reply_text(
          text=f"{P_EMOJI_FIRE} {to_small_font('2-step login successful & saved!')}\n"
          f"{to_small_font('your string session is securely stored in database:')}\n\n"
          f"`{string_session}`"
      )
      user_temp_data.pop(user_id, None)
      await client.disconnect()

    except Exception as e:
      await update.message.reply_text(
          text=f"{to_small_files if 'To_small_files' in globals() else to_small_font}(f'❌ wrong password: {str(e)}')\n"
          f"{to_small_font('please restart using /start')}"
      )
      user_temp_data.pop(user_id, None)


def main():
  app = ApplicationBuilder().token(BOT_TOKEN).build()
  app.add_handler(CommandHandler("start", start))
  app.add_handler(CallbackQueryHandler(button_handler))
  app.add_handler(
      MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
  )

  logger.info("bot started successfully with mongodb support...")
  print("bot started successfully...")

  app.run_polling()


if __name__ == "__main__":
  main()
    

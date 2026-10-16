
import os

# Telegram Bot
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

# Telegram API credentials
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "").strip()

# MongoDB
MONGO_DB_URI = os.environ.get("MONGO_DB_URI", "").strip()
MONGO_DB_NAME = "vampire_userbot_db"

# Owner
OWNER_USERNAME = os.environ.get(
    "OWNER_USERNAME", "YourUsername"
).strip().lstrip("@")

# Update channel and support group
UPDATE_CHANNEL = os.environ.get(
    "UPDATE_CHANNEL", "https://t.me/YourUpdateChannel"
).strip()

SUPPORT_GROUP = os.environ.get(
    "SUPPORT_GROUP", "https://t.me/YourSupportGroup"
).strip()

# Welcome/start image
START_IMAGE_URL = os.environ.get(
    "START_IMAGE_URL", "https://files.catbox.moe/3vlh9i.jpg"
).strip()


def validate_config():
    """Validate required deployment settings."""
    missing = []

    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")

    if API_ID <= 0:
        missing.append("API_ID")

    if not API_HASH:
        missing.append("API_HASH")

    if not MONGO_DB_URI:
        missing.append("MONGO_DB_URI")

    if missing:
        raise RuntimeError(
            "Missing or invalid Heroku Config Vars: "
            + ", ".join(missing)
        )

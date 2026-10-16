import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
API_ID = int(os.environ.get("API_ID", "12345678"))
API_HASH = os.environ.get("API_HASH", "your_api_hash_here")

# MongoDB Connection String
MONGO_DB_URI = os.environ.get("MONGO_DB_URI", "your_mongodb_connection_uri_here")

OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "YourUsername")
UPDATE_CHANNEL = os.environ.get("UPDATE_CHANNEL", "https://t.me/YourUpdateChannel")
SUPPORT_GROUP = os.environ.get("SUPPORT_GROUP", "https://t.me/YourSupportGroup")
START_IMAGE_URL = os.environ.get("START_IMAGE_URL", "https://files.catbox.moe/3vlh9i.jpg")

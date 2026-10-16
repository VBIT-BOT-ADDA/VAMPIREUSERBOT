import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
API_ID = int(os.environ.get("API_ID", "12345678"))
API_HASH = os.environ.get("API_HASH", "your_api_hash_here")

# Owner and Channels configuration
OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "YourUsername")
UPDATE_CHANNEL = os.environ.get(
    "UPDATE_CHANNEL", "https://t.me/YourUpdateChannel"
)
SUPPORT_GROUP = os.environ.get("SUPPORT_GROUP", "https://t.me/YourSupportGroup")

# Start Image URL for the welcome message
START_IMAGE_URL = os.environ.get(
    "START_IMAGE_URL", "https://envs.sh/Xxx.jpg"
)  # अपनी इमेज का लिंक यहाँ डालें

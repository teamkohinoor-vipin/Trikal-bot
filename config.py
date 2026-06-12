import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "KHRsupportBot")
REFERRAL_NOTIFICATION_GROUP = os.getenv("REFERRAL_NOTIFICATION_GROUP", "https://t.me/+tIwH7ctrekc1YThl")

OFFICIAL_GROUP_ID = int(os.getenv("OFFICIAL_GROUP_ID", "-1003490016636"))
OFFICIAL_GROUP_LINK = os.getenv("OFFICIAL_GROUP_LINK", "https://t.me/+OdNjwHMDXZtiNzA1")

CHANNEL_1_INVITE_LINK = os.getenv("CHANNEL_1_INVITE_LINK", "https://t.me/osnitInfo")
REQUIRED_CHANNEL_1_ID = int(os.getenv("REQUIRED_CHANNEL_1_ID", "-1003411597042"))
CHANNEL_2_INVITE_LINK = os.getenv("CHANNEL_2_INVITE_LINK", "https://t.me/+EnHwtMwircJkNzk1")
REQUIRED_CHANNEL_2_ID = int(os.getenv("REQUIRED_CHANNEL_2_ID", "-1003227457437"))

SEARCH_LOGGING_CHANNEL_ID = int(os.getenv("SEARCH_LOGGING_CHANNEL_ID", "-1003472844347"))

PHONE_API = os.getenv("PHONE_API", "https://your-api.com/search?number={num}")  # Change to your real API

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "phone_bot")

INITIAL_CREDITS = 3
REFERRAL_CREDITS = 5
NEW_USER_REFERRAL_CREDITS = 2
SEARCH_COST = 1
REDEEM_COOLDOWN_SECONDS = 3600
REFERRAL_PREMIUM_DAYS = 1
REFERRAL_TIER_1_COUNT = 15
REFERRAL_TIER_2_COUNT = 70

if not ADMIN_IDS:
    ADMIN_IDS = [8262107211]

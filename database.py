import time
import secrets
from datetime import datetime, timedelta
from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, INITIAL_CREDITS, REFERRAL_CREDITS, NEW_USER_REFERRAL_CREDITS, REFERRAL_PREMIUM_DAYS, REDEEM_COOLDOWN_SECONDS

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collections
users = db["users"]
redeem_codes = db["redeem_codes"]
banned_users = db["banned_users"]
admins = db["admins"]
protected_numbers = db["protected_numbers"]
free_mode = db["free_mode"]
global_free_mode = db["global_free_mode"]
daily_limit = db["daily_limit"]
auto_delete_time = db["auto_delete_time"]
maintenance_mode = db["maintenance_mode"]
user_history = db["user_history"]
settings = db["settings"]  # New collection for toggles

# Initialise config documents
def init_config():
    if free_mode.count_documents({}) == 0:
        free_mode.insert_one({"active": False})
    if global_free_mode.count_documents({}) == 0:
        global_free_mode.insert_one({"active": False})
    if daily_limit.count_documents({}) == 0:
        daily_limit.insert_one({"limit": 3})
    if auto_delete_time.count_documents({}) == 0:
        auto_delete_time.insert_one({"seconds": 60})
    if maintenance_mode.count_documents({}) == 0:
        maintenance_mode.insert_one({"active": False})
    # Public protection default ON
    if settings.count_documents({"_id": "public_protection"}) == 0:
        settings.insert_one({"_id": "public_protection", "enabled": True})

init_config()

# ---------- Settings functions ----------
def get_setting(key, default=None):
    doc = settings.find_one({"_id": key})
    return doc.get("value", default) if doc else default

def set_setting(key, value):
    settings.update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)

def is_public_protection_enabled():
    return get_setting("public_protection", True)

def set_public_protection_status(enabled):
    set_setting("public_protection", enabled)

# ---------- User functions ----------
def get_user(user_id):
    return users.find_one({"_id": user_id})

def create_user(user_id, referred_by=None):
    if get_user(user_id):
        return
    initial = NEW_USER_REFERRAL_CREDITS if referred_by else INITIAL_CREDITS
    user = {
        "_id": user_id,
        "credits": initial,
        "referred_by": referred_by,
        "referral_count": 0,
        "daily_searches": 0,
        "last_search_date": datetime.now().strftime("%Y-%m-%d"),
        "redeemed_codes": [],
        "last_redeem_timestamp": 0,
        "premium_until": None
    }
    users.insert_one(user)
    if referred_by:
        referrer = get_user(referred_by)
        if referrer:
            users.update_one({"_id": referred_by}, {"$inc": {"credits": REFERRAL_CREDITS, "referral_count": 1}})
            new_count = referrer.get("referral_count", 0) + 1
            if new_count == REFERRAL_TIER_1_COUNT:
                until = (datetime.now() + timedelta(days=REFERRAL_PREMIUM_DAYS)).isoformat()
                users.update_one({"_id": referred_by}, {"$set": {"premium_until": until}})
    return user

def update_credits(user_id, delta):
    users.update_one({"_id": user_id}, {"$inc": {"credits": delta}})

def set_premium_until(user_id, days=None):
    if days:
        until = (datetime.now() + timedelta(days=days)).isoformat()
        users.update_one({"_id": user_id}, {"$set": {"premium_until": until}})
    else:
        users.update_one({"_id": user_id}, {"$set": {"premium_until": None}})

def remove_premium(user_id):
    users.update_one({"_id": user_id}, {"$set": {"premium_until": None}})

def get_daily_data(user_id):
    user = get_user(user_id)
    if not user:
        return 0, datetime.now().strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    last = user.get("last_search_date", "")
    if last != today:
        users.update_one({"_id": user_id}, {"$set": {"daily_searches": 0, "last_search_date": today}})
        return 0, today
    return user.get("daily_searches", 0), today

def increment_daily_searches(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    user = get_user(user_id)
    if not user or user.get("last_search_date") != today:
        users.update_one({"_id": user_id}, {"$set": {"daily_searches": 1, "last_search_date": today}})
    else:
        users.update_one({"_id": user_id}, {"$inc": {"daily_searches": 1}})

def log_user_action(user_id, action, details):
    user_history.insert_one({
        "user_id": user_id,
        "timestamp": datetime.now(),
        "action": action,
        "details": details
    })

# ---------- Admin & settings ----------
def is_admin(user_id):
    from config import ADMIN_IDS
    if user_id in ADMIN_IDS:
        return True
    return admins.find_one({"_id": user_id}) is not None

def add_admin(user_id):
    if not is_admin(user_id):
        admins.insert_one({"_id": user_id})

def remove_admin(user_id):
    admins.delete_one({"_id": user_id})

def get_all_admins():
    from config import ADMIN_IDS
    return ADMIN_IDS + [doc["_id"] for doc in admins.find()]

def is_banned(user_id):
    return banned_users.find_one({"_id": user_id}) is not None

def ban_user(user_id):
    if not is_banned(user_id):
        banned_users.insert_one({"_id": user_id})

def unban_user(user_id):
    banned_users.delete_one({"_id": user_id})

def set_free_mode(active):
    free_mode.update_one({}, {"$set": {"active": active}})

def is_free_mode_active():
    return free_mode.find_one().get("active", False)

def set_global_free_mode(active):
    global_free_mode.update_one({}, {"$set": {"active": active}})

def is_global_free_mode_active():
    return global_free_mode.find_one().get("active", False)

def set_maintenance_mode(active):
    maintenance_mode.update_one({}, {"$set": {"active": active}})

def is_maintenance_mode_active():
    return maintenance_mode.find_one().get("active", False)

def get_daily_free_limit():
    doc = daily_limit.find_one()
    return doc.get("limit", 3) if doc else 3

def set_daily_free_limit(limit):
    daily_limit.update_one({}, {"$set": {"limit": limit}})

def get_auto_delete_time():
    doc = auto_delete_time.find_one()
    return doc.get("seconds", 60) if doc else 60

def set_auto_delete_time(seconds):
    auto_delete_time.update_one({}, {"$set": {"seconds": seconds}})

# ---------- Number protection (Phone) with User Info ----------
def is_number_protected(number):
    return protected_numbers.find_one({"_id": number}) is not None

def protect_number(number, user_id, message=None, first_name=None, username=None):
    """
    Protect a number for a user. Stores user_id, first_name (display name), 
    telegram username (optional), timestamp, and optional custom message.
    Returns True if protected, False if already protected.
    """
    if is_number_protected(number):
        return False
    
    # Use provided first_name, else fallback to "Unknown"
    display_name = first_name or "Unknown"
    # Use provided username (telegram @) or fallback to None
    tg_username = username or None
    
    protected_numbers.insert_one({
        "_id": number,
        "user_id": user_id,
        "display_name": display_name,
        "username": tg_username,
        "protected_at": datetime.now(),
        "message": message or "❌ No data found for this number."
    })
    log_user_action(user_id, "Protected Number", number)
    return True

def unprotect_number(number, user_id=None):
    """
    Unprotect a number. If user_id is provided, only allow if the protector is same user or admin.
    Returns True if deleted, False if not found or not authorized.
    """
    doc = protected_numbers.find_one({"_id": number})
    if not doc:
        return False
    # If user_id provided, check if user is the protector or an admin
    if user_id:
        # Check if user is admin (from config or admins collection)
        if is_admin(user_id):
            # Admin can delete any
            pass
        elif doc.get("user_id") != user_id:
            return False  # Not authorized
    result = protected_numbers.delete_one({"_id": number})
    if result.deleted_count > 0:
        log_user_action(user_id or "system", "Unprotected Number", number)
        return True
    return False

def get_all_protected_numbers():
    """Returns list of all protected numbers (old format, without user info) - kept for backward compatibility."""
    return list(protected_numbers.find())

def get_all_protected_numbers_with_user_info():
    """Returns list of all protected numbers with user info (user_id, display_name, username, timestamp)."""
    return list(protected_numbers.find())

def get_user_protected_numbers(user_id):
    """Returns list of numbers protected by a specific user."""
    return list(protected_numbers.find({"user_id": user_id}))

# ---------- Redeem codes ----------
def generate_redeem_code(credits, uses, created_by):
    code = secrets.token_hex(4).upper()
    redeem_codes.insert_one({
        "_id": code,
        "credits": credits,
        "uses_left": uses,
        "created_by": created_by,
        "created_at": datetime.now()
    })
    return code

def use_redeem_code(code, user_id):
    doc = redeem_codes.find_one({"_id": code})
    if not doc or doc["uses_left"] <= 0:
        return None
    user = get_user(user_id)
    if code in user.get("redeemed_codes", []):
        return None
    last_ts = user.get("last_redeem_timestamp", 0)
    if time.time() - last_ts < REDEEM_COOLDOWN_SECONDS:
        return None
    redeem_codes.update_one({"_id": code}, {"$inc": {"uses_left": -1}})
    users.update_one(
        {"_id": user_id},
        {"$inc": {"credits": doc["credits"]}, "$push": {"redeemed_codes": code}, "$set": {"last_redeem_timestamp": time.time()}}
    )
    return doc["credits"]

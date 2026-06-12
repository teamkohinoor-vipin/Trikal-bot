from pymongo import MongoClient
from datetime import datetime, timedelta
from config import MONGO_URI, DB_NAME, INITIAL_CREDITS, REFERRAL_CREDITS, NEW_USER_REFERRAL_CREDITS, REFERRAL_PREMIUM_DAYS, REDEEM_COOLDOWN_SECONDS

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

users = db["users"]
redeem_codes = db["redeem_codes"]
banned_users = db["banned_users"]
admins = db["admins"]
protected_numbers = db["protected_numbers"]
protected_aadhaar = db["protected_aadhaar"]
free_mode = db["free_mode"]
user_history = db["user_history"]
premium_features = db["premium_features"]
premium_users = db["premium_users"]   # old style

def init_config():
    if free_mode.count_documents({}) == 0:
        free_mode.insert_one({"active": False})
init_config()

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

def log_user_action(user_id, action, details):
    user_history.insert_one({
        "user_id": user_id,
        "timestamp": datetime.now(),
        "action": action,
        "details": details
    })

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

def is_number_protected(number):
    return protected_numbers.find_one({"_id": number}) is not None

def protect_number(number, admin_id, message=None):
    if is_number_protected(number):
        return False
    protected_numbers.insert_one({
        "_id": number,
        "protected_by": admin_id,
        "protected_at": datetime.now(),
        "message": message or "❌ No data found for this number."
    })
    return True

def unprotect_number(number):
    result = protected_numbers.delete_one({"_id": number})
    return result.deleted_count > 0

def get_all_protected_numbers():
    return list(protected_numbers.find())

def is_aadhaar_protected(aadhaar):
    return protected_aadhaar.find_one({"_id": aadhaar}) is not None

def protect_aadhaar(aadhaar, admin_id, message=None):
    if is_aadhaar_protected(aadhaar):
        return False
    protected_aadhaar.insert_one({
        "_id": aadhaar,
        "protected_by": admin_id,
        "protected_at": datetime.now(),
        "message": message or "❌ No data found for this Aadhaar."
    })
    return True

def unprotect_aadhaar(aadhaar):
    result = protected_aadhaar.delete_one({"_id": aadhaar})
    return result.deleted_count > 0

def get_all_protected_aadhaar():
    return list(protected_aadhaar.find())

def generate_redeem_code(credits, uses, created_by):
    import secrets
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
    import time
    last_ts = user.get("last_redeem_timestamp", 0)
    if time.time() - last_ts < REDEEM_COOLDOWN_SECONDS:
        return None
    redeem_codes.update_one({"_id": code}, {"$inc": {"uses_left": -1}})
    users.update_one(
        {"_id": user_id},
        {"$inc": {"credits": doc["credits"]}, "$push": {"redeemed_codes": code}, "$set": {"last_redeem_timestamp": time.time()}}
    )
    return doc["credits"]

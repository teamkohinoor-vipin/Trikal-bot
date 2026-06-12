import logging
import requests
import secrets
import time
import re
import html
from io import BytesIO
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

from config import *
from database import *
from utils import *

logger = logging.getLogger(__name__)

# ========== Helper functions ==========
def is_owner(user_id):
    return user_id in ADMIN_IDS

def is_admin(user_id):
    return database.is_admin(user_id)  # from database

def is_premium(user_id):
    # old style premium users
    if premium_users.find_one({"_id": user_id}):
        return True
    user = get_user(user_id)
    if user and user.get("premium_until"):
        try:
            until = datetime.fromisoformat(user["premium_until"])
            if datetime.now() < until:
                return True
        except:
            pass
    return False

def can_use_daily_free(user_id):
    # No daily limit in this version – you can add if needed
    return True

def deduct_credits(user_id, chat_id=None):
    if chat_id == OFFICIAL_GROUP_ID:
        return True
    if is_free_mode_active():
        return True
    if is_admin(user_id) or is_premium(user_id):
        return True
    user = get_user(user_id)
    if not user:
        return False
    if user.get("referral_count", 0) >= REFERRAL_TIER_2_COUNT:
        return True
    if user.get("credits", 0) >= SEARCH_COST:
        update_credits(user_id, -SEARCH_COST)
        return True
    return False

def get_info_footer(user_id, chat_id=None):
    if chat_id == OFFICIAL_GROUP_ID:
        return "\n\n🚀 <b>Official Group:</b> No credits used"
    if is_free_mode_active():
        return "\n\n✨ <b>Free Mode ACTIVE!</b>"
    user = get_user(user_id)
    credits = user["credits"] if user else 0
    if is_admin(user_id):
        return f"\n\n💰 Credits: <b>{credits}</b> | 👑 Admin"
    if is_premium(user_id):
        return f"\n\n💰 Credits: <b>{credits}</b> | ⭐ Premium"
    return f"\n\n💰 Credits: <b>{credits}</b>"

# ========== Channel subscription ==========
async def check_membership(user_id, channel_id, bot):
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

async def is_subscribed(user_id, bot):
    return (await check_membership(user_id, REQUIRED_CHANNEL_1_ID, bot) and
            await check_membership(user_id, REQUIRED_CHANNEL_2_ID, bot))

async def send_join_message(update, context):
    kb = [
        [InlineKeyboardButton("➡️ Join Channel 1", url=CHANNEL_1_INVITE_LINK)],
        [InlineKeyboardButton("➡️ Join Channel 2", url=CHANNEL_2_INVITE_LINK)],
        [InlineKeyboardButton("✅ Verify", callback_data="verify_join")],
    ]
    await update.message.reply_text(
        "❌ <b>You must join both channels to use this bot!</b>\n\nJoin and click Verify.",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.HTML,
    )

# ========== Logging ==========
async def log_search_to_channel(context, user, search_type, query, result="", success=True):
    try:
        uid = user.id
        name = user.first_name or "Unknown"
        username = f"@{user.username}" if user.username else "No username"
        link = f"tg://user?id={uid}"
        status = "✅" if success else "❌"
        msg = f"{status} <b>Search Log</b>\n\n<b>👤 User:</b> <a href='{link}'>{name}</a>\n<b>🆔 ID:</b> <code>{uid}</code>\n<b>🔍 Type:</b> {search_type}\n<b>📝 Query:</b> <code>{query}</code>\n<b>⏰ Time:</b> {datetime.now()}\n"
        if result:
            msg += f"<b>📄 Result:</b> {result[:300]}...\n"
        await context.bot.send_message(chat_id=SEARCH_LOGGING_CHANNEL_ID, text=msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Log error: {e}")

# ========== Phone lookup ==========
async def perform_phone_lookup(update, context, phone, raw):
    user = update.effective_user
    chat = update.effective_chat

    # Protection check
    if is_number_protected(phone):
        msg = get_protected_numbers().find_one({"_id": phone})["message"]
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]))
        await log_search_to_channel(context, user, "Phone", raw, "Protected", False)
        return

    # Credit deduction
    if chat.type == 'private' and not await deduct_credits(user.id, chat.id):
        await update.message.reply_text(f"❌ Insufficient credits! You need {SEARCH_COST} credit.\nUse referrals to earn more.")
        return

    msg = await update.message.reply_text("🔍 Searching...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]))
    records = fetch_phone_info(phone)
    if not records:
        footer = get_info_footer(user.id, chat.id)
        await msg.edit_text(f"❌ No data found for {phone}.\n{footer}", parse_mode=ParseMode.HTML)
        await log_search_to_channel(context, user, "Phone", raw, "No data", False)
        return

    # Build result
    result = f"🔍 <b>Phone Lookup Results for {phone}</b>\n\n"
    for i, rec in enumerate(records[:10], 1):
        result += f"✅ <b>Result {i}:</b>\n\n"
        fields = [
            ('name', '👤 Name'),
            ('father_name', '👨‍👦 Father'),
            ('address', '📍 Address'),
            ('mobile', '📱 Mobile'),
            ('circle', '📡 Circle'),
            ('id', '🆔 ID')
        ]
        for key, label in fields:
            val = rec.get(key, '')
            if val and str(val).lower() not in ['', 'n/a', 'null']:
                if key == 'address':
                    val = format_address(val)
                result += f"<b>{label}:</b> {val}\n"
        result += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    result += "\n💞<b>Developer: @ll_VIPIN_ll</b>"
    result += get_info_footer(user.id, chat.id)

    context.user_data['last_search_result'] = result
    context.user_data['last_search_query'] = phone
    context.user_data['last_search_type'] = 'phone'

    keyboard = [
        [InlineKeyboardButton("📥 Download", callback_data="download_info")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")],
    ]
    await msg.edit_text(result, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    await log_search_to_channel(context, user, "Phone", raw, result[:300], True)

# ========== Admin panel markup ==========
def get_admin_panel_markup():
    free_status = "🟢 ON" if is_free_mode_active() else "🔴 OFF"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Credits", callback_data="admin_add_credits"), InlineKeyboardButton("➖ Remove Credits", callback_data="admin_remove_credits")],
        [InlineKeyboardButton("➕ Add Premium", callback_data="admin_add_premium"), InlineKeyboardButton("➖ Remove Premium", callback_data="admin_remove_premium")],
        [InlineKeyboardButton("👥 All Users", callback_data="admin_all_users"), InlineKeyboardButton("📝 User History", callback_data="admin_user_history")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("⭐ Premium List", callback_data="admin_premium_list")],
        [InlineKeyboardButton("🚫 Block User", callback_data="admin_block_user"), InlineKeyboardButton("✅ Unblock User", callback_data="admin_unblock_user")],
        [InlineKeyboardButton("📋 Blocked List", callback_data="admin_blocked_list"), InlineKeyboardButton("📊 Bot Stats", callback_data="admin_bot_stats")],
        [InlineKeyboardButton("🎁 Generate Code", callback_data="admin_gen_code"), InlineKeyboardButton(f"🎯 Free Mode ({free_status})", callback_data="admin_toggle_free")],
        [InlineKeyboardButton("📈 Referral Stats", callback_data="admin_referral_stats")],
        [InlineKeyboardButton("🛡️ Number Protection", callback_data="admin_number_protection")],
        [InlineKeyboardButton("🆔 Aadhaar Protection", callback_data="admin_aadhaar_protection")],
        [InlineKeyboardButton("👨‍💼 Admin Management", callback_data="admin_management")],
        [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")],
    ])

# ========== Command handlers ==========
async def start(update: Update, context):
    user = update.effective_user
    chat = update.effective_chat

    if is_banned(user.id):
        return
    if chat.type != 'private' and chat.id != OFFICIAL_GROUP_ID:
        await update.message.reply_text("❌ This bot only works in private chat or official group.")
        return
    if chat.type == 'private' and not await is_subscribed(user.id, context.bot):
        await send_join_message(update, context)
        return

    if not get_user(user.id):
        referrer_id = None
        if context.args and context.args[0].isdigit():
            rid = int(context.args[0])
            if rid != user.id and get_user(rid):
                referrer_id = rid
        create_user(user.id, referrer_id)
        if referrer_id:
            referrer = get_user(referrer_id)
            if referrer:
                await context.bot.send_message(chat_id=referrer_id,
                    text=f"🎉 New referral! {user.first_name} joined.\nYou received {REFERRAL_CREDITS} credits.\nTotal referrals: {referrer['referral_count']}")
    daily_limit = 3  # if you want to show, can fetch from config
    text = f"<b>🎉 Welcome, {user.first_name}!</b>\n\n🔍 India Number Lookup\n💰 {daily_limit} free searches daily (if implemented)\n🔗 Referrals: 5 credits each, premium at {REFERRAL_TIER_1_COUNT}, unlimited at {REFERRAL_TIER_2_COUNT}\n\nUse buttons below."
    keyboard = [
        [InlineKeyboardButton("India Number 🇮🇳", callback_data="search_phone")],
        [InlineKeyboardButton("Check Credit 💰", callback_data="check_credit"), InlineKeyboardButton("Get Referral Link 🔗", callback_data="get_referral")],
        [InlineKeyboardButton("Redeem Code 🎁", callback_data="redeem_code"), InlineKeyboardButton("Buy Premium & Credits 💎", callback_data="buy_premium_main")],
        [InlineKeyboardButton("Support 👨‍💻", callback_data="support"), InlineKeyboardButton("Official Group 🚀", url=OFFICIAL_GROUP_LINK)],
        [InlineKeyboardButton("🔒 Privacy Policy", callback_data="privacy_policy")],
    ]
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def phone_command(update: Update, context):
    if not context.args:
        await update.message.reply_text("Usage: /phone 9876543210")
        return
    raw = context.args[0].strip()
    num = normalize_phone_number(raw)
    if not num:
        await update.message.reply_text("❌ Invalid Indian phone number.")
        return
    await perform_phone_lookup(update, context, num, raw)

async def redeem_command(update: Update, context):
    if not context.args:
        context.user_data['awaiting_redeem'] = True
        await update.message.reply_text("🎁 Send me your redeem code.")
        return
    code = context.args[0].strip().upper()
    credits = use_redeem_code(code, update.effective_user.id)
    if credits is None:
        await update.message.reply_text("❌ Invalid or already used code.")
    else:
        await update.message.reply_text(f"✅ {credits} credits added!")

# ========== Button handler (main, admin, etc.) ==========
async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    # Main menu actions
    if data == "back_to_main":
        await query.edit_message_text("Main menu", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("India Number 🇮🇳", callback_data="search_phone")],
            [InlineKeyboardButton("Check Credit 💰", callback_data="check_credit"), InlineKeyboardButton("Get Referral Link 🔗", callback_data="get_referral")],
            [InlineKeyboardButton("Redeem Code 🎁", callback_data="redeem_code"), InlineKeyboardButton("Buy Premium & Credits 💎", callback_data="buy_premium_main")],
            [InlineKeyboardButton("Support 👨‍💻", callback_data="support"), InlineKeyboardButton("Official Group 🚀", url=OFFICIAL_GROUP_LINK)],
            [InlineKeyboardButton("🔒 Privacy Policy", callback_data="privacy_policy")],
        ] + ([ [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")] ] if is_admin(user.id) else [])), parse_mode=ParseMode.HTML)
        return

    if data == "search_phone":
        context.user_data['awaiting_search'] = True
        await query.edit_message_text("🔍 Send 10-digit Indian mobile number:")
        return

    if data == "check_credit":
        u = get_user(user.id)
        credits = u["credits"] if u else 0
        refc = u["referral_count"] if u else 0
        msg = f"💰 Credits: {credits}\n📊 Referrals: {refc}"
        if refc >= REFERRAL_TIER_2_COUNT:
            msg += "\n♾️ Unlimited credits (Tier 2)"
        elif refc >= REFERRAL_TIER_1_COUNT:
            msg += "\n⭐ Premium user (1 day)"
        else:
            msg += f"\n🎯 {REFERRAL_TIER_1_COUNT - refc} referrals to premium"
        await query.edit_message_text(msg)
        return

    if data == "get_referral":
        botu = (await context.bot.get_me()).username
        link = f"https://t.me/{botu}?start={user.id}"
        await query.edit_message_text(f"🔗 Your referral link:\n<code>{link}</code>\n\nEarn 5 credits per referral!", parse_mode=ParseMode.HTML)
        return

    if data == "redeem_code":
        context.user_data['awaiting_redeem'] = True
        await query.edit_message_text("🎁 Send your redeem code:")
        return

    if data == "buy_premium_main":
        await query.edit_message_text("💎 Choose an option:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Premium Plans", callback_data="buy_premium")],
            [InlineKeyboardButton("💰 Credit Packages", callback_data="buy_credits")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")],
        ]))
        return

    if data == "buy_premium":
        await query.edit_message_text("⭐ Premium Plans:\n1 Day - ₹35\n1 Week - ₹79\n1 Month - ₹149\nLifetime - ₹999\n\nContact @ll_VIPIN_ll to purchase.")
        return

    if data == "buy_credits":
        await query.edit_message_text("💰 Credit Packages:\n10 - ₹15\n25 - ₹20\n50 - ₹49\n100 - ₹79\n250 - ₹149\n\nContact @ll_VIPIN_ll to purchase.")
        return

    if data == "support":
        await query.edit_message_text(f"👨‍💻 Contact @{SUPPORT_USERNAME} for support.")
        return

    if data == "privacy_policy":
        await query.edit_message_text("🔒 We only store user credits and referral counts. No search data is stored.")
        return

    if data == "verify_join":
        if await is_subscribed(user.id, context.bot):
            await query.edit_message_text("✅ Verified! You can use the bot.")
            if not get_user(user.id):
                create_user(user.id)
        else:
            await query.edit_message_text("❌ You haven't joined both channels.")
        return

    if data == "download_info":
        if 'last_search_result' not in context.user_data:
            await query.answer("No result to download", show_alert=True)
            return
        botu = (await context.bot.get_me()).username
        file = create_search_result_file(context.user_data['last_search_result'], context.user_data['last_search_query'], context.user_data['last_search_type'], botu)
        await context.bot.send_document(chat_id=query.message.chat_id, document=file, caption="✅ Download complete.")
        await query.answer("File sent")
        return

    # Admin panel
    if data == "admin_panel":
        if not is_admin(user.id):
            await query.answer("Unauthorized", show_alert=True)
            return
        await query.edit_message_text("👑 Admin Panel", reply_markup=get_admin_panel_markup(), parse_mode=ParseMode.HTML)
        return

    # Admin actions (simplified – you can expand as needed)
    if data.startswith("admin_"):
        if not is_admin(user.id):
            await query.answer("Unauthorized", show_alert=True)
            return
        # We'll implement a few essential ones; the rest you can add from your old code.
        if data == "admin_add_credits":
            context.user_data['admin_action'] = 'add_credits'
            await query.edit_message_text("Send: user_id credits")
        elif data == "admin_remove_credits":
            context.user_data['admin_action'] = 'remove_credits'
            await query.edit_message_text("Send: user_id credits")
        elif data == "admin_add_premium":
            context.user_data['admin_action'] = 'add_premium'
            await query.edit_message_text("Send: user_id days (or leave blank for permanent)")
        elif data == "admin_remove_premium":
            context.user_data['admin_action'] = 'remove_premium'
            await query.edit_message_text("Send: user_id")
        elif data == "admin_block_user":
            context.user_data['admin_action'] = 'block_user'
            await query.edit_message_text("Send: user_id")
        elif data == "admin_unblock_user":
            context.user_data['admin_action'] = 'unblock_user'
            await query.edit_message_text("Send: user_id")
        elif data == "admin_broadcast":
            context.user_data['admin_action'] = 'broadcast'
            await query.edit_message_text("Send broadcast message")
        elif data == "admin_toggle_free":
            cur = is_free_mode_active()
            set_free_mode(not cur)
            await query.edit_message_text(f"Free mode is now {'ON' if not cur else 'OFF'}")
        elif data == "admin_bot_stats":
            total = users.count_documents({})
            premium_cnt = premium_users.count_documents({}) + users.count_documents({"premium_until": {"$ne": None}})
            banned_cnt = banned_users.count_documents({})
            await query.edit_message_text(f"📊 Stats:\n👥 Users: {total}\n⭐ Premium: {premium_cnt}\n🚫 Banned: {banned_cnt}")
        elif data == "admin_number_protection":
            await query.edit_message_text("Number Protection", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Protect Number", callback_data="admin_protect_number")],
                [InlineKeyboardButton("➖ Unprotect Number", callback_data="admin_unprotect_number")],
                [InlineKeyboardButton("📋 Protected List", callback_data="admin_protected_list")],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")],
            ]))
        elif data == "admin_protect_number":
            context.user_data['admin_action'] = 'protect_number'
            await query.edit_message_text("Send number and optional message:\n`9876543210 This is private`")
        elif data == "admin_unprotect_number":
            context.user_data['admin_action'] = 'unprotect_number'
            await query.edit_message_text("Send number to unprotect")
        elif data == "admin_protected_list":
            prot = get_all_protected_numbers()
            if not prot:
                await query.edit_message_text("No protected numbers")
                return
            msg = "🛡️ Protected Numbers:\n"
            for p in prot[:20]:
                msg += f"<code>{p['_id']}</code> - {p.get('message', '')[:30]}\n"
            await query.edit_message_text(msg, parse_mode=ParseMode.HTML)
        else:
            await query.edit_message_text("Not implemented yet")

# ========== Message handler ==========
async def handle_message(update: Update, context):
    user = update.effective_user
    text = update.message.text.strip()
    chat = update.effective_chat

    if is_banned(user.id):
        return
    if chat.type != 'private' and chat.id != OFFICIAL_GROUP_ID:
        await update.message.reply_text("❌ Not allowed")
        return
    if chat.type == 'private' and not await is_subscribed(user.id, context.bot):
        await send_join_message(update, context)
        return

    # Admin action
    if context.user_data.get('admin_action'):
        act = context.user_data.pop('admin_action')
        try:
            if act == 'add_credits':
                parts = text.split()
                uid = int(parts[0])
                amt = int(parts[1])
                update_credits(uid, amt)
                await update.message.reply_text(f"Added {amt} credits to {uid}")
            elif act == 'remove_credits':
                parts = text.split()
                uid = int(parts[0])
                amt = int(parts[1])
                update_credits(uid, -amt)
                await update.message.reply_text(f"Removed {amt} credits from {uid}")
            elif act == 'add_premium':
                parts = text.split()
                uid = int(parts[0])
                days = int(parts[1]) if len(parts) > 1 else None
                set_premium_until(uid, days)
                await update.message.reply_text(f"Premium added to {uid}{' for '+str(days)+' days' if days else ' permanently'}")
            elif act == 'remove_premium':
                uid = int(text)
                remove_premium(uid)
                await update.message.reply_text(f"Premium removed from {uid}")
            elif act == 'block_user':
                uid = int(text)
                ban_user(uid)
                await update.message.reply_text(f"User {uid} blocked")
            elif act == 'unblock_user':
                uid = int(text)
                unban_user(uid)
                await update.message.reply_text(f"User {uid} unblocked")
            elif act == 'broadcast':
                success, fail = 0, 0
                for u in users.find():
                    try:
                        await context.bot.send_message(chat_id=u["_id"], text=text, parse_mode=ParseMode.HTML)
                        success += 1
                    except:
                        fail += 1
                await update.message.reply_text(f"Broadcast done: {success} sent, {fail} failed")
            elif act == 'protect_number':
                parts = text.split(maxsplit=1)
                num = parts[0]
                msg = parts[1] if len(parts) > 1 else None
                if protect_number(num, user.id, msg):
                    await update.message.reply_text(f"Number {num} protected")
                else:
                    await update.message.reply_text("Already protected")
            elif act == 'unprotect_number':
                num = text
                if unprotect_number(num):
                    await update.message.reply_text(f"Number {num} unprotected")
                else:
                    await update.message.reply_text("Not protected")
            else:
                await update.message.reply_text("Unknown action")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
        return

    # Redeem code waiting
    if context.user_data.get('awaiting_redeem'):
        context.user_data['awaiting_redeem'] = False
        code = text.upper()
        credits = use_redeem_code(code, user.id)
        if credits is None:
            await update.message.reply_text("❌ Invalid or used code")
        else:
            await update.message.reply_text(f"✅ {credits} credits added!")
        return

    # Awaiting phone number
    if context.user_data.get('awaiting_search'):
        context.user_data['awaiting_search'] = False
        num = normalize_phone_number(text)
        if not num:
            await update.message.reply_text("❌ Invalid number")
        else:
            await perform_phone_lookup(update, context, num, text)
        return

    # Direct number
    num = normalize_phone_number(text)
    if num:
        await perform_phone_lookup(update, context, num, text)

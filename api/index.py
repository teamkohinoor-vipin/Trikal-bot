import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from bot import *
from config import BOT_TOKEN

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Register all handlers from bot.py
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("phone", phone_command))
dispatcher.add_handler(CommandHandler("redeem", redeem_command))
dispatcher.add_handler(CommandHandler("admin", admin_command))
dispatcher.add_handler(CommandHandler("addadmin", addadmin_command))
dispatcher.add_handler(CommandHandler("removeadmin", removeadmin_command))
dispatcher.add_handler(CommandHandler("admins", admins_command))
dispatcher.add_handler(CommandHandler("gencode", gencode))
dispatcher.add_handler(CommandHandler("history", history_command))
dispatcher.add_handler(CommandHandler("protect", protect_command))
dispatcher.add_handler(CommandHandler("unprotect", unprotect_command))
dispatcher.add_handler(CommandHandler("protected", protected_command))
dispatcher.add_handler(CallbackQueryHandler(button_handler))
dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.route("/", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return "OK", 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return "ERROR", 500

# For local testing
if __name__ == "__main__":
    app.run(port=5000)

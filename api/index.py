import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request
from telegram import Update, Bot, ParseMode
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from bot import *
from config import BOT_TOKEN

app = Flask(__name__)

if not BOT_TOKEN:
    raise Exception("BOT_TOKEN environment variable not set")

bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, None, workers=1)

# Register all handlers with run_async=True
dispatcher.add_handler(CommandHandler("start", start, run_async=True))
dispatcher.add_handler(CommandHandler("help", help_command, run_async=True))
dispatcher.add_handler(CommandHandler("phone", phone_command, run_async=True))
dispatcher.add_handler(CommandHandler("redeem", redeem_command, run_async=True))
dispatcher.add_handler(CommandHandler("admin", admin_command, run_async=True))
dispatcher.add_handler(CommandHandler("addadmin", addadmin_command, run_async=True))
dispatcher.add_handler(CommandHandler("removeadmin", removeadmin_command, run_async=True))
dispatcher.add_handler(CommandHandler("admins", admins_command, run_async=True))
dispatcher.add_handler(CommandHandler("gencode", gencode, run_async=True))
dispatcher.add_handler(CommandHandler("history", history_command, run_async=True))
dispatcher.add_handler(CommandHandler("protect", protect_command, run_async=True))
dispatcher.add_handler(CommandHandler("unprotect", unprotect_command, run_async=True))
dispatcher.add_handler(CommandHandler("protected", protected_command, run_async=True))
dispatcher.add_handler(CallbackQueryHandler(button_handler, run_async=True))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message, run_async=True))

@app.route("/", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return "OK", 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return "ERROR", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

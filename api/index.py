import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, JobQueue
from bot import *
from config import BOT_TOKEN

app = Flask(__name__)

if not BOT_TOKEN:
    raise Exception("BOT_TOKEN missing")

bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, None, workers=1)

# 🔥 JobQueue for auto-delete
job_queue = JobQueue()
job_queue.set_dispatcher(dispatcher)
dispatcher.job_queue = job_queue
job_queue.start()

# Register all handlers
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
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "Bot is running! Webhook is active.", 200
    try:
        json_data = request.get_json(force=True)
        if not json_data:
            return "No JSON received", 400
        update = Update.de_json(json_data, bot)
        dispatcher.process_update(update)
        return "OK", 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return "ERROR", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

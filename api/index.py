import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler
import json

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN missing")

bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, None, workers=1)

async def start(update, context):
    print("✅ start handler called")
    try:
        user = update.effective_user
        print(f"User ID: {user.id}")
        await update.message.reply_text("pong")
        print("✅ reply sent")
    except Exception as e:
        print(f"Error: {e}")

# Use run_async=True instead of decorator
dispatcher.add_handler(CommandHandler("start", start, run_async=True))

@app.route("/", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📨 Received:", data.get("message", {}).get("text"))
        update = Update.de_json(data, bot)
        dispatcher.process_update(update)
        return "OK", 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return "ERROR", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

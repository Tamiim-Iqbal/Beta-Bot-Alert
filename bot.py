
import json
import os
import requests
import asyncio
import nest_asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ========== CONFIG ==========
ALERT_FILE = 'prices.json'
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PING_URL = os.getenv("PING_URL")
ALLOWED_USERS = {5817239686, 5274796002}

SYMBOL_MAP = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "bnb": "binancecoin",
    "sol": "solana",
    "ada": "cardano",
    "doge": "dogecoin",
    "xrp": "ripple",
    "meme": "meme",
    "moxie": "moxie",
    "degen": "degen-base",
}

# ========== UTILITIES ==========
def load_alerts():
    if os.path.exists(ALERT_FILE):
        with open(ALERT_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_alerts(data):
    with open(ALERT_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ========== COMMAND HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        return await update.message.reply_text("❌ Not authorized.")
    await update.message.reply_text("Welcome to Crypto Alert Bot (Beta). Use /add to set an alert.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/add COIN PRICE [above|below]\n/list\n/remove 1\n/price COIN\n/coin")

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Supported coins: " + ", ".join(SYMBOL_MAP.keys()))

async def add_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if update.effective_user.id not in ALLOWED_USERS:
        return await update.message.reply_text("❌ Not authorized.")

    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /add COIN PRICE [above|below]")

    alerts = load_alerts()
    if user_id in alerts and len(alerts[user_id]) >= 1:
        return await update.message.reply_text("❗ You can only have 1 alert in beta.")

    symbol = context.args[0].lower()
    coin = SYMBOL_MAP.get(symbol)
    if not coin:
        return await update.message.reply_text("❗ Unsupported coin.")

    try:
        price = float(context.args[1])
    except ValueError:
        return await update.message.reply_text("❗ Invalid price.")

    direction = "above"
    if len(context.args) > 2 and context.args[2] in ["above", "below"]:
        direction = context.args[2]

    alerts[user_id] = [{"coin": coin, "symbol": symbol, "price": price, "direction": direction}]
    save_alerts(alerts)
    await update.message.reply_text(f"✅ Alert set for {symbol.upper()} {direction} ${price}")

async def list_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    alerts = load_alerts().get(user_id, [])
    if not alerts:
        return await update.message.reply_text("No active alerts.")
    await update.message.reply_text("\n".join([f"{a['symbol'].upper()} {a['direction']} ${a['price']}" for a in alerts]))

async def remove_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    alerts = load_alerts()
    if user_id in alerts:
        alerts.pop(user_id)
        save_alerts(alerts)
        await update.message.reply_text("✅ Alert removed.")
    else:
        await update.message.reply_text("No alert to remove.")

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbols = [s.lower() for s in context.args if s.lower() in SYMBOL_MAP]
    ids = [SYMBOL_MAP[s] for s in symbols]
    try:
        res = requests.get("https://api.coingecko.com/api/v3/simple/price", params={"ids": ",".join(ids), "vs_currencies": "usd"}).json()
        msg = "\n".join([f"{s.upper()}: ${res[SYMBOL_MAP[s]]['usd']:.4f}" for s in symbols])
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text("Failed to fetch prices.")

async def check_prices(context: ContextTypes.DEFAULT_TYPE):
    alerts = load_alerts()
    if not alerts:
        return

    coins = list({a['coin'] for lst in alerts.values() for a in lst})
    try:
        res = requests.get("https://api.coingecko.com/api/v3/simple/price", params={"ids": ",".join(coins), "vs_currencies": "usd"}).json()
    except Exception as e:
        print("Price fetch failed", e)
        return

    for user_id, alert_list in list(alerts.items()):
        to_remove = []
        for i, alert in enumerate(alert_list):
            price = res.get(alert['coin'], {}).get("usd")
            if price is None:
                continue
            if (alert['direction'] == "above" and price >= alert['price']) or \
               (alert['direction'] == "below" and price <= alert['price']):
                await context.bot.send_message(chat_id=int(user_id), text=f"🚨 {alert['symbol'].upper()} is ${price:.4f}, triggered alert {alert['direction']} ${alert['price']}")
                to_remove.append(i)

        for idx in reversed(to_remove):
            alert_list.pop(idx)
        if alert_list:
            alerts[user_id] = alert_list
        else:
            alerts.pop(user_id)

    save_alerts(alerts)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Unknown command. Use /help")

# ========== SELF-PINGING ==========
async def ping_self():
    while True:
        try:
            if PING_URL:
                requests.get(PING_URL)
                print("🔁 Pinged self")
        except Exception as e:
            print("Ping failed", e)
        await asyncio.sleep(300)  # every 5 minutes

# ========== SIMPLE SERVER ==========
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Pong")

def run_ping_server():
    def server_thread():
        server = HTTPServer(('0.0.0.0', 10000), PingHandler)
        server.serve_forever()
    Thread(target=server_thread, daemon=True).start()

async def main():
    run_ping_server()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("coin", coin_command))
    app.add_handler(CommandHandler("add", add_alert))
    app.add_handler(CommandHandler("list", list_alerts))
    app.add_handler(CommandHandler("remove", remove_alert))
    app.add_handler(CommandHandler("price", get_price))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    app.job_queue.run_repeating(check_prices, interval=15, first=5)
    asyncio.create_task(ping_self())

    print("🤖 Bot running on Render...")

    # Delete webhook before polling to avoid conflict
    await app.bot.delete_webhook(drop_pending_updates=True)

    await app.run_polling()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        nest_asyncio.apply()
        asyncio.run(main())

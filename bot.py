import json
import os
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

ALERT_FILE = 'prices.json'


def load_alerts():
    if os.path.exists(ALERT_FILE):
        with open(ALERT_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_alerts(data):
    with open(ALERT_FILE, 'w') as f:
        json.dump(data, f, indent=2)


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ Error: TELEGRAM_BOT_TOKEN environment variable not set.")
    exit(1)

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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        return await update.message.reply_text("❌ Sorry, you are not authorized to use this bot. Contact the bot owner to get access.")
    await update.message.reply_text(
        "👋 Welcome to Crypto Alert Bot (Beta)!\n\n"
        "Use <b><i>/add COIN PRICE [above|below]</i></b> - to set a price alert.\n"
        "Note: You can only set 1 alert at a time in this beta version. Want unlimited alerts? Contact the bot owner.\n\n"
        "Example: <b><i>/add btc 30000 below</i></b>",
        parse_mode="HTML"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Commands:\n\n"
        "<b>/add COIN PRICE [above|below]</b> - Set a price alert (only one at a time)\n"
        "<b>/list</b> - View your alert\n"
        "<b>/remove 1</b> - Remove your alert\n"
        "<b>/price COIN [COIN2...]</b> - Get live prices\n"
        "<b>/coin</b> - List supported coins\n"
        "<b>/help</b> - Show this help message",
        parse_mode="HTML"
    )


async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    coin_list = "\n".join([f"• {k.upper()} ({v})" for k, v in SYMBOL_MAP.items()])
    await update.message.reply_text(
        "📊 Supported Coins:\n" + coin_list,
        parse_mode="HTML"
    )


async def add_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        return await update.message.reply_text("❌ You are not authorized to use this bot.")

    if len(context.args) < 2:
        return await update.message.reply_text("❗ Usage: /add COIN PRICE [above|below]")

    alerts = load_alerts()
    if str(user_id) in alerts and len(alerts[str(user_id)]) >= 1:
        return await update.message.reply_text(
    "❗ You can only have one alert in this beta version.\n"
    "🗑️ Remove it first using <b>/remove 1</b>.\n\n"
    "➕ Want unlimited alerts? Contact the bot owner.",
    parse_mode="HTML"
)

    symbol = context.args[0].lower()
    coin = SYMBOL_MAP.get(symbol)
    if not coin:
        return await update.message.reply_text("❗ Unsupported coin.")

    try:
        price = float(context.args[1])
    except ValueError:
        return await update.message.reply_text("❗ Invalid price format.")

    direction = "above"
    if len(context.args) >= 3 and context.args[2].lower() in ["above", "below"]:
        direction = context.args[2].lower()

    alerts[str(user_id)] = [{
        "coin": coin,
        "symbol": symbol,
        "price": price,
        "direction": direction
    }]
    save_alerts(alerts)
    await update.message.reply_text(f"✅ Alert set for {symbol.upper()} {direction} ${price}")


async def list_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    alerts = load_alerts()
    user_alerts = alerts.get(user_id, [])

    if not user_alerts:
        return await update.message.reply_text("📭 You have no active alerts.")

    message = "📋 Your active alert:\n"
    for idx, alert in enumerate(user_alerts, start=1):
        message += f"{idx}. {alert['symbol'].upper()} {alert['direction']} ${alert['price']}\n"
    await update.message.reply_text(message)


async def remove_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    alerts = load_alerts()

    if len(context.args) != 1:
        return await update.message.reply_text("❗ Usage: /remove 1")

    try:
        idx = int(context.args[0]) - 1
    except ValueError:
        return await update.message.reply_text("❗ Invalid number.")

    user_alerts = alerts.get(user_id, [])
    if idx < 0 or idx >= len(user_alerts):
        return await update.message.reply_text("❗ Alert not found.")

    removed = user_alerts.pop(idx)
    if not user_alerts:
        alerts.pop(user_id)
    else:
        alerts[user_id] = user_alerts
    save_alerts(alerts)
    await update.message.reply_text(f"✅ Removed alert for {removed['symbol'].upper()} {removed['direction']} ${removed['price']}")


async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("❗ Usage: /price COIN [COIN2...]")

    symbols = [arg.lower() for arg in context.args]
    unknown = [s for s in symbols if s not in SYMBOL_MAP]
    if unknown:
        return await update.message.reply_text(f"❗ Unsupported coin(s): {', '.join(unknown)}")

    ids = [SYMBOL_MAP[s] for s in symbols]
    url = "https://api.coingecko.com/api/v3/simple/price"

    try:
        res = requests.get(url, params={"ids": ",".join(ids), "vs_currencies": "usd"})
        data = res.json()
        reply = "\n".join([f"💰 {s.upper()}: ${data.get(SYMBOL_MAP[s], {}).get('usd', 'N/A'):.5f}" for s in symbols])
        await update.message.reply_text(reply)
    except Exception as e:
        print("⚠️ Price fetch error:", e)
        await update.message.reply_text("⚠️ Failed to fetch prices.")


async def check_prices(context: ContextTypes.DEFAULT_TYPE):
    alerts = load_alerts()
    if not alerts:
        return

    coins = list({a['coin'] for alerts_list in alerts.values() for a in alerts_list})
    try:
        res = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": ",".join(coins), "vs_currencies": "usd"}
        ).json()
    except Exception as e:
        print("⚠️ Failed to fetch prices:", e)
        return

    for user_id, alert_list in list(alerts.items()):
        to_remove = []
        for i, alert in enumerate(alert_list):
            price = res.get(alert['coin'], {}).get("usd")
            if price is None:
                continue

            if (alert['direction'] == "above" and price >= alert['price']) or \
               (alert['direction'] == "below" and price <= alert['price']):
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=f"🚨 {alert['symbol'].upper()} is ${price:.5f}, reached your alert ({alert['direction']} ${alert['price']})!"
                )
                to_remove.append(i)

        for idx in reversed(to_remove):
            alert_list.pop(idx)
        if alert_list:
            alerts[user_id] = alert_list
        else:
            alerts.pop(user_id)

    save_alerts(alerts)


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Unknown command. Use /help to see available commands.")


async def main():
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

    print("🤖 Bot is running (Beta)...")
    await app.run_polling()


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except RuntimeError:
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.run(main())

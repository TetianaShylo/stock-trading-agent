import os
import asyncio
import logging
from dotenv import load_dotenv
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from agent import analyze_market, execute_signal, alpaca_client

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

WATCHLIST = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN"]

# Micro web server to satisfy Render's port scan
async def handle_ping(request):
    return web.Response(text="Stock Trading Agent is Live and Running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Web server started on port {port}")

# Automated periodic scanning job
async def auto_scan_and_trade(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    for symbol in WATCHLIST:
        try:
            signal = analyze_market(symbol)
            action = signal.get("action")
            score = signal.get("score")
            reason = signal.get("reason")
            price = signal.get("price")

            if action in ["BUY", "SELL"]:
                trade_result = execute_signal(symbol, action)
                msg = (
                    f"🤖 <b>Auto-Trade Alert</b>\n"
                    f"<b>Asset:</b> {symbol}\n"
                    f"<b>Action:</b> {action}\n"
                    f"<b>Current Price:</b> ${price:.2f}\n"
                    f"<b>Agent Score:</b> {score}/100\n"
                    f"<b>Analysis:</b> {reason}\n"
                    f"<b>Execution:</b> {trade_result}"
                )
                await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
            await asyncio.sleep(2)  # Pause to respect API rate limits
        except Exception as e:
            logger.error(f"Error evaluating {symbol}: {e}")

# Telegram Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 <b>Welcome to AI Stock Analyst & Trading Agent!</b>\n\n"
        "Available commands:\n"
        "/analyze [SYMBOL] - Get instant AI market score\n"
        "/buy [SYMBOL] [QTY] - Submit Paper Buy Order\n"
        "/sell [SYMBOL] [QTY] - Submit Paper Sell Order\n"
        "/portfolio - Check live account balance\n"
        "/scan - Run full watchlist scan manually"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")

async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a stock symbol, e.g. <code>/analyze AAPL</code>", parse_mode="HTML")
        return
    symbol = context.args[0].upper()
    await update.message.reply_text(f"⏳ Analyzing <b>{symbol}</b> with multi-factor engine...", parse_mode="HTML")
    try:
        signal = analyze_market(symbol)
        action_emoji = "🟢" if signal['action'] == "BUY" else "🔴" if signal['action'] == "SELL" else "🟡"
        text = (
            f"📊 <b>Agent Report: {symbol}</b>\n\n"
            f"<b>Price:</b> ${signal['price']:.2f}\n"
            f"<b>Signal:</b> {action_emoji} <b>{signal['action']}</b>\n"
            f"<b>Composite Score:</b> {signal['score']}/100\n\n"
            f"<b>Reasoning:</b> {signal['reason']}"
        )
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error analyzing {symbol}: {str(e)}")

async def portfolio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        account = alpaca_client.get_account()
        msg = ( 
            f"💼 <b>Alpaca Paper Portfolio</b>\n\n"
            f"<b>Cash:</b> ${float(account.cash):,.2f}\n"
            f"<b>Portfolio Value:</b> ${float(account.portfolio_value):,.2f}\n"
            f"<b>Buying Power:</b> ${float(account.buying_power):,.2f}\n"
            f"<b>Status:</b> {account.status}"
        )
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching portfolio: {str(e)}")

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Scanning current watchlist...")
    for symbol in WATCHLIST:
        try:
            signal = analyze_market(symbol)
            await update.message.reply_text(
                f"• <b>{symbol}</b>: {signal['action']} (Score: {signal['score']}/100, Price: ${signal['price']:.2f})",
                parse_mode="HTML"
            )
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Scan error {symbol}: {e}")

# Background auto-scanner via standard asyncio loop
async def background_scanner(application: Application):
    await asyncio.sleep(10)  # Initial delay before first run
    while True:
        if TELEGRAM_CHAT_ID:
            for symbol in WATCHLIST:
                try:
                    signal = analyze_market(symbol)
                    action = signal.get("action")
                    score = signal.get("score")
                    reason = signal.get("reason")
                    price = signal.get("price")

                    if action in ["BUY", "SELL"]:
                        trade_result = execute_signal(symbol, action)
                        msg = (
                            f"🤖 <b>Auto-Trade Alert</b>\n"
                            f"<b>Asset:</b> {symbol}\n"
                            f"<b>Action:</b> {action}\n"
                            f"<b>Current Price:</b> ${price:.2f}\n"
                            f"<b>Agent Score:</b> {score}/100\n"
                            f"<b>Analysis:</b> {reason}\n"
                            f"<b>Execution:</b> {trade_result}"
                        )
                        await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="HTML")
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Error evaluating {symbol}: {e}")
        await asyncio.sleep(900)  # Repeat every 15 minutes

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment.")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("analyze", analyze_cmd))
    application.add_handler(CommandHandler("portfolio", portfolio_cmd))
    application.add_handler(CommandHandler("scan", scan_cmd))

    async def post_init(app: Application):
        await start_web_server()
        asyncio.create_task(background_scanner(app))

    application.post_init = post_init

    logger.info("Agent is active with Web Server & Auto-Trading engine...")
    application.run_polling()

if __name__ == "__main__":
    main()
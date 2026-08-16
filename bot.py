import os
import logging
import asyncio
import yfinance as yf
from dotenv import load_dotenv
from textblob import TextBlob
import ta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Alpaca Trading SDK
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# Load environment configuration
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

if not TELEGRAM_BOT_TOKEN:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN is missing from .env file!")
    exit(1)

# Initialize Alpaca Paper Trading Client
trading_client = None
if ALPACA_API_KEY and ALPACA_SECRET_KEY:
    try:
        trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
        print("✅ Connected to Alpaca Paper Trading successfully.")
    except Exception as e:
        print(f"⚠️ Warning: Could not connect to Alpaca: {e}")

# Target watchlist for automated trading
WATCHLIST = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN"]
AUTOTRADE_ENABLED = True

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def evaluate_stock_strategy(ticker_symbol):
    """
    Performs comprehensive quantitative, sentiment, and technical analysis.
    Returns a dictionary with metrics and actionable signals: BUY, SELL, or HOLD.
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        if not info or 'longName' not in info:
            return None

        # 1. Fundamental Analysis Scoring (0-5)
        score = 0
        pe_ratio = info.get('trailingPE', None)
        forward_pe = info.get('forwardPE', None)
        profit_margins = info.get('profitMargins', None)
        debt_to_equity = info.get('debtToEquity', None)
        revenue_growth = info.get('revenueGrowth', None)

        if pe_ratio and pe_ratio < 25: score += 1
        if profit_margins and (profit_margins * 100) > 15: score += 1
        if debt_to_equity is not None and debt_to_equity < 150: score += 1
        if revenue_growth is not None and (revenue_growth * 100) > 5: score += 1
        if forward_pe and pe_ratio and forward_pe < pe_ratio: score += 1

        # 2. Market News Sentiment Analysis
        news_list = ticker.news or []
        polarities = []
        for item in news_list[:5]:
            title = item.get('title') or item.get('content', {}).get('title', '')
            if title:
                polarities.append(TextBlob(title).sentiment.polarity)
        avg_polarity = (sum(polarities) / len(polarities)) if polarities else 0.0

        # 3. Technical Momentum & Trend (RSI)
        df = yf.download(ticker_symbol, period="1y", interval="1d", progress=False)
        if df.empty or len(df) < 50:
            return None

        if hasattr(df.columns, 'levels'):
            df.columns = df.columns.get_level_values(0)

        df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
        latest_rsi = float(df['RSI'].iloc[-1])
        current_price = float(df['Close'].iloc[-1])

        # Strategy Signal Generation
        signal = "HOLD"
        if score >= 4 and avg_polarity >= -0.05 and latest_rsi < 70:
            signal = "BUY"
        elif latest_rsi > 75 or score <= 1:
            signal = "SELL"

        return {
            "symbol": ticker_symbol,
            "name": info.get('longName', ticker_symbol),
            "score": score,
            "sentiment": avg_polarity,
            "rsi": latest_rsi,
            "price": current_price,
            "signal": signal
        }
    except Exception as e:
        logging.error(f"Error evaluating {ticker_symbol}: {e}")
        return None

# --- Autonomous Background Trading Engine ---

async def auto_trade_loop(app):
    """Background task: Periodically scans the market and executes algorithmic orders."""
    await asyncio.sleep(5)
    while True:
        if AUTOTRADE_ENABLED and trading_client and TELEGRAM_CHAT_ID:
            print("🔍 [Auto-Trader] Scanning watchlist...")
            try:
                positions = {p.symbol: float(p.qty) for p in trading_client.get_all_positions()}

                for symbol in WATCHLIST:
                    data = evaluate_stock_strategy(symbol)
                    if not data:
                        continue

                    # Automated BUY condition
                    if data["signal"] == "BUY" and symbol not in positions:
                        qty_to_buy = 1
                        order_data = MarketOrderRequest(
                            symbol=symbol,
                            qty=qty_to_buy,
                            side=OrderSide.BUY,
                            time_in_force=TimeInForce.DAY
                        )
                        order = trading_client.submit_order(order_data=order_data)
                        msg = (
                            f"🤖 *[Auto-Trader] Order Executed: BUY*\n\n"
                            f"• *Asset:* {data['name']} (`{symbol}`)\n"
                            f"• *Quantity:* {qty_to_buy} shares (~${data['price']:.2f})\n"
                            f"• *Fundamental Score:* {data['score']}/5 | *RSI:* `{data['rsi']:.1f}`\n"
                            f"• *Order Status:* `{order.status}`"
                        )
                        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="Markdown")

                    # Automated SELL condition
                    elif data["signal"] == "SELL" and symbol in positions:
                        qty_to_sell = positions[symbol]
                        order_data = MarketOrderRequest(
                            symbol=symbol,
                            qty=qty_to_sell,
                            side=OrderSide.SELL,
                            time_in_force=TimeInForce.DAY
                        )
                        order = trading_client.submit_order(order_data=order_data)
                        msg = (
                            f"🚨 *[Auto-Trader] Order Executed: SELL*\n\n"
                            f"• *Asset:* {data['name']} (`{symbol}`)\n"
                            f"• *Quantity:* {qty_to_sell} shares\n"
                            f"• *Trigger:* RSI {data['rsi']:.1f} / Score `{data['score']}/5`\n"
                            f"• *Order Status:* `{order.status}`"
                        )
                        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="Markdown")

                    await asyncio.sleep(2)

            except Exception as e:
                logging.error(f"Error in auto-trade cycle: {e}")

        # Scan interval: 1800 seconds (30 minutes)
        await asyncio.sleep(1800)

async def post_init(application):
    asyncio.create_task(auto_trade_loop(application))

# --- Interactive Telegram Commands ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *Autonomous AI Trading Agent is Active!*\n\n"
        "📊 *Commands:*\n"
        "• /portfolio — View account balance and active positions\n"
        "• /scan — Scan watchlist immediately\n"
        "• /buy <TICKER> <QTY> — Submit manual buy order (e.g. `/buy AAPL 1`)\n"
        "• /sell <TICKER> <QTY> — Submit manual sell order (e.g. `/sell AAPL 1`)\n\n"
        "You can also send any stock ticker (e.g., `NVDA`) for an on-demand analysis report."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Scanning market watchlist...")
    results = []
    for sym in WATCHLIST:
        d = evaluate_stock_strategy(sym)
        if d:
            icon = "🟢" if d["signal"] == "BUY" else ("🔴" if d["signal"] == "SELL" else "⚪")
            results.append(f"{icon} *{d['symbol']}*: Score {d['score']}/5 | RSI {d['rsi']:.1f} | Signal: *{d['signal']}*")
    
    await update.message.reply_text("\n".join(results) or "No data available.", parse_mode="Markdown")

async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not trading_client:
        await update.message.reply_text("❌ Trading client is not configured.")
        return
    try:
        account = trading_client.get_account()
        positions = trading_client.get_all_positions()

        portfolio_val = float(account.portfolio_value)
        cash = float(account.cash)
        buying_power = float(account.buying_power)

        holdings_text = ""
        if positions:
            holdings_text = "\n\n*Active Positions:*\n"
            for pos in positions:
                pl_val = float(pos.unrealized_pl)
                pl_pct = float(pos.unrealized_plpc) * 100
                icon = "🟢" if pl_val >= 0 else "🔴"
                holdings_text += (
                    f"• *{pos.symbol}*: {pos.qty} shares @ ${float(pos.avg_entry_price):.2f} "
                    f"(Current: ${float(pos.current_price):.2f} | P&L: {icon} ${pl_val:+.2f} / `{pl_pct:+.2f}%`)\n"
                )
        else:
            holdings_text = "\n\n*Positions:* None (100% Cash Allocation)"

        report = (
            f"💼 *Paper Trading Portfolio Status*\n\n"
            f"💰 *Portfolio Value:* `${portfolio_val:,.2f}`\n"
            f"💵 *Available Cash:* `${cash:,.2f}`\n"
            f"⚡ *Buying Power:* `${buying_power:,.2f}`"
            f"{holdings_text}"
        )
        await update.message.reply_text(report, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not trading_client or len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: `/buy AAPL 2`", parse_mode="Markdown")
        return
    symbol = context.args[0].upper().strip()
    try:
        qty = float(context.args[1])
        order = trading_client.submit_order(MarketOrderRequest(symbol=symbol, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.DAY))
        await update.message.reply_text(f"✅ Buy order for {qty} share(s) of {symbol} submitted!", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Order failed: {e}")

async def sell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not trading_client or len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: `/sell AAPL 1`", parse_mode="Markdown")
        return
    symbol = context.args[0].upper().strip()
    try:
        qty = float(context.args[1])
        order = trading_client.submit_order(MarketOrderRequest(symbol=symbol, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.DAY))
        await update.message.reply_text(f"✅ Sell order for {qty} share(s) of {symbol} submitted!", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Order failed: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticker = update.message.text.strip().upper()
    await update.message.reply_text(f"🔎 Analyzing {ticker}...")
    data = evaluate_stock_strategy(ticker)
    if not data:
        await update.message.reply_text("⚠️ Could not retrieve market data for this symbol.")
        return
    msg = (
        f"📊 *Analysis Report for {data['name']} ({data['symbol']})*\n\n"
        f"⭐ *Fundamental Score:* `{data['score']}/5`\n"
        f"📈 *RSI (14):* `{data['rsi']:.1f}`\n"
        f"💵 *Market Price:* `${data['price']:.2f}`\n"
        f"🚦 *Strategy Signal:* *{data['signal']}*"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan_command))
    app.add_handler(CommandHandler("portfolio", portfolio_command))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(CommandHandler("sell", sell_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Agent is active with Auto-Trading engine...")
    app.run_polling()
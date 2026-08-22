import os
import yfinance as yf
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

load_dotenv()

# Initialize Alpaca client
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

alpaca_client = None
if ALPACA_API_KEY and ALPACA_SECRET_KEY:
    alpaca_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)

def analyze_market(ticker_symbol: str) -> dict:
    ticker_symbol = ticker_symbol.upper()
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        history = ticker.history(period="1d")
        current_price = history["Close"].iloc[-1] if not history.empty else info.get("currentPrice", 0.0)
    except Exception as e:
        return {
            "symbol": ticker_symbol,
            "price": 0.0,
            "score": 0,
            "action": "HOLD",
            "reason": f"Failed to fetch data: {str(e)}"
        }

    company_name = info.get("longName", ticker_symbol)
    pe_ratio = info.get("trailingPE", None)
    forward_pe = info.get("forwardPE", None)
    profit_margins = info.get("profitMargins", None)
    debt_to_equity = info.get("debtToEquity", None)
    revenue_growth = info.get("revenueGrowth", None)

    score = 0
    max_score = 5
    reasons = []

    # 1. P/E Valuation
    if pe_ratio:
        if pe_ratio < 25:
            score += 1
            reasons.append(f"✅ Reasonable P/E: {pe_ratio:.2f}")
        else:
            reasons.append(f"⚠️ High P/E: {pe_ratio:.2f}")

    # 2. Profitability
    if profit_margins:
        margin_pct = profit_margins * 100
        if margin_pct > 15:
            score += 1
            reasons.append(f"✅ Profit Margin: {margin_pct:.2f}%")
        else:
            reasons.append(f"⚠️ Low Profit Margin: {margin_pct:.2f}%")

    # 3. Debt Level
    if debt_to_equity is not None:
        if debt_to_equity < 150:
            score += 1
            reasons.append(f"✅ Healthy Debt (D/E): {debt_to_equity:.2f}%")
        else:
            reasons.append(f"⚠️ High Debt (D/E): {debt_to_equity:.2f}%")

    # 4. Revenue Growth
    if revenue_growth is not None:
        growth_pct = revenue_growth * 100
        if growth_pct > 5:
            score += 1
            reasons.append(f"✅ Revenue Growth: {growth_pct:.2f}%")
        else:
            reasons.append(f"⚠️ Weak Revenue Growth: {growth_pct:.2f}%")

    # 5. Forward P/E vs Trailing P/E
    if forward_pe and pe_ratio:
        if forward_pe < pe_ratio:
            score += 1
            reasons.append(f"✅ Positive Earnings Outlook (Forward P/E {forward_pe:.2f} < {pe_ratio:.2f})")

    # Determine action signal
    if score >= 4:
        action = "BUY"
    elif score <= 1:
        action = "SELL"
    else:
        action = "HOLD"

    return {
        "symbol": ticker_symbol,
        "name": company_name,
        "price": float(current_price),
        "score": int((score / max_score) * 100),
        "action": action,
        "reason": "\n".join(reasons) if reasons else "Limited fundamental analysis data available."
    }

def execute_signal(symbol: str, action: str, qty: int = 1) -> str:
    if not alpaca_client:
        return "Alpaca API credentials not configured."
    try:
        side = OrderSide.BUY if action == "BUY" else OrderSide.SELL
        order_data = MarketOrderRequest(
            symbol=symbol.upper(),
            qty=qty,
            side=side,
            time_in_force=TimeInForce.GTC
        )
        order = alpaca_client.submit_order(order_data=order_data)
        return f"Order {order.id} submitted ({action} {qty} {symbol})."
    except Exception as e:
        return f"Order execution failed: {str(e)}"
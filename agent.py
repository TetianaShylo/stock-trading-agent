import yfinance as yf

def analyze_fundamentals(ticker_symbol):
    print(f"🔎 Збираємо фундаментальні дані для: {ticker_symbol}...\n")
    
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
    except Exception as e:
        print(f"❌ Помилка завантаження даних: {e}")
        return

    if not info or 'longName' not in info:
        print("⚠️ Не вдалося отримати деталі по цьому тикеру.")
        return

    company_name = info.get('longName', ticker_symbol)
    pe_ratio = info.get('trailingPE', None)
    forward_pe = info.get('forwardPE', None)
    profit_margins = info.get('profitMargins', None)
    debt_to_equity = info.get('debtToEquity', None)
    revenue_growth = info.get('revenueGrowth', None)
    
    score = 0
    max_score = 5
    reasons = []

    # 1. P/E Оцінка
    if pe_ratio:
        if pe_ratio < 25:
            score += 1
            reasons.append(f"✅ Адекватний P/E ratio: {pe_ratio:.2f}")
        else:
            reasons.append(f"⚠️ Високий P/E ratio: {pe_ratio:.2f}")

    # 2. Рентабельність
    if profit_margins:
        margin_pct = profit_margins * 100
        if margin_pct > 15:
            score += 1
            reasons.append(f"✅ Висока маржинальність: {margin_pct:.2f}%")
        else:
            reasons.append(f"⚠️ Низька маржинальність: {margin_pct:.2f}%")

    # 3. Боргове навантаження
    if debt_to_equity is not None:
        if debt_to_equity < 150:
            score += 1
            reasons.append(f"✅ Безпечний рівень боргу (D/E): {debt_to_equity:.2f}%")
        else:
            reasons.append(f"⚠️ Високий борг (D/E): {debt_to_equity:.2f}%")

    # 4. Зростання виручки
    if revenue_growth is not None:
        growth_pct = revenue_growth * 100
        if growth_pct > 5:
            score += 1
            reasons.append(f"✅ Хороший темп зростання виручки: {growth_pct:.2f}%")
        else:
            reasons.append(f"⚠️ Повільне зростання/падіння виручки: {growth_pct:.2f}%")

    # 5. Forward P/E vs Trailing P/E
    if forward_pe and pe_ratio:
        if forward_pe < pe_ratio:
            score += 1
            reasons.append(f"✅ Прогнозується зростання прибутку (Forward P/E {forward_pe:.2f} < Trailing P/E {pe_ratio:.2f})")

    # Вивід результату
    print(f"📊 Результат аналізу для {company_name} ({ticker_symbol})")
    print(f"Оцінка фундаментального здоров'я: {score}/{max_score}\n")
    print("Деталі:")
    for reason in reasons:
        print(reason)

if __name__ == "__main__":
    analyze_fundamentals("AAPL")
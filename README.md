# 📈 Autonomous AI Market Analyst & Trading Bot

An automated quantitative trading and market analysis agent built in Python. The bot integrates with Yahoo Finance for fundamental and technical indicators, utilizes NLP Sentiment Analysis on real-time financial news, and executes automated paper trades via the Alpaca Markets REST API.

## 🚀 Key Features
* Autonomous Trading Engine: Periodically screens target watchlists and executes market orders when multi-variable criteria are met.
* Fundamental Scoring (0-5): Evaluates valuation metrics ($P/E$, Forward $P/E$, Profit Margins, Debt-to-Equity, Revenue Growth).
* News Sentiment Analysis: Real-time polarity scoring via NLP (`TextBlob`) on the latest market headlines.
* Technical Indicator: Analyzes momentum trends with a 14-day Relative Strength Index (RSI).
* Telegram Terminal Interface: Real-time P&L tracking, manual trade overrides, on-demand tickers analysis, and push notifications.

## 🛠 Tech Stack
* Language: Python 3.10+
* Libraries: python-telegram-bot, alpaca-py, yfinance, ta, textblob, pandas
* Broker Integration: Alpaca Markets API (Paper Trading)
* Deployment: Cloud 24/7 Background Worker

## ⚙️ Telegram Commands
* /portfolio — View current account balance, cash, and open positions.
* /scan — Trigger an immediate algorithmic analysis on the watchlist.
* /buy <TICKER> <QTY> — Submit a manual market buy order.
* /sell <TICKER> <QTY> — Submit a manual market sell order.
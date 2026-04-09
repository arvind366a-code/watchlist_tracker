# Watchlist Tracker

Personal stock watchlist tracker with technical indicators and alerts.

## Features

- Track US and India stocks (via Yahoo Finance)
- Calculate technical indicators (RSI, EMA, MACD, ATR)
- Configurable price and indicator alerts
- CLI for easy management
- Telegram notifications (optional)

## Install

```bash
cd ~/projects/watchlist_tracker
uv sync
```

## Usage

```bash
# Initialize with default stocks
uv run watchlist init

# Add a stock
uv run watchlist add AAPL --market us --name "Apple Inc."

# Add India stock
uv run watchlist add RELIANCE --market india

# List with indicators
uv run watchlist list --indicators

# Add alerts
uv run watchlist alerts AAPL --add-type price_above --value 200

# Generate summary (for cron)
uv run watchlist summary
```

## stocks (US)

- AAPL — Apple Inc.
- TSLA — Tesla Inc.
- DOCN— DigitalOcean Holdings, Inc.
- NET — Cloudflare, Inc.
- NVDA — NVIDIA Corporation
- GOOGL — Alphabet Inc. (Google)
- AMZN — Amazon.com, Inc.
- NBIS — NeuroBio Infosys

## Stocks (India)

- EICHERMOT — Eicher Motors Ltd.
- RELIANCE — Reliance Industries Ltd.
- CPSEETF — CPSE ETF

## Alert Types

- `price_above` — Alert when price crosses above threshold
- `price_below` — Alert when price crosses below threshold
- `rsi_oversold` — Alert when RSI <30
- `rsi_overbought` — Alert when RSI > 70
- `ema_crossover_bullish` — EMA crossover (golden cross)

## Cron Setup

Add to crontab for periodic checks:

```bash
# Check watchlist every hour during market hours
0 10-16 * * 1-5 cd /home/you/projects/watchlist_tracker && uv run watchlist summary >> /var/log/watchlist.log 2>&1
```

## License

MIT
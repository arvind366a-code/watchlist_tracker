"""Yahoo Finance price provider."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd
import yfinance as yf

from watchlist_tracker.domain.models import Market, MarketData
from watchlist_tracker.domain.markets import get_yfinance_symbol
from watchlist_tracker.infrastructure.providers.base import PriceProvider


class YFinanceProvider(PriceProvider):
    """Fetch prices using yfinance library."""

    def __init__(self, cache_seconds: int = 60):
        self.cache_seconds = cache_seconds
        self._cache: dict[str, tuple[datetime, MarketData]] = {}

    def get_current_price(self, symbol: str, market: Market) -> MarketData | None:
        """Fetch current price for a single symbol."""
        yf_symbol = get_yfinance_symbol(symbol, market.value)
        try:
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info

            # Try fast_info first (faster, less rate limiting)
            fast_info = getattr(ticker, 'fast_info', None)

            price = Decimal(str(info.get("currentPrice") or info.get("regularMarketPrice") or 0))
            if price == 0 and fast_info:
                price = Decimal(str(getattr(fast_info, 'last_price', 0) or 0))

            prev_close = Decimal(str(info.get("previousClose") or info.get("regularMarketPreviousClose") or price))
            change = price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else Decimal(0)

            volume = info.get("volume") or info.get("regularMarketVolume") or 0
            avg_volume = info.get("averageVolume") or info.get("averageDailyVolume10Day")

            high_52w = info.get("fiftyTwoWeekHigh")
            low_52w = info.get("fiftyTwoWeekLow")

            return MarketData(
                symbol=symbol,
                exchange=info.get("exchange", market.value.upper()),
                market=market,
                price=price,
                change=change,
                change_pct=change_pct,
                volume=int(volume) if volume else 0,
                avg_volume=int(avg_volume) if avg_volume else None,
                high_52w=Decimal(str(high_52w)) if high_52w else None,
                low_52w=Decimal(str(low_52w)) if low_52w else None,
                timestamp=datetime.now(),
            )
        except Exception as e:
            print(f"Error fetching {yf_symbol}: {e}")
            return None

    def get_current_prices(
        self, symbols: list[tuple[str, Market]]
    ) -> dict[str, MarketData]:
        """Fetch current prices for multiple symbols."""
        results = {}
        for symbol, market in symbols:
            data = self.get_current_price(symbol, market)
            if data:
                results[symbol] = data
        return results

    def get_historical_prices(
        self, symbol: str, market: Market, days: int = 200
    ) -> list[dict]:
        """Fetch historical OHLCV data for indicator calculation."""
        yf_symbol = get_yfinance_symbol(symbol, market.value)
        try:
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period=f"{days}d")

            if df.empty:
                return []

            df = df.reset_index()
            return [
                {
                    "date": row["Date"].to_pydatetime(),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                }
                for _, row in df.iterrows()
            ]
        except Exception as e:
            print(f"Error fetching history for {yf_symbol}: {e}")
            return []

    def get_symbols_batch(
        self, symbols: list[tuple[str, Market]]
    ) -> dict[str, MarketData]:
        """Fetch multiple symbols in a single request (more efficient)."""
        results = {}

        # Group by market for efficient batching
        yf_symbols = [get_yfinance_symbol(s, m.value) for s, m in symbols]
        symbol_map = {get_yfinance_symbol(s, m.value): s for s, m in symbols}

        try:
            tickers = yf.Tickers(" ".join(yf_symbols))
            for yf_sym in yf_symbols:
                symbol = symbol_map.get(yf_sym)
                if not symbol:
                    continue

                ticker = tickers.tickers.get(yf_sym)
                if not ticker:
                    continue

                info = ticker.info or {}
                fast_info = getattr(ticker, 'fast_info', None)

                # Find market
                market = next((m for s, m in symbols if s == symbol), Market.US)

                price = Decimal(str(info.get("currentPrice") or info.get("regularMarketPrice") or 0))
                if price == 0 and fast_info:
                    price = Decimal(str(getattr(fast_info, 'last_price', 0) or 0))

                prev_close = Decimal(str(info.get("previousClose") or info.get("regularMarketPreviousClose") or price))
                change = price - prev_close
                change_pct = (change / prev_close * 100) if prev_close else Decimal(0)

                volume = info.get("volume") or info.get("regularMarketVolume") or 0
                avg_volume = info.get("averageVolume")

                results[symbol] = MarketData(
                    symbol=symbol,
                    exchange=info.get("exchange", ""),
                    market=market,
                    price=price,
                    change=change,
                    change_pct=change_pct,
                    volume=int(volume) if volume else 0,
                    avg_volume=int(avg_volume) if avg_volume else None,
                    timestamp=datetime.now(),
                )
        except Exception as e:
            print(f"Batch fetch error: {e}")

        return results
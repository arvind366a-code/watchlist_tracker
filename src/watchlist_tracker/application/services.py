"""Application services for watchlist tracking."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pandas as pd
import pandas_ta as ta

from watchlist_tracker.domain.models import (
    AlertType,
    MarketData,
    TriggeredAlert,
    WatchlistEntry,
    WatchlistSummary,
)
from watchlist_tracker.domain.models import Market
from watchlist_tracker.domain.markets import get_yfinance_symbol
from watchlist_tracker.infrastructure.database import WatchlistStore
from watchlist_tracker.infrastructure.providers.base import PriceProvider


class IndicatorCalculator:
    """Calculate technical indicators from price history."""

    @staticmethod
    def calculate(df: pd.DataFrame, indicators: list[str] | None = None) -> dict[str, float]:
        """Calculate indicators from OHLCV DataFrame."""
        result = {}
        if df.empty:
            return result

        close = df["close"]
        volume = df["volume"]

        # RSI
        rsi = ta.rsi(close, length=14)
        if not rsi.empty:
            result["rsi_14"] = float(rsi.iloc[-1])

        # EMAs
        for period in [9, 21, 50, 200]:
            ema = ta.ema(close, length=period)
            if not ema.empty:
                result[f"ema_{period}"] = float(ema.iloc[-1])

        # MACD
        macd = ta.macd(close)
        if macd is not None and not macd.empty:
            result["macd"] = float(macd["MACD_12_26_9"].iloc[-1])
            result["macd_signal"] = float(macd["MACDs_12_26_9"].iloc[-1])

        # ATR
        atr = ta.atr(df["high"], df["low"], close, length=14)
        if not atr.empty:
            result["atr_14"] = float(atr.iloc[-1])

        # Bollinger Bands
        bb = ta.bbands(close, length=20)
        if bb is not None and not bb.empty:
            # Find BB upper and lower columns dynamically
            bb_cols = [c for c in bb.columns if 'BBU' in c or 'BBL' in c]
            for col in bb_cols:
                if 'BBU' in col:
                    result["bb_upper"] = float(bb[col].iloc[-1])
                elif 'BBL' in col:
                    result["bb_lower"] = float(bb[col].iloc[-1])

        # Supertrend
        supertrend = ta.supertrend(df["high"], df["low"], close, length=10, multiplier=3.0)
        if supertrend is not None and not supertrend.empty:
            # Columns: SUPERT_10_3.0, SUPERTd_10_3.0, SUPERTl_10_3.0, SUPERTs_10_3.0
            st_col = [c for c in supertrend.columns if c.startswith("SUPERT_") and "d" not in c.lower() and "l" not in c.lower() and "s" not in c.lower()]
            if st_col:
                result["supertrend"] = float(supertrend[st_col[0]].iloc[-1])
            # Direction: 1 = bullish, -1 = bearish
            st_dir = [c for c in supertrend.columns if "SUPERTd" in c]
            if st_dir:
                result["supertrend_dir"] = float(supertrend[st_dir[0]].iloc[-1])

        # Volume relative to average
        vol_sma = ta.sma(volume, length=20)
        if not vol_sma.empty:
            result["volume_ratio"] = float(volume.iloc[-1]) / float(vol_sma.iloc[-1])

        return result


class WatchlistService:
    """Service for managing watchlist entries."""

    def __init__(self, store: WatchlistStore):
        self.store = store

    def add(
        self,
        symbol: str,
        market: str,
        name: str = "",
        tags: list[str] | None = None,
        notes: str = "",
    ) -> WatchlistEntry:
        """Add a stock to the watchlist."""
        entry = WatchlistEntry(
            symbol=symbol.upper(),
            exchange=market.upper(),
            name=name,
            market=Market(market.lower()),
            tags=tags or [],
            notes=notes,
        )
        self.store.add_entry(entry)
        return entry

    def remove(self, symbol: str) -> bool:
        """Remove a stock from the watchlist."""
        return self.store.remove_entry(symbol)

    def get(self, symbol: str) -> WatchlistEntry | None:
        """Get a single watchlist entry."""
        return self.store.get_entry(symbol)

    def list_all(self) -> list[WatchlistEntry]:
        """List all watchlist entries."""
        return self.store.get_all_entries()


class MonitoringService:
    """Service for monitoring watchlist and triggering alerts."""

    def __init__(
        self,
        store: WatchlistStore,
        provider: PriceProvider,
    ):
        self.store = store
        self.provider = provider
        self.indicator_calc = IndicatorCalculator()

    def fetch_all_prices(self) -> dict[str, MarketData]:
        """Fetch current prices for all watchlist entries."""
        entries = self.store.get_all_entries()
        symbols = [(e.symbol, e.market) for e in entries]
        return self.provider.get_current_prices(symbols)

    def calculate_indicators(self, symbol: str, market: Market) -> dict[str, float]:
        """Calculate indicators for a symbol."""
        history = self.provider.get_historical_prices(symbol, market, days=200)
        if not history:
            return {}

        df = pd.DataFrame(history)
        return self.indicator_calc.calculate(df)

    def check_alerts(
        self,
        entry: WatchlistEntry,
        data: MarketData,
        indicators: dict[str, float],
    ) -> list[TriggeredAlert]:
        """Check if any alerts should trigger for an entry."""
        triggered = []

        for alert in entry.alerts:
            if not alert.enabled:
                continue

            # Check cooldown
            last_alert = self.store.get_last_alert(entry.symbol, alert.type.value)
            if last_alert:
                from datetime import timedelta
                elapsed = datetime.now() - last_alert
                if elapsed.total_seconds() < alert.cooldown_hours * 3600:
                    continue

            # Evaluate condition
            should_trigger = False
            value_str = ""

            if alert.type == AlertType.PRICE_ABOVE:
                threshold = Decimal(str(alert.value or 0))
                if data.price >= threshold:
                    should_trigger = True
                    value_str = f"price {float(data.price):.2f} >= {alert.value}"

            elif alert.type == AlertType.PRICE_BELOW:
                threshold = Decimal(str(alert.value or 0))
                if data.price <= threshold:
                    should_trigger = True
                    value_str = f"price {float(data.price):.2f} <= {alert.value}"

            elif alert.type == AlertType.RSI_OVERSOLD:
                rsi = indicators.get("rsi_14", 100)
                threshold = alert.params.get("threshold", 30)
                if rsi < threshold:
                    should_trigger = True
                    value_str = f"RSI {rsi:.1f} < {threshold}"

            elif alert.type == AlertType.RSI_OVERBOUGHT:
                rsi = indicators.get("rsi_14", 0)
                threshold = alert.params.get("threshold", 70)
                if rsi > threshold:
                    should_trigger = True
                    value_str = f"RSI {rsi:.1f} > {threshold}"

            elif alert.type == AlertType.EMA_CROSSOVER_BULLISH:
                ema_fast = indicators.get(f"ema_{alert.params.get('fast', 9)}")
                ema_slow = indicators.get(f"ema_{alert.params.get('slow', 21)}")
                if ema_fast and ema_slow and ema_fast > ema_slow:
                    should_trigger = True
                    value_str = f"EMA crossover bullish"

            elif alert.type == AlertType.VOLUME_SURGE:
                vol_ratio = indicators.get("volume_ratio", 0)
                threshold = alert.params.get("multiplier", 2.0)
                if vol_ratio > threshold:
                    should_trigger = True
                    value_str = f"Volume {vol_ratio:.1f}x average"

            if should_trigger:
                triggered_alert = TriggeredAlert(
                    entry_id=entry.symbol,
                    alert=alert,
                    market_data=data,
                    value=value_str,
                    message=f"{entry.symbol}: {value_str}",
                )
                self.store.log_alert(triggered_alert)
                triggered.append(triggered_alert)

        return triggered

    def get_summary(self) -> WatchlistSummary:
        """Get full watchlist summary with prices and alerts."""
        entries = self.store.get_all_entries()
        market_data = self.fetch_all_prices()
        all_alerts = []

        for entry in entries:
            data = market_data.get(entry.symbol)
            if data:
                # Calculate indicators
                indicators = self.calculate_indicators(entry.symbol, entry.market)
                data.indicators = indicators

                # Check alerts
                alerts = self.check_alerts(entry, data, indicators)
                all_alerts.extend(alerts)

        return WatchlistSummary(
            entries=entries,
            market_data=market_data,
            triggered_alerts=all_alerts,
            last_updated=datetime.now(),
        )
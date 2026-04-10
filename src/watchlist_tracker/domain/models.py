"""Domain models for watchlist tracking."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Market(str, Enum):
    US = "us"
    INDIA = "india"


class AlertType(str, Enum):
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    RSI_OVERSOLD = "rsi_oversold"
    RSI_OVERBOUGHT = "rsi_overbought"
    SUPERTREND_BULLISH = "supertrend_bullish"  # Flips to bullish
    SUPERTREND_BEARISH = "supertrend_bearish"  # Flips to bearish
    EMA_CROSSOVER_BULLISH = "ema_crossover_bullish"  # EMA9 > EMA21
    EMA_CROSSOVER_BEARISH = "ema_crossover_bearish"  # EMA9 < EMA21
    MACD_CROSSOVER_BULLISH = "macd_crossover_bullish"
    MACD_CROSSOVER_BEARISH = "macd_crossover_bearish"
    VOLUME_SURGE = "volume_surge"  # Volume >2x average
    PRICE_NEAR_EMA = "price_near_ema"  # Price within 2% of EMA


class AlertSpec(BaseModel):
    """Alert condition specification."""
    type: AlertType
    value: float | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    cooldown_hours: float = 4.0
    enabled: bool = True


class PositionPlan(BaseModel):
    """Entry/exit plan with position sizing."""
    entry_price: Decimal | None = None
    stop_loss: Decimal | None = None
    targets: list[Decimal] = Field(default_factory=list)
    risk_per_trade: Decimal | None = None  # Max acceptable loss
    notes: str = ""

    @property
    def risk_per_share(self) -> Decimal | None:
        if self.entry_price and self.stop_loss:
            return self.entry_price - self.stop_loss
        return None

    @property
    def recommended_shares(self) -> int | None:
        if self.risk_per_share and self.risk_per_trade:
            risk = float(self.risk_per_share)
            if risk <= 0:
                return None
            return int(float(self.risk_per_trade) / risk)
        return None

    @property
    def capital_required(self) -> Decimal | None:
        if self.recommended_shares and self.entry_price:
            return Decimal(self.recommended_shares) * self.entry_price
        return None


class IndicatorConfig(BaseModel):
    """Technical indicator to track."""
    type: str  # ema, rsi, macd, atr, bb
    params: dict[str, Any] = Field(default_factory=dict)
    alert_on: dict[str, float] | None = None  # e.g., {"below": 30, "above": 70}


class WatchlistEntry(BaseModel):
    """A single watchlist stock entry."""
    symbol: str
    exchange: str
    name: str = ""
    market: Market
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    position_plan: PositionPlan | None = None
    indicators: list[IndicatorConfig] = Field(default_factory=list)
    alerts: list[AlertSpec] = Field(default_factory=list)
    added_date: datetime = Field(default_factory=datetime.now)
    last_checked: datetime | None = None
    status: str = "active"  # active, paused, closed

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        return v.upper().strip()


class MarketData(BaseModel):
    """Current market data for a stock."""
    symbol: str
    exchange: str
    market: Market
    price: Decimal
    change: Decimal
    change_pct: Decimal
    volume: int
    avg_volume: int | None = None
    high_52w: Decimal | None = None
    low_52w: Decimal | None = None
    timestamp: datetime = Field(default_factory=datetime.now)

    # Computed indicators
    indicators: dict[str, float] = Field(default_factory=dict)


class TriggeredAlert(BaseModel):
    """An alert that has been triggered."""
    entry_id: str
    alert: AlertSpec
    market_data: MarketData
    value: str  # Human-readable value that triggered
    timestamp: datetime = Field(default_factory=datetime.now)
    message: str = ""


class WatchlistSummary(BaseModel):
    """Summary of watchlist status."""
    entries: list[WatchlistEntry]
    market_data: dict[str, MarketData]  # symbol -> data
    triggered_alerts: list[TriggeredAlert]
    last_updated: datetime = Field(default_factory=datetime.now)

    @property
    def us_stocks(self) -> list[WatchlistEntry]:
        return [e for e in self.entries if e.market == Market.US]

    @property
    def india_stocks(self) -> list[WatchlistEntry]:
        return [e for e in self.entries if e.market == Market.INDIA]
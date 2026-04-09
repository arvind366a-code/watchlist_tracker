"""Data providers for fetching stock prices."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from watchlist_tracker.domain.models import Market, MarketData


class PriceProvider(ABC):
    """Abstract base class for price data providers."""

    @abstractmethod
    def get_current_price(self, symbol: str, market: Market) -> MarketData | None:
        """Fetch current price for a single symbol."""
        ...

    @abstractmethod
    def get_current_prices(
        self, symbols: list[tuple[str, Market]]
    ) -> dict[str, MarketData]:
        """Fetch current prices for multiple symbols."""
        ...

    @abstractmethod
    def get_historical_prices(
        self, symbol: str, market: Market, days: int = 200
    ) -> list[dict]:
        """Fetch historical OHLCV data for indicator calculation."""
        ...
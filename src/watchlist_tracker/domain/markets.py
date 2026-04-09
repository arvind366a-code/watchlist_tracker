"""Market definitions for US and India."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketInfo:
    slug: str
    name: str
    timezone: str
    open_time: str
    close_time: str
    yfinance_suffix: str  # e.g., ".NS" for NSE, "" for US


MARKETS = {
    "us": MarketInfo(
        slug="us",
        name="US Markets",
        timezone="America/New_York",
        open_time="09:30",
        close_time="16:00",
        yfinance_suffix="",
    ),
    "india": MarketInfo(
        slug="india",
        name="Indian Markets (NSE/BSE)",
        timezone="Asia/Kolkata",
        open_time="09:15",
        close_time="15:30",
        yfinance_suffix=".NS",  # Default to NSE
    ),
}


def get_yfinance_symbol(symbol: str, market: str) -> str:
    """Convert symbol to yfinance format."""
    info = MARKETS.get(market)
    if not info:
        return symbol
    return f"{symbol}{info.yfinance_suffix}" if info.yfinance_suffix else symbol


def get_market_hours(market: str) -> tuple[str, str]:
    """Get market open/close times in local timezone."""
    info = MARKETS.get(market)
    if not info:
        return ("09:30", "16:00")
    return (info.open_time, info.close_time)
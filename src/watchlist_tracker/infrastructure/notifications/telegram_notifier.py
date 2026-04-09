"""Telegram notification for watchlist alerts."""

from __future__ import annotations

from decimal import Decimal

from watchlist_tracker.domain.models import WatchlistSummary, TriggeredAlert, MarketData


class TelegramNotifier:
    """Send watchlist alerts via Telegram."""

    def __init__(self, bot_token: str |None = None, chat_id: str | None = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._bot = None

    def _get_bot(self):
        """Lazily initialize telegram bot."""
        if self._bot is None and self.bot_token:
            import telegram
            self._bot = telegram.Bot(token=self.bot_token)
        return self._bot

    def format_summary(self, summary: WatchlistSummary) -> str:
        """Format watchlist summary for Telegram."""
        lines = ["📊 **Watchlist Summary**\n"]

        # US Stocks
        us_stocks = summary.us_stocks
        if us_stocks:
            lines.append("🇺🇸 **US Stocks**")
            for entry in us_stocks:
                data = summary.market_data.get(entry.symbol)
                if data:
                    change_emoji = "🟢" if data.change >= 0 else "🔴"
                    lines.append(
                        f"  {change_emoji} **{entry.symbol}** ${float(data.price):.2f} "
                        f"({ float(data.change_pct):+.2f }%)"
                    )
                else:
                    lines.append(f" ⚠️{ entry.symbol} - No data")

            lines.append("")

        # India Stocks
        india_stocks = summary.india_stocks
        if india_stocks:
            lines.append("🇮🇳 **India Stocks**")
            for entry in india_stocks:
                data = summary.market_data.get(entry.symbol)
                if data:
                    change_emoji = "🟢" if data.change >= 0 else "🔴"
                    lines.append(
                        f"  {change_emoji} **{entry.symbol}** ₹{ float(data.price):.2f} "
                        f"({ float(data.change_pct):+.2f}%)"
                    )
                else:
                    lines.append(f"  ⚠️ {entry.symbol} - No data")

            lines.append("")

        #Alerts
        if summary.triggered_alerts:
            lines.append("⚠️ **Alerts Triggered**")
            for alert in summary.triggered_alerts:
                lines.append(f"  • {alert.message}")
            lines.append("")

        # Indicators
        lines.append("📈 **Key Indicators**")
        for entry in summary.entries[:5]:  # Top 5
            data = summary.market_data.get(entry.symbol)
            if data and data.indicators:
                rsi = data.indicators.get("rsi_14")
                if rsi:
                    rsi_status = "overbought" if rsi > 70 else "oversold" if rsi < 30 else ""
                    lines.append(f"  {entry.symbol}: RSI={ rsi:.1f}{ '⚠️ ' + rsi_status if rsi_status else ''}")

        lines.append(f"\n_Updated: {summary.last_updated.strftime('%Y-%m-%d %H:%M')} UTC_")
        return "\n".join(lines)

    async def send_summary(self, summary: WatchlistSummary) -> bool:
        """Send watchlist summary to Telegram."""
        if not self.bot_token or not self.chat_id:
            print("Telegram not configured, skipping notification")
            return False

        bot = self._get_bot()
        if not bot:
            return False

        message = self.format_summary(summary)
        try:
            async with bot:
                await bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode="Markdown",
                )
            return True
        except Exception as e:
            print(f"Failed to send Telegram message: {e}")
            return False

    def format_alert(self, alert: TriggeredAlert) -> str:
        """Format a single alert for Telegram."""
        emoji = {
            "price_above": "📈",
            "price_below": "📉",
            "rsi_oversold": "🔵",
            "rsi_overbought": "🔴",
            "ema_crossover_bullish": "🟢",
            "ema_crossover_bearish": "🔴",
            "volume_surge": "📊",
        }.get(alert.alert.type.value, "⚠️")

        return f"{emoji} **{alert.entry_id}**: {alert.message}"
"""Command-line interface for watchlist tracker."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from watchlist_tracker.domain.models import Market, WatchlistEntry, AlertSpec, AlertType
from watchlist_tracker.domain.markets import MARKETS
from watchlist_tracker.infrastructure.database import WatchlistStore
from watchlist_tracker.infrastructure.providers.yfinance_provider import YFinanceProvider
from watchlist_tracker.application.services import WatchlistService, MonitoringService

app = typer.Typer(help="Personal stock watchlist tracker")
console = Console()

# Default paths
DEFAULT_DB_PATH = Path.home() / ".watchlist_tracker" / "watchlist.json"


def get_store() -> WatchlistStore:
    """Get the watchlist store."""
    return WatchlistStore(DEFAULT_DB_PATH)


def get_services():
    """Get all services."""
    store = get_store()
    provider = YFinanceProvider()
    return WatchlistService(store), MonitoringService(store, provider), store


@app.command()
def add(
    symbol: Annotated[str, typer.Argument(help="Stock symbol (e.g., AAPL, RELIANCE)")],
    market: Annotated[str, typer.Option("--market", "-m", help="Market: us or india")] = "us",
    name: Annotated[str, typer.Option("--name", "-n", help="Company name")] = "",
    tags: Annotated[str | None, typer.Option("--tags", "-t", help="Comma-separated tags")] = None,
    notes: Annotated[str | None, typer.Option("--notes", help="Notes about this stock")] = None,
):
    """Add a stock to the watchlist."""
    watchlist_svc, _, _ = get_services()

    try:
        market_enum = Market(market.lower())
    except ValueError:
        console.print(f"[red]Invalid market '{market}'. Use 'us' or 'india'.[/red]")
        raise typer.Exit(1)

    tags_list = [t.strip() for t in tags.split(",")] if tags else []

    entry = watchlist_svc.add(
        symbol=symbol,
        market=market_enum.value,
        name=name,
        tags=tags_list,
        notes=notes or "",
    )

    console.print(f"[green]✓ Added {symbol} to {market} watchlist[/green]")
    console.print(f"Use `watchlist alerts add {symbol} --type price_above --value 150` to add alerts")


@app.command()
def remove(
    symbol: Annotated[str, typer.Argument(help="Stock symbol to remove")],
):
    """Remove a stock from the watchlist."""
    watchlist_svc, _, _ = get_services()

    if watchlist_svc.remove(symbol):
        console.print(f"[green]✓ Removed {symbol} from watchlist[/green]")
    else:
        console.print(f"[yellow]⚠ {symbol} not found in watchlist[/yellow]")


@app.command("list")
def list_entries(
    market: Annotated[str | None, typer.Option("--market", "-m", help="Filter by market")] = None,
    show_indicators: Annotated[bool, typer.Option("--indicators", "-i", help="Show indicators")] = False,
):
    """List all watchlist entries with current prices."""
    _, monitor_svc, _ = get_services()

    entries = monitor_svc.store.get_all_entries()
    if not entries:
        console.print("[yellow]No stocks in watchlist. Add with `watchlist add SYMBOL`[/yellow]")
        return

    # Filter by market
    if market:
        entries = [e for e in entries if e.market.value == market.lower()]

    # Fetch prices
    market_data = monitor_svc.fetch_all_prices()

    # Create table
    table = Table(title="📊 Watchlist", show_header=True, header_style="bold cyan")
    table.add_column("Symbol", style="bold")
    table.add_column("Market")
    table.add_column("Price", justify="right")
    table.add_column("Change", justify="right")
    table.add_column("Tags")
    if show_indicators:
        table.add_column("RSI", justify="right")
        table.add_column("EMA 21", justify="right")

    for entry in entries:
        data = market_data.get(entry.symbol)
        indicators = {}

        if data:
            if show_indicators:
                indicators = monitor_svc.calculate_indicators(entry.symbol, entry.market)
                data.indicators = indicators

            change_emoji = "🟢" if data.change >= 0 else "🔴"
            change_str = f"{change_emoji} {float(data.change_pct):+.2f}%"

            row = [
                entry.symbol,
                entry.market.value.upper(),
                f"${float(data.price):.2f}" if entry.market == Market.US else f"₹{float(data.price):.2f}",
                change_str,
                ", ".join(entry.tags[:2]) if entry.tags else "-",
            ]

            if show_indicators:
                rsi = indicators.get("rsi_14", 0)
                rsi_str = f"{rsi:.1f}" if rsi else "-"
                ema21 = indicators.get("ema_21", 0)
                ema_str = f"{ema21:.2f}" if ema21 else "-"
                row.extend([rsi_str, ema_str])

            table.add_row(*row)
        else:
            row = [entry.symbol, entry.market.value.upper(), "N/A", "N/A", "-"]
            if show_indicators:
                row.extend(["-", "-"])
            table.add_row(*row)

    console.print(table)


@app.command()
def alerts(
    symbol: Annotated[str | None, typer.Argument(help="Stock symbol")] = None,
    fired: Annotated[bool, typer.Option("--fired", "-f", help="Show recently fired alerts")] = False,
    add_type: Annotated[str | None, typer.Option("--add-type", help="Add alert: price_above, price_below, rsi_oversold, rsi_overbought")] = None,
    value: Annotated[float | None, typer.Option("--value", "-v", help="Alert value")] = None,
):
    """Manage alerts for watchlist entries."""
    _, _, store = get_services()

    if fired:
        # Show recent fired alerts
        recent = store.get_recent_alerts(hours=24)
        if not recent:
            console.print("[yellow]No alerts fired in last 24 hours[/yellow]")
            return

        table = Table(title="⚠️ Recent Alerts", show_header=True)
        table.add_column("Symbol", style="bold")
        table.add_column("Type")
        table.add_column("Message")
        table.add_column("Time")

        for alert in recent[-10:]:  # Last 10
            table.add_row(
                alert.get("entry_id", "?"),
                alert.get("type", "?"),
                alert.get("message", ""),
                alert.get("timestamp", "")[:16],
            )

        console.print(table)
        return

    if add_type and symbol and value:
        # Add alert to entry
        entry = store.get_entry(symbol)
        if not entry:
            console.print(f"[red]✗ {symbol} not in watchlist[/red]")
            raise typer.Exit(1)

        try:
            alert_type = AlertType(add_type)
        except ValueError:
            console.print(f"[red]Invalid alert type. Use: price_above, price_below, rsi_oversold, rsi_overbought[/red]")
            raise typer.Exit(1)

        alert = AlertSpec(type=alert_type, value=value)
        entry.alerts.append(alert)

        # Update entry
        store.update_entry(symbol, {"alerts": [a.model_dump() for a in entry.alerts]})
        console.print(f"[green]✓ Added {add_type} alert for {symbol} at {value}[/green]")
        return

    # List all configured alerts
    entries = store.get_all_entries()
    if not entries:
        console.print("[yellow]No stocks in watchlist[/yellow]")
        return

    table = Table(title="🔔 Configured Alerts", show_header=True)
    table.add_column("Symbol", style="bold")
    table.add_column("Alert Type")
    table.add_column("Value")
    table.add_column("Cooldown")

    for entry in entries:
        for alert in entry.alerts:
            table.add_row(
                entry.symbol,
                alert.type.value,
                str(alert.value) if alert.value else "-",
                f"{alert.cooldown_hours}h",
            )

    console.print(table)


@app.command()
def summary():
    """Generate a watchlist summary (for cron jobs)."""
    _, monitor_svc, _ = get_services()

    summary_data = monitor_svc.get_summary()

    # US Stocks
    console.print("\n🇺🇸 [bold]US Stocks[/bold]")
    for entry in summary_data.us_stocks:
        data = summary_data.market_data.get(entry.symbol)
        if data:
            change_emoji = "🟢" if data.change >= 0 else "🔴"
            rsi = data.indicators.get("rsi_14", 0)
            rsi_status = "⚠️" if rsi > 70 or rsi < 30 else ""
            console.print(
                f"  {change_emoji} {entry.symbol}: ${float(data.price):.2f} "
                f"({float(data.change_pct):+.2f}%) RSI:{rsi:.1f}{rsi_status}"
            )

    # India Stocks
    console.print("\n🇮🇳 [bold]India Stocks[/bold]")
    for entry in summary_data.india_stocks:
        data = summary_data.market_data.get(entry.symbol)
        if data:
            change_emoji = "🟢" if data.change >= 0 else "🔴"
            rsi = data.indicators.get("rsi_14", 0)
            rsi_status = "⚠️" if rsi > 70 or rsi < 30 else ""
            console.print(
                f"  {change_emoji} {entry.symbol}: ₹{float(data.price):.2f} "
                f"({float(data.change_pct):+.2f}%) RSI:{rsi:.1f}{rsi_status}"
            )

    # Alerts
    if summary_data.triggered_alerts:
        console.print("\n⚠️ [bold red]Alerts Triggered[/bold red]")
        for alert in summary_data.triggered_alerts:
            console.print(f"  • {alert.message}")

    console.print(f"\n[dim]Updated: {summary_data.last_updated.strftime('%Y-%m-%d %H:%M')}[/dim]")


@app.command()
def init():
    """Initialize watchlist with default stocks."""
    _, _, store = get_services()

    default_us = [
        ("AAPL", "Apple Inc."),
        ("TSLA", "Tesla Inc."),
        ("DOCN", "DigitalOcean Holdings, Inc."),
        ("NET", "Cloudflare, Inc."),
        ("NVDA", "NVIDIA Corporation"),
        ("GOOGL", "Alphabet Inc."),
        ("AMZN", "Amazon.com, Inc."),
        ("NBIS", "NeuroBio Infosys"),
    ]

    default_india = [
        ("EICHERMOT", "Eicher Motors Ltd."),
        ("RELIANCE", "Reliance Industries Ltd."),
        ("CPSEETF", "CPSE ETF"),
    ]

    console.print("[cyan]Adding US stocks...[/cyan]")
    for symbol, name in default_us:
        if not store.get_entry(symbol):
            entry = WatchlistEntry(
                symbol=symbol,
                exchange="NASDAQ" if symbol not in ["DOCN"] else "NYSE",
                name=name,
                market=Market.US,
            )
            store.add_entry(entry)
            console.print(f"  ✓ {symbol}")

    console.print("[cyan]Adding India stocks...[/cyan]")
    for symbol, name in default_india:
        if not store.get_entry(symbol):
            entry = WatchlistEntry(
                symbol=symbol,
                exchange="NSE",
                name=name,
                market=Market.INDIA,
            )
            store.add_entry(entry)
            console.print(f" ✓ {symbol}")

    console.print("[green]✓ Watchlist initialized![/green]")
    console.print("Run `watchlist list --indicators` to see current prices")


def main():
    app()


if __name__ == "__main__":
    main()
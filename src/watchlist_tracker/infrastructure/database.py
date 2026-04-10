"""Database layer using TinyDB."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from tinydb import TinyDB, Query

from watchlist_tracker.domain.models import WatchlistEntry, Market, TriggeredAlert


class WatchlistStore:
    """TinyDB-backed storage for watchlist entries."""

    def __init__(self, db_path: Path | str |None = None):
        if db_path is None:
            db_path = Path.home() / ".watchlist_tracker" / "watchlist.json"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: TinyDB | None = None

    @property
    def db(self) -> TinyDB:
        if self._db is None:
            self._db = TinyDB(self.db_path)
        return self._db

    @property
    def entries_table(self):
        return self.db.table("entries")

    @property
    def alerts_table(self):
        return self.db.table("alerts")


    # === Watchlist CRUD ===

    def add_entry(self, entry: WatchlistEntry) -> str:
        """Add a new watchlist entry. Returns entry ID."""
        entry_dict = entry.model_dump()
        entry_dict["added_date"] = entry.added_date.isoformat()
        entry_dict["market"] = entry.market.value
        entry_id = self.entries_table.insert(entry_dict)
        return str(entry_id)

    def get_entry(self, symbol: str) -> WatchlistEntry | None:
        """Get entry by symbol."""
        Entry = Query()
        result = self.entries_table.get(Entry.symbol == symbol.upper())
        if result:
            return self._dict_to_entry(result)
        return None

    def get_all_entries(self) -> list[WatchlistEntry]:
        """Get all watchlist entries."""
        return [self._dict_to_entry(e) for e in self.entries_table.all()]

    def update_entry(self, symbol: str, updates: dict[str, Any]) -> bool:
        """Update an entry."""
        Entry = Query()
        # TinyDB update returns number of documents updated
        result = self.entries_table.update(updates, Entry.symbol == symbol.upper())
        return len(result) > 0 if isinstance(result, list) else result > 0

    def remove_entry(self, symbol: str) -> bool:
        """Remove an entry from watchlist."""
        Entry = Query()
        return self.entries_table.remove(Entry.symbol == symbol.upper()) > 0

    # === Alert History===

    def log_alert(self, alert: TriggeredAlert) -> None:
        """Log a triggered alert."""
        alert_dict = alert.model_dump()
        alert_dict["timestamp"] = alert.timestamp.isoformat()
        self.alerts_table.insert(alert_dict)

    def get_last_alert(self, entry_id: str, alert_type: str) -> datetime | None:
        """Get last alert timestamp for cooldown check."""
        Alert = Query()
        results = self.alerts_table.search(
            (Alert.entry_id == entry_id) & (Alert.type == alert_type)
        )
        if results:
            timestamps = [r.get("timestamp") for r in results if r.get("timestamp")]
            if timestamps:
                return datetime.fromisoformat(max(timestamps))
        return None

    def get_recent_alerts(self, hours: int = 24) -> list[dict]:
        """Get alerts from last N hours."""
        cutoff = datetime.now().timestamp() - (hours * 3600)
        Alert = Query()
        return self.alerts_table.search(Alert.timestamp >= cutoff)

    def _dict_to_entry(self, d: dict) -> WatchlistEntry:
        """Convert dict to WatchlistEntry."""
        d["market"] = Market(d.get("market", "us"))
        if "added_date" in d and isinstance(d["added_date"], str):
            d["added_date"] = datetime.fromisoformat(d["added_date"])
        if "last_checked" in d and isinstance(d["last_checked"], str):
            d["last_checked"] = datetime.fromisoformat(d["last_checked"])
        return WatchlistEntry(**{k: v for k, v in d.items() if k != "doc_id"})
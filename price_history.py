"""SQLite persistence for fetched cryptocurrency prices."""

import os
import sqlite3
from pathlib import Path

DEFAULT_DATABASE_PATH = Path(__file__).with_name("market_history.sqlite3")


def get_database_path() -> Path:
    """Return the configured SQLite path, defaulting to the project directory."""
    return Path(os.getenv("FINPILOT_DB_PATH", str(DEFAULT_DATABASE_PATH)))


def _initialize_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            price_usd REAL NOT NULL,
            fetched_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_price_history_symbol_fetched_at
        ON price_history (symbol, fetched_at DESC, id DESC)
        """
    )


def save_quotes(quotes: list[dict[str, str | float]], fetched_at: str) -> None:
    """Save a batch of quotes with one shared timestamp."""
    connection = sqlite3.connect(get_database_path())
    try:
        _initialize_schema(connection)
        with connection:
            connection.executemany(
                "INSERT INTO price_history (symbol, price_usd, fetched_at) VALUES (?, ?, ?)",
                [(quote["symbol"], quote["price"], fetched_at) for quote in quotes],
            )
    finally:
        connection.close()


def get_history(symbol: str, limit: int) -> list[dict[str, str | float | int]]:
    """Read a symbol's newest price records first."""
    connection = sqlite3.connect(get_database_path())
    connection.row_factory = sqlite3.Row
    try:
        _initialize_schema(connection)
        rows = connection.execute(
            """
            SELECT id, symbol, price_usd, fetched_at
            FROM price_history
            WHERE symbol = ?
            ORDER BY fetched_at DESC, id DESC
            LIMIT ?
            """,
            (symbol, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()

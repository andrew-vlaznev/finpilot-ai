"""SQLite persistence for fetched cryptocurrency prices."""

import os
import sqlite3
from datetime import datetime, timezone
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
        CREATE TABLE IF NOT EXISTS market_refresh_status (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            updated_at TEXT NOT NULL
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


def save_refresh(quotes: list[dict[str, str | float]]) -> str:
    """Atomically save a refresh batch and its successful-update timestamp."""
    connection = sqlite3.connect(get_database_path(), timeout=10)
    try:
        connection.execute("BEGIN IMMEDIATE")
        _initialize_schema(connection)
        updated_at = datetime.now(timezone.utc).isoformat()
        connection.executemany(
            "INSERT INTO price_history (symbol, price_usd, fetched_at) VALUES (?, ?, ?)",
            [(quote["symbol"], quote["price"], updated_at) for quote in quotes],
        )
        connection.execute(
            """
            INSERT INTO market_refresh_status (id, updated_at) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (updated_at,),
        )
        connection.commit()
        return updated_at
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_status() -> dict[str, str | int | None]:
    """Return the last committed refresh timestamp and total history row count."""
    connection = sqlite3.connect(get_database_path(), timeout=10)
    try:
        _initialize_schema(connection)
        row = connection.execute(
            "SELECT updated_at FROM market_refresh_status WHERE id = 1"
        ).fetchone()
        count = connection.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        return {"last_updated_at": row[0] if row else None, "history_records": count}
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

"""SQLite persistence for the educational portfolio's individual positions."""

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal

import price_history


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(price_history.get_database_path())
    connection.row_factory = sqlite3.Row
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                quantity TEXT NOT NULL,
                purchase_price TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        return connection
    except Exception:
        connection.close()
        raise


def _position_from_row(row: sqlite3.Row) -> dict[str, int | str | Decimal]:
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "quantity": Decimal(row["quantity"]),
        "purchase_price": Decimal(row["purchase_price"]),
        "created_at": row["created_at"],
    }


def create_position(
    symbol: str, quantity: Decimal, purchase_price: Decimal
) -> dict[str, int | str | Decimal]:
    connection = _connect()
    try:
        created_at = datetime.now(timezone.utc).isoformat()
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO portfolio_positions
                    (symbol, quantity, purchase_price, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    symbol.upper(),
                    format(quantity, "f"),
                    format(purchase_price, "f"),
                    created_at,
                ),
            )
        return {
            "id": cursor.lastrowid,
            "symbol": symbol.upper(),
            "quantity": quantity,
            "purchase_price": purchase_price,
            "created_at": created_at,
        }
    finally:
        connection.close()


def list_positions() -> list[dict[str, int | str | Decimal]]:
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT id, symbol, quantity, purchase_price, created_at
            FROM portfolio_positions
            ORDER BY id
            """
        ).fetchall()
        return [_position_from_row(row) for row in rows]
    finally:
        connection.close()


def get_position(position_id: int) -> dict[str, int | str | Decimal] | None:
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT id, symbol, quantity, purchase_price, created_at
            FROM portfolio_positions
            WHERE id = ?
            """,
            (position_id,),
        ).fetchone()
        return _position_from_row(row) if row else None
    finally:
        connection.close()


def delete_position(position_id: int) -> bool:
    connection = _connect()
    try:
        with connection:
            cursor = connection.execute(
                "DELETE FROM portfolio_positions WHERE id = ?",
                (position_id,),
            )
        return cursor.rowcount > 0
    finally:
        connection.close()

import json
import logging
import math
import os
import sqlite3
import socket
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException, Query

import price_history

app = FastAPI(title="FinPilot AI")
logger = logging.getLogger(__name__)

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "DOGE": "dogecoin",
}
REQUEST_TIMEOUT_SECONDS = 5


def fetch_market_prices() -> list[dict[str, str | float]]:
    """Fetch BTC and ETH prices in USD from CoinGecko's Demo API."""
    api_key = os.getenv("COINGECKO_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="CoinGecko API key is not configured",
        )

    params = urlencode({"ids": ",".join(COINGECKO_IDS.values()), "vs_currencies": "usd"})
    request = Request(
        f"{COINGECKO_URL}?{params}",
        headers={"x-cg-demo-api-key": api_key, "Accept": "application/json"},
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, socket.timeout):
        raise HTTPException(
            status_code=504,
            detail="CoinGecko request timed out",
        ) from None
    except HTTPError as exc:
        if exc.code in (401, 403):
            detail = f"CoinGecko authentication failed (HTTP {exc.code})"
        elif exc.code == 429:
            detail = "CoinGecko rate limit exceeded (HTTP 429)"
        else:
            detail = f"CoinGecko returned HTTP {exc.code}"
        raise HTTPException(
            status_code=502,
            detail=detail,
        ) from None
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise HTTPException(
                status_code=504,
                detail="CoinGecko request timed out",
            ) from None
        raise HTTPException(
            status_code=502,
            detail="Could not connect to CoinGecko",
        ) from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=502,
            detail="CoinGecko returned an invalid response",
        ) from None

    try:
        assets = []
        for symbol, coin_id in COINGECKO_IDS.items():
            price = payload[coin_id]["usd"]
            if isinstance(price, bool) or not isinstance(price, (int, float)):
                raise ValueError("Price must be numeric")
            if not math.isfinite(price):
                raise ValueError("Price must be finite")
            assets.append({"symbol": symbol, "price": price})
        return assets
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=502,
            detail="CoinGecko returned an invalid response",
        ) from None


def refresh_market_data(require_persistence: bool = True) -> dict[str, object]:
    """Fetch prices and persist them, optionally keeping quotes on storage failure."""
    assets = fetch_market_prices()
    try:
        updated_at = price_history.save_refresh(assets)
    except sqlite3.Error:
        if require_persistence:
            raise
        logger.warning("Could not save market quotes to SQLite price history")
        updated_at = datetime.now(timezone.utc).isoformat()
    return {"assets": assets, "updated_at": updated_at}


@app.get("/")
def root():
    return {
        "message": "FinPilot AI API is running!",
        "status": "ok",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/market")
def market_data(asset: str | None = None):
    if asset is not None and asset.upper() not in COINGECKO_IDS:
        raise HTTPException(
            status_code=404,
            detail=f"Asset '{asset}' was not found",
        )

    refreshed = refresh_market_data(require_persistence=False)
    assets = refreshed["assets"]
    updated_at = refreshed["updated_at"]

    if asset is not None:
        assets = [item for item in assets if item["symbol"] == asset.upper()]

    return {
        "market": "crypto",
        "assets": assets,
        "source": "CoinGecko",
        "updated_at": updated_at,
    }


@app.post("/market/refresh")
def refresh_market():
    try:
        refreshed = refresh_market_data()
    except sqlite3.Error:
        raise HTTPException(
            status_code=503,
            detail="Market refresh could not be saved",
        ) from None

    return {
        "status": "updated",
        "assets": refreshed["assets"],
        "updated_at": refreshed["updated_at"],
    }


@app.get("/market/status")
def market_status():
    try:
        status = price_history.get_status()
    except sqlite3.Error:
        raise HTTPException(
            status_code=503,
            detail="Market status is temporarily unavailable",
        ) from None
    return status


@app.get("/market/history/{symbol}")
def market_history(symbol: str, limit: int = Query(default=100, ge=1, le=500)):
    normalized_symbol = symbol.upper()
    if normalized_symbol not in COINGECKO_IDS:
        raise HTTPException(
            status_code=404,
            detail=f"Asset '{symbol}' was not found",
        )

    try:
        history = price_history.get_history(normalized_symbol, limit)
    except sqlite3.Error:
        raise HTTPException(
            status_code=503,
            detail="Price history is temporarily unavailable",
        ) from None

    return {"symbol": normalized_symbol, "history": history}


@app.get("/market/analysis/{symbol}")
def market_analysis(symbol: str, limit: int = Query(default=100, ge=1, le=500)):
    normalized_symbol = symbol.upper()
    if normalized_symbol not in COINGECKO_IDS:
        raise HTTPException(
            status_code=404,
            detail=f"Asset '{symbol}' was not found",
        )

    try:
        history = price_history.get_history(normalized_symbol, limit)
    except sqlite3.Error:
        raise HTTPException(
            status_code=503,
            detail="Price history is temporarily unavailable",
        ) from None

    if not history:
        raise HTTPException(
            status_code=404,
            detail=f"No price history found for asset '{normalized_symbol}'",
        )

    oldest = history[-1]
    newest = history[0]
    first_price = oldest["price_usd"]
    last_price = newest["price_usd"]
    change = last_price - first_price
    change_percent = change / first_price * 100 if first_price != 0 else None

    return {
        "symbol": normalized_symbol,
        "record_count": len(history),
        "period_start": oldest["fetched_at"],
        "period_end": newest["fetched_at"],
        "first_price_usd": first_price,
        "last_price_usd": last_price,
        "min_price_usd": min(item["price_usd"] for item in history),
        "max_price_usd": max(item["price_usd"] for item in history),
        "change_usd": change,
        "change_percent": change_percent,
    }


def calculate_rsi(prices: list[float], period: int = 14) -> float | None:
    """Calculate Wilder RSI, returning None until a full period is available."""
    if len(prices) < period + 1:
        return None

    changes = [current - previous for previous, current in zip(prices, prices[1:])]
    gains = [max(change, 0) for change in changes]
    losses = [max(-change, 0) for change in changes]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period

    for gain, loss in zip(gains[period:], losses[period:]):
        average_gain = (average_gain * (period - 1) + gain) / period
        average_loss = (average_loss * (period - 1) + loss) / period

    if average_loss == 0:
        return 50.0 if average_gain == 0 else 100.0
    if average_gain == 0:
        return 0.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


@app.get("/market/indicators")
def market_indicators(
    symbol: str = Query(...),
    limit: int = Query(default=14, ge=2, le=1000),
):
    normalized_symbol = symbol.upper()
    if normalized_symbol not in COINGECKO_IDS:
        raise HTTPException(
            status_code=404,
            detail=f"Asset '{symbol}' was not found",
        )

    try:
        newest_first = price_history.get_history(normalized_symbol, limit)
    except sqlite3.Error:
        raise HTTPException(
            status_code=503,
            detail="Price history is temporarily unavailable",
        ) from None

    chronological = list(reversed(newest_first))
    prices = [record["price_usd"] for record in chronological]
    records_analyzed = len(prices)
    sma = sum(prices) / records_analyzed if records_analyzed >= 2 else None

    return {
        "symbol": normalized_symbol,
        "records_analyzed": records_analyzed,
        "sma": sma,
        "rsi": calculate_rsi(prices),
        "rsi_period": 14,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/market/signals")
def market_signals(
    limit: int = Query(default=100, ge=2, le=1000),
    threshold_percent: float = Query(default=3.0, gt=0, le=100),
):
    signals = []
    try:
        for symbol in COINGECKO_IDS:
            history = price_history.get_history(symbol, limit)
            chronological_history = list(reversed(history))
            records_analyzed = len(chronological_history)

            if not chronological_history:
                first_price = None
                last_price = None
                change_percent = None
                signal = "INSUFFICIENT_DATA"
            else:
                first_price = chronological_history[0]["price_usd"]
                last_price = chronological_history[-1]["price_usd"]
                if records_analyzed < 2 or first_price == 0:
                    change_percent = None
                    signal = "INSUFFICIENT_DATA"
                else:
                    change_percent = (last_price - first_price) / first_price * 100
                    if change_percent >= threshold_percent:
                        signal = "BUY"
                    elif change_percent <= -threshold_percent:
                        signal = "SELL"
                    else:
                        signal = "HOLD"

            signals.append(
                {
                    "symbol": symbol,
                    "signal": signal,
                    "first_price": first_price,
                    "last_price": last_price,
                    "change_percent": change_percent,
                    "records_analyzed": records_analyzed,
                }
            )
    except sqlite3.Error:
        raise HTTPException(
            status_code=503,
            detail="Price history is temporarily unavailable",
        ) from None

    return {
        "limit": limit,
        "threshold_percent": threshold_percent,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signals": signals,
    }

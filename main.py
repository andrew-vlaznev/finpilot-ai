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

    assets = fetch_market_prices()
    updated_at = datetime.now(timezone.utc).isoformat()
    try:
        price_history.save_quotes(assets, updated_at)
    except sqlite3.Error:
        logger.warning("Could not save market quotes to SQLite price history")

    if asset is not None:
        assets = [item for item in assets if item["symbol"] == asset.upper()]

    return {
        "market": "crypto",
        "assets": assets,
        "source": "CoinGecko",
        "updated_at": updated_at,
    }


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

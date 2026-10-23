# FinPilot AI

FinPilot AI is a Python pet project that combines QA automation practice with an evolving financial analytics API. The current application provides cryptocurrency quotes and stores a local price history.

## Current features

- FastAPI endpoints for health, current market data, and price history.
- BTC, ETH, SOL, and DOGE quotes in USD from the CoinGecko Demo API.
- Optional asset filtering on `GET /market`, case-insensitive for supported symbols.
- UTC `updated_at` metadata in ISO 8601 format and a `source` field in market responses.
- SQLite storage of fetched prices and their UTC timestamps.
- `GET /market/history/{symbol}` returns the latest stored records first.
- `GET /market/analysis/{symbol}` summarizes a selected window of saved prices, including its range and price change.
- `GET /market/indicators` calculates SMA and Wilder RSI from saved price history.
- `GET /market/signals` classifies recent saved price changes as simple educational signals.
- `POST /market/refresh` fetches and stores a new batch of prices; `GET /market/status` reports the last successful stored refresh and total history rows.
- A SQLite-backed educational portfolio stores individual crypto purchase positions and calculates their current value and profit or loss.
- Pytest coverage using mocked CoinGecko responses and a temporary SQLite database.

## Technology

- Python 3.10+
- FastAPI and Uvicorn
- SQLite via Python's built-in `sqlite3` module
- Pytest
- Git and GitHub

## Setup and local run

Create and activate a virtual environment on macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Set a CoinGecko Demo API key in the current shell. Do not put a real key in source code or commit it:

```bash
export COINGECKO_API_KEY="your-demo-api-key"
```

Start the API:

```bash
python -m uvicorn main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Interactive API documentation is available at `/docs`.

The SQLite database defaults to `market_history.sqlite3` in the project directory. Set `FINPILOT_DB_PATH` to use another path:

```bash
mkdir -p "$PWD/data"
export FINPILOT_DB_PATH="$PWD/data/market_history.sqlite3"
```

## API examples

### Health check

```bash
curl http://127.0.0.1:8000/health
```

```json
{"status":"healthy"}
```

### Current market data

```bash
curl http://127.0.0.1:8000/market
```

Prices vary with the market; this example shows the response shape:

```json
{
  "market": "crypto",
  "assets": [
    {"symbol": "BTC", "price": 65000.0},
    {"symbol": "ETH", "price": 3200.0},
    {"symbol": "SOL", "price": 150.0},
    {"symbol": "DOGE", "price": 0.2}
  ],
  "source": "CoinGecko",
  "updated_at": "2026-10-21T12:00:00+00:00"
}
```

### Filter by asset

```bash
curl "http://127.0.0.1:8000/market?asset=BTC"
```

The response keeps the same metadata and includes only the requested asset in `assets`:

```json
{
  "market": "crypto",
  "assets": [{"symbol": "BTC", "price": 65000.0}],
  "source": "CoinGecko",
  "updated_at": "2026-10-21T12:00:00+00:00"
}
```

### Read stored price history

```bash
curl "http://127.0.0.1:8000/market/history/BTC?limit=100"
```

`limit` defaults to 100 and accepts values from 1 to 500. Supported symbols are case-insensitive; an unknown symbol returns 404.

```json
{
  "symbol": "BTC",
  "history": [
    {
      "id": 1,
      "symbol": "BTC",
      "price_usd": 65000.0,
      "fetched_at": "2026-10-21T12:00:00+00:00"
    }
  ]
}
```

### Analyze stored market prices

```bash
curl "http://127.0.0.1:8000/market/analysis/BTC?limit=100"
```

`limit` defaults to 100 and accepts values from 1 to 500. The analysis uses up to that many latest records; `period_start` and `period_end` show the oldest and newest timestamps in the selected window. The change values compare the oldest selected price with the newest. If the initial price is zero, `change_percent` is `null` because a percentage change cannot be calculated.

```json
{
  "symbol": "BTC",
  "record_count": 3,
  "period_start": "2026-10-19T12:00:00+00:00",
  "period_end": "2026-10-21T12:00:00+00:00",
  "first_price_usd": 64000.0,
  "last_price_usd": 65000.0,
  "min_price_usd": 63500.0,
  "max_price_usd": 65000.0,
  "change_usd": 1000.0,
  "change_percent": 1.5625
}
```

Supported symbols are case-insensitive. Unknown symbols and assets without stored history return 404; a `limit` outside 1–500 returns 422.

### Technical indicators

```bash
curl "http://127.0.0.1:8000/market/indicators?symbol=BTC&limit=14"
```

`symbol` must be one of BTC, ETH, SOL, or DOGE. `limit` defaults to 14 and accepts values from 2 to 1000. The endpoint reads the latest selected records in chronological order and does not fetch or save prices.

- **SMA** is the arithmetic mean of the available selected prices. It is `null` when fewer than two records are available.
- **RSI** uses Wilder's smoothing with a 14-change period. It is `null` until at least 15 prices are available. RSI is 100 when there are gains and no losses, 0 when there are losses and no gains, and 50 when prices are unchanged throughout.

The timestamp reflects when the indicator response was generated. These indicators are educational analysis, not a guarantee of future market movement or investment advice.

```json
{
  "symbol": "BTC",
  "records_analyzed": 14,
  "sma": 67500.25,
  "rsi": null,
  "rsi_period": 14,
  "updated_at": "2026-10-21T12:00:00+00:00"
}
```

### Educational market signals

```bash
curl "http://127.0.0.1:8000/market/signals?limit=100&threshold_percent=3"
```

The endpoint analyzes the latest records for BTC, ETH, SOL, and DOGE. `limit` defaults to 100 and must be from 2 to 1000. `threshold_percent` defaults to 3.0 and must be greater than 0 and no more than 100. It reads history only and does not add records.

- `BUY`: the change from the oldest to the newest selected price is at least the positive threshold.
- `SELL`: the change is at most the negative threshold.
- `HOLD`: the change is between the thresholds.
- `INSUFFICIENT_DATA`: fewer than two records are available, or a percentage cannot be calculated because the first price is zero.

Signals are a simple educational heuristic and are not investment advice or a recommendation.

```json
{
  "limit": 100,
  "threshold_percent": 3.0,
  "generated_at": "2026-10-21T12:00:00+00:00",
  "signals": [
    {
      "symbol": "BTC",
      "signal": "BUY",
      "first_price": 64000.0,
      "last_price": 66000.0,
      "change_percent": 3.125,
      "records_analyzed": 4
    },
    {
      "symbol": "ETH",
      "signal": "HOLD",
      "first_price": 3200.0,
      "last_price": 3220.0,
      "change_percent": 0.625,
      "records_analyzed": 4
    },
    {
      "symbol": "SOL",
      "signal": "SELL",
      "first_price": 150.0,
      "last_price": 145.0,
      "change_percent": -3.3333333333333335,
      "records_analyzed": 4
    },
    {
      "symbol": "DOGE",
      "signal": "INSUFFICIENT_DATA",
      "first_price": null,
      "last_price": null,
      "change_percent": null,
      "records_analyzed": 0
    }
  ]
}
```

### Refresh market data

```bash
curl -X POST http://127.0.0.1:8000/market/refresh
```

The endpoint fetches current prices and stores all four assets with one shared UTC timestamp. Repeated calls append new history records.

```json
{
  "status": "updated",
  "assets": [
    {"symbol": "BTC", "price": 65000.0},
    {"symbol": "ETH", "price": 3200.0},
    {"symbol": "SOL", "price": 150.0},
    {"symbol": "DOGE", "price": 0.2}
  ],
  "updated_at": "2026-10-21T12:00:00+00:00"
}
```

If CoinGecko or SQLite fails, the endpoint returns an error and does not report a successful update.

### Market refresh status

```bash
curl http://127.0.0.1:8000/market/status
```

```json
{
  "last_updated_at": "2026-10-21T12:00:00+00:00",
  "history_records": 4
}
```

Before the first successful refresh, `last_updated_at` is `null` and `history_records` is `0`.

### Educational portfolio

Create a position with `POST /portfolio/positions`:

```bash
curl -X POST http://127.0.0.1:8000/portfolio/positions \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"BTC","quantity":0.25,"purchase_price":60000}'
```

Each request creates a separate position; purchases of the same asset are not combined. Symbols are normalized to uppercase and must be BTC, ETH, SOL, or DOGE. Quantity and purchase price must be positive.

```json
{
  "id": 1,
  "symbol": "BTC",
  "quantity": 0.25,
  "purchase_price": 60000,
  "created_at": "2026-10-21T12:00:00+00:00"
}
```

Use `GET /portfolio` for a valuation summary, `GET /portfolio/positions/{position_id}` to read one position, and `DELETE /portfolio/positions/{position_id}` to remove one. Deleting a position does not affect market history or other positions.

```bash
curl http://127.0.0.1:8000/portfolio
curl http://127.0.0.1:8000/portfolio/positions/1
curl -X DELETE http://127.0.0.1:8000/portfolio/positions/1
```

The summary fetches all supported market prices in one request and does not write those quotes to market history. If price retrieval fails or an asset price is missing, that position's current price, current value, and profit/loss fields are `null`. `total_purchase_value` includes every position. `total_current_value` and `total_profit_loss` include only positions with available prices; the total percentage uses only the purchase value of those priced positions, or is `null` when none can be valued. An empty portfolio returns zero totals, zero positions, and a `null` total percentage.

Example summary for one position:

```json
{
  "positions": [
    {
      "id": 1,
      "symbol": "BTC",
      "quantity": 0.25,
      "purchase_price": 60000,
      "purchase_value": 15000,
      "current_price": 65000,
      "current_value": 16250,
      "profit_loss": 1250,
      "profit_loss_percent": 8.333333333333334,
      "created_at": "2026-10-21T12:00:00+00:00"
    }
  ],
  "total_purchase_value": 15000,
  "total_current_value": 16250,
  "total_profit_loss": 1250,
  "total_profit_loss_percent": 8.333333333333334,
  "positions_count": 1,
  "generated_at": "2026-10-21T12:00:05+00:00"
}
```

The portfolio is an educational local feature. These endpoints do not implement authentication or protect one user's positions from another user with access to the service. They do not place trades or connect to an exchange.

## Tests

Run the automated tests from the activated virtual environment:

```bash
python -m pytest -v
```

Tests mock CoinGecko requests and use temporary SQLite files, so they do not require a real API key or external API calls.

## Continuous integration

GitHub Actions runs the test suite on pushes to `main` and pull requests targeting `main`. The workflow uses the latest available patch release of Python 3.12, installs packages from `requirements.txt`, and runs `python -m pytest -v`. Tests use mocked CoinGecko responses and do not need an API key or network access to CoinGecko.

## Security

- Keep `COINGECKO_API_KEY` in the process environment; never commit the key.
- `.env` and the default `market_history.sqlite3` database are excluded by `.gitignore`.
- The API key is not stored in SQLite.

## Roadmap

These are future ideas and are not implemented in the current application:

- Advanced market analytics and additional derived indicators.
- AI agents for financial data analysis.
- MCP integration.
- Broader QA automation, including additional API and data-layer scenarios.

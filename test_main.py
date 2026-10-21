
import io
import json
import sqlite3
import socket
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError

import pytest

from fastapi.testclient import TestClient

import main
import price_history
from main import app

client = TestClient(app)

TEST_ASSETS = [
    {"symbol": "BTC", "price": 65000},
    {"symbol": "ETH", "price": 3200},
    {"symbol": "SOL", "price": 150},
    {"symbol": "DOGE", "price": 0.2},
]


@pytest.fixture(autouse=True)
def use_temporary_database(tmp_path, monkeypatch):
    monkeypatch.setenv("FINPILOT_DB_PATH", str(tmp_path / "price-history.sqlite3"))


def fake_prices(monkeypatch):
    monkeypatch.setattr(main, "fetch_market_prices", lambda: TEST_ASSETS.copy())


def assert_market_metadata(data):
    assert data["source"] == "CoinGecko"
    updated_at = datetime.fromisoformat(data["updated_at"])
    assert updated_at.tzinfo is not None
    assert updated_at.utcoffset() == timezone.utc.utcoffset(updated_at)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_root():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_market_data(monkeypatch):
    fake_prices(monkeypatch)
    response = client.get("/market")

    assert response.status_code == 200
    data = response.json()
    assert data["market"] == "crypto"
    assert_market_metadata(data)
    assert {asset["symbol"]: asset["price"] for asset in data["assets"]} == {
        "BTC": 65000,
        "ETH": 3200,
        "SOL": 150,
        "DOGE": 0.2,
    }


def test_market_saves_all_quotes_with_shared_timestamp(monkeypatch):
    fake_prices(monkeypatch)

    response = client.get("/market?asset=BTC")

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["assets"] == [{"symbol": "BTC", "price": 65000}]
    histories = {
        symbol: price_history.get_history(symbol, limit=10)
        for symbol in ("BTC", "ETH", "SOL", "DOGE")
    }
    assert all(len(records) == 1 for records in histories.values())
    assert {
        records[0]["fetched_at"] for records in histories.values()
    } == {response_data["updated_at"]}
    assert {
        symbol: records[0]["price_usd"] for symbol, records in histories.items()
    } == {asset["symbol"]: asset["price"] for asset in TEST_ASSETS}


def test_history_table_has_expected_columns_and_index():
    database_path = price_history.get_database_path()
    price_history.get_history("BTC", limit=1)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(price_history)")
        }
        indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(price_history)")
        }

    assert columns == {"id", "symbol", "price_usd", "fetched_at"}
    assert "idx_price_history_symbol_fetched_at" in indexes


def test_market_history_returns_newest_first(monkeypatch):
    price_history.save_quotes([{"symbol": "BTC", "price": 1}], "2026-01-01T00:00:00+00:00")
    price_history.save_quotes([{"symbol": "BTC", "price": 2}], "2026-01-02T00:00:00+00:00")
    price_history.save_quotes([{"symbol": "BTC", "price": 3}], "2026-01-03T00:00:00+00:00")

    response = client.get("/market/history/BTC")

    assert response.status_code == 200
    assert response.json()["symbol"] == "BTC"
    assert [item["price_usd"] for item in response.json()["history"]] == [3, 2, 1]


def test_market_history_respects_limit():
    for price, day in ((1, "01"), (2, "02"), (3, "03")):
        price_history.save_quotes(
            [{"symbol": "ETH", "price": price}],
            f"2026-01-{day}T00:00:00+00:00",
        )

    response = client.get("/market/history/ETH?limit=2")

    assert response.status_code == 200
    assert [item["price_usd"] for item in response.json()["history"]] == [3, 2]


def test_market_history_rejects_invalid_limit():
    assert client.get("/market/history/BTC?limit=0").status_code == 422
    assert client.get("/market/history/BTC?limit=501").status_code == 422


def test_market_history_returns_404_for_unknown_symbol():
    response = client.get("/market/history/XYZ")

    assert response.status_code == 404
    assert response.json() == {"detail": "Asset 'XYZ' was not found"}


def test_market_still_returns_quotes_when_history_save_fails(monkeypatch, caplog):
    fake_prices(monkeypatch)

    def fail_to_save(*_args, **_kwargs):
        raise sqlite3.OperationalError("database failure at /private/secret-path")

    monkeypatch.setattr(main.price_history, "save_quotes", fail_to_save)

    response = client.get("/market")

    assert response.status_code == 200
    assert len(response.json()["assets"]) == 4
    assert "Could not save market quotes to SQLite price history" in caplog.text
    assert "/private/secret-path" not in caplog.text


def test_market_data_for_btc(monkeypatch):
    fake_prices(monkeypatch)
    response = client.get("/market?asset=BTC")

    assert response.status_code == 200
    data = response.json()
    assert data["market"] == "crypto"
    assert data["assets"] == [{"symbol": "BTC", "price": 65000}]
    assert_market_metadata(data)


def test_market_data_for_lowercase_btc(monkeypatch):
    fake_prices(monkeypatch)
    response = client.get("/market?asset=btc")

    assert response.status_code == 200
    data = response.json()
    assert data["assets"] == [{"symbol": "BTC", "price": 65000}]
    assert_market_metadata(data)


def test_market_data_for_eth(monkeypatch):
    fake_prices(monkeypatch)
    response = client.get("/market?asset=ETH")

    assert response.status_code == 200
    data = response.json()
    assert data["market"] == "crypto"
    assert data["assets"] == [{"symbol": "ETH", "price": 3200}]
    assert_market_metadata(data)


def test_market_data_for_unknown_asset():
    response = client.get("/market?asset=XYZ")

    assert response.status_code == 404
    assert response.json() == {"detail": "Asset 'XYZ' was not found"}


def test_market_does_not_require_coin_gecko_for_unknown_asset(monkeypatch):
    def unexpected_fetch():
        raise AssertionError("CoinGecko should not be called for an unknown asset")

    monkeypatch.setattr(main, "fetch_market_prices", unexpected_fetch)
    response = client.get("/market?asset=XYZ")

    assert response.status_code == 404


def test_market_returns_service_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)

    response = client.get("/market")

    assert response.status_code == 503
    assert response.json() == {"detail": "CoinGecko API key is not configured"}


def test_fetch_market_prices_uses_demo_api_and_maps_response(monkeypatch):
    monkeypatch.setenv("COINGECKO_API_KEY", "test-key")
    response_body = json.dumps(
        {
            "bitcoin": {"usd": 65000},
            "ethereum": {"usd": 3200},
            "solana": {"usd": 150},
            "dogecoin": {"usd": 0.2},
        }
    ).encode()

    def fake_urlopen(request, timeout):
        assert request.full_url.startswith(main.COINGECKO_URL)
        assert "ids=bitcoin%2Cethereum%2Csolana%2Cdogecoin" in request.full_url
        assert "vs_currencies=usd" in request.full_url
        assert request.get_header("X-cg-demo-api-key") == "test-key"
        assert timeout == main.REQUEST_TIMEOUT_SECONDS
        return io.BytesIO(response_body)

    monkeypatch.setattr(main, "urlopen", fake_urlopen)

    assert main.fetch_market_prices() == TEST_ASSETS


def test_fetch_market_prices_handles_timeout(monkeypatch):
    monkeypatch.setenv("COINGECKO_API_KEY", "test-key")
    monkeypatch.setattr(
        main, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(socket.timeout())
    )

    try:
        main.fetch_market_prices()
    except main.HTTPException as exc:
        assert exc.status_code == 504
        assert exc.detail == "CoinGecko request timed out"
    else:
        raise AssertionError("Expected a timeout HTTP error")


def test_fetch_market_prices_handles_network_error(monkeypatch):
    monkeypatch.setenv("COINGECKO_API_KEY", "test-key")
    monkeypatch.setattr(
        main,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("offline")),
    )

    try:
        main.fetch_market_prices()
    except main.HTTPException as exc:
        assert exc.status_code == 502
        assert exc.detail == "Could not connect to CoinGecko"
    else:
        raise AssertionError("Expected a network HTTP error")


def test_fetch_market_prices_handles_invalid_response(monkeypatch):
    monkeypatch.setenv("COINGECKO_API_KEY", "test-key")
    monkeypatch.setattr(main, "urlopen", lambda *_args, **_kwargs: io.BytesIO(b"not json"))

    try:
        main.fetch_market_prices()
    except main.HTTPException as exc:
        assert exc.status_code == 502
        assert exc.detail == "CoinGecko returned an invalid response"
    else:
        raise AssertionError("Expected an invalid-response HTTP error")


@pytest.mark.parametrize(
    ("upstream_status", "expected_detail"),
    [
        (401, "CoinGecko authentication failed (HTTP 401)"),
        (403, "CoinGecko authentication failed (HTTP 403)"),
        (429, "CoinGecko rate limit exceeded (HTTP 429)"),
        (500, "CoinGecko returned HTTP 500"),
    ],
)
def test_market_reports_safe_coin_gecko_http_error(
    monkeypatch, upstream_status, expected_detail
):
    monkeypatch.setenv("COINGECKO_API_KEY", "test-key")

    def raise_http_error(*_args, **_kwargs):
        raise HTTPError(
            main.COINGECKO_URL,
            upstream_status,
            "upstream error containing secret-value",
            {"Authorization": "secret-value"},
            io.BytesIO(b"secret-value"),
        )

    monkeypatch.setattr(main, "urlopen", raise_http_error)

    response = client.get("/market")

    assert response.status_code == 502
    assert response.json() == {"detail": expected_detail}
    assert "secret-value" not in response.text

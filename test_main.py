
import io
import json
import socket
from urllib.error import URLError

from fastapi.testclient import TestClient

import main
from main import app

client = TestClient(app)

TEST_ASSETS = [
    {"symbol": "BTC", "price": 65000},
    {"symbol": "ETH", "price": 3200},
]


def fake_prices(monkeypatch):
    monkeypatch.setattr(main, "fetch_market_prices", lambda: TEST_ASSETS.copy())


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
    assert {asset["symbol"]: asset["price"] for asset in data["assets"]} == {
        "BTC": 65000,
        "ETH": 3200,
    }


def test_market_data_for_btc(monkeypatch):
    fake_prices(monkeypatch)
    response = client.get("/market?asset=BTC")

    assert response.status_code == 200
    assert response.json() == {
        "market": "crypto",
        "assets": [{"symbol": "BTC", "price": 65000}],
    }


def test_market_data_for_lowercase_btc(monkeypatch):
    fake_prices(monkeypatch)
    response = client.get("/market?asset=btc")

    assert response.status_code == 200
    assert response.json()["assets"] == [{"symbol": "BTC", "price": 65000}]


def test_market_data_for_eth(monkeypatch):
    fake_prices(monkeypatch)
    response = client.get("/market?asset=ETH")

    assert response.status_code == 200
    assert response.json() == {
        "market": "crypto",
        "assets": [{"symbol": "ETH", "price": 3200}],
    }


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
        {"bitcoin": {"usd": 65000}, "ethereum": {"usd": 3200}}
    ).encode()

    def fake_urlopen(request, timeout):
        assert request.full_url.startswith(main.COINGECKO_URL)
        assert "bitcoin%2Cethereum" in request.full_url
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

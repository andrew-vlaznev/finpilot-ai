
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_root():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_market_data():
    response = client.get("/market")

    assert response.status_code == 200
    data = response.json()
    assert data["market"] == "crypto"
    assert {asset["symbol"]: asset["price"] for asset in data["assets"]} == {
        "BTC": 65000,
        "ETH": 3200,
    }


def test_market_data_for_btc():
    response = client.get("/market?asset=BTC")

    assert response.status_code == 200
    assert response.json() == {
        "market": "crypto",
        "assets": [{"symbol": "BTC", "price": 65000}],
    }


def test_market_data_for_eth():
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

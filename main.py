
from fastapi import FastAPI

app = FastAPI(title="Market Intelligence")


@app.get("/")
def root():
    return {
        "message": "Market Intelligence API is running!",
        "status": "ok",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/market")
def market_data():
    return {
        "market": "crypto",
        "assets": [
            {"symbol": "BTC", "price": 65000},
            {"symbol": "ETH", "price": 3200},
        ],
    }

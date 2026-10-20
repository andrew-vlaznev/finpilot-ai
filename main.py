
from fastapi import FastAPI, HTTPException

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
def market_data(asset: str | None = None):
    assets = [
        {"symbol": "BTC", "price": 65000},
        {"symbol": "ETH", "price": 3200},
    ]

    if asset is not None:
        assets = [item for item in assets if item["symbol"] == asset.upper()]
        if not assets:
            raise HTTPException(
                status_code=404,
                detail=f"Asset '{asset}' was not found",
            )

    return {
        "market": "crypto",
        "assets": assets,
    }

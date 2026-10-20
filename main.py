
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

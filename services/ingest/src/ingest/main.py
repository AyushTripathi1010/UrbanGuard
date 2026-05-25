from fastapi import FastAPI

app = FastAPI(title="urbanguard-ingest")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

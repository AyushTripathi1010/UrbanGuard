from fastapi import FastAPI

app = FastAPI(title="urbanguard-gateway")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

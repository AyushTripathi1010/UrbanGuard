from fastapi import FastAPI

app = FastAPI(title="urbanguard-agents")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

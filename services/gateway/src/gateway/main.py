"""FastAPI gateway: SSE alerts + REST /alerts /heatmap /cameras."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from agents.nodes.memory import dispose_engine, init_schema
from gateway.routes import alerts, cameras, heatmap


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Best-effort schema init: if Postgres is down, the gateway still serves
    # /healthz, /metrics, and any non-DB endpoint. DB-backed routes will then
    # surface their own error per request rather than blocking app start.
    try:
        await init_schema()
    except Exception as exc:  # noqa: BLE001
        import structlog

        structlog.get_logger("gateway.lifespan").warning(
            "schema_init_skipped", error=str(exc)
        )
    yield
    try:
        await dispose_engine()
    except Exception:  # noqa: BLE001
        pass


app = FastAPI(title="urbanguard-gateway", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.include_router(alerts.router)
app.include_router(heatmap.router)
app.include_router(cameras.router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

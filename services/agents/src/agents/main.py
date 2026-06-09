"""Entry point for the agents consumer. Runnable via `python -m agents.main`."""

from __future__ import annotations

import asyncio
import logging

import structlog
from fastapi import FastAPI

from shared.observability import install_prometheus

from agents.consumer import run as run_consumer

app = FastAPI(title="urbanguard-agents")
install_prometheus(app)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
    )
    asyncio.run(run_consumer())


if __name__ == "__main__":
    main()

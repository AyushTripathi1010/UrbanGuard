"""Entry point for the detect consumer."""

from __future__ import annotations

import asyncio
import logging

import structlog

from detect.consumer import run


def main() -> None:
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()

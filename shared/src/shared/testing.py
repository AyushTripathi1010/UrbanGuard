"""Shared pytest skip markers — used by every service's integration tests.

Probes are re-evaluated at test-call time (not at module import) so a briefly
unhealthy docker stack doesn't poison the whole session. We also use a 2s
timeout because Apple Silicon docker-desktop can be slow on cold start.
"""

from __future__ import annotations

import socket
from functools import wraps

import pytest


def _port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _live_skip(host: str, port: int, label: str):
    """Return a decorator that calls pytest.skip inside the test body, so the
    probe happens when the test runs — not when pytest collects the file."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not _port_open(host, port):
                pytest.skip(f"{label} not reachable on {host}:{port} (run `make up`)")
            return fn(*args, **kwargs)

        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            if not _port_open(host, port):
                pytest.skip(f"{label} not reachable on {host}:{port} (run `make up`)")
            return await fn(*args, **kwargs)

        import inspect

        return async_wrapper if inspect.iscoroutinefunction(fn) else wrapper

    return decorator


requires_kafka = _live_skip("localhost", 9092, "kafka broker")
requires_postgres = _live_skip("localhost", 5432, "postgres")
requires_redis = _live_skip("localhost", 6379, "redis")

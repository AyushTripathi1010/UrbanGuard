"""Shared pytest skip markers — used by every service's integration tests."""

from __future__ import annotations

import socket

import pytest


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


requires_kafka = pytest.mark.skipif(
    not _port_open("localhost", 9092),
    reason="kafka broker not reachable on localhost:9092 (run `make up`)",
)

requires_postgres = pytest.mark.skipif(
    not _port_open("localhost", 5432),
    reason="postgres not reachable on localhost:5432 (run `make up`)",
)

requires_redis = pytest.mark.skipif(
    not _port_open("localhost", 6379),
    reason="redis not reachable on localhost:6379 (run `make up`)",
)

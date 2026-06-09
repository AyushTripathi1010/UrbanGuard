"""Tiny observability surface: Langfuse client + Prometheus instrumentor helper.

Everything here is best-effort. If Langfuse credentials are missing we return
a no-op client so callers can `with span(...)` unconditionally without `if`
checks scattered through the agent code.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import structlog

from shared.settings import settings

log = structlog.get_logger("shared.observability")

_langfuse_client = None
_langfuse_disabled = False


def _client() -> Any | None:
    global _langfuse_client, _langfuse_disabled
    if _langfuse_disabled:
        return None
    if _langfuse_client is not None:
        return _langfuse_client
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        _langfuse_disabled = True
        return None
    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        return _langfuse_client
    except Exception as exc:
        log.warning("langfuse.disabled", error=str(exc))
        _langfuse_disabled = True
        return None


@contextmanager
def trace(
    name: str, *, input: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None
):
    """Yield a trace handle. If Langfuse isn't configured, yields None.

    Use as::

        with trace("triage", input={"alert_id": "..."}) as t:
            result = do_work()
            if t is not None:
                t.update(output=result.model_dump())
    """
    client = _client()
    if client is None:
        yield None
        return
    try:
        t = client.trace(name=name, input=input, metadata=metadata or {})
    except Exception as exc:
        log.warning("langfuse.trace_create_failed", error=str(exc))
        yield None
        return
    try:
        yield t
    finally:
        try:
            client.flush()
        except Exception:
            pass


def install_prometheus(app, endpoint: str = "/metrics") -> None:
    """Attach Prometheus instrumentor to a FastAPI app. Safe to no-op if missing."""
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator().instrument(app).expose(app, endpoint=endpoint)
    except Exception as exc:
        log.warning("prometheus.skipped", error=str(exc))

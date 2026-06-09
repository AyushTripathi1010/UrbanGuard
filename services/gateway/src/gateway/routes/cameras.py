"""Cameras endpoint: proxy through to the ingest service."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from shared.settings import settings

router = APIRouter()


@router.get("/cameras")
async def list_cameras() -> list[dict]:
    url = f"http://localhost:{settings.ingest_port}/cameras"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(url)
        if r.status_code != 200:
            raise HTTPException(r.status_code, r.text)
        return r.json()
    except httpx.RequestError:
        return []

"""End-to-end Kafka round-trip: produce a Frame, consume it back, assert equality."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from shared import Frame, RAW_FRAMES, consumer, producer, send_model
from tests.conftest import requires_kafka


@pytest.mark.asyncio
@requires_kafka
async def test_frame_produce_consume_roundtrip() -> None:
    frame = Frame(
        frame_id=f"smoke-{uuid.uuid4().hex[:8]}",
        camera_id="cam-smoke",
        zone_id="z-smoke",
        width=320,
        height=240,
        jpeg_bytes_b64="",
    )
    group = f"smoke-{uuid.uuid4().hex[:8]}"

    async with consumer(RAW_FRAMES, group_id=group, auto_offset_reset="latest") as c:
        # consumer has to be subscribed before producing for `latest` to work
        await c.seek_to_end()

        async with producer() as p:
            await send_model(p, RAW_FRAMES, frame, key=frame.camera_id)

        record = await asyncio.wait_for(c.getone(), timeout=20.0)
        got = Frame.model_validate_json(record.value)

    assert got == frame
    assert record.key == frame.camera_id.encode("utf-8")

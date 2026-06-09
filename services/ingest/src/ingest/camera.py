"""Per-camera Kafka producer with bounded backpressure."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import structlog
from aiokafka import AIOKafkaProducer
from shared.kafka_io import send_model
from shared.settings import settings
from shared.topics import RAW_FRAMES

from ingest.video_loader import DecodedFrame, iter_clip_frames
from shared import Frame, GeoPoint

log = structlog.get_logger("ingest.camera")


@dataclass
class CameraSpec:
    camera_id: str
    zone_id: str
    clip_path: Path
    geo: GeoPoint | None = None
    target_fps: int = field(default_factory=lambda: settings.ingest_target_fps)
    queue_max: int = 8  # bounded backpressure


class CameraProducer:
    """Drains a clip through a bounded queue onto raw-frames.

    Decoupling the decode loop from the Kafka send via an `asyncio.Queue` means
    a slow broker pushes back on the decoder rather than dropping frames or
    growing memory unboundedly. The queue size is small on purpose: when the
    broker stalls we want the decode loop to actually pause.
    """

    def __init__(self, spec: CameraSpec, producer: AIOKafkaProducer) -> None:
        self.spec = spec
        self._producer = producer
        self._queue: asyncio.Queue[DecodedFrame] = asyncio.Queue(maxsize=spec.queue_max)
        self._stop = asyncio.Event()
        self._decode_task: asyncio.Task[None] | None = None
        self._send_task: asyncio.Task[None] | None = None
        self.frames_sent = 0

    async def start(self) -> None:
        if self._decode_task is not None:
            return
        self._decode_task = asyncio.create_task(
            self._decode_loop(), name=f"decode-{self.spec.camera_id}"
        )
        self._send_task = asyncio.create_task(self._send_loop(), name=f"send-{self.spec.camera_id}")
        log.info("camera.started", camera_id=self.spec.camera_id, zone=self.spec.zone_id)

    async def stop(self) -> None:
        self._stop.set()
        for t in (self._decode_task, self._send_task):
            if t is not None:
                t.cancel()
        for t in (self._decode_task, self._send_task):
            if t is not None:
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
        self._decode_task = None
        self._send_task = None
        log.info("camera.stopped", camera_id=self.spec.camera_id, sent=self.frames_sent)

    @property
    def running(self) -> bool:
        return self._decode_task is not None and not self._decode_task.done()

    async def _decode_loop(self) -> None:
        async for decoded in iter_clip_frames(
            self.spec.clip_path,
            target_fps=self.spec.target_fps,
        ):
            if self._stop.is_set():
                break
            await self._queue.put(decoded)

    async def _send_loop(self) -> None:
        try:
            while not self._stop.is_set():
                decoded = await self._queue.get()
                frame = Frame(
                    frame_id=uuid.uuid4().hex,
                    camera_id=self.spec.camera_id,
                    zone_id=self.spec.zone_id,
                    width=decoded.width,
                    height=decoded.height,
                    jpeg_bytes_b64=decoded.jpeg_b64,
                    geo=self.spec.geo,
                )
                await send_model(self._producer, RAW_FRAMES, frame, key=self.spec.camera_id)
                self.frames_sent += 1
        except asyncio.CancelledError:
            raise

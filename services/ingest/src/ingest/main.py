"""FastAPI control plane for the ingest service.

POST /cameras            — register and start a simulated camera from a clip path
DELETE /cameras/{id}     — stop a camera and detach it
GET /cameras             — list active cameras and their frame counts
GET /healthz             — liveness probe
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared import GeoPoint
from shared.observability import install_prometheus
from shared.settings import settings

from ingest.camera import CameraProducer, CameraSpec


class StartCameraRequest(BaseModel):
    camera_id: str
    zone_id: str
    clip_path: str
    geo: GeoPoint | None = None
    target_fps: int | None = None


class CameraInfo(BaseModel):
    camera_id: str
    zone_id: str
    clip_path: str
    running: bool
    frames_sent: int


_producer: AIOKafkaProducer | None = None
_cameras: dict[str, CameraProducer] = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _producer
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        enable_idempotence=True,
        acks="all",
        linger_ms=10,
        compression_type="lz4",
    )
    await _producer.start()
    try:
        yield
    finally:
        for cam in list(_cameras.values()):
            await cam.stop()
        _cameras.clear()
        await _producer.stop()
        _producer = None


app = FastAPI(title="urbanguard-ingest", lifespan=lifespan)
install_prometheus(app)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/cameras", response_model=CameraInfo, status_code=201)
async def start_camera(req: StartCameraRequest) -> CameraInfo:
    if _producer is None:
        raise HTTPException(503, "ingest producer not ready")
    if req.camera_id in _cameras:
        raise HTTPException(409, f"camera {req.camera_id} already running")
    clip = Path(req.clip_path)
    if not clip.exists():
        raise HTTPException(400, f"clip not found: {clip}")
    spec = CameraSpec(
        camera_id=req.camera_id,
        zone_id=req.zone_id,
        clip_path=clip,
        geo=req.geo,
        target_fps=req.target_fps or settings.ingest_target_fps,
    )
    cam = CameraProducer(spec, _producer)
    await cam.start()
    _cameras[req.camera_id] = cam
    return _camera_info(cam)


@app.delete("/cameras/{camera_id}", response_model=CameraInfo)
async def stop_camera(camera_id: str) -> CameraInfo:
    cam = _cameras.pop(camera_id, None)
    if cam is None:
        raise HTTPException(404, f"camera {camera_id} not running")
    await cam.stop()
    return _camera_info(cam)


@app.get("/cameras", response_model=list[CameraInfo])
async def list_cameras() -> list[CameraInfo]:
    return [_camera_info(c) for c in _cameras.values()]


def _camera_info(cam: CameraProducer) -> CameraInfo:
    return CameraInfo(
        camera_id=cam.spec.camera_id,
        zone_id=cam.spec.zone_id,
        clip_path=str(cam.spec.clip_path),
        running=cam.running,
        frames_sent=cam.frames_sent,
    )

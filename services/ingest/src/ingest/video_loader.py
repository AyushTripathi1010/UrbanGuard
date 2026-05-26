"""Read video clips off disk, decode them, and emit JPEG byte frames at the target fps."""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class DecodedFrame:
    jpeg_bytes: bytes
    width: int
    height: int

    @property
    def jpeg_b64(self) -> str:
        return base64.b64encode(self.jpeg_bytes).decode("ascii")


def _encode_jpeg(image: np.ndarray, quality: int = 80) -> bytes:
    ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("jpeg encode failed")
    return bytes(buf)


async def iter_clip_frames(
    clip_path: Path,
    target_fps: int = 2,
    jpeg_quality: int = 80,
    loop: bool = True,
) -> AsyncIterator[DecodedFrame]:
    """Yield frames decoded from `clip_path` at `target_fps`.

    The function down-samples by skipping frames; it does not interpolate. When
    `loop=True` the clip restarts from the beginning, which is what we want for
    simulated CCTV that should "always be on."
    """
    cap = cv2.VideoCapture(str(clip_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"cannot open clip: {clip_path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    skip = max(1, int(round(src_fps / max(1, target_fps))))
    idx = 0
    try:
        while True:
            ok, image = cap.read()
            if not ok:
                if not loop:
                    return
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                idx = 0
                continue
            if idx % skip == 0:
                yield DecodedFrame(_encode_jpeg(image, jpeg_quality), width, height)
            idx += 1
    finally:
        cap.release()


def synthesize_clip(
    out_path: Path,
    *,
    seconds: int = 4,
    fps: int = 30,
    width: int = 320,
    height: int = 240,
) -> Path:
    """Write a tiny synthetic mp4 used by ingest tests (no real dataset needed)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
    try:
        for i in range(seconds * fps):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            # moving rectangle so consecutive frames differ; verifies decode is sane
            x = (i * 4) % (width - 40)
            cv2.rectangle(frame, (x, 80), (x + 40, 160), (0, 200, 255), -1)
            cv2.putText(
                frame,
                f"{i:03d}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
            )
            writer.write(frame)
    finally:
        writer.release()
    return out_path

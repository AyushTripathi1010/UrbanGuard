from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from ingest.video_loader import iter_clip_frames, synthesize_clip


@pytest.fixture
def tiny_clip(tmp_path: Path) -> Path:
    return synthesize_clip(tmp_path / "tiny.mp4", seconds=2, fps=30, width=160, height=120)


async def _collect(it, n: int) -> list:
    out = []
    async for f in it:
        out.append(f)
        if len(out) >= n:
            break
    return out


def test_iter_clip_frames_downsamples_to_target_fps(tiny_clip: Path) -> None:
    frames = asyncio.run(_collect(iter_clip_frames(tiny_clip, target_fps=2, loop=False), 100))
    # 2s clip @ 30fps source, downsample to 2fps -> ~4 frames before EOF
    assert 3 <= len(frames) <= 5
    assert all(f.width == 160 and f.height == 120 for f in frames)
    assert all(f.jpeg_bytes.startswith(b"\xff\xd8") for f in frames)  # JPEG SOI marker


def test_iter_clip_frames_loops_when_loop_true(tiny_clip: Path) -> None:
    frames = asyncio.run(_collect(iter_clip_frames(tiny_clip, target_fps=2, loop=True), 12))
    assert len(frames) == 12

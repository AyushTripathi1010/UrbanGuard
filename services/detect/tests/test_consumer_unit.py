"""Unit-test the classify-and-score gate logic by mocking the heavy models."""

from __future__ import annotations

import base64
import io

from PIL import Image

from shared import Frame


def _make_frame(jpeg_quality: int = 80) -> Frame:
    img = Image.new("RGB", (160, 120), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=jpeg_quality)
    return Frame(
        frame_id="f-unit",
        camera_id="cam-unit",
        zone_id="z-unit",
        width=160,
        height=120,
        jpeg_bytes_b64=base64.b64encode(buf.getvalue()).decode("ascii"),
    )


def test_classify_and_score_returns_none_when_clip_below_threshold(monkeypatch) -> None:
    from dataclasses import dataclass

    from detect import consumer as cons

    @dataclass(frozen=True)
    class FakePred:
        label_idx: int = 3
        label: str = "normal city traffic with cars moving safely"
        score: float = 0.9
        incident_score: float = 0.1

        @property
        def is_incident(self) -> bool:
            return False

    monkeypatch.setattr(cons, "classify", lambda _img: FakePred())
    monkeypatch.setattr(cons, "score_severity", lambda _img: (0.99, True))
    out = cons._classify_and_score(_make_frame())
    assert out is None


def test_classify_and_score_returns_alert_when_both_gates_open(monkeypatch) -> None:
    from dataclasses import dataclass

    from detect import consumer as cons

    @dataclass(frozen=True)
    class FakePred:
        label_idx: int = 0
        label: str = "a road traffic accident, crash, or collision"
        score: float = 0.8
        incident_score: float = 0.92

        @property
        def is_incident(self) -> bool:
            return True

    monkeypatch.setattr(cons, "classify", lambda _img: FakePred())
    monkeypatch.setattr(cons, "score_severity", lambda _img: (0.77, True))
    alert = cons._classify_and_score(_make_frame())
    assert alert is not None
    assert alert.camera_id == "cam-unit"
    assert alert.clip_score == 0.92
    assert alert.resnet_severity == 0.77


def test_classify_and_score_drops_when_severity_below_threshold(monkeypatch) -> None:
    from dataclasses import dataclass

    from detect import consumer as cons

    @dataclass(frozen=True)
    class FakePred:
        label_idx: int = 0
        label: str = "a road traffic accident, crash, or collision"
        score: float = 0.8
        incident_score: float = 0.7

        @property
        def is_incident(self) -> bool:
            return True

    monkeypatch.setattr(cons, "classify", lambda _img: FakePred())
    monkeypatch.setattr(cons, "score_severity", lambda _img: (0.1, True))
    assert cons._classify_and_score(_make_frame()) is None

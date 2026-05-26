from __future__ import annotations

import os

import pytest
from PIL import Image

from detect.clip_classifier import INCIDENT_LABELS, PROMPTS


def test_prompt_set_shape() -> None:
    assert len(PROMPTS) == 5
    assert INCIDENT_LABELS == {0, 1, 2}
    assert all(isinstance(p, str) and p for p in PROMPTS)


@pytest.mark.skipif(os.environ.get("URBANGUARD_RUN_MODELS") != "1", reason="set URBANGUARD_RUN_MODELS=1 to download weights and run")
def test_classify_returns_valid_distribution() -> None:
    from detect.clip_classifier import classify

    image = Image.new("RGB", (640, 480), color=(80, 80, 80))
    pred = classify(image)
    assert 0.0 <= pred.score <= 1.0
    assert 0.0 <= pred.incident_score <= 1.0
    assert pred.label in PROMPTS

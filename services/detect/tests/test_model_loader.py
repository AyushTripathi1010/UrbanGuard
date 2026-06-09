from __future__ import annotations

import os

import pytest
import torch
from detect.model_loader import resolve_device


def test_resolve_device_falls_back_off_unavailable() -> None:
    # If MPS or CUDA isn't available, request them anyway and confirm CPU fallback.
    if not torch.backends.mps.is_available() and not torch.cuda.is_available():
        assert resolve_device("mps").type == "cpu"
        assert resolve_device("cuda").type == "cpu"


def test_resolve_device_explicit_cpu() -> None:
    assert resolve_device("cpu").type == "cpu"


@pytest.mark.skipif(
    os.environ.get("URBANGUARD_RUN_MODELS") != "1",
    reason="set URBANGUARD_RUN_MODELS=1 to download weights and run",
)
def test_load_resnet_scorer_outputs_in_unit_interval() -> None:
    from detect.resnet_scorer import score_severity
    from PIL import Image

    img = Image.new("RGB", (224, 224), color=(120, 120, 120))
    severity, is_finetuned = score_severity(img)
    assert 0.0 <= severity <= 1.0
    assert isinstance(is_finetuned, bool)

"""ResNet-50 severity scorer — the slow precise second stage."""

from __future__ import annotations

import torch
from PIL.Image import Image

from detect.model_loader import load_resnet_scorer, pil_to_tensor


def score_severity(image: Image) -> tuple[float, bool]:
    """Return (severity in [0,1], is_finetuned)."""
    model, device, is_finetuned = load_resnet_scorer()
    x = pil_to_tensor(image, device)
    with torch.no_grad():
        out = model(x).squeeze().cpu().item()
    return float(out), is_finetuned

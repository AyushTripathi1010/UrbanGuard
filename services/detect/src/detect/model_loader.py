"""Lazy model loaders that cache weights + the selected device."""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import TYPE_CHECKING

import torch
from shared.settings import settings

if TYPE_CHECKING:
    from PIL.Image import Image

_LOCK = threading.Lock()


def resolve_device(requested: str | None = None) -> torch.device:
    """Resolve the inference device, falling back gracefully off MPS / CUDA."""
    wanted = (requested or settings.detect_device).lower()
    if wanted == "mps" and torch.backends.mps.is_available():
        return torch.device("mps")
    if wanted == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


@lru_cache(maxsize=1)
def load_clip():
    """Load open_clip ViT-B-32 once. Returns (model, preprocess, tokenizer, device)."""
    import open_clip

    device = resolve_device()
    with _LOCK:
        model, _, preprocess = open_clip.create_model_and_transforms(
            settings.clip_model,
            pretrained=settings.clip_pretrained,
            device=str(device),
        )
        model.eval()
        tokenizer = open_clip.get_tokenizer(settings.clip_model)
    return model, preprocess, tokenizer, device


@lru_cache(maxsize=1)
def load_resnet_scorer():
    """Load the severity ResNet-50.

    Until the Colab fine-tune lands, we initialize a fresh head on top of a
    pretrained backbone and warn the caller via the `is_finetuned` flag. The
    consumer can still emit alerts; severity will just be ~0.5 placeholder.
    """
    from pathlib import Path

    import torch.nn as nn
    from torchvision.models import ResNet50_Weights, resnet50

    device = resolve_device()
    backbone = resnet50(weights=ResNet50_Weights.IMAGENET1K_V2)
    in_features = backbone.fc.in_features
    backbone.fc = nn.Sequential(
        nn.Dropout(0.2),
        nn.Linear(in_features, 1),
        nn.Sigmoid(),
    )
    is_finetuned = False
    ckpt = Path(settings.resnet_checkpoint)
    if ckpt.exists():
        state = torch.load(ckpt, map_location="cpu", weights_only=True)
        backbone.load_state_dict(state)
        is_finetuned = True
    backbone.to(device)
    backbone.eval()
    # MPS fp16 is unstable for ResNet-50 (see difficulties.md #04 if you hit NaNs);
    # we stay in fp32 on MPS. CUDA path can use fp16 if you wire it up later.
    return backbone, device, is_finetuned


def pil_to_tensor(image: Image, device: torch.device) -> torch.Tensor:
    import torchvision.transforms as T

    transform = T.Compose(
        [
            T.Resize(256),
            T.CenterCrop(224),
            T.ToTensor(),
            T.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ]
    )
    return transform(image.convert("RGB")).unsqueeze(0).to(device)

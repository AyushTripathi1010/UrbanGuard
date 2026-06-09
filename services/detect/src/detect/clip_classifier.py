"""CLIP zero-shot scene classifier — the cheap first stage of detection."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from PIL.Image import Image

from detect.model_loader import load_clip

# Ordering matters: index 0 is the "incident" class, the rest are negatives.
# Prompt phrasing tested against DoTA + Nexar val samples in notebook 03.
PROMPTS: list[str] = [
    "a road traffic accident, crash, or collision",
    "a pedestrian almost being hit by a vehicle",
    "vehicles overturned or on fire after a crash",
    "normal city traffic with cars moving safely",
    "an empty road with no incident",
]
INCIDENT_LABELS: set[int] = {0, 1, 2}


@dataclass(frozen=True)
class ClipPrediction:
    label_idx: int
    label: str
    score: float
    incident_score: float  # sum of probabilities over the incident-class indices

    @property
    def is_incident(self) -> bool:
        from shared.settings import settings

        return self.incident_score >= settings.clip_accident_threshold


def classify(image: Image) -> ClipPrediction:
    model, preprocess, tokenizer, device = load_clip()
    tokens = tokenizer(PROMPTS).to(device)
    pixel = preprocess(image).unsqueeze(0).to(device)
    with torch.no_grad():
        image_features = model.encode_image(pixel)
        text_features = model.encode_text(tokens)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        logits = (100.0 * image_features @ text_features.T).softmax(dim=-1)
    probs = logits.cpu().squeeze(0).tolist()
    incident_score = float(sum(probs[i] for i in INCIDENT_LABELS))
    best_idx = max(range(len(PROMPTS)), key=lambda i: probs[i])
    return ClipPrediction(
        label_idx=best_idx,
        label=PROMPTS[best_idx],
        score=float(probs[best_idx]),
        incident_score=incident_score,
    )

"""CLIP model loading and inference — a thin wrapper around open-clip-torch.

The model is loaded lazily and cached as a module-level singleton so that
calling ``classify_batch()`` multiple times in one session reuses the
loaded weights without re-initialising.
"""

import logging
from typing import Callable, Optional
import open_clip
import torch
from PIL import Image

logger = logging.getLogger("cull.models")


# ── Module-level caches (singleton) ──────────────────────────────────

_model: open_clip.CLIP | None = None
_tokenizer: Callable | None = None
_preprocess: Callable | None = None
_current_model_name: str | None = None
_current_pretrained: str | None = None


def _resolve_device() -> str:
    """Return the best available torch device."""
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load_model(
    model_name: str = "ViT-B-32",
    pretrained: str = "laion2b_s34b_b79k",
    force_reload: bool = False,
) -> tuple:
    """Load (or retrieve cached) CLIP model, tokenizer, and preprocess pipeline.

    The model is cached globally so that calling ``classify_batch``
    multiple times in the same session avoids redundant downloads.

    Args:
        model_name: CLIP model variant (e.g. ``ViT-B-32``, ``ViT-L-14``).
        pretrained: Pretrained weights tag (e.g. ``laion2b_s34b_b79k``).
        force_reload: If True, discard cache and reload from scratch.

    Returns:
        Tuple of ``(model, tokenizer, preprocess)``.
    """
    global _model, _tokenizer, _preprocess, _current_model_name, _current_pretrained

    if (
        not force_reload
        and _model is not None
        and _current_model_name == model_name
        and _current_pretrained == pretrained
    ):
        return _model, _tokenizer, _preprocess

    device = _resolve_device()
    logger.info(
        "Loading model — device=%s model=%s pretrained=%s",
        device,
        model_name,
        pretrained,
    )

    model, _, preprocess = open_clip.create_model_and_transforms(
        model_name,
        pretrained=pretrained,
    )
    model = model.to(device).eval()
    tokenizer = open_clip.get_tokenizer(model_name)

    _model = model
    _tokenizer = tokenizer
    _preprocess = preprocess
    _current_model_name = model_name
    _current_pretrained = pretrained

    logger.info("Model loaded and cached")
    return _model, _tokenizer, _preprocess


@torch.no_grad()
def classify_batch(
    images: list[Image.Image],
    labels: list[str],
    model_name: str = "ViT-B-32",
    pretrained: str = "laion2b_s34b_b79k",
) -> list[list[dict]]:
    """Classify a batch of PIL images against the given label set.

    Args:
        images: Pre-processed PIL images (already run through ``preprocess``).
        labels: Category names to score against.
        model_name: CLIP model variant.
        pretrained: Pretrained weights tag.

    Returns:
        A list with one entry per input image.  Each entry is a list of
        ``{"category": str, "score": float}`` dicts sorted by score
        descending.
    """
    model, tokenizer, preprocess = load_model(model_name, pretrained)
    device = _resolve_device()

    # Pre-process images
    processed = [preprocess(img) for img in images]
    image_tensor = torch.stack(processed).to(device)
    text_tensor = tokenizer(labels).to(device)

    with torch.autocast(device):
        image_features = model.encode_image(image_tensor)
        text_features = model.encode_text(text_tensor)

        image_features /= image_features.norm(dim=-1, keepdim=True)
        text_features /= text_features.norm(dim=-1, keepdim=True)

        probs = (100.0 * image_features @ text_features.T).softmax(dim=-1)
        scores = probs.cpu().numpy()

    results = []
    for row in scores:
        indexed = [
            {"category": labels[i], "score": float(row[i])} for i in range(len(labels))
        ]
        indexed.sort(key=lambda x: x["score"], reverse=True)  # type: ignore[arg-type, return-value]
        results.append(indexed)

    return results

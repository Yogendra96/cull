"""Classification service — runs CLIP zero-shot on a directory of files.

This is the core classification logic, separated from both the CLI
entry point (``__main__.py``) and the model-management layer (``models.py``).
It knows about categories, confidence thresholds, and how to handle
videos/PDFs, but not about CLI flags or output formatting.
"""

import logging
from pathlib import Path
from typing import Optional, Callable

from PIL import Image

from cull.media import is_video, is_pdf, extract_video_frame, should_skip, SUPPORTED_IMAGE_EXTS, SUPPORTED_EXTS
from cull.categories import DEFAULT_CATEGORIES, NON_CLIP_CATEGORIES
from cull.models import classify_batch
from cull import config

logger = logging.getLogger("cull.classify")


def collect_files(
    root: str,
    include_media: bool = False,
    skip_hidden: bool = True,
) -> list[str]:
    """Recursively collect all processable files under *root*.

    Args:
        root: Directory to scan.
        include_media: Also include videos and PDFs.
        skip_hidden: Skip macOS dotfiles and system artifacts.

    Returns:
        Sorted list of absolute file paths.
    """
    exts = SUPPORTED_IMAGE_EXTS if not include_media else SUPPORTED_EXTS
    root_path = Path(root)
    paths: list[str] = []

    for f in root_path.rglob("*"):
        if not f.is_file():
            continue
        if skip_hidden and should_skip(f.name):
            continue
        if f.suffix.lower() in exts:
            paths.append(str(f))

    paths.sort()
    return paths


def classify_directory(
    image_paths: list[str],
    labels: Optional[list[str]] = None,
    batch_size: int = config.DEFAULT_BATCH_SIZE,
    top_k: int = config.DEFAULT_TOP_K,
    model_name: str = config.DEFAULT_MODEL,
    pretrained: str = config.DEFAULT_PRETRAINED,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> list[dict]:
    """Classify a list of image paths using CLIP zero-shot.

    Args:
        image_paths: Absolute paths to image/video/pdf files.
        labels: Category names to classify against.
            Defaults to all categories from ``categories.py``.
        batch_size: Images per inference batch.
        top_k: Top-K predicted categories to record.
        model_name: CLIP model variant.
        pretrained: Pretrained weights tag.
        progress_callback: Optional ``(current, total)`` callback for UI progress.

    Returns:
        A list of result dicts, one per input file::

            {"path": str, "scores": [{"category": str, "score": float}, ...]}
            {"path": str, "error": "reason"}  # on failure
    """
    if labels is None:
        labels = list(DEFAULT_CATEGORIES.keys())

    results: list[dict] = []
    total = len(image_paths)
    temp_files: list[str] = []

    # Non-CLIP categories (e.g. PDFs) are handled by extension
    non_clip = NON_CLIP_CATEGORIES

    for i in range(0, total, batch_size):
        batch = image_paths[i : i + batch_size]
        batch_images: list[Image.Image] = []
        valid_paths: list[str] = []

        for p in batch:
            try:
                # PDFs — classified by extension, skip CLIP
                if is_pdf(p):
                    results.append({
                        "path": p,
                        "scores": [{"category": "pdf", "score": 1.0}],
                    })
                    continue

                # Videos — extract a single frame for CLIP
                if is_video(p):
                    frame = extract_video_frame(p)
                    if frame is None:
                        results.append({"path": p, "error": "failed to extract frame"})
                        continue
                    temp_files.append(frame)
                    img = Image.open(frame).convert("RGB")
                else:
                    img = Image.open(p).convert("RGB")

                batch_images.append(img)
                valid_paths.append(p)

            except Exception:
                results.append({"path": p, "error": "failed to open"})

        if not batch_images:
            if progress_callback:
                progress_callback(min(i + batch_size, total), total)
            continue

        # Run CLIP on the valid images in this batch
        all_scores = classify_batch(
            batch_images, labels,
            model_name=model_name, pretrained=pretrained,
        )

        for j, scores in enumerate(all_scores):
            results.append({
                "path": valid_paths[j],
                "scores": scores[:top_k],
            })

        if progress_callback:
            progress_callback(min(i + batch_size, total), total)

    # Cleanup temp files
    for tf in temp_files:
        Path(tf).unlink(missing_ok=True)

    success = sum(1 for r in results if "error" not in r)
    failed = sum(1 for r in results if "error" in r)
    logger.info("Classification done — ok=%d failed=%d total=%d", success, failed, total)

    return results

"""cull — AI-powered orphan image cleaner.

Classify, organise, deduplicate, and clean up messy image collections
using CLIP zero-shot vision.  Runs on macOS, Linux, and Windows.
"""

__version__ = "0.2.0"
__author__ = "Yogendra Bairagi"
__license__ = "MIT"

# Re-export key symbols for convenient ``from cull import X`` usage.
from cull.categories import DEFAULT_CATEGORIES
from cull.config import (
    DEFAULT_THRESHOLD,
    DEFAULT_BATCH_SIZE,
    DEFAULT_MODEL,
)
from cull.media import is_image, is_video, is_pdf, is_supported
from cull.volumes import list_volumes, validate_mount, safe_eject

__all__ = [
    "DEFAULT_CATEGORIES",
    "DEFAULT_THRESHOLD",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_MODEL",
    "is_image",
    "is_video",
    "is_pdf",
    "is_supported",
    "list_volumes",
    "validate_mount",
    "safe_eject",
]

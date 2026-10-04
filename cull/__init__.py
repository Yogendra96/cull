"""cull — AI-powered orphan image cleaner.

Classify, organise, deduplicate, and clean up messy image collections
using CLIP zero-shot vision.  Runs on macOS, Linux, and Windows.
"""

__version__ = "0.2.0"
__license__ = "MIT"

# Re-export key symbols for convenient ``from cull import X`` usage.
from cull.categories import DEFAULT_CATEGORIES
from cull.config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MODEL,
    DEFAULT_THRESHOLD,
)
from cull.media import is_image, is_pdf, is_supported, is_video
from cull.volumes import list_volumes, safe_eject, validate_mount

__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_CATEGORIES",
    "DEFAULT_MODEL",
    "DEFAULT_THRESHOLD",
    "is_image",
    "is_pdf",
    "is_supported",
    "is_video",
    "list_volumes",
    "safe_eject",
    "validate_mount",
]

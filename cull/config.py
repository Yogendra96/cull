"""Centralized configuration defaults for cull.

Every magic number, default path, and named constant lives here
so modules depend on an abstraction (this module) rather than
hardcoded values scattered across the codebase.
"""

from pathlib import Path

# ── Classification defaults ──────────────────────────────────────────

DEFAULT_THRESHOLD = 0.3
"""Minimum CLIP confidence score (0–1) to assign a category."""

DEFAULT_BATCH_SIZE = 32
"""Images per inference batch.  Higher = more throughput, more VRAM."""

DEFAULT_TOP_K = 2
"""Top-K predicted categories to record per image."""

DEFAULT_MODEL = "ViT-B-32"
DEFAULT_PRETRAINED = "laion2b_s34b_b79k"

ACCURATE_MODEL = "ViT-L-14"
ACCURATE_PRETRAINED = "laion2b_s32b_b82k"


# ── Directory / output naming ────────────────────────────────────────

DUPLICATES_DIR_NAME = "duplicates"
"""Sub-directory name used by ``dedup`` for moved duplicates."""

DEFAULT_REPORT = Path("cull_report.json")
"""Default report filename created by ``classify``."""

DEFAULT_OUTPUT_DIR = None
"""When None, output dir defaults to the report's parent directory."""


# ── File / path constants ────────────────────────────────────────────

MACOS_VOLUMES_ROOT = Path("/Volumes")

DUPLICATES_ROOT = Path.home() / "duplicates"
"""Top-level directory under which orphan_sorted/ and duplicates/ live."""

ORPHANS_SORTED = DUPLICATES_ROOT / "orphans_sorted"
"""Where the organised (non-duplicate) files were moved."""

DUPLICATES_DIR = DUPLICATES_ROOT / "duplicates"
"""Where the duplicate files were moved."""


# ── Category file (future: user-defined categories from YAML) ────────

CATEGORY_CONFIG_PATH = Path.home() / ".cull" / "categories.yaml"
"""Optional user-defined category overrides (not yet implemented)."""

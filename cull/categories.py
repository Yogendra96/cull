"""Default category definitions for CLIP zero-shot classification.

Categories are defined as prompt templates — natural-language descriptions
that CLIP matches against image embeddings.  Adding a new category here
automatically makes it available to the classify pipeline.

Users can also define custom categories via a YAML file (see
:func:`load_categories_yaml`).  Custom categories are merged with the
defaults — new categories are added, existing ones are overridden.
"""

import logging
from pathlib import Path

import yaml

logger = logging.getLogger("cull.categories")


# ── Image categories ─────────────────────────────────────────────────

IMAGE_CATEGORIES: dict[str, list[str]] = {
    "person": ["a photo of a person", "a selfie", "a portrait"],
    "screenshot": ["a screenshot", "a screen capture of an app or website"],
    "meme": ["a meme", "an image macro with text overlay"],
    "document": ["a document", "a receipt", "a scanned paper", "a printed page"],
    "wallpaper": ["a wallpaper", "abstract art", "a gradient background"],
    "food": ["a photo of food", "a dish", "a meal"],
    "landscape": ["a landscape photo", "nature", "a travel photo"],
    "animal": ["a photo of an animal", "a pet", "a wild animal"],
    "urban": ["a cityscape", "a building", "a street photo"],
    "object": ["a photo of an object", "a product photo"],
    "text_heavy": ["an image with lots of text", "a presentation slide"],
    "low_quality": ["a blurry image", "a pixelated image", "a low resolution image"],
    "downloaded": ["a stock photo", "a downloaded image from the internet"],
    "NSFW": ["an explicit image", "adult content", "not safe for work"],
}

# ── Video categories ─────────────────────────────────────────────────

VIDEO_CATEGORIES: dict[str, list[str]] = {
    "screencast": [
        "a screencast video",
        "a screen recording",
        "a software tutorial video",
    ],
    "movie_clip": ["a movie clip", "a television show clip", "a scene from a film"],
    "animation": ["an animated video", "a cartoon", "an animated short"],
    "video_call": ["a video call recording", "a selfie video", "a video message"],
    "gaming": ["a gaming video", "a gameplay recording"],
    "short_clip": ["a short social media clip", "a status video", "a reel"],
    "nsfw_video": [
        "an explicit video",
        "adult content video",
        "not safe for work video",
    ],
}

# ── Combined lookup ──────────────────────────────────────────────────

DEFAULT_CATEGORIES: dict[str, list[str]] = {**IMAGE_CATEGORIES, **VIDEO_CATEGORIES}

# Categories that cannot be assigned by CLIP and are determined by extension
NON_CLIP_CATEGORIES: set[str] = {"pdf"}

# Categories whose files live under a parent directory
VIDEO_CATEGORY_NAMES: set[str] = set(VIDEO_CATEGORIES.keys())


# ── YAML category loading ────────────────────────────────────────────

YAML_EXAMPLE = """\
# Custom categories for cull — merge with defaults when passed as
#   cull classify /path/ --categories my_categories.yaml
#
# New categories are added.  Existing categories with the same name
# are overridden entirely.

categories:
  receipt: ["a receipt", "a scanned receipt", "a shopping receipt"]
  whiteboard: ["a whiteboard photo", "a whiteboard with writing"]
  cat: ["a photo of a cat", "a feline"]
"""


def load_categories_yaml(path: str | Path) -> dict[str, list[str]]:
    """Load custom category definitions from a YAML file.

    The YAML format is::

        categories:
          <name>: [<prompt 1>, <prompt 2>, ...]

    Returns a dict of ``{name: [prompts]}]``.  Does **not** merge with
    defaults — the caller (typically :func:`merge_with_defaults`) handles
    that.

    Args:
        path: Path to the YAML file.

    Returns:
        The parsed custom categories.

    Raises:
        FileNotFoundError: If *path* doesn't exist.
        ValueError: If the YAML is malformed or missing the ``categories`` key.
    """
    yaml_path = Path(path)
    if not yaml_path.exists():
        raise FileNotFoundError(f"Categories file not found: {yaml_path}")

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "categories" not in data:
        raise ValueError(
            f"YAML file must have a top-level 'categories' key.\n"
            f"Example format:\n\n{YAML_EXAMPLE}"
        )

    cats = data["categories"]
    if not isinstance(cats, dict):
        raise TypeError("'categories' must be a mapping (dict)")

    validated: dict[str, list[str]] = {}
    for name, prompts in cats.items():
        if isinstance(prompts, str):
            prompts = [prompts]
        if not isinstance(prompts, list) or not all(
            isinstance(p, str) for p in prompts
        ):
            raise ValueError(
                f"Category {name!r}: prompts must be a string or list of strings"
            )
        validated[str(name)] = prompts

    return validated


def merge_with_defaults(
    custom: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """Merge custom categories with the built-in defaults.

    Args:
        custom: Optional dict of user-defined categories (name → prompts).
            If ``None``, returns only the defaults.

    Returns:
        A new dict combining defaults and custom entries.  Custom entries
        with the same name as a default override it entirely.
    """
    if not custom:
        return dict(DEFAULT_CATEGORIES)

    merged = {**DEFAULT_CATEGORIES, **custom}
    logger.info(
        "Merged categories — %d default + %d custom = %d total",
        len(DEFAULT_CATEGORIES),
        len(custom),
        len(merged),
    )
    return merged


# ── Validation helpers ───────────────────────────────────────────────


def validate_categories(categories: dict[str, list[str]]) -> list[str]:
    """Return a list of validation warnings for a category dictionary."""
    warnings: list[str] = []
    for name, prompts in categories.items():
        if not name.isidentifier():
            warnings.append(f"Category name is not a valid identifier: {name!r}")
        if not prompts:
            warnings.append(f"Category has no prompts: {name!r}")
        for p in prompts:
            if len(p) < 5:
                warnings.append(f"Prompt too short in {name!r}: {p!r}")
    return warnings

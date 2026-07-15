"""File type detection, media handling, and volume utilities.

Single source of truth for all file extension sets used across the project.
Also handles external volume discovery, mount validation, and safe ejection.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image

# ── File extension sets (single source of truth) ──────────────────────

IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
    ".tiff", ".tif", ".heic", ".heif", ".avif", ".jxl",
}

VIDEO_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
    ".wmv", ".flv", ".m4v", ".3gp", ".ts",
}

PDF_EXTS = {".pdf"}

DOC_EXTS = {
    ".doc", ".docx", ".xls", ".xlsx",
    ".ppt", ".pptx", ".txt", ".rtf",
}

ARCHIVE_EXTS = {".zip", ".rar", ".tar", ".gz", ".7z"}

# All file types the tool can process
SUPPORTED_IMAGE_EXTS = IMAGE_EXTS
SUPPORTED_EXTS = IMAGE_EXTS | VIDEO_EXTS | PDF_EXTS

# macOS system artifacts to always skip
SKIP_FILES = {".DS_Store", ".localized", ".Trashes", ".fseventsd", ".Spotlight-V100"}


# ── File type predicates ─────────────────────────────────────────────

def is_image(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTS


def is_video(path: str | Path) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXTS


def is_pdf(path: str | Path) -> bool:
    return Path(path).suffix.lower() in PDF_EXTS


def is_supported(path: str | Path) -> bool:
    """Return True if the file extension is in any supported set."""
    return Path(path).suffix.lower() in SUPPORTED_EXTS


def should_skip(name: str) -> bool:
    """Return True for macOS system artifacts and hidden dotfiles."""
    return name.startswith(".") or name in SKIP_FILES


# ── Media processing ─────────────────────────────────────────────────

def extract_video_frame(path: str | Path) -> Optional[str]:
    """Extract a single frame from a video using ffmpeg.

    Returns the path to a temporary JPEG file, or None on failure.
    The caller is responsible for cleaning up the temp file.
    """
    out = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    out.close()
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(path), "-vframes", "1", "-q:v", "3", out.name],
            capture_output=True,
            timeout=30,
        )
        img = Image.open(out.name)
        img.verify()
        return out.name
    except Exception:
        Path(out.name).unlink(missing_ok=True)
        return None


# ── External volume support ──────────────────────────────────────────

MACOS_VOLUMES_ROOT = Path("/Volumes")


def list_volumes() -> list[dict]:
    """Discover mounted external volumes on macOS.

    Returns a list of dicts with keys: name, path, is_internal, is_readonly.
    Skips the internal Macintosh HD and any system mounts.
    """
    if not MACOS_VOLUMES_ROOT.exists():
        return []

    volumes = []
    for child in sorted(MACOS_VOLUMES_ROOT.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        # Skip the internal drive (macOS system volume)
        if child.name == "Macintosh HD":
            continue
        try:
            stat = child.stat()
            volumes.append({
                "name": child.name,
                "path": str(child),
                "is_internal": False,
                "is_readonly": not os.access(str(child), os.W_OK),
                "mount_point": str(child),
            })
        except OSError:
            # Permission error or disappeared mount — skip
            continue

    return volumes


def validate_mount(path: str | Path) -> tuple[bool, str]:
    """Check whether a path is on a reachable, mounted volume.

    Returns (is_valid, message).  The message explains failures.
    """
    p = Path(path).resolve()
    if not p.exists():
        return False, f"Path does not exist: {p}"

    # On macOS, mounted volumes live under /Volumes
    try:
        # Walk up to find the mount root
        for parent in p.parents:
            if parent == MACOS_VOLUMES_ROOT or parent.parent == MACOS_VOLUMES_ROOT:
                # The path is on a volume — check it's still mounted
                if not p.stat():
                    return False, f"Volume appears to be unmounted: path inaccessible"
                return True, "Path is accessible"
        # Path is on the internal drive
        return True, "Path on internal drive"
    except OSError as exc:
        return False, f"Cannot access path: {exc}"


def get_volume_for_path(path: str | Path) -> Optional[dict]:
    """Return the volume dict for the volume containing *path*, or None."""
    p = Path(path).resolve()
    volumes = list_volumes()
    for vol in volumes:
        vol_path = Path(vol["path"])
        if vol_path in p.parents or vol_path == p:
            return vol
    return None


def safe_eject(volume_path: str | Path, force: bool = False) -> tuple[bool, str]:
    """Eject an external volume using macOS ``diskutil``.

    Returns (success, message).  Does nothing on non-macOS systems.
    """
    vol = Path(volume_path)
    if not vol.exists():
        return False, f"Volume not found: {vol}"

    if force:
        cmd = ["diskutil", "eject", "force", str(vol)]
    else:
        cmd = ["diskutil", "eject", str(vol)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, f"Ejected {vol.name}"
        return False, result.stderr.strip() or "Eject failed (unknown reason)"
    except FileNotFoundError:
        return False, "diskutil not found (only available on macOS)"
    except subprocess.TimeoutExpired:
        return False, "Eject timed out"
    except Exception as exc:
        return False, f"Eject error: {exc}"

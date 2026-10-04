"""Duplicate detection service — perceptual hashing for near-duplicate images.

Uses ``imagehash.dhash`` (difference hash) for images.  Videos are hashed
by extracting a single representative frame via ffmpeg and hashing that
frame — more accurate than the previous size-only fallback, though still
not full video fingerprinting.  PDFs use a size-based key as a crude
approximation.
"""

import logging
import shutil
from collections import defaultdict
from pathlib import Path

import imagehash
from PIL import Image

from cull.media import (
    extract_video_frame,
    is_pdf,
    is_video,
    should_skip,
)
from cull.volumes import validate_mount

logger = logging.getLogger("cull.dedup")


def _hash_file(path: Path) -> str | None:
    """Compute a perceptual hash for *path*.

    - **Images:** ``imagehash.dhash`` — fast difference hash (64-bit).
    - **Videos:** single-frame extraction → ``dhash`` — accurate but
      requires ffmpeg.  Falls back to size on failure.
    - **PDFs:** size-based key (``pdf:<bytes>``) — files are too
      variable for a single-frame approach.

    Returns ``None`` for unreadable files.
    """
    try:
        if is_video(str(path)):
            return _hash_video(path)
        if is_pdf(str(path)):
            size = path.stat().st_size
            return f"pdf:{size}"
        # Image — perceptual hash
        img = Image.open(path)
        img = img.convert("RGB")
        h = str(imagehash.dhash(img))
        img.close()
        return h
    except Exception as exc:  # noqa: BLE001  # intentional — any hash failure is non-fatal
        logger.debug("Failed to hash %s: %s", path, exc)
        return None


def _hash_video(path: Path) -> str | None:
    """Extract a representative frame from *path* and hash it.

    Falls back to a size-based key (``size:<bytes>``) if ffmpeg
    is unavailable or the frame can't be extracted.
    """
    frame = extract_video_frame(str(path))
    if frame is None:
        # Fallback: size-based
        size = path.stat().st_size
        return f"size:{size}"

    try:
        img = Image.open(frame).convert("RGB")
        h = str(imagehash.dhash(img))
        img.close()
        return h
    finally:
        # Clean up temp frame file
        try:
            Path(frame).unlink(missing_ok=True)
        except OSError:
            pass


def deduplicate(
    scan_dir: str,
    dupes_dir: str | None = None,
    dry_run: bool = True,
) -> None:
    """Find near-duplicate images under *scan_dir* and move them out.

    Uses perceptual hashing to group similar images.  Within each group
    the *first* file is kept in place; all others are moved to *dupes_dir*.

    Args:
        scan_dir: Directory to scan recursively for duplicates.
        dupes_dir: Where to move duplicates.  Defaults to ``../duplicates/``
            relative to *scan_dir*.
        dry_run: If True, only print what would happen (default).
    """
    scan_path = Path(scan_dir)
    if not scan_path.exists():
        print(f"Directory not found: {scan_dir}")
        return

    # Mount validation
    valid, msg = validate_mount(scan_path)
    if not valid:
        print(f"⚠️  Warning — scan directory may be unreachable: {msg}")

    if dupes_dir is None:
        dupes_path = scan_path.parent / "duplicates"
    else:
        dupes_path = Path(dupes_dir)
    dupes_path.mkdir(parents=True, exist_ok=True)

    all_files = sorted(
        f for f in scan_path.rglob("*") if f.is_file() and not should_skip(f.name)
    )

    print(f"Scanning {len(all_files)} files in {scan_path}...")

    # Group by hash
    by_hash: dict[str, list[Path]] = defaultdict(list)
    hashed = 0
    for f in all_files:
        h = _hash_file(f)
        if h is not None:
            by_hash[h].append(f)
            hashed += 1

    print(f"Hashed {hashed} files, {len(by_hash)} unique hashes.")

    # Identify duplicates (second+ occurrence per hash)
    dupes_found = 0
    dupes_size = 0
    for h, files in sorted(by_hash.items()):
        if len(files) < 2:
            continue
        keep = files[0]
        for dup in files[1:]:
            dupes_found += 1
            dupes_size += dup.stat().st_size
            rel = dup.relative_to(scan_path)
            dest = dupes_path / rel
            dest.parent.mkdir(parents=True, exist_ok=True)

            if dry_run:
                print(
                    f"  [would move] {rel}  (duplicate of {keep.relative_to(scan_path)})"
                )
            else:
                try:
                    shutil.move(str(dup), str(dest))
                    print(f"  [moved] {rel} -> {dest}")
                except OSError as exc:
                    print(f"  [error] {rel}: {exc}")

    size_mb = dupes_size / 1_000_000
    tag = "Dry run — " if dry_run else ""
    print(f"\n{tag}{dupes_found} duplicate files ({size_mb:.1f} MB) found.")
    if dupes_found:
        print(f"  Originals remain under: {scan_path}")
        print(f"  Duplicates would go to: {dupes_path}")
    if dry_run:
        print("Run with --execute to actually move duplicates.")

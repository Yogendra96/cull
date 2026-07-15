"""Organization service — moves/copies classified files into category folders.

Called *after* classification to physically sort the files on disk.
Supports both move (default) and copy modes, dry-runs, and cross-volume
validation for external drives.
"""

import json
import shutil
from pathlib import Path

from cull.categories import VIDEO_CATEGORY_NAMES
from cull.volumes import validate_mount


def _cat_dir(output_dir: Path, cat: str) -> Path:
    """Return the category directory, handling video sub-directories."""
    if cat in VIDEO_CATEGORY_NAMES:
        return output_dir / "videos" / cat
    return output_dir / cat


def organize_by_category(
    report_path: str,
    output_dir: str | None = None,
    copy: bool = False,
    dry_run: bool = True,
    include_unclassified: bool = True,
) -> None:
    """Move / copy classified files into category-named folders.

    Args:
        report_path: Path to the JSON report from ``classify``.
        output_dir: Target root directory.  Defaults to the report's parent.
        copy: If True, copy files instead of moving them.
        dry_run: If True, only print what would happen.
        include_unclassified: Also organise files in the ``unclassified`` bucket.
    """
    report_path = Path(report_path)
    if not report_path.exists():
        print(f"Report not found: {report_path}")
        return

    if output_dir is None:
        output_dir = report_path.parent
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Mount validation — warn if target is on an external volume about to disappear
    valid, msg = validate_mount(output_dir)
    if not valid:
        print(f"⚠️  Warning — output directory may be unreachable: {msg}")

    with open(report_path) as f:
        report = json.load(f)

    total = 0
    for cat, info in report.get("categories", {}).items():
        if cat == "unclassified" and not include_unclassified:
            continue

        cat_dir = _cat_dir(output_dir, cat)
        cat_dir.mkdir(parents=True, exist_ok=True)

        for fp in info.get("files", []):
            src = Path(fp)
            if not src.exists():
                print(f"  [missing] {fp}")
                continue

            dest = cat_dir / src.name
            # Handle name collisions
            if dest.exists():
                stem = src.stem
                suffix = src.suffix
                dest = cat_dir / f"{stem}_{src.parent.name}{suffix}"

            total += 1
            action = "copy" if copy else "move"
            if dry_run:
                print(f"  [would {action}] {fp} -> {dest}")
            else:
                try:
                    if copy:
                        shutil.copy2(src, dest)
                    else:
                        shutil.move(str(src), str(dest))
                    print(f"  [{action}d] {fp} -> {dest}")
                except OSError as exc:
                    print(f"  [error] {fp} → {dest}: {exc}")

    tag = "Dry run — " if dry_run else ""
    print(f"\n{tag}{total} files would be {'copied' if copy else 'moved'} to {output_dir}")
    if dry_run:
        print("Run with --execute to actually move/copy files.")

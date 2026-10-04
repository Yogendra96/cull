"""Cleanup service — delete, trash, or report on duplicates.

Provides safe strategies for dealing with the duplicate files that
``dedup`` moved aside, including dry-run mode and trash integration.
"""

import shutil
from pathlib import Path

from cull import config


def _count_files_in(dir_path: Path) -> tuple[int, int]:
    """Count files and total bytes in *dir_path* (non-recursive)."""
    total = 0
    bytes_total = 0
    for f in dir_path.iterdir():
        if f.is_file():
            total += 1
            bytes_total += f.stat().st_size
    return total, bytes_total


def _expand_nested_dirs(dupes_path: Path) -> list[tuple[str, Path, bool]]:
    """Return a list of ``(display_name, dir_path, is_nested)`` tuples.

    Top-level dirs are returned as-is.  If a dir contains mostly
    sub-directories (like ``videos/`` with ``video_call/``, ``animation/``),
    its children are returned instead, with the parent name as prefix.
    """
    entries: list[tuple[str, Path, bool]] = []
    for cat_dir in sorted(dupes_path.iterdir()):
        if not cat_dir.is_dir():
            continue
        # Check if this dir contains subdirs with files
        subdirs = [d for d in cat_dir.iterdir() if d.is_dir()]
        if subdirs:
            # This is a parent dir (e.g. videos/) — expand its children
            for sub in sorted(subdirs):
                sub_count, _ = _count_files_in(sub)
                if sub_count:
                    entries.append((f"{cat_dir.name}/{sub.name}", sub, True))
            # Also include any files directly in the parent
            parent_count, _ = _count_files_in(cat_dir)
            if parent_count:
                entries.append((cat_dir.name, cat_dir, False))
        else:
            entries.append((cat_dir.name, cat_dir, False))
    return entries


def report_duplicates(dupes_dir: str | None = None) -> dict:
    """Scan the duplicates directory and return a summary.

    Args:
        dupes_dir: Path to the duplicates folder.
            Defaults to ``~/duplicates/duplicates/``.

    Returns::

        {
            "total_files": int,
            "total_bytes": int,
            "categories": {name: {"files": int, "bytes": int}, ...},
            "dir": str,
        }
    """
    dupes_path = _resolve_dupes_dir(dupes_dir)
    if not dupes_path.exists():
        return {
            "total_files": 0,
            "total_bytes": 0,
            "categories": {},
            "dir": str(dupes_path),
        }

    summary: dict[str, dict] = {}
    total_files = 0
    total_bytes = 0

    for display_name, cat_dir, _is_nested in _expand_nested_dirs(dupes_path):
        cat_files = list(cat_dir.rglob("*"))
        cat_total = sum(1 for f in cat_files if f.is_file())
        cat_bytes = sum(f.stat().st_size for f in cat_files if f.is_file())
        if cat_total:
            summary[display_name] = {"files": cat_total, "bytes": cat_bytes}
            total_files += cat_total
            total_bytes += cat_bytes

    return {
        "total_files": total_files,
        "total_bytes": total_bytes,
        "categories": summary,
        "dir": str(dupes_path),
    }


def delete_duplicates(
    dupes_dir: str | None = None,
    strategy: str = "trash",
    category: str | None = None,
    dry_run: bool = True,
) -> dict:
    """Remove or trash duplicate files.

    Args:
        dupes_dir: Path to the duplicates folder.
        strategy: One of ``"trash"`` (move to macOS Trash), ``"delete"``
            (permanent unlink), or ``"list"`` (print paths only).
        category: If set, only process this category sub-directory.
        dry_run: If True, only print what would happen (default).

    Returns::

        {"removed": int, "bytes_freed": int, "strategy": str}
    """
    dupes_path = _resolve_dupes_dir(dupes_dir)
    if not dupes_path.exists():
        print(f"Duplicates directory not found: {dupes_path}")
        return {"removed": 0, "bytes_freed": 0, "strategy": strategy}

    targets: list[Path] = []
    if category:
        cat_dir = dupes_path / category
        if cat_dir.exists():
            targets.extend(f for f in cat_dir.rglob("*") if f.is_file())
            print(f"Category: {category} ({len(targets)} files)")
        else:
            print(f"Category not found in duplicates: {category}")
            return {"removed": 0, "bytes_freed": 0, "strategy": strategy}
    else:
        for f in dupes_path.rglob("*"):
            if f.is_file():
                targets.append(f)
        print(f"All duplicates: {len(targets)} files")

    # Dry-run
    if dry_run:
        total_bytes = sum(f.stat().st_size for f in targets)
        print(
            f"\nDry run — would remove {len(targets)} files ({total_bytes / 1_000_000:.1f} MB)"
        )
        print(f"Strategy: {strategy}")
        print("Run with --execute to actually clean up.")
        return {"removed": 0, "bytes_freed": 0, "strategy": strategy}

    # Execute
    removed = 0
    freed = 0
    for f in targets:
        try:
            if strategy == "trash":
                _send_to_trash(f)
            elif strategy == "delete":
                f.unlink()
            elif strategy == "list":
                print(str(f))
                removed += 1
                continue
            removed += 1
            freed += f.stat().st_size
            print(f"  [{'trashed' if strategy == 'trash' else 'deleted'}] {f}")
        except OSError as exc:
            print(f"  [error] {f}: {exc}")

    print(f"\nRemoved {removed} files, freed {freed / 1_000_000:.1f} MB")
    return {"removed": removed, "bytes_freed": freed, "strategy": strategy}


def _resolve_dupes_dir(dupes_dir: str | None) -> Path:
    """Resolve the duplicates directory, preferring explicit paths."""
    if dupes_dir:
        return Path(dupes_dir)
    return config.DUPLICATES_DIR


def _send_to_trash(path: Path) -> None:
    """Move a file to the macOS Trash (``~/.Trash``)."""
    trash_dir = Path.home() / ".Trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    dest = trash_dir / path.name
    # Handle name collisions in Trash
    if dest.exists():
        stem = path.stem
        suffix = path.suffix
        dest = trash_dir / f"{stem}_{hash(path)}{suffix}"
    shutil.move(str(path), str(dest))

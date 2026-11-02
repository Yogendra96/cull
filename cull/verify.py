"""Exact-hash verification for duplicate folders.

``cull dedup`` uses perceptual hashing, so a "duplicate" may be merely
*visually similar* (a crop, a re-export, or another frame of a burst).
Before deleting a duplicates folder, confirm each file is byte-identical
to a copy that still exists somewhere else — typically an external drive
or a backup tree.

``cull verify`` indexes the reference tree by file size, then confirms
candidate matches with SHA-256. Files without an exact match are reported
as *unverified* and preserved: when executing, they are moved to a
quarantine folder before the verified copies are removed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
from collections import defaultdict
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cull import config
from cull.cleanup import send_to_trash
from cull.volumes import validate_mount

logger = logging.getLogger("cull.verify")

CHUNK_SIZE = 1 << 20  # 1 MiB


# ── Hashing ──────────────────────────────────────────────────────────


def sha256_file(path: Path) -> str | None:
    """Return the SHA-256 hex digest of *path*, or ``None`` if unreadable."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(CHUNK_SIZE), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as exc:
        logger.debug("Failed to hash %s: %s", path, exc)
        return None


def _hash_many(paths: Sequence[Path], workers: int) -> dict[Path, str | None]:
    """Hash several files concurrently (I/O bound)."""
    if not paths:
        return {}
    workers = max(1, min(workers, len(paths)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        digests = list(pool.map(sha256_file, paths))
    return dict(zip(paths, digests))


# ── Reference indexing ───────────────────────────────────────────────


def _iter_files(root: Path, exclude: set[Path]) -> Iterable[Path]:
    """Yield regular files under *root*, pruning *exclude* directories."""
    if root.resolve() in exclude:
        return
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = [
            d for d in dirnames if (current / d).resolve() not in exclude
        ]
        for name in filenames:
            candidate = current / name
            if candidate.is_symlink():
                continue
            yield candidate


def build_size_index(
    roots: Sequence[Path],
    exclude: set[Path] | None = None,
) -> dict[int, list[Path]]:
    """Index every file under *roots* by byte size.

    Size is a cheap first-pass filter: only files sharing a size with a
    duplicate ever need hashing.
    """
    exclude = exclude or set()
    index: dict[int, list[Path]] = defaultdict(list)
    for root in roots:
        for path in _iter_files(root, exclude):
            try:
                index[path.stat().st_size].append(path)
            except OSError:
                continue
    return dict(index)


# ── Verification ─────────────────────────────────────────────────────


def _normalize_roots(against: str | Sequence[str]) -> list[Path]:
    """Accept a comma-separated string, a single path, or a sequence."""
    if isinstance(against, str):
        parts = [p.strip() for p in against.split(",")]
    else:
        parts = [str(p).strip() for p in against]
    return [Path(p).expanduser() for p in parts if p]


def _remove_file(path: Path, strategy: str) -> None:
    """Remove one file using *strategy* (``trash`` / ``delete`` / ``list``)."""
    if strategy == "trash":
        send_to_trash(path)
    elif strategy == "delete":
        path.unlink()
    elif strategy == "list":
        print(str(path))
    else:
        raise ValueError(
            f"Unknown strategy {strategy!r} (expected trash, delete, or list)"
        )


def _remove_empty_dirs(root: Path) -> None:
    """Prune empty directories under *root* (bottom-up, root excluded)."""
    for dirpath, _dirnames, _filenames in os.walk(root, topdown=False):
        current = Path(dirpath)
        if current == root:
            continue
        try:
            current.rmdir()
        except OSError:
            pass


def verify_duplicates(
    dupes_dir: str | None = None,
    against: str | Sequence[str] | None = None,
    execute: bool = False,
    strategy: str = "trash",
    quarantine: str | None = None,
    report: str | None = None,
    workers: int = config.DEFAULT_HASH_WORKERS,
) -> dict:
    """Verify duplicates are exact copies of files in a reference tree.

    Args:
        dupes_dir: Duplicates folder to verify.  Defaults to
            :data:`cull.config.DUPLICATES_DIR`.
        against: One or more reference trees (comma-separated string or a
            sequence of paths).  Typically an external drive or backup.
        execute: Remove verified files (default is dry-run).
        strategy: ``"trash"`` (default), ``"delete"``, or ``"list"``.
        quarantine: Where to preserve unverified files.  Defaults to a
            sibling of *dupes_dir* named ``duplicates_unverified``.
        report: Path for the JSON report.  Defaults to
            :data:`cull.config.DEFAULT_VERIFY_REPORT`.
        workers: Hashing thread count.

    Returns:
        The report dictionary (also written to *report*).
    """
    started = time.monotonic()

    if not against:
        print("Error: --against is required (reference tree or backup).")
        return {}

    dupes_path = Path(dupes_dir).expanduser() if dupes_dir else config.DUPLICATES_DIR
    if not dupes_path.exists():
        print(f"Duplicates directory not found: {dupes_path}")
        return {}

    roots = _normalize_roots(against)
    if not roots:
        print("Error: no valid reference paths given.")
        return {}

    # Every reference must be reachable and be a directory before we trust it.
    for root in roots:
        if not root.is_dir():
            print(f"⚠️  Reference unavailable: {root} (not an existing directory)")
            return {}
        valid, msg = validate_mount(str(root))
        if not valid:
            print(f"⚠️  Reference unavailable: {root} ({msg})")
            return {}

    quarantine_path = (
        Path(quarantine).expanduser()
        if quarantine
        else dupes_path.parent / config.DEFAULT_QUARANTINE_DIR_NAME
    )

    # Never let a reference index include the duplicates folder itself,
    # otherwise every file would "match" itself.
    exclude = {dupes_path.resolve(), quarantine_path.resolve()}

    print(f"Indexing {len(roots)} reference tree(s)...")
    index = build_size_index(roots, exclude=exclude)
    indexed_files = sum(len(v) for v in index.values())
    print(f"Indexed {indexed_files} reference files by size.")

    all_files = list(_iter_files(dupes_path, exclude=set()))
    targets = [p for p in all_files if p.name not in config.JUNK_FILENAMES]
    junk = [p for p in all_files if p.name in config.JUNK_FILENAMES]

    if not targets:
        print(f"No files to verify in {dupes_path}")
        return {}

    print(f"Hashing {len(targets)} duplicate candidates with {workers} threads...")
    target_hashes = _hash_many(targets, workers)

    reference_hash_cache: dict[Path, str | None] = {}
    verified: list[tuple[Path, int]] = []
    unverified: list[Path] = []
    errors: list[Path] = []

    for path, digest in target_hashes.items():
        try:
            size = path.stat().st_size
        except OSError:
            errors.append(path)
            continue

        if digest is None:
            errors.append(path)
            continue

        candidates = index.get(size, [])
        match = False
        for candidate in candidates:
            if candidate not in reference_hash_cache:
                reference_hash_cache[candidate] = sha256_file(candidate)
            if reference_hash_cache[candidate] == digest:
                match = True
                break

        if match:
            verified.append((path, size))
        else:
            unverified.append(path)

    verified_bytes = sum(size for _path, size in verified)
    unverified_bytes = sum(p.stat().st_size for p in unverified if p.exists())

    print(
        f"\n[verify] {len(targets)} checked — "
        f"{len(verified)} exact matches, "
        f"{len(unverified)} unverified, "
        f"{len(errors)} unreadable"
    )
    print(
        f"  Verified:   {len(verified)} files "
        f"({verified_bytes / 1_000_000:.1f} MB) — safe to remove"
    )
    print(
        f"  Unverified: {len(unverified)} files "
        f"({unverified_bytes / 1_000_000:.1f} MB) — would be preserved"
    )
    if junk:
        print(f"  Junk:       {len(junk)} OS metadata files ignored")

    if unverified:
        print("\nUnverified files (no exact copy in the reference):")
        for path in unverified[:20]:
            print(f"  · {path.relative_to(dupes_path)}")
        if len(unverified) > 20:
            print(f"  … and {len(unverified) - 20} more")

    removed = 0
    quarantined = 0
    bytes_freed = 0

    if execute:
        if unverified:
            print(f"\nQuarantining unverified files → {quarantine_path}")
            for path in unverified:
                try:
                    rel = path.relative_to(dupes_path)
                except ValueError:
                    rel = Path(path.name)
                dest = quarantine_path / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(str(path), str(dest))
                    quarantined += 1
                except OSError as exc:
                    print(f"  [error] {path}: {exc}")
                    errors.append(path)

        print(f"\nRemoving verified duplicates (strategy={strategy})...")
        for path, size in verified:
            try:
                _remove_file(path, strategy)
                removed += 1
                bytes_freed += size
            except OSError as exc:
                print(f"  [error] {path}: {exc}")
                errors.append(path)

        _remove_empty_dirs(dupes_path)
        print(
            f"\nRemoved {removed} files, freed {bytes_freed / 1_000_000:.1f} MB; "
            f"quarantined {quarantined}."
        )
    else:
        print(
            f"\nDry run — {len(verified)} files would be removed "
            f"({verified_bytes / 1_000_000:.1f} MB), "
            f"{len(unverified)} preserved."
        )
        print("Run with --execute to commit.")

    result = {
        "dupes_dir": str(dupes_path),
        "against": [str(r) for r in roots],
        "reference_files_indexed": indexed_files,
        "total_files": len(targets),
        "verified": len(verified),
        "unverified": len(unverified),
        "junk": len(junk),
        "errors": len(errors),
        "verified_bytes": verified_bytes,
        "unverified_bytes": unverified_bytes,
        "unverified_files": [str(p) for p in unverified],
        "junk_files": [str(p) for p in junk],
        "executed": execute,
        "strategy": strategy,
        "quarantine": str(quarantine_path),
        "removed": removed,
        "quarantined": quarantined,
        "bytes_freed": bytes_freed,
        "duration_seconds": round(time.monotonic() - started, 2),
    }

    report_path = Path(report) if report else config.DEFAULT_VERIFY_REPORT
    try:
        with open(report_path, "w") as fh:
            json.dump(result, fh, indent=2)
        print(f"Report saved to {report_path}")
    except OSError as exc:
        print(f"⚠️  Could not write report: {exc}")

    return result

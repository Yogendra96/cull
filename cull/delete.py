"""Legacy bulk-delete by category — kept for backward compatibility.

Prefer ``cull cleanup`` for new workflows.  This module provides
the same CLI interface as v0.1 but delegates to the refactored
modules where possible.
"""

import json
from pathlib import Path

from cull.volumes import validate_mount


def delete_category(report_path: str, category: str, dry_run: bool = True) -> None:
    """Delete all files belonging to *category* in the report.

    Args:
        report_path: Path to the cull report JSON.
        category: Category name (e.g. ``screenshot``, ``meme``).
        dry_run: If True, only print what would happen (default).
    """
    report_file = Path(report_path)
    if not report_file.exists():
        print(f"Report not found: {report_path}")
        return

    # Mount validation
    valid, msg = validate_mount(report_file.parent)
    if not valid:
        print(f"⚠️  {msg}")

    with open(report_file) as f:
        report = json.load(f)

    files = report.get("categories", {}).get(category, {}).get("files", [])
    if not files:
        print(f"No files found for category '{category}'")
        return

    print(f"Category '{category}': {len(files)} files")
    for fp in files:
        p = Path(fp)
        if not p.exists():
            print(f"  [missing] {fp}")
            continue
        if dry_run:
            print(f"  [would delete] {fp}")
        else:
            p.unlink()
            print(f"  [deleted] {fp}")

    if dry_run:
        print(f"\nDry run — {len(files)} files would be deleted")
        print("Run with --no-dry-run to actually delete")


def delete_report(report_path: str, dry_run: bool = True) -> None:
    """Delete every file listed in the report (across all categories).

    Args:
        report_path: Path to the cull report JSON.
        dry_run: If True, only print what would happen (default).
    """
    report_file = Path(report_path)
    if not report_file.exists():
        print(f"Report not found: {report_path}")
        return

    # Mount validation
    valid, msg = validate_mount(report_file.parent)
    if not valid:
        print(f"⚠️  {msg}")

    with open(report_file) as f:
        report = json.load(f)

    total = 0
    for cat, info in report.get("categories", {}).items():
        for fp in info.get("files", []):
            p = Path(fp)
            if not p.exists():
                continue
            total += 1
            if dry_run:
                print(f"  [would delete] {fp}")
            else:
                p.unlink()

    print(f"\n{'Dry run — ' if dry_run else ''}{total} files {'would be ' if dry_run else ''}deleted")

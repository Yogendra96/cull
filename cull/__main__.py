#!/usr/bin/env python3
"""cull — AI-powered orphan image cleaner.

CLI entry point.  Usage::

    cull classify ~/Pictures/
    cull organize --report cull_report.json --execute
    cull dedup ~/Pictures/orphans_sorted/ --execute
    cull cleanup --strategy trash --execute
    cull volumes
    cull gui
    cull browse
    cull categories
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

import fire

from cull import config


# ── Subcommand: classify ─────────────────────────────────────────────

def classify(
    path: str,
    report: str = str(config.DEFAULT_REPORT),
    threshold: float = config.DEFAULT_THRESHOLD,
    batch_size: int = config.DEFAULT_BATCH_SIZE,
    model: str = config.DEFAULT_MODEL,
    pretrained: str = config.DEFAULT_PRETRAINED,
    include_media: bool = False,
    categories_file: str | None = None,
) -> None:
    """Classify orphan images (and optionally videos/PDFs) using CLIP zero-shot.

    Args:
        path: Directory of orphan files to classify.
        report: Output JSON report path.
        threshold: Minimum confidence score (0-1) to assign a category.
        batch_size: Images per inference batch.
        model: CLIP model variant (ViT-B-32, ViT-L-14, etc).
        pretrained: Pretrained weights tag.
        include_media: Also classify videos and PDFs.
        categories_file: Optional YAML file with custom category definitions.
    """
    from cull.classify import collect_files, classify_directory
    from cull.categories import DEFAULT_CATEGORIES, load_categories_yaml, merge_with_defaults
    from cull.report import generate_report, print_summary, save_report
    from cull.volumes import validate_mount

    # Resolve categories — merge custom YAML with defaults if provided
    if categories_file:
        custom = load_categories_yaml(categories_file)
        labels = list(merge_with_defaults(custom).keys())
        print(f"Loaded {len(custom)} custom categories from {categories_file}")
    else:
        labels = list(DEFAULT_CATEGORIES.keys())
    valid, msg = validate_mount(path)
    if not valid:
        print(f"⚠️  {msg}")
        if not Path(path).exists():
            sys.exit(1)

    image_paths = collect_files(path, include_media=include_media)
    if not image_paths:
        print(f"No processable files found in {path}")
        return

    print(f"Found {len(image_paths)} files ({'with' if include_media else 'images only'})")
    print(f"Using model: {model} ({pretrained})")

    results = classify_directory(
        image_paths, labels,
        batch_size=batch_size,
        model_name=model,
        pretrained=pretrained,
    )

    report_data = generate_report(results, threshold=threshold)
    print_summary(report_data)
    save_report(report_data, report)
    print(f"Report saved to {report}")


# ── Subcommand: organise ─────────────────────────────────────────────

def organize(
    report: str = str(config.DEFAULT_REPORT),
    output_dir: str = None,
    copy: bool = False,
    execute: bool = False,
    include_unclassified: bool = True,
) -> None:
    """Move classified images into category-named folders.

    Args:
        report: Path to report JSON.
        output_dir: Target directory (default: same dir as report).
        copy: Copy instead of move.
        execute: Actually move files (default is dry-run).
        include_unclassified: Also organise unclassified files.
    """
    from cull.organize import organize_by_category
    organize_by_category(
        report,
        output_dir=output_dir,
        copy=copy,
        dry_run=not execute,
        include_unclassified=include_unclassified,
    )


# ── Subcommand: dedup ────────────────────────────────────────────────

def dedup(
    path: str,
    dupes_dir: str = None,
    execute: bool = False,
) -> None:
    """Find and remove duplicate images using perceptual hashing.

    Args:
        path: Directory to scan for duplicates.
        dupes_dir: Where to move duplicates (default: ../duplicates/).
        execute: Actually move duplicates (default is dry-run).
    """
    from cull.dedup import deduplicate
    deduplicate(path, dupes_dir=dupes_dir, dry_run=not execute)


# ── Subcommand: cleanup ──────────────────────────────────────────────

def cleanup(
    dupes_dir: str = None,
    strategy: str = "trash",
    category: str = None,
    execute: bool = False,
) -> None:
    """Remove or report on duplicate files previously moved by ``dedup``.

    Args:
        dupes_dir: Path to the duplicates folder.
        strategy: One of 'trash' (macOS Trash), 'delete' (permanent),
            or 'list' (print paths).
        category: Only clean a specific category folder (e.g. 'screenshot').
        execute: Actually clean (default is dry-run report-only).
    """
    from cull.cleanup import report_duplicates, delete_duplicates

    if not execute:
        print("=== Duplicate summary ===")
        summary = report_duplicates(dupes_dir)
        if summary["total_files"] == 0:
            print("  No duplicates found.")
            return
        for cat, info in sorted(summary["categories"].items(), key=lambda x: -x[1]["files"]):
            print(f"  {cat}: {info['files']} files, {info['bytes'] / 1_000_000:.1f} MB")
        print(f"\n  Total: {summary['total_files']} files, {summary['total_bytes'] / 1_000_000:.1f} MB")
        print("\nRun with --execute --strategy <trash|delete> to clean up.")
        return

    delete_duplicates(
        dupes_dir=dupes_dir,
        strategy=strategy,
        category=category,
        dry_run=False,
    )


# ── Subcommand: volumes ──────────────────────────────────────────────

def volumes(
    list_only: bool = False,
    eject: str = None,
    force: bool = False,
) -> None:
    """List, inspect, or eject external volumes.

    Args:
        list_only: Just list available volumes (no action).
        eject: Name or path of a volume to eject.
        force: Force eject even if volume is busy.
    """
    from cull.volumes import list_volumes, format_volume_summary, safe_eject

    vols = list_volumes()

    if eject:
        target_path = None
        for v in vols:
            if v["name"] == eject or v["path"] == eject:
                target_path = v["path"]
                break
        if not target_path:
            print(f"Volume not found: {eject}")
            sys.exit(1)
        ok, msg = safe_eject(target_path, force=force)
        print(f"{'✅' if ok else '❌'} {msg}")
        return

    print(format_volume_summary())


# ── Subcommand: categories ───────────────────────────────────────────

def categories(path: str = None) -> None:
    """Print available category labels."""
    from cull.categories import DEFAULT_CATEGORIES, validate_categories

    print("\nAvailable categories:")
    for cat, prompts in DEFAULT_CATEGORIES.items():
        print(f"  {cat}: {prompts[0]}")

    warnings = validate_categories(DEFAULT_CATEGORIES)
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  ⚠️  {w}")


# ── Subcommand: gui ──────────────────────────────────────────────────

def gui() -> None:
    """Launch the Gradio web interface."""
    import gradio as gr
    from cull.gui import app, CSS
    app.launch(show_error=True, css=CSS, theme=gr.themes.Soft())


# ── Subcommand: browse ───────────────────────────────────────────────

def browse(report: str = str(config.DEFAULT_REPORT)) -> None:
    """Launch interactive Streamlit report viewer."""
    viewer = Path(__file__).parent / "browse.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(viewer), "--", report])


# ── Subcommand: delete (legacy) ──────────────────────────────────────

def delete(report: str = str(config.DEFAULT_REPORT), category: str = None, dry_run: bool = True):
    """Delete files from a category in the report."""
    from cull.delete import delete_category, delete_report
    if category:
        delete_category(report, category, dry_run=dry_run)
    else:
        delete_report(report, dry_run=dry_run)


# ── Entry point ──────────────────────────────────────────────────────

def _setup_logging() -> None:
    level = os.environ.get("LOG_LEVEL", "WARNING").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
        datefmt="%H:%M:%S",
    )


def version() -> None:
    """Print the installed cull version."""
    from cull import __version__
    print(f"cull v{__version__}")


def main() -> None:
    _setup_logging()
    fire.Fire({
        "classify": classify,
        "organize": organize,
        "dedup": dedup,
        "cleanup": cleanup,
        "volumes": volumes,
        "categories": categories,
        "gui": gui,
        "browse": browse,
        "delete": delete,
        "version": version,
    })


if __name__ == "__main__":
    main()

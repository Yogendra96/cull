"""Pytest fixtures and shared helpers for cull tests."""

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Yield a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_report(temp_dir):
    """Create a minimal cull report JSON in a temp directory and return its path."""
    report = {
        "total": 3,
        "classified": 2,
        "unclassified": 1,
        "errors": 0,
        "categories": {
            "screenshot": {
                "count": 1,
                "files": [str(temp_dir / "screen.png")],
            },
            "person": {
                "count": 1,
                "files": [str(temp_dir / "selfie.jpg")],
            },
            "unclassified": {
                "count": 1,
                "files": [str(temp_dir / "blurry.png")],
            },
        },
    }
    # Create dummy files so organise tests can verify moves
    for info in report["categories"].values():
        for fp in info["files"]:
            Path(fp).write_text("fake-image-data")

    report_path = temp_dir / "cull_report.json"
    report_path.write_text(json.dumps(report))
    return report_path


@pytest.fixture
def sample_duplicates_dir(temp_dir):
    """Create a mini duplicates structure for cleanup tests."""
    cats = {"screenshot": 3, "meme": 2, "unclassified": 1}
    for cat, count in cats.items():
        cat_dir = temp_dir / cat
        cat_dir.mkdir(parents=True)
        for i in range(count):
            f = cat_dir / f"dup_{i}.jpg"
            f.write_text(f"fake-dup-{i}")
    return temp_dir

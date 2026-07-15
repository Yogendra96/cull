"""Tests for media.py — file type detection and volume utilities."""

from pathlib import Path

import pytest

from cull.media import (
    is_image,
    is_video,
    is_pdf,
    is_supported,
    should_skip,
)


class TestFileTypeDetection:
    """Verify that extension-based predicates work correctly."""

    @pytest.mark.parametrize(
        "path, expected",
        [
            ("photo.jpg", True),
            ("photo.jpeg", True),
            ("photo.png", True),
            ("photo.gif", True),
            ("photo.webp", True),
            ("photo.bmp", True),
            ("photo.tiff", True),
            ("photo.tif", True),
            ("photo.heic", True),
            ("photo.heif", True),
            ("photo.avif", True),
            ("photo.jxl", True),
            ("photo.JPG", True),  # case-insensitive
            ("document.pdf", False),
            ("video.mp4", False),
            ("notes.txt", False),
        ],
    )
    def test_is_image(self, path: str, expected: bool):
        assert is_image(path) == expected

    @pytest.mark.parametrize(
        "path, expected",
        [
            ("video.mp4", True),
            ("video.mov", True),
            ("video.avi", True),
            ("video.mkv", True),
            ("video.webm", True),
            ("video.wmv", True),
            ("video.flv", True),
            ("video.m4v", True),
            ("video.3gp", True),
            ("video.ts", True),
            ("video.MP4", True),
            ("photo.jpg", False),
            ("document.pdf", False),
        ],
    )
    def test_is_video(self, path: str, expected: bool):
        assert is_video(path) == expected

    @pytest.mark.parametrize(
        "path, expected",
        [
            ("document.pdf", True),
            ("document.PDF", True),
            ("photo.jpg", False),
            ("video.mp4", False),
        ],
    )
    def test_is_pdf(self, path: str, expected: bool):
        assert is_pdf(path) == expected

    @pytest.mark.parametrize(
        "path, expected",
        [
            ("photo.jpg", True),
            ("video.mp4", True),
            ("document.pdf", True),
            ("notes.txt", False),
            ("archive.zip", False),
            ("script.py", False),
        ],
    )
    def test_is_supported(self, path: str, expected: bool):
        assert is_supported(path) == expected


class TestSkipDetection:
    """Verify macOS artifact filtering."""

    @pytest.mark.parametrize(
        "name, expected",
        [
            (".DS_Store", True),
            (".localized", True),
            (".Trashes", True),
            (".fseventsd", True),
            (".Spotlight-V100", True),
            (".hidden_file", True),
            (".gitkeep", True),
            ("photo.jpg", False),
            ("normal.txt", False),
            ("My File.pdf", False),
        ],
    )
    def test_should_skip(self, name: str, expected: bool):
        assert should_skip(name) == expected


class TestVolumeUtilities:
    """Tests for volume helpers that don't require actual mounts."""

    def test_list_volumes_no_volumes_root(self, monkeypatch):
        """When /Volumes doesn't exist, return empty list."""
        monkeypatch.setattr("cull.media.MACOS_VOLUMES_ROOT", Path("/nonexistent"))
        from cull.media import list_volumes

        assert list_volumes() == []

    def test_validate_mount_nonexistent_path(self):
        """A path that doesn't exist should report as invalid."""
        from cull.media import validate_mount

        valid, msg = validate_mount("/tmp/nonexistent_path_xyz")
        assert not valid
        assert "does not exist" in msg.lower()

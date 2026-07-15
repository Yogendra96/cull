"""Tests for config.py — configuration defaults and constants."""

from pathlib import Path

from cull import config


class TestConfigDefaults:
    """Verify configuration defaults are sensible."""

    def test_threshold_range(self):
        """Threshold should be between 0 and 1."""
        assert 0 < config.DEFAULT_THRESHOLD < 1

    def test_batch_size_positive(self):
        """Batch size should be a positive integer."""
        assert config.DEFAULT_BATCH_SIZE > 0

    def test_model_name_is_string(self):
        """Model name should be a non-empty string."""
        assert isinstance(config.DEFAULT_MODEL, str)
        assert len(config.DEFAULT_MODEL) > 0

    def test_pretrained_is_string(self):
        """Pretrained tag should be a non-empty string."""
        assert isinstance(config.DEFAULT_PRETRAINED, str)
        assert len(config.DEFAULT_PRETRAINED) > 0

    def test_accurate_model_different(self):
        """Accurate model should differ from the default model."""
        assert config.ACCURATE_MODEL != config.DEFAULT_MODEL

    def test_duplicates_dir_path(self):
        """DUPLICATES_DIR should resolve to a path under home."""
        path = config.DUPLICATES_DIR
        assert isinstance(path, Path)
        assert str(path).startswith(str(Path.home()))

    def test_orphans_sorted_path(self):
        """ORPHANS_SORTED should resolve to a path under home."""
        path = config.ORPHANS_SORTED
        assert isinstance(path, Path)
        assert str(path).startswith(str(Path.home()))

"""Tests for cleanup.py — duplicate report and deletion logic."""

from cull.cleanup import delete_duplicates, report_duplicates


class TestReportDuplicates:
    """Test the duplicate reporting function."""

    def test_empty_dir(self, temp_dir):
        """An empty directory should report zero files."""
        result = report_duplicates(str(temp_dir))
        assert result["total_files"] == 0
        assert result["total_bytes"] == 0
        assert result["categories"] == {}

    def test_non_existent_dir(self):
        """A non-existent directory should report zero files."""
        result = report_duplicates("/tmp/nonexistent_xyz")
        assert result["total_files"] == 0

    def test_reports_categories(self, sample_duplicates_dir):
        """Should return correct file counts per category."""
        result = report_duplicates(str(sample_duplicates_dir))
        assert result["total_files"] == 6  # 3 + 2 + 1
        assert result["categories"]["screenshot"]["files"] == 3
        assert result["categories"]["meme"]["files"] == 2
        assert result["categories"]["unclassified"]["files"] == 1

    def test_expands_nested_dirs(self, temp_dir):
        """Should expand nested dirs like videos/animation."""
        # Create: top-cat/file1.jpg, videos/animation/file2.jpg, videos/video_call/file3.jpg
        (temp_dir / "top-cat").mkdir()
        (temp_dir / "top-cat" / "file1.jpg").write_text("data")
        (temp_dir / "videos" / "animation").mkdir(parents=True)
        (temp_dir / "videos" / "animation" / "file2.jpg").write_text("data")
        (temp_dir / "videos" / "video_call").mkdir(parents=True)
        (temp_dir / "videos" / "video_call" / "file3.jpg").write_text("data")

        result = report_duplicates(str(temp_dir))
        assert "top-cat" in result["categories"]
        assert "videos/animation" in result["categories"]
        assert "videos/video_call" in result["categories"]
        assert "videos" not in result["categories"]  # flat name should not appear
        assert result["total_files"] == 3


class TestDeleteDuplicates:
    """Test the duplicate deletion function."""

    def test_dry_run_does_not_delete(self, sample_duplicates_dir):
        """Dry-run should not remove any files."""
        result = delete_duplicates(
            str(sample_duplicates_dir),
            strategy="delete",
            dry_run=True,
        )
        assert result["removed"] == 0
        # Files should still exist
        assert (sample_duplicates_dir / "screenshot" / "dup_0.jpg").exists()

    def test_delete_removes_files(self, sample_duplicates_dir):
        """Executed delete should remove all files."""
        result = delete_duplicates(
            str(sample_duplicates_dir),
            strategy="delete",
            dry_run=False,
        )
        assert result["removed"] == 6
        assert result["strategy"] == "delete"
        # All files should be gone
        assert not (sample_duplicates_dir / "screenshot" / "dup_0.jpg").exists()

    def test_delete_by_category(self, sample_duplicates_dir):
        """Should only delete files in the specified category."""
        result = delete_duplicates(
            str(sample_duplicates_dir),
            strategy="delete",
            category="meme",
            dry_run=False,
        )
        assert result["removed"] == 2
        # Screenshot files should still exist
        assert (sample_duplicates_dir / "screenshot" / "dup_0.jpg").exists()
        # Meme files should be gone
        assert not (sample_duplicates_dir / "meme" / "dup_0.jpg").exists()

    def test_list_strategy_does_not_delete(self, sample_duplicates_dir):
        """'list' strategy should not remove files."""
        delete_duplicates(
            str(sample_duplicates_dir),
            strategy="list",
            dry_run=False,
        )
        assert (sample_duplicates_dir / "screenshot" / "dup_0.jpg").exists()

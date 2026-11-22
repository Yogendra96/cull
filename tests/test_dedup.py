"""Tests for the dedup command's progress/ETA integration."""

from PIL import Image, ImageDraw

from cull.dedup import deduplicate


def _png(path, variant: int):
    """Create a patterned image; equal variants are byte-identical."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(img)
    if variant == 0:
        for i in range(0, 64, 8):
            draw.line((0, i, 64, i), fill="black", width=2)
    else:
        for i in range(0, 64, 8):
            draw.line((i, 0, i, 64), fill="black", width=2)
    img.save(path)


def test_dedup_reports_estimate_and_finds_duplicates(tmp_path, capsys):
    _png(tmp_path / "a.png", 0)
    _png(tmp_path / "b.png", 0)
    _png(tmp_path / "c.png", 1)

    deduplicate(str(tmp_path), dupes_dir=str(tmp_path / "dupes"), dry_run=True)

    out = capsys.readouterr().out
    assert "Estimated time:" in out
    assert "ETA" in out
    assert "1 duplicate files" in out
    assert "Dry run" in out


def test_dedup_progress_can_be_disabled(tmp_path, capsys):
    _png(tmp_path / "a.png", 0)
    deduplicate(str(tmp_path), dupes_dir=str(tmp_path / "dupes"), progress=False)
    out = capsys.readouterr().out
    assert "ETA" not in out
    assert "Estimated time:" in out

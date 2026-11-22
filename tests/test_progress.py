"""Tests for progress reporting and ETA estimates."""

from cull import config
from cull.progress import Progress, estimate_line, estimate_seconds, format_duration


def test_format_duration_seconds():
    assert format_duration(0) == "0s"
    assert format_duration(7) == "7s"
    assert format_duration(65) == "1m 05s"
    assert format_duration(3661) == "1h 01m 01s"
    assert format_duration(None) == "?"


def test_estimate_seconds_uses_type_rates(tmp_path):
    images = [tmp_path / f"{i}.jpg" for i in range(config.ESTIMATE_IMAGES_PER_SEC)]
    videos = [tmp_path / f"{i}.mp4" for i in range(config.ESTIMATE_VIDEOS_PER_SEC)]
    pdfs = [tmp_path / f"{i}.pdf" for i in range(config.ESTIMATE_OTHER_PER_SEC)]
    seconds = estimate_seconds(images + videos + pdfs)
    # Each group is sized to take exactly one second.
    assert 2.9 <= seconds <= 3.1


def test_estimate_line_contains_count_and_time(tmp_path):
    paths = [tmp_path / "a.jpg", tmp_path / "b.jpg"]
    line = estimate_line(paths)
    assert "Estimated time:" in line
    assert "2 files" in line


def test_progress_emits_eta_on_close(capsys):
    bar = Progress(10, desc="Hashing", enabled=True)
    for _ in range(10):
        bar.update()
    bar.close()
    out = capsys.readouterr().out
    assert "Hashing:" in out
    assert "10/10" in out
    assert "ETA" in out
    assert "elapsed" in out


def test_progress_disabled_prints_nothing(capsys):
    bar = Progress(10, desc="Hashing", enabled=False)
    bar.update(10)
    bar.close()
    assert capsys.readouterr().out == ""


def test_progress_zero_total_does_not_divide_by_zero(capsys):
    bar = Progress(0, desc="Empty", enabled=True)
    bar.update()
    bar.close()
    out = capsys.readouterr().out
    assert "Empty:" in out
    assert "ETA" in out

"""Tests for exact-hash verification (``cull verify``)."""

import hashlib
import json
from pathlib import Path

from cull.verify import build_size_index, sha256_file, verify_duplicates


def _make(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_sha256_file(tmp_path):
    path = _make(tmp_path / "a.bin", b"hello")
    assert sha256_file(path) == hashlib.sha256(b"hello").hexdigest()


def test_sha256_missing_file_returns_none(tmp_path):
    assert sha256_file(tmp_path / "nope.bin") is None


def test_build_size_index_groups_by_size(tmp_path):
    _make(tmp_path / "ref" / "a.bin", b"1234")
    _make(tmp_path / "ref" / "sub" / "b.bin", b"1234")
    _make(tmp_path / "ref" / "c.bin", b"1")
    index = build_size_index([tmp_path / "ref"])
    assert len(index[4]) == 2
    assert len(index[1]) == 1


def test_build_size_index_excludes_dirs(tmp_path):
    _make(tmp_path / "ref" / "a.bin", b"1234")
    _make(tmp_path / "ref" / "skip" / "b.bin", b"1234")
    index = build_size_index([tmp_path / "ref"], exclude={(tmp_path / "ref" / "skip").resolve()})
    assert len(index[4]) == 1


def test_verify_dry_run_counts_and_keeps_files(tmp_path):
    dupes = tmp_path / "dupes"
    ref = tmp_path / "ref"
    _make(dupes / "cat" / "a.jpg", b"AAA")
    _make(dupes / "cat" / "b.jpg", b"BBB")
    _make(dupes / "cat" / "c.jpg", b"CCC")
    _make(ref / "x.jpg", b"AAA")
    _make(ref / "y.jpg", b"BBB")

    report = tmp_path / "report.json"
    result = verify_duplicates(
        dupes_dir=str(dupes),
        against=str(ref),
        report=str(report),
        execute=False,
    )

    assert result["total_files"] == 3
    assert result["verified"] == 2
    assert result["unverified"] == 1
    assert result["removed"] == 0
    # Dry run must not touch anything
    assert (dupes / "cat" / "a.jpg").exists()
    assert (dupes / "cat" / "c.jpg").exists()
    # Report written
    assert json.loads(report.read_text())["verified"] == 2


def test_verify_execute_removes_verified_and_quarantines_rest(tmp_path):
    dupes = tmp_path / "dupes"
    ref = tmp_path / "ref"
    _make(dupes / "cat" / "a.jpg", b"AAA")
    _make(dupes / "cat" / "c.jpg", b"CCC")
    _make(ref / "x.jpg", b"AAA")

    result = verify_duplicates(
        dupes_dir=str(dupes),
        against=str(ref),
        report=str(tmp_path / "r.json"),
        execute=True,
        strategy="delete",
    )

    assert result["removed"] == 1
    assert result["quarantined"] == 1
    assert not (dupes / "cat" / "a.jpg").exists()
    assert not (dupes / "cat" / "c.jpg").exists()
    quarantined = tmp_path / "duplicates_unverified" / "cat" / "c.jpg"
    assert quarantined.exists()
    assert quarantined.read_bytes() == b"CCC"


def test_same_size_different_content_is_unverified(tmp_path):
    dupes = tmp_path / "dupes"
    ref = tmp_path / "ref"
    _make(dupes / "x.bin", b"AAAA")
    _make(ref / "x.bin", b"BBBB")

    result = verify_duplicates(
        dupes_dir=str(dupes),
        against=str(ref),
        report=str(tmp_path / "r.json"),
    )

    assert result["verified"] == 0
    assert result["unverified"] == 1


def test_junk_files_are_ignored(tmp_path):
    dupes = tmp_path / "dupes"
    ref = tmp_path / "ref"
    _make(dupes / "cat" / "a.jpg", b"AAA")
    _make(dupes / "cat" / ".DS_Store", b"junk")
    _make(ref / "x.jpg", b"AAA")

    result = verify_duplicates(
        dupes_dir=str(dupes),
        against=str(ref),
        report=str(tmp_path / "r.json"),
    )

    assert result["total_files"] == 1
    assert result["junk"] == 1
    assert result["verified"] == 1


def test_reference_inside_dupes_dir_is_not_self_matched(tmp_path):
    dupes = tmp_path / "dupes"
    _make(dupes / "a.bin", b"AAAA")

    result = verify_duplicates(
        dupes_dir=str(dupes),
        against=str(dupes),
        report=str(tmp_path / "r.json"),
    )

    assert result["verified"] == 0
    assert result["unverified"] == 1


def test_missing_dupes_dir_returns_empty(tmp_path):
    result = verify_duplicates(
        dupes_dir=str(tmp_path / "missing"),
        against=str(tmp_path),
    )
    assert result == {}


def test_missing_reference_returns_empty(tmp_path):
    dupes = tmp_path / "dupes"
    _make(dupes / "a.bin", b"AAAA")
    result = verify_duplicates(
        dupes_dir=str(dupes),
        against=str(tmp_path / "missing"),
    )
    assert result == {}


def test_requires_against(tmp_path):
    dupes = tmp_path / "dupes"
    _make(dupes / "a.bin", b"AAAA")
    assert verify_duplicates(dupes_dir=str(dupes), against=None) == {}

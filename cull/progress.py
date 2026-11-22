"""Progress reporting with elapsed time and ETA.

Long hashing passes over thousands of files are otherwise silent.  This
module provides a small, dependency-free reporter (plus a cheap upfront
estimate based on file types) so the user knows roughly how long a run
will take and how far along it is.

Design notes:
  - Works in a TTY (single updating line) and in a log/non-TTY (one line
    per interval, no carriage returns).
  - Emits at most once per ``PROGRESS_INTERVAL_SECONDS`` to avoid flooding.
  - No assumptions about throughput: the ETA is based on the observed rate
    since the pass started.
"""

from __future__ import annotations

import math
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import TextIO

from cull import config
from cull.media import is_pdf, is_video


def format_duration(seconds: float | None) -> str:
    """Format a duration as ``1h 02m 03s`` / ``2m 05s`` / ``7s``."""
    if seconds is None or seconds < 0:
        return "?"
    total = math.ceil(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def estimate_seconds(paths: Iterable[Path]) -> float:
    """Rough upfront estimate for a hashing pass.

    Uses per-type throughput constants from :mod:`cull.config`.  This is a
    planning aid, not a promise: real speed depends on file size, disk I/O
    (USB/ExFAT is much slower than an internal APFS SSD) and whether videos
    need a frame extracted by ffmpeg.
    """
    images = videos = documents = 0
    for path in paths:
        name = str(path)
        if is_video(name):
            videos += 1
        elif is_pdf(name):
            documents += 1
        else:
            images += 1
    return (
        images / max(config.ESTIMATE_IMAGES_PER_SEC, 1)
        + videos / max(config.ESTIMATE_VIDEOS_PER_SEC, 1)
        + documents / max(config.ESTIMATE_OTHER_PER_SEC, 1)
    )


def estimate_line(paths: Iterable[Path]) -> str:
    """Human-readable one-line estimate for *paths*."""
    paths = list(paths) if not isinstance(paths, list) else paths
    seconds = estimate_seconds(paths)
    return (
        f"Estimated time: ~{format_duration(seconds)} "
        f"for {len(paths):,} files"
    )


class Progress:
    """Minimal progress reporter with elapsed time, rate and ETA."""

    def __init__(
        self,
        total: int,
        desc: str = "Working",
        enabled: bool = True,
        interval: float | None = None,
        stream: TextIO | None = None,
    ) -> None:
        self.total = max(int(total), 0)
        self.desc = desc
        self.enabled = enabled
        self.interval = (
            interval if interval is not None else config.PROGRESS_INTERVAL_SECONDS
        )
        self.stream = stream if stream is not None else sys.stdout
        self._tty = bool(getattr(self.stream, "isatty", lambda: False)())
        self._start = time.monotonic()
        self._last_emit = self._start
        self._done = 0

    # ── internals ────────────────────────────────────────────────────

    def _line(self, now: float) -> str:
        elapsed = max(now - self._start, 1e-9)
        rate = self._done / elapsed
        if self.total:
            pct = self._done / self.total * 100
            remaining = (self.total - self._done) / rate if rate > 0 else None
            counter = f"{self._done:,}/{self.total:,} ({pct:5.1f}%)"
        else:
            remaining = None
            counter = f"{self._done:,}"
        return (
            f"{self.desc}: {counter} · elapsed {format_duration(elapsed)}"
            f" · {rate:.1f}/s · ETA {format_duration(remaining)}"
        )

    def _emit(self, now: float) -> None:
        line = self._line(now)
        if self._tty:
            print(f"\r{line}", end="", file=self.stream, flush=True)
        else:
            print(line, file=self.stream, flush=True)

    # ── public API ───────────────────────────────────────────────────

    def update(self, n: int = 1) -> None:
        """Advance the counter; emits at most once per interval."""
        self._done += n
        if not self.enabled:
            return
        now = time.monotonic()
        if now - self._last_emit >= self.interval:
            self._emit(now)
            self._last_emit = now

    def close(self) -> None:
        """Emit the final state (always) and finish the line in a TTY."""
        if not self.enabled:
            return
        self._emit(time.monotonic())
        if self._tty:
            print(file=self.stream)

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start

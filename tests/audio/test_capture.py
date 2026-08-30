"""`record_until_silence` endpointing, driven by a fake `sounddevice` stream.

The real stream calls `callback(indata, ...)` from an audio thread; the fake
feeds canned blocks the same way, then pads with silence so `queue.get()` never
deadlocks if the block math is slightly off.
"""

from __future__ import annotations

import threading
import time

import numpy as np

from buddy.audio import capture

BLOCK = capture.BLOCK_SIZE  # 1600 samples = 100ms at 16kHz
LOUD = np.full((BLOCK, 1), 2000, dtype=np.int16)
QUIET = np.zeros((BLOCK, 1), dtype=np.int16)


class FakeStream:
    def __init__(self, blocks, **kw):
        self._blocks = list(blocks)
        self._cb = kw["callback"]
        self._stop = False
        self._thread: threading.Thread | None = None

    def __enter__(self):
        self._thread = threading.Thread(target=self._feed, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop = True
        return False

    def _feed(self):
        for b in self._blocks:
            self._cb(b, len(b), None, None)
            time.sleep(0.001)
        while not self._stop:  # keep the consumer from blocking
            self._cb(QUIET, BLOCK, None, None)
            time.sleep(0.001)


def _patch_stream(monkeypatch, blocks):
    monkeypatch.setattr(
        capture.sd, "InputStream", lambda **kw: FakeStream(blocks, **kw)
    )


def test_onset_timeout_returns_early_on_silence(monkeypatch):
    _patch_stream(monkeypatch, [QUIET] * 40)
    out = capture.record_until_silence(
        silence_duration=5.0, max_seconds=30, onset_timeout=0.5
    )
    # onset window is ~5 blocks; must bail there, not run for 5s of silence.
    assert len(out) <= 8 * BLOCK


def test_onset_timeout_does_not_fire_once_speech_heard(monkeypatch):
    _patch_stream(monkeypatch, [LOUD] * 3 + [QUIET] * 30)
    out = capture.record_until_silence(
        silence_duration=0.3, max_seconds=30, onset_timeout=0.5
    )
    # speech was heard before the 5-block onset cutoff, so it kept recording and
    # endpointed on ~3 blocks of trailing silence instead.
    assert 5 * BLOCK <= len(out) <= 12 * BLOCK


def test_no_onset_timeout_preserves_existing_behavior(monkeypatch):
    _patch_stream(monkeypatch, [LOUD] * 2 + [QUIET] * 30)
    out = capture.record_until_silence(silence_duration=0.3, max_seconds=30)
    # 2 loud + 3 silent blocks to endpoint = 5 blocks, no early onset bail.
    assert 4 * BLOCK <= len(out) <= 8 * BLOCK

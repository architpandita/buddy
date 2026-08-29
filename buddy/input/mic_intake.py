"""Voice intake for the voice-agent-plane.

Phase 0 established there is no external Whisper process on this machine — STT is
`whisper-cli` invoked per utterance, in-process. So this adapter is a thin
`Iterator[str]` over the existing trigger -> capture -> transcribe pipeline, not
a file/pipe/HTTP reader (docs/phase0-findings.md §4).

`trigger()` is the shared callback both `buddy.audio.hotkey` and
`buddy.audio.wakeword` fire. First trigger while idle starts a capture; a trigger
that lands mid-capture stops it early (push-to-talk pressed again), matching the
Milestone-1 behaviour in `buddy.assistant`.
"""

from __future__ import annotations

import queue
import threading
from typing import Callable, Iterator

import numpy as np

from buddy.audio import capture as _capture
from buddy.stt import whisper_transcriber as _stt

_SENTINEL = object()

Recorder = Callable[[threading.Event], "np.ndarray"]
Transcriber = Callable[["np.ndarray"], str]


def _default_record(stop_event: threading.Event) -> "np.ndarray":
    return _capture.record_until_silence(
        _capture.SILENCE_DURATION_S, _capture.MAX_RECORD_SECONDS, stop_event
    )


class MicIntake:
    def __init__(
        self,
        record: Recorder | None = None,
        transcribe: Transcriber | None = None,
    ):
        self._record = record or _default_record
        self._transcribe = transcribe or _stt.transcribe
        self._triggers: "queue.Queue[object]" = queue.Queue()
        self._recording = threading.Event()
        self._stop = threading.Event()
        self._closed = False

    def trigger(self) -> None:
        """Fire from the hotkey / wake-word callback (any thread)."""
        if self._recording.is_set():
            self._stop.set()
        elif not self._closed:
            self._triggers.put(True)

    def shutdown(self) -> None:
        self._closed = True
        self._triggers.put(_SENTINEL)

    def utterances(self) -> Iterator[str]:
        while True:
            item = self._triggers.get()
            if item is _SENTINEL:
                return

            self._recording.set()
            self._stop.clear()
            try:
                samples = self._record(self._stop)
            finally:
                self._recording.clear()

            try:
                text = self._transcribe(samples)
            except Exception as exc:  # whisper-cli failure: skip, keep listening
                print(f"[mic_intake] transcription failed: {exc}")
                continue

            text = (text or "").strip()
            if text:
                yield text

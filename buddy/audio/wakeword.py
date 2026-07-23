"""Continuous 'Hi Buddy' wake-word detection via openWakeWord.

Requires a trained model at config.WAKEWORD_MODEL_PATH (see README for the
one-time training steps). If the model file is missing, the listener logs a
warning and simply never fires -- push-to-talk still works standalone.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

import numpy as np
import sounddevice as sd

from buddy import config

SAMPLE_RATE = 16_000
FRAME_SIZE = 1_280  # openWakeWord expects 80ms chunks at 16kHz


class WakeWordListener:
    def __init__(self, on_detected: Callable[[], None]):
        self._on_detected = on_detected
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._model = None

    def available(self) -> bool:
        return config.WAKEWORD_MODEL_PATH.exists()

    def start(self) -> None:
        if not self.available():
            print(
                f"[wakeword] No model at {config.WAKEWORD_MODEL_PATH} -- "
                "wake word disabled, push-to-talk still works. See README."
            )
            return

        from openwakeword.model import Model

        self._model = Model(wakeword_models=[str(config.WAKEWORD_MODEL_PATH)])
        self._start_thread()
        print("[wakeword] Listening for 'Hi Buddy'...")

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def pause(self) -> None:
        """Releases the mic input stream while Buddy is actively recording a
        command, so the two don't open competing streams on the same device
        (which otherwise starves the recording stream and makes it look like
        Buddy "never stops listening"). No-op if the wake word isn't active.
        """
        if self._thread is None:
            return
        self.stop()
        self._stop.clear()

    def resume(self) -> None:
        """Re-arms wake-word detection after a command finishes. No-op if the
        wake word was never available (no model) or wasn't paused."""
        if self._model is None or self._thread is not None:
            return
        self._start_thread()

    def _start_thread(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME_SIZE
        ) as stream:
            while not self._stop.is_set():
                frame, _ = stream.read(FRAME_SIZE)
                audio = frame[:, 0].astype(np.int16)
                predictions = self._model.predict(audio)
                for score in predictions.values():
                    if score > config.WAKEWORD_THRESHOLD:
                        self._on_detected()
                        break

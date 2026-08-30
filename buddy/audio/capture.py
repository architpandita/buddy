"""Microphone recording with silence-based endpointing.

Records from the default input device starting immediately and stops once the
user has been quiet for `silence_duration` seconds (or `max_seconds` is hit).
Returns 16kHz mono PCM16 samples, ready for whisper.cpp.
"""

from __future__ import annotations

import queue

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000
BLOCK_SIZE = 1_600  # 100ms blocks at 16kHz
SILENCE_RMS_THRESHOLD = 500  # int16 RMS; tune to your mic/room
SILENCE_DURATION_S = 1.2
MAX_RECORD_SECONDS = 30


def _rms(block: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(block.astype(np.float64)))))


def record_until_silence(
    silence_duration: float = SILENCE_DURATION_S,
    max_seconds: float = MAX_RECORD_SECONDS,
    stop_event=None,
    onset_timeout: float | None = None,
) -> np.ndarray:
    """Blocking call: records mic audio until silence (or `stop_event` is set).

    `stop_event` (threading.Event) lets a hotkey "press again to stop" cancel
    the silence-based endpointing early — used for push-to-talk mode.

    `onset_timeout` (seconds): if set and no speech is heard within that window,
    stop and return whatever was captured (usually empty). Used by conversation
    mode's follow-up listen so a silent user drops the mic instead of holding it
    open for `max_seconds`. Once speech is heard the onset cutoff no longer
    applies — normal `silence_duration` endpointing takes over.
    """
    q: queue.Queue[np.ndarray] = queue.Queue()

    def _callback(indata, frames, time_info, status):
        q.put(indata.copy())

    blocks: list[np.ndarray] = []
    silence_blocks_needed = int(silence_duration * SAMPLE_RATE / BLOCK_SIZE)
    max_blocks = int(max_seconds * SAMPLE_RATE / BLOCK_SIZE)
    onset_blocks = (
        int(onset_timeout * SAMPLE_RATE / BLOCK_SIZE) if onset_timeout else None
    )
    consecutive_silence = 0
    heard_speech = False

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=BLOCK_SIZE,
        callback=_callback,
    ):
        while len(blocks) < max_blocks:
            if stop_event is not None and stop_event.is_set():
                break
            block = q.get()[:, 0]
            blocks.append(block)
            level = _rms(block)
            if (
                onset_blocks is not None
                and not heard_speech
                and len(blocks) >= onset_blocks
            ):
                break
            if level > SILENCE_RMS_THRESHOLD:
                heard_speech = True
                consecutive_silence = 0
            elif heard_speech:
                consecutive_silence += 1
                if consecutive_silence >= silence_blocks_needed:
                    break

    if not blocks:
        return np.zeros(0, dtype=np.int16)
    return np.concatenate(blocks)

"""Transcription via a locally installed whisper.cpp (`brew install whisper-cpp`)."""

from __future__ import annotations

import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from buddy import config
from buddy.audio.capture import SAMPLE_RATE


def _write_wav(samples: np.ndarray, path: Path) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(samples.tobytes())


def _run_whisper_on_wav(wav_path: Path, tmp_dir: Path) -> str:
    result = subprocess.run(
        [
            config.WHISPER_BIN,
            "-m", str(config.WHISPER_MODEL_PATH),
            "-f", str(wav_path),
            "-nt",  # no timestamps
            "-otxt",
            "-of", str(tmp_dir / "out"),
            "--language", "en",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[whisper] transcription failed: {result.stderr.strip()}")
        return ""

    out_txt = tmp_dir / "out.txt"
    if not out_txt.exists():
        return ""
    return out_txt.read_text().strip()


def transcribe(samples: np.ndarray) -> str:
    """Transcribes 16kHz mono PCM16 samples captured via `buddy.audio.capture`."""
    if samples.size == 0:
        return ""

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wav_path = tmp_path / "utterance.wav"
        _write_wav(samples, wav_path)
        return _run_whisper_on_wav(wav_path, tmp_path)


def transcribe_wav_bytes(wav_bytes: bytes) -> str:
    """Transcribes an already-encoded mono WAV file, e.g. one recorded in-browser."""
    if not wav_bytes:
        return ""

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wav_path = tmp_path / "utterance.wav"
        wav_path.write_bytes(wav_bytes)
        return _run_whisper_on_wav(wav_path, tmp_path)

"""Text-to-speech backend. Uses macOS `say` for now; swap the body of
`speak()` for a Piper/Kokoro (or other) backend later without touching callers.
"""

from __future__ import annotations

import subprocess
from typing import Callable

from buddy import config


def _default_runner(cmd: list[str]) -> None:
    subprocess.run(cmd)


def speak(text: str, runner: Callable[[list[str]], None] | None = None) -> None:
    if not text or not text.strip():
        return
    run = runner or _default_runner
    cmd = ["say"]
    if config.TTS_VOICE:
        cmd += ["-v", config.TTS_VOICE]
    cmd.append(text)
    run(cmd)

"""Text-to-speech backend. Uses macOS `say` for now; swap the body of
`speak()` for a Piper (or other) backend later without touching callers.
"""

from __future__ import annotations

import subprocess

from buddy import config


def speak(text: str) -> None:
    if not text:
        return
    cmd = ["say"]
    if config.TTS_VOICE:
        cmd += ["-v", config.TTS_VOICE]
    cmd.append(text)
    subprocess.run(cmd)

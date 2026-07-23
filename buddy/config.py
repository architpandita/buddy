"""Central settings for Buddy. Edit these to match your machine/projects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

BUDDY_ROOT = Path(__file__).resolve().parent.parent

# --- Wake word ---
WAKEWORD_MODEL_PATH = BUDDY_ROOT / "models" / "wakeword" / "hi_buddy.onnx"
WAKEWORD_THRESHOLD = 0.5

# --- Push-to-talk hotkey (pynput GlobalHotKeys format) ---
HOTKEY_COMBO = "<alt>+<space>"

# --- Whisper.cpp STT ---
WHISPER_BIN = "whisper-cli"  # installed via `brew install whisper-cpp`
WHISPER_MODEL_PATH = BUDDY_ROOT / "models" / "whisper" / "ggml-base.en.bin"

# --- TTS ---
TTS_VOICE = None  # None = macOS default voice; e.g. "Samantha" to override

# --- Browser server (web_main.py) ---
# Mic capture, push-to-talk, and TTS playback all happen in the browser tab;
# this server only transcribes + routes. Keep it bound to localhost.
WEB_HOST = "127.0.0.1"
WEB_PORT = 8765

# --- Claude Agent SDK / dev target ---
# The project directory Buddy will actually edit code in. Change this (or use
# the "switch to project <name>" voice command) to point at a real repo.
DEFAULT_PROJECT_DIR = BUDDY_ROOT

# Named projects reachable via "switch to project <name>". Add your own repos.
PROJECTS: dict[str, Path] = {
    "buddy": BUDDY_ROOT,
}

ALLOWED_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
PERMISSION_MODE = "acceptEdits"

# Deep-think OFF: fast model, low effort, thinking disabled -- snappy replies.
# Deep-think ON: stronger model, high effort, extended thinking budget -- for
# harder reasoning/design questions, at the cost of latency.
FAST_MODEL = "claude-sonnet-5"
DEEP_THINK_MODEL = "claude-opus-4-8"
DEEP_THINK_BUDGET_TOKENS = 16_000


@dataclass
class RuntimeState:
    """Mutable state flipped by voice control commands, not persisted."""

    active_project_dir: Path = field(default_factory=lambda: DEFAULT_PROJECT_DIR)
    deep_think: bool = False

    @property
    def model(self) -> str:
        return DEEP_THINK_MODEL if self.deep_think else FAST_MODEL

    @property
    def effort(self) -> str:
        return "high" if self.deep_think else "low"


state = RuntimeState()

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

# ==========================================================================
# Voice Agent Plane (docs/voice-assistant-plan.md) — separate from Milestone 1
# ==========================================================================

# Every `claude -p` call runs with cwd here, NOT the repo dir: Phase 0 found the
# repo dir adds ~15s of MCP/hook discovery per call, and an empty sandbox also
# satisfies the plan §7 filesystem-access mitigation.
VAP_SANDBOX_DIR = Path.home() / ".buddy" / "sandbox"

# Agent spec markdown files (system prompt + frontmatter) live here.
VAP_AGENTS_DIR = BUDDY_ROOT / "agents"

# Per-agent persisted Claude session ids (short-term memory, plan §4.6).
VAP_STATE_DIR = Path.home() / ".buddy" / "state"

# Claude Code writes for a terminal; cap how much we ever speak in one turn.
SPOKEN_TURN_MAX_SENTENCES = 4

# Workhorse models on Pro (Opus is allowance-limited — never auto-selected).
VAP_FAST_MODEL = "claude-haiku-4-5-20251001"
VAP_SMART_MODEL = "claude-sonnet-5"

# Long-term memory (plan §4.6): flat markdown, explicit writes only, never
# auto-deleted. Keyword retrieval injects at most this many characters into a
# turn (~200 tokens) — never the whole store.
VAP_MEMORY_DIR = Path.home() / ".buddy" / "memory"
VAP_MEMORY_RETRIEVAL_BUDGET_CHARS = 800

# Spoken-turn transcripts, kept for the janitor to prune. 0 = keep nothing.
VAP_TRANSCRIPT_DIR = Path.home() / ".buddy" / "transcripts"
VAP_TRANSCRIPT_TTL_DAYS = 7

# Conversation mode (docs/superpowers/specs/2026-08-30-conversation-mode-design.md):
# after "start conversation", the voice loop auto-listens once per reply. It waits
# ONSET_TIMEOUT_S for the user to start talking, then ends their turn on
# SILENCE_S of trailing quiet. MAX_IDLE_WINDOWS consecutive silent windows exit
# the mode (first window + 2 retries).
VAP_CONVERSATION_ONSET_TIMEOUT_S = 8.0
VAP_CONVERSATION_SILENCE_S = 4.0
VAP_CONVERSATION_MAX_IDLE_WINDOWS = 3

# Router (plan §4.3): turns longer than this many words escalate a fast-model
# agent to the smart model. Opus is never auto-selected — override only.
VAP_LONG_TURN_WORDS = 40

# Session rotation (plan §4.6): every N Claude turns per agent, summarise to a
# card and start a fresh session so long transcripts stop being resent.
VAP_ROTATE_EVERY_N_TURNS = 8
VAP_ROTATION_CARD_MAX_CHARS = 900

# Allowance control (plan §6.7): hard daily cap on Claude turns. On hit Buddy
# says so and stops — no degraded fallback. Start conservative; raise once you
# have observed real headroom (Phase 0 left this unmeasured).
VAP_DAILY_TURN_CAP = 40
VAP_ALLOWANCE_FILE = Path.home() / ".buddy" / "allowance.json"

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

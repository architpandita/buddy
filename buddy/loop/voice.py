"""End-to-end voice loop: mic intake -> run_turn -> spoken reply.

A single sequential loop. Utterances the intake buffers while a turn is being
spoken are handled on the next iteration (barge-in policy: queue, don't
interrupt). The spoken reply is returned by `run_turn` and never handed back to
the intake, so TTS can't feed itself.

Conversation mode (see docs/superpowers/specs/2026-08-30-conversation-mode-design.md):
when a shared `VapState.conversation_mode` is on, the loop auto-listens after each
reply via `intake.follow_up()` instead of waiting for a fresh trigger. Three
consecutive silent windows turn the mode back off.
"""

from __future__ import annotations

from typing import Callable

from buddy import config
from buddy.tts.speaker import speak as _real_speak

_IDLE_EXIT = "I'll be here — say start conversation when you're back."


class VoiceLoop:
    def __init__(self, intake, turn_runner, state=None, speak: Callable[[str], None] | None = None):
        self._intake = intake
        self._turn_runner = turn_runner
        self._state = state
        self._speak = speak or _real_speak

    def run(self) -> None:
        for text in self._intake.utterances():
            self._run_turn_safely(text)
            self._drain_follow_ups()

    def _run_turn_safely(self, text: str) -> None:
        try:
            self._turn_runner.run_turn(text)
        except Exception as exc:  # one bad turn shouldn't end the session
            print(f"[voice] turn failed: {exc}")

    def _drain_follow_ups(self) -> None:
        if self._state is None:
            return
        empty = 0
        while self._state.conversation_mode:
            follow = self._intake.follow_up()
            if follow is None:
                empty += 1
                if empty >= config.VAP_CONVERSATION_MAX_IDLE_WINDOWS:
                    self._state.conversation_mode = False
                    self._speak(_IDLE_EXIT)
                continue
            empty = 0
            self._run_turn_safely(follow)

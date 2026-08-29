"""End-to-end voice loop: mic intake -> run_turn -> spoken reply.

A single sequential loop. Utterances the intake buffers while a turn is being
spoken are handled on the next iteration (barge-in policy: queue, don't
interrupt). The spoken reply is returned by `run_turn` and never handed back to
the intake, so TTS can't feed itself.
"""

from __future__ import annotations


class VoiceLoop:
    def __init__(self, intake, turn_runner):
        self._intake = intake
        self._turn_runner = turn_runner

    def run(self) -> None:
        for text in self._intake.utterances():
            try:
                self._turn_runner.run_turn(text)
            except Exception as exc:  # one bad turn shouldn't end the session
                print(f"[voice] turn failed: {exc}")

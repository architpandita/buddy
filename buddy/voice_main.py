"""Phase 2 entrypoint: end-to-end voice for the voice-agent-plane.

    python -m buddy.voice_main

Push-to-talk hotkey or "Hi Buddy" wake word -> mic capture -> whisper -> Claude
(Companion agent) -> spoken reply. Same TurnRunner as `buddy.textloop`; only the
input side changes.

This is separate from Milestone-1's `main.py` (which drives a code-editing Claude
Code session). Shared: the audio / STT / TTS primitives.
"""

from __future__ import annotations

import threading

from buddy import config
from buddy.audio import capture
from buddy.audio.hotkey import HotkeyListener
from buddy.audio.wakeword import WakeWordListener
from buddy.input.mic_intake import MicIntake
from buddy.loop.build import build_switchboard
from buddy.loop.voice import VoiceLoop
from buddy.memory.janitor import Janitor


def main() -> None:
    runner = build_switchboard()
    wakeword_box: dict[str, WakeWordListener] = {}

    def record(stop_event: threading.Event):
        ww = wakeword_box.get("ww")
        # Wake-word detection competes with capture for the mic device; pause it
        # while we're actively recording a command (matches buddy.assistant).
        if ww is not None:
            ww.pause()
        try:
            return capture.record_until_silence(
                capture.SILENCE_DURATION_S, capture.MAX_RECORD_SECONDS, stop_event
            )
        finally:
            if ww is not None:
                ww.resume()

    def follow_up_record(stop_event: threading.Event):
        ww = wakeword_box.get("ww")
        if ww is not None:
            ww.pause()
        try:
            return capture.record_until_silence(
                config.VAP_CONVERSATION_SILENCE_S,
                capture.MAX_RECORD_SECONDS,
                stop_event,
                onset_timeout=config.VAP_CONVERSATION_ONSET_TIMEOUT_S,
            )
        finally:
            if ww is not None:
                ww.resume()

    intake = MicIntake(record=record, follow_up_record=follow_up_record)
    hotkey = HotkeyListener(on_press=intake.trigger)
    wakeword = WakeWordListener(on_detected=intake.trigger)
    wakeword_box["ww"] = wakeword

    hotkey.start()
    wakeword.start()
    print("[voice] Ready. Press the hotkey or say 'Hi Buddy'. Ctrl-C to quit.")
    try:
        VoiceLoop(intake=intake, turn_runner=runner, state=runner.state).run()
    except KeyboardInterrupt:
        pass
    finally:
        intake.shutdown()
        hotkey.stop()
        wakeword.stop()
        Janitor().purge_sessions()  # conversation end: drop session state


if __name__ == "__main__":
    main()

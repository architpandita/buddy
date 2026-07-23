"""Orchestrates Buddy: trigger -> record -> transcribe -> route -> respond."""

from __future__ import annotations

import asyncio
import queue
import threading

from buddy import config
from buddy.agent import claude_driver
from buddy.audio import capture
from buddy.audio.hotkey import HotkeyListener
from buddy.audio.wakeword import WakeWordListener
from buddy.stt import whisper_transcriber
from buddy.tts import speaker

_trigger_queue: queue.Queue[bool] = queue.Queue()
_recording_active = threading.Event()
_manual_stop = threading.Event()


def _on_trigger() -> None:
    """Shared callback for both the hotkey and the wake word.

    First trigger while idle starts a recording. A second trigger while a
    recording is already in progress (push-to-talk pressed again) stops it
    early instead of waiting for silence.
    """
    if _recording_active.is_set():
        _manual_stop.set()
    else:
        _trigger_queue.put(True)


def _try_handle_control_command(text: str) -> str | None:
    """Handles phrases Buddy answers locally, without calling Claude.

    Returns the response text if `text` was a recognized control command
    (possibly "" for a silent no-op like "stop"), or None if it wasn't one and
    should be forwarded to Claude instead.
    """
    lowered = text.lower().strip().rstrip(".")

    if lowered in ("deep think on", "enable deep thinking", "turn on deep thinking"):
        config.state.deep_think = True
        print("[assistant] deep think -> ON")
        return "Deep thinking mode on."

    if lowered in ("deep think off", "disable deep thinking", "turn off deep thinking"):
        config.state.deep_think = False
        print("[assistant] deep think -> OFF")
        return "Deep thinking mode off."

    for prefix in ("switch to project ", "work on project "):
        if lowered.startswith(prefix):
            name = lowered[len(prefix):].strip()
            target = config.PROJECTS.get(name)
            if target is None:
                return f"I don't know a project called {name}."
            config.state.active_project_dir = target
            print(f"[assistant] active project -> {target}")
            return f"Switched to project {name}."

    if lowered in ("stop", "cancel", "never mind", "nevermind"):
        return ""

    return None


async def process_utterance(text: str) -> str:
    """Routes a transcribed utterance to a control command or Claude.

    Shared by the CLI loop and the browser server -- callers decide how to
    surface the returned response text (spoken via `say`, spoken via the
    browser's Web Speech API, displayed, etc.).
    """
    print(f"[assistant] heard: {text}")
    if not text:
        return ""

    control_response = _try_handle_control_command(text)
    if control_response is not None:
        return control_response

    result = await claude_driver.run_instruction(text)
    if result:
        print(f"[assistant] result: {result}")
    return result


async def _handle_utterance(text: str) -> None:
    response = await process_utterance(text)
    if response:
        speaker.speak(response)


async def run() -> None:
    loop = asyncio.get_running_loop()

    hotkey = HotkeyListener(on_press=_on_trigger)
    wakeword = WakeWordListener(on_detected=_on_trigger)
    hotkey.start()
    wakeword.start()

    print("[assistant] Ready. Press the hotkey or say 'Hi Buddy'.")

    try:
        while True:
            await loop.run_in_executor(None, _trigger_queue.get)

            _recording_active.set()
            _manual_stop.clear()
            # Pause wake-word detection while actively recording a command --
            # otherwise its mic stream competes with capture's for the same
            # device, and the recording never reliably detects silence.
            wakeword.pause()
            try:
                print("[assistant] listening...")
                samples = await loop.run_in_executor(
                    None, capture.record_until_silence, capture.SILENCE_DURATION_S,
                    capture.MAX_RECORD_SECONDS, _manual_stop,
                )
                _recording_active.clear()

                text = await loop.run_in_executor(None, whisper_transcriber.transcribe, samples)
                await _handle_utterance(text)
            finally:
                wakeword.resume()
    finally:
        hotkey.stop()
        wakeword.stop()

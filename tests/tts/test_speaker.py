from __future__ import annotations

from buddy import config
from buddy.tts import speaker


def test_speak_invokes_say_with_configured_voice(monkeypatch):
    calls = []
    monkeypatch.setattr(config, "TTS_VOICE", "Samantha")
    speaker.speak("hello world", runner=calls.append)
    assert calls == [["say", "-v", "Samantha", "hello world"]]


def test_speak_without_voice_omits_v_flag(monkeypatch):
    calls = []
    monkeypatch.setattr(config, "TTS_VOICE", None)
    speaker.speak("hi", runner=calls.append)
    assert calls == [["say", "hi"]]


def test_speak_is_noop_on_empty_string():
    calls = []
    speaker.speak("", runner=calls.append)
    speaker.speak("   ", runner=calls.append)
    assert calls == []

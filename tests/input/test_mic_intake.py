from __future__ import annotations

import numpy as np

from buddy.input.mic_intake import MicIntake

SAMPLES = np.ones(1600, dtype=np.int16)


def take(iterator, n):
    out = []
    for item in iterator:
        out.append(item)
        if len(out) >= n:
            break
    return out


def test_trigger_then_capture_then_transcribe_yields_text():
    intake = MicIntake(
        record=lambda stop_event: SAMPLES,
        transcribe=lambda samples: "hello buddy",
    )
    intake.trigger()
    intake.shutdown()  # let the loop end after draining
    assert take(intake.utterances(), 1) == ["hello buddy"]


def test_empty_transcription_is_skipped():
    texts = iter(["", "   ", "real one"])
    intake = MicIntake(
        record=lambda stop_event: SAMPLES,
        transcribe=lambda samples: next(texts),
    )
    for _ in range(3):
        intake.trigger()
    intake.shutdown()
    assert list(intake.utterances()) == ["real one"]


def test_second_trigger_while_recording_stops_capture_early():
    seen = {}

    def record(stop_event):
        # a trigger arriving mid-recording must set our stop event
        intake.trigger()
        seen["stopped_early"] = stop_event.is_set()
        return SAMPLES

    intake = MicIntake(record=record, transcribe=lambda s: "x")
    intake.trigger()
    intake.shutdown()
    take(intake.utterances(), 1)
    assert seen["stopped_early"] is True


def test_transcriber_failure_yields_nothing_not_crash():
    def boom(samples):
        raise RuntimeError("whisper exited 1")

    intake = MicIntake(record=lambda stop_event: SAMPLES, transcribe=boom)
    intake.trigger()
    intake.shutdown()
    assert list(intake.utterances()) == []


def test_shutdown_ends_iteration():
    intake = MicIntake(record=lambda stop_event: SAMPLES, transcribe=lambda s: "hi")
    intake.shutdown()
    assert list(intake.utterances()) == []


# -- conversation-mode follow-up ------------------------------------------------


def test_follow_up_returns_transcript_on_speech():
    intake = MicIntake(
        follow_up_record=lambda stop_event: SAMPLES,
        transcribe=lambda samples: "yes please",
    )
    assert intake.follow_up() == "yes please"


def test_follow_up_returns_none_on_empty_samples():
    intake = MicIntake(
        follow_up_record=lambda stop_event: np.zeros(0, dtype=np.int16),
        transcribe=lambda samples: "should not be called",
    )
    assert intake.follow_up() is None


def test_follow_up_returns_none_on_transcription_failure():
    def boom(samples):
        raise RuntimeError("whisper exited 1")

    intake = MicIntake(follow_up_record=lambda stop_event: SAMPLES, transcribe=boom)
    assert intake.follow_up() is None


def test_follow_up_does_not_consume_trigger_queue():
    main_calls = []
    intake = MicIntake(
        record=lambda stop_event: main_calls.append(1) or SAMPLES,
        follow_up_record=lambda stop_event: SAMPLES,
        transcribe=lambda s: "hi",
    )
    intake.trigger()
    intake.follow_up()
    assert main_calls == []  # follow-up used its own recorder
    assert intake._triggers.qsize() == 1  # the queued trigger is untouched

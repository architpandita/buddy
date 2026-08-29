from __future__ import annotations

from buddy.loop.voice import VoiceLoop


class FakeIntake:
    def __init__(self, *texts):
        self._texts = list(texts)

    def utterances(self):
        yield from self._texts


class RecordingRunner:
    def __init__(self, reply_for=None):
        self.seen = []
        self._reply_for = reply_for or (lambda t: f"echo: {t}")

    def run_turn(self, text):
        self.seen.append(text)
        return self._reply_for(text)


def test_each_utterance_drives_run_turn():
    runner = RecordingRunner()
    VoiceLoop(intake=FakeIntake("what time is it", "thanks"), turn_runner=runner).run()
    assert runner.seen == ["what time is it", "thanks"]


def test_speaker_output_not_fed_back_as_input():
    """The spoken reply must never re-enter the intake."""
    fed_back = []

    class Intake:
        def utterances(self):
            yield "hello"

        def trigger(self):
            fed_back.append("triggered")

    runner = RecordingRunner(reply_for=lambda t: "a reply that mentions hello")
    VoiceLoop(intake=Intake(), turn_runner=runner).run()
    assert runner.seen == ["hello"]
    assert fed_back == []


def test_turn_exception_does_not_kill_the_loop():
    class Flaky:
        def __init__(self):
            self.seen = []

        def run_turn(self, text):
            self.seen.append(text)
            if text == "bad":
                raise RuntimeError("turn blew up")
            return "ok"

    runner = Flaky()
    VoiceLoop(intake=FakeIntake("bad", "good"), turn_runner=runner).run()
    assert runner.seen == ["bad", "good"]

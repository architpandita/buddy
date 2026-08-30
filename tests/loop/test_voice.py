from __future__ import annotations

from buddy import config
from buddy.loop.voice import VoiceLoop
from buddy.route.state import VapState


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


# -- conversation mode --------------------------------------------------------


class ConvoIntake:
    def __init__(self, trigger_texts, follow_ups):
        self._triggers = list(trigger_texts)
        self._follow_ups = list(follow_ups)
        self.follow_up_calls = 0

    def utterances(self):
        yield from self._triggers

    def follow_up(self):
        self.follow_up_calls += 1
        return self._follow_ups.pop(0) if self._follow_ups else None


def test_no_state_means_no_follow_ups():
    intake = ConvoIntake(["hi"], ["should-never-run"])
    runner = RecordingRunner()
    VoiceLoop(intake=intake, turn_runner=runner).run()  # state defaults to None
    assert runner.seen == ["hi"]
    assert intake.follow_up_calls == 0


def test_follow_up_turn_runs_when_conversation_mode_on():
    state = VapState(conversation_mode=True)
    intake = ConvoIntake(["hi"], ["yes please"])
    runner = RecordingRunner()
    VoiceLoop(intake=intake, turn_runner=runner, state=state, speak=lambda _: None).run()
    assert runner.seen == ["hi", "yes please"]
    assert state.conversation_mode is False  # trailing silent windows exited it


def test_three_empty_windows_exit_conversation_mode():
    state = VapState(conversation_mode=True)
    intake = ConvoIntake(["hi"], [])  # every follow_up returns None
    spoken = []
    runner = RecordingRunner()
    VoiceLoop(intake=intake, turn_runner=runner, state=state, speak=spoken.append).run()
    assert intake.follow_up_calls == config.VAP_CONVERSATION_MAX_IDLE_WINDOWS
    assert state.conversation_mode is False
    assert spoken and "start conversation" in spoken[-1].lower()


def test_non_empty_window_resets_empty_counter():
    state = VapState(conversation_mode=True)
    intake = ConvoIntake(["hi"], [None, None, "still here", None, None])
    runner = RecordingRunner()
    VoiceLoop(intake=intake, turn_runner=runner, state=state, speak=lambda _: None).run()
    assert runner.seen == ["hi", "still here"]
    assert state.conversation_mode is False


def test_end_conversation_during_follow_up_stops_the_drain():
    state = VapState(conversation_mode=True)
    intake = ConvoIntake(["hi"], ["end conversation", "should-not-be-reached"])

    def on_text(text):
        if text == "end conversation":
            state.conversation_mode = False

    runner = RecordingRunner()
    runner._reply_for = lambda t: "ok"
    orig = runner.run_turn

    def wrapped(text):
        on_text(text)
        return orig(text)

    runner.run_turn = wrapped
    VoiceLoop(intake=intake, turn_runner=runner, state=state).run()
    assert runner.seen == ["hi", "end conversation"]
    assert intake.follow_up_calls == 1

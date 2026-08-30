from __future__ import annotations

import pytest

from buddy.route.preparser import preparse
from buddy.route.state import VapState


class FakeMemory:
    def __init__(self, hits=None):
        self.facts = []
        self._hits = hits or []

    def append_fact(self, text):
        self.facts.append(text)

    def search(self, query):
        return list(self._hits)


@pytest.fixture
def state():
    return VapState()


def test_unmatched_returns_none(state):
    assert preparse("what is the capital of France", memory=FakeMemory(), state=state) is None


def test_remember_that_writes_to_memory_no_claude(state):
    mem = FakeMemory()
    out = preparse("remember that the wifi password is hunter2", memory=mem, state=state)
    assert mem.facts == ["the wifi password is hunter2"]
    assert out is not None and out != ""  # spoken confirmation


def test_note_that_and_make_a_note_variants(state):
    mem = FakeMemory()
    preparse("note that I use a standing desk", memory=mem, state=state)
    preparse("make a note that the demo is on Friday", memory=mem, state=state)
    assert mem.facts == ["I use a standing desk", "the demo is on Friday"]


def test_save_this_saves_last_reply(state):
    mem = FakeMemory()
    out = preparse("save this", memory=mem, state=state, last_reply="Tokyo has 14 million people")
    assert mem.facts == ["Tokyo has 14 million people"]
    assert out != ""


def test_switch_to_agent(state):
    out = preparse("switch to researcher", memory=FakeMemory(), state=state)
    assert state.active_agent == "researcher"
    assert "researcher" in out.lower()


def test_think_harder_sets_model_override(state):
    preparse("think harder", memory=FakeMemory(), state=state)
    assert state.model_override == "claude-sonnet-5"


def test_use_the_big_model_sets_override(state):
    preparse("use the big model", memory=FakeMemory(), state=state)
    assert state.model_override == "claude-sonnet-5"


def test_repeat_that_replays_last_reply(state):
    out = preparse("repeat that", memory=FakeMemory(), state=state, last_reply="I said hello")
    assert out == "I said hello"


def test_start_conversation_sets_mode(state):
    for phrase in ("start conversation", "let's have a conversation", "begin conversation"):
        state.conversation_mode = False
        out = preparse(phrase, memory=FakeMemory(), state=state)
        assert state.conversation_mode is True, phrase
        assert out and out != ""


def test_end_conversation_clears_mode(state):
    state.conversation_mode = True
    out = preparse("end conversation", memory=FakeMemory(), state=state)
    assert state.conversation_mode is False
    assert out and out != ""


def test_stop_conversation_ends_mode_not_bare_stop(state):
    state.conversation_mode = True
    out = preparse("stop conversation", memory=FakeMemory(), state=state)
    assert state.conversation_mode is False
    assert out != ""  # spoken, not the silent bare-"stop" no-op


def test_bare_stop_still_returns_empty(state):
    assert preparse("stop", memory=FakeMemory(), state=state) == ""


def test_stop_and_nevermind_are_silent_noops(state):
    for phrase in ("stop", "cancel", "never mind", "nevermind", "forget it"):
        assert preparse(phrase, memory=FakeMemory(), state=state) == ""


def test_what_do_you_know_about_x_hits_memory(state):
    mem = FakeMemory(hits=["- the user lives in Bangalore"])
    out = preparse("what do you know about where I live", memory=mem, state=state)
    assert "Bangalore" in out


def test_what_do_you_know_about_x_no_hits(state):
    out = preparse("what do you know about my car", memory=FakeMemory(hits=[]), state=state)
    assert out is not None and "car" in out.lower()


def test_case_and_filler_word_insensitive(state):
    mem = FakeMemory()
    preparse("Uh, remember that the cat's name is Mochi.", memory=mem, state=state)
    assert mem.facts == ["the cat's name is Mochi"]

    preparse("um, okay, switch to tutor", memory=FakeMemory(), state=state)
    assert state.active_agent == "tutor"

from __future__ import annotations

import pytest

from buddy.agents.rotation import SessionRotator


class FakeRegistry:
    def __init__(self):
        self.cleared = []

    def clear_session(self, name):
        self.cleared.append(name)


def test_does_not_rotate_before_n_turns():
    reg = FakeRegistry()
    calls = []
    rot = SessionRotator(reg, every_n=3, summarize=lambda a, s: calls.append((a, s)) or "card")
    for _ in range(2):
        rot.count_turn("companion", "sess-1")
    assert calls == []
    assert reg.cleared == []


def test_rotates_after_n_turns():
    reg = FakeRegistry()
    calls = []
    rot = SessionRotator(reg, every_n=3, summarize=lambda a, s: calls.append((a, s)) or "the card")
    for _ in range(3):
        rot.count_turn("companion", "sess-1")
    assert calls == [("companion", "sess-1")]
    assert reg.cleared == ["companion"]


def test_new_session_seeded_with_card_once():
    reg = FakeRegistry()
    rot = SessionRotator(reg, every_n=1, summarize=lambda a, s: "conversation so far: X")
    rot.count_turn("tutor", "sess-9")
    assert rot.take_card("tutor") == "conversation so far: X"
    assert rot.take_card("tutor") is None


def test_summary_card_bounded_to_max_chars():
    reg = FakeRegistry()
    rot = SessionRotator(
        reg, every_n=1, max_chars=20, summarize=lambda a, s: "x" * 500
    )
    rot.count_turn("companion", "s")
    assert len(rot.take_card("companion")) <= 20


def test_counts_are_per_agent():
    reg = FakeRegistry()
    calls = []
    rot = SessionRotator(reg, every_n=2, summarize=lambda a, s: calls.append(a) or "c")
    rot.count_turn("companion", "s")
    rot.count_turn("brainstorm", "s")
    rot.count_turn("companion", "s")
    assert calls == ["companion"]

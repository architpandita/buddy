from __future__ import annotations

from buddy.speech.segmenter import first_sentence


def _chunks(*items):
    yield from items


def test_emits_on_first_terminator():
    sentence, rest = first_sentence(_chunks("Hello there. ", "More text later."))
    assert sentence == "Hello there."
    assert "".join(rest) == "More text later."


def test_terminator_split_across_chunks():
    sentence, rest = first_sentence(_chunks("Hel", "lo wor", "ld! tail"))
    assert sentence == "Hello world!"
    assert "".join(rest).strip() == "tail"


def test_handles_common_abbreviations():
    sentence, rest = first_sentence(_chunks("See Dr. Smith e.g. today. Then go."))
    assert sentence == "See Dr. Smith e.g. today."


def test_no_terminator_returns_whole_buffer_on_close():
    sentence, rest = first_sentence(_chunks("no end here", " still none"))
    assert sentence == "no end here still none"
    assert "".join(rest) == ""

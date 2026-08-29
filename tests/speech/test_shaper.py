from __future__ import annotations

from buddy.speech.shaper import shape_for_speech


def test_strips_code_fences():
    txt = "Here is code:\n```python\nprint('hi')\n```\nDone."
    out = shape_for_speech(txt)
    assert "print" not in out and "```" not in out
    assert "Here is code:" in out and "Done." in out


def test_strips_headers_and_bullets():
    txt = "# Title\n\n- first point\n- second point\n* third"
    out = shape_for_speech(txt)
    assert "#" not in out and not out.lstrip().startswith("-")
    assert "first point" in out and "third" in out


def test_strips_inline_markdown():
    out = shape_for_speech("This is **bold** and `code` and a [link](http://x.com).")
    assert "**" not in out and "`" not in out
    assert "[" not in out and "](" not in out
    assert "bold" in out and "code" in out and "link" in out


def test_collapses_whitespace():
    out = shape_for_speech("one\n\n\n\ntwo    three")
    assert "\n\n" not in out
    assert "    " not in out


def test_truncates_to_sentence_limit():
    txt = "One. Two. Three. Four. Five. Six."
    out = shape_for_speech(txt, max_sentences=3)
    assert out.count(".") <= 4  # 3 sentences + optional ellipsis
    assert "One." in out and "Four" not in out


def test_plain_text_passthrough():
    assert shape_for_speech("Just a normal sentence.") == "Just a normal sentence."


def test_empty_stays_empty():
    assert shape_for_speech("") == ""

from __future__ import annotations

import datetime as dt

import pytest

from buddy.research.brief import BriefWriter


@pytest.fixture
def writer(tmp_path):
    return BriefWriter(base_dir=tmp_path)


def test_brief_saved_to_research_dir(writer, tmp_path):
    writer.write(
        topic="Quantum Error Correction!",
        query="research quantum error correction",
        body="Full findings live here.",
    )
    p = tmp_path / "research" / "quantum-error-correction.md"
    assert p.exists()
    assert "Full findings live here." in p.read_text()


def test_spoken_reply_is_summary_not_full_brief(writer, tmp_path):
    long_body = " ".join(f"Sentence number {i} of the brief." for i in range(20))
    spoken = writer.write_and_summarize(topic="topic", query="q", body=long_body)

    on_disk = (tmp_path / "research" / "topic.md").read_text()
    assert long_body in on_disk  # full text to file
    assert spoken != long_body  # shaper limit applied to speech
    assert len(spoken) < len(long_body)


def test_brief_has_frontmatter_with_date_and_query(writer, tmp_path):
    writer.write(
        topic="Coffee",
        query="research the history of coffee",
        body="Body text.",
        today=dt.date(2026, 8, 30),
    )
    text = (tmp_path / "research" / "coffee.md").read_text()
    assert text.startswith("---\n")
    assert "date: 2026-08-30" in text
    assert "query: research the history of coffee" in text


def test_existing_brief_on_same_topic_is_appended_not_overwritten(writer, tmp_path):
    writer.write(topic="Coffee", query="q1", body="First finding.")
    writer.write(topic="Coffee", query="q2", body="Second finding.")

    text = (tmp_path / "research" / "coffee.md").read_text()
    assert "First finding." in text and "Second finding." in text
    assert text.count("date:") == 2

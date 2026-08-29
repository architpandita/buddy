from __future__ import annotations

import pytest

from buddy.memory.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    return MemoryStore(base_dir=tmp_path)


def test_append_fact_writes_bullet(store, tmp_path):
    store.append_fact("the user prefers dark mode")
    assert (tmp_path / "facts.md").read_text() == "- the user prefers dark mode\n"


def test_append_preference_dedupes_exact_line(store, tmp_path):
    store.append_preference("call me Archit")
    store.append_preference("call me Archit")
    assert (tmp_path / "preferences.md").read_text().count("- call me Archit\n") == 1


def test_project_note_creates_file_on_first_write(store, tmp_path):
    store.append_project_note("Buddy Voice", "milestone 2 is the voice agent plane")
    p = tmp_path / "projects" / "buddy-voice.md"
    assert p.exists()
    assert "milestone 2 is the voice agent plane" in p.read_text()


def test_never_deletes_existing_lines(store, tmp_path):
    store.append_fact("first fact")
    store.append_fact("second fact")
    text = (tmp_path / "facts.md").read_text()
    assert "- first fact\n" in text and "- second fact\n" in text
    assert not hasattr(store, "delete") and not hasattr(store, "remove")


def test_write_is_atomic_no_tmp_left_behind(store, tmp_path):
    store.append_fact("a fact")
    leftovers = list(tmp_path.glob("**/*.tmp"))
    assert leftovers == []


def test_append_research_slugifies_topic(store, tmp_path):
    store.append_research("Rust vs. Go!", "both compile fast")
    assert (tmp_path / "research" / "rust-vs-go.md").exists()


def test_blank_text_is_ignored(store, tmp_path):
    store.append_fact("   ")
    assert not (tmp_path / "facts.md").exists()

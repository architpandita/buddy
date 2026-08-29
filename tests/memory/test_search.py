from __future__ import annotations

import pytest

from buddy.memory.search import MemorySearch
from buddy.memory.store import MemoryStore


@pytest.fixture
def populated(tmp_path):
    s = MemoryStore(base_dir=tmp_path)
    s.append_fact("the user lives in Bangalore")
    s.append_fact("the user works on a voice assistant called Buddy")
    s.append_preference("prefers short spoken answers")
    s.append_project_note("Buddy", "milestone 3 adds long term memory")
    return MemorySearch(base_dir=tmp_path), tmp_path


def test_keyword_match_returns_ranked_snippets(populated):
    search, _ = populated
    hits = search.search("user Buddy voice")
    assert any("voice assistant called Buddy" in h for h in hits)
    # the line matching the most query terms ranks first
    assert "voice assistant called Buddy" in hits[0]


def test_no_match_returns_empty(populated):
    search, _ = populated
    assert search.search("photosynthesis quantum") == []


def test_result_bounded_to_budget(populated):
    search, _ = populated
    hits = search.search("user", budget_chars=20)
    assert sum(len(h) for h in hits) <= 20


def test_load_named_file_returns_full_text(populated):
    search, _ = populated
    text = search.load("Buddy")
    assert "milestone 3 adds long term memory" in text


def test_load_unknown_name_returns_none(populated):
    search, _ = populated
    assert search.load("nonexistent") is None


def test_search_empty_query_returns_empty(populated):
    search, _ = populated
    assert search.search("   ") == []

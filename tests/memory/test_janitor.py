from __future__ import annotations

import os
import time

import pytest

from buddy.memory.janitor import Janitor


def _age(path, days):
    old = time.time() - days * 86400
    os.utime(path, (old, old))


@pytest.fixture
def janitor(tmp_path):
    state = tmp_path / "state"
    transcripts = tmp_path / "transcripts"
    claude_home = tmp_path / "dot-claude"
    for d in (state, transcripts, claude_home / "projects" / "x"):
        d.mkdir(parents=True)
    return Janitor(
        state_dir=state,
        transcript_dir=transcripts,
        claude_home=claude_home,
        ttl_days=7,
    ), tmp_path


def test_purges_session_state_on_conversation_end(janitor):
    j, tmp = janitor
    (tmp / "state" / "companion.session").write_text("abc")
    (tmp / "state" / "researcher.session").write_text("def")
    removed = j.purge_sessions()
    assert len(removed) == 2
    assert list((tmp / "state").iterdir()) == []


def test_transcripts_past_ttl_deleted(janitor):
    j, tmp = janitor
    old = tmp / "transcripts" / "old.md"
    fresh = tmp / "transcripts" / "fresh.md"
    old.write_text("x")
    fresh.write_text("y")
    _age(old, 10)
    removed = j.prune_transcripts()
    assert old not in [p for p in (tmp / "transcripts").iterdir()]
    assert fresh.exists()
    assert old in removed


def test_ttl_zero_keeps_nothing(janitor):
    j, tmp = janitor
    j._ttl_days = 0
    for name in ("a.md", "b.md"):
        (tmp / "transcripts" / name).write_text("x")
    j.prune_transcripts()
    assert list((tmp / "transcripts").iterdir()) == []


def test_prunes_stale_claude_home_sessions(janitor):
    j, tmp = janitor
    d = tmp / "dot-claude" / "projects" / "x"
    stale = d / "stale.jsonl"
    recent = d / "recent.jsonl"
    stale.write_text("{}")
    recent.write_text("{}")
    _age(stale, 30)
    j.prune_claude_home()
    assert not stale.exists()
    assert recent.exists()


def test_dry_run_lists_without_deleting(janitor):
    j, tmp = janitor
    (tmp / "state" / "companion.session").write_text("abc")
    would_remove = j.purge_sessions(dry_run=True)
    assert (tmp / "state" / "companion.session").exists()
    assert would_remove == [tmp / "state" / "companion.session"]


def test_run_does_all_three(janitor):
    j, tmp = janitor
    (tmp / "state" / "companion.session").write_text("a")
    t = tmp / "transcripts" / "old.md"
    t.write_text("x")
    _age(t, 30)
    s = tmp / "dot-claude" / "projects" / "x" / "s.jsonl"
    s.write_text("{}")
    _age(s, 30)
    removed = j.run()
    assert len(removed) == 3

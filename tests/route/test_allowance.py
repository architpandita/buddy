from __future__ import annotations

import datetime as dt

import pytest

from buddy.route.allowance import AllowanceGuard


@pytest.fixture
def guard(tmp_path):
    day = {"d": dt.date(2026, 8, 30)}
    g = AllowanceGuard(cap=3, path=tmp_path / "allowance.json", today=lambda: day["d"])
    return g, day


def test_allows_until_cap(guard):
    g, _ = guard
    assert g.allowed()
    g.record_turn()
    g.record_turn()
    assert g.allowed()  # 2 < 3


def test_blocks_at_daily_cap(guard):
    g, _ = guard
    for _ in range(3):
        g.record_turn()
    assert not g.allowed()


def test_counter_resets_at_local_midnight(guard):
    g, day = guard
    for _ in range(3):
        g.record_turn()
    assert not g.allowed()
    day["d"] = dt.date(2026, 8, 31)
    assert g.allowed()
    assert g.remaining() == 3


def test_count_persists_across_instances(tmp_path):
    path = tmp_path / "a.json"
    today = lambda: dt.date(2026, 8, 30)
    AllowanceGuard(cap=5, path=path, today=today).record_turn()
    g2 = AllowanceGuard(cap=5, path=path, today=today)
    assert g2.remaining() == 4


def test_identical_question_served_from_cache(guard):
    g, _ = guard
    assert g.cached("what time is it") is None
    g.cache("what time is it", "It's noon.")
    assert g.cached("  What time is it?  ") == "It's noon."

from __future__ import annotations

from pathlib import Path

import pytest

from buddy.agents.registry import AgentRegistry
from buddy.agents.rotation import SessionRotator
from buddy.agents.sessions import SessionStore
from buddy.engine.claude_cli import ClaudeCLIEngine
from buddy.loop.switchboard import Switchboard
from buddy.research.brief import BriefWriter
from buddy.route.allowance import AllowanceGuard
from tests.conftest import FakeRunner

STREAM = (
    Path(__file__).parent.parent / "fixtures" / "streams" / "research.jsonl"
).read_text()


def _build(tmp_path, runner):
    registry = AgentRegistry(sessions=SessionStore(state_dir=tmp_path))
    engine = ClaudeCLIEngine(runner=runner, sandbox_dir=tmp_path)
    spoken: list[str] = []
    sb = Switchboard(
        engine=engine,
        registry=registry,
        allowance=AllowanceGuard(cap=100, path=tmp_path / "a.json"),
        rotator=SessionRotator(registry, every_n=1000, summarize=lambda a, s: "card"),
        memory=None,
        speak=spoken.append,
        brief_writer=BriefWriter(base_dir=tmp_path / "memory"),
    )
    return sb, spoken


def _tool_arg(argv):
    return argv[argv.index("--allowedTools") + 1]


def test_recorded_research_stream_produces_summary_and_brief(tmp_path):
    sb, spoken = _build(tmp_path, FakeRunner(stdout=STREAM))

    out = sb.run_turn("research quantum error correction")

    briefs = list((tmp_path / "memory" / "research").glob("*.md"))
    assert len(briefs) == 1
    brief_text = briefs[0].read_text()
    assert "surface code" in brief_text.lower()  # full detail persisted
    assert out in spoken
    assert len(out) < len(brief_text)  # spoken part is the short summary


def test_max_turns_bounds_tool_loop(tmp_path):
    runner = FakeRunner(stdout=STREAM)
    sb, _ = _build(tmp_path, runner)

    sb.run_turn("research quantum error correction")

    argv = runner.last.argv
    assert "--max-turns" in argv
    assert int(argv[argv.index("--max-turns") + 1]) == 8  # agents/researcher.md


def test_websearch_only_when_router_picked_researcher(tmp_path):
    runner = FakeRunner(stdout=STREAM)
    sb, _ = _build(tmp_path, runner)

    sb.run_turn("research quantum error correction")
    assert "WebSearch" in _tool_arg(runner.last.argv)

    sb.run_turn("how are you feeling today")
    assert "WebSearch" not in _tool_arg(runner.last.argv)

    # companion turn leaves no brief behind
    briefs = list((tmp_path / "memory" / "research").glob("*.md"))
    assert len(briefs) == 1


@pytest.mark.live
def test_live_research_roundtrip(tmp_path):
    """Real `claude` + web search. Deselected by default (see pytest.ini)."""
    registry = AgentRegistry(sessions=SessionStore(state_dir=tmp_path))
    engine = ClaudeCLIEngine(sandbox_dir=tmp_path)
    spoken: list[str] = []
    sb = Switchboard(
        engine=engine,
        registry=registry,
        allowance=AllowanceGuard(cap=100, path=tmp_path / "a.json"),
        rotator=SessionRotator(registry, every_n=1000, summarize=lambda a, s: ""),
        memory=None,
        speak=spoken.append,
        brief_writer=BriefWriter(base_dir=tmp_path / "memory"),
    )

    out = sb.run_turn("research who won the most recent Nobel Prize in Physics")

    briefs = list((tmp_path / "memory" / "research").glob("*.md"))
    assert len(briefs) == 1 and briefs[0].read_text().strip()
    assert out and len(out) < len(briefs[0].read_text())

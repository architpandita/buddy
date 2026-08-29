from __future__ import annotations

import pytest

from buddy.engine.claude_cli import ClaudeCLIEngine, EngineError
from tests.conftest import FakeRunner, stream_json


def make_engine(runner, **kw):
    return ClaudeCLIEngine(runner=runner, sandbox_dir="/tmp/buddy-sandbox", **kw)


def test_parses_stream_json_result(agent):
    runner = FakeRunner(stdout=stream_json(result="hello there", session_id="s1"))
    out = make_engine(runner).send("hi", agent=agent, model=agent.model, session_id=None)
    assert out.reply == "hello there"
    assert out.session_id == "s1"


def test_builds_command_flags(agent):
    runner = FakeRunner(stdout=stream_json())
    make_engine(runner).send("do a thing", agent=agent, model="claude-sonnet-5", session_id=None)
    argv = runner.last.argv
    assert argv[:3] == ["claude", "-p", "do a thing"]
    assert "--output-format" in argv and argv[argv.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in argv
    assert argv[argv.index("--model") + 1] == "claude-sonnet-5"
    assert argv[argv.index("--append-system-prompt") + 1] == agent.system_prompt
    assert argv[argv.index("--max-turns") + 1] == str(agent.max_turns)
    assert "--allowedTools" in argv


def test_allowed_tools_joined_comma(agent):
    agent.allowed_tools = ["WebSearch", "WebFetch", "Write"]
    runner = FakeRunner(stdout=stream_json())
    make_engine(runner).send("x", agent=agent, model=agent.model, session_id=None)
    argv = runner.last.argv
    assert argv[argv.index("--allowedTools") + 1] == "WebSearch,WebFetch,Write"


def test_resume_flag_present_when_session_id_given(agent):
    runner = FakeRunner(stdout=stream_json(session_id="s9"))
    make_engine(runner).send("x", agent=agent, model=agent.model, session_id="s9")
    argv = runner.last.argv
    assert argv[argv.index("--resume") + 1] == "s9"


def test_no_resume_flag_on_first_turn(agent):
    runner = FakeRunner(stdout=stream_json())
    make_engine(runner).send("x", agent=agent, model=agent.model, session_id=None)
    assert "--resume" not in runner.last.argv


def test_extracts_session_id_from_stream_not_input(agent):
    runner = FakeRunner(stdout=stream_json(session_id="new-sess"))
    out = make_engine(runner).send("x", agent=agent, model=agent.model, session_id="old-sess")
    assert out.session_id == "new-sess"


def test_meta_carries_cost_turns_duration(agent):
    runner = FakeRunner(
        stdout=stream_json(num_turns=3, total_cost_usd=0.042, duration_ms=5555)
    )
    out = make_engine(runner).send("x", agent=agent, model=agent.model, session_id=None)
    assert out.meta["num_turns"] == 3
    assert out.meta["total_cost_usd"] == 0.042
    assert out.meta["duration_ms"] == 5555


def test_strips_anthropic_api_key_from_env(agent, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    runner = FakeRunner(stdout=stream_json())
    make_engine(runner).send("x", agent=agent, model=agent.model, session_id=None)
    assert "ANTHROPIC_API_KEY" not in runner.last.env


def test_runs_in_sandbox_dir(agent):
    runner = FakeRunner(stdout=stream_json())
    make_engine(runner).send("x", agent=agent, model=agent.model, session_id=None)
    assert runner.last.cwd == "/tmp/buddy-sandbox"


def test_nonzero_exit_raises_engine_error(agent):
    runner = FakeRunner(stdout="", stderr="boom happened", returncode=1)
    with pytest.raises(EngineError, match="boom happened"):
        make_engine(runner).send("x", agent=agent, model=agent.model, session_id=None)


def test_error_result_raises_engine_error(agent):
    import json

    bad = json.dumps(
        {"type": "result", "is_error": True, "result": "rate limited", "session_id": "s"}
    )
    runner = FakeRunner(stdout=bad + "\n")
    with pytest.raises(EngineError):
        make_engine(runner).send("x", agent=agent, model=agent.model, session_id=None)


def test_malformed_json_line_is_skipped(agent):
    stdout = "not json at all\n" + stream_json(result="survived", session_id="s2")
    runner = FakeRunner(stdout="{ broken\n" + stdout)
    out = make_engine(runner).send("x", agent=agent, model=agent.model, session_id=None)
    assert out.reply == "survived"


def test_no_result_object_raises(agent):
    runner = FakeRunner(stdout='{"type": "assistant", "message": {}}\n')
    with pytest.raises(EngineError):
        make_engine(runner).send("x", agent=agent, model=agent.model, session_id=None)


@pytest.mark.live
def test_live_roundtrip_haiku(agent, tmp_path):
    """Real `claude -p`. Run with: pytest -m live"""
    engine = ClaudeCLIEngine(sandbox_dir=tmp_path)
    agent.system_prompt = "Answer in one word."
    out = engine.send(
        "Reply with the single word PONG.",
        agent=agent,
        model="claude-haiku-4-5-20251001",
        session_id=None,
    )
    assert out.reply
    assert out.session_id

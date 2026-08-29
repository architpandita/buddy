from __future__ import annotations

import pytest

from buddy.agents.sessions import SessionStore
from buddy.engine.claude_cli import EngineError, EngineResult
from buddy.loop.turn import TurnRunner
from tests.conftest import StubAgent


class FakeEngine:
    def __init__(self, reply="a reply", session_id="sess-1", error=None):
        self.reply, self.session_id, self.error = reply, session_id, error
        self.calls = []

    def send(self, text, agent, model, session_id):
        self.calls.append(dict(text=text, model=model, session_id=session_id))
        if self.error:
            raise self.error
        return EngineResult(reply=self.reply, session_id=self.session_id, meta={})


@pytest.fixture
def spoken():
    out = []
    return out, (lambda text: out.append(text))


def make_runner(engine, speak, tmp_path, agent=None):
    return TurnRunner(
        engine=engine,
        speak=speak,
        agent=agent or StubAgent(),
        sessions=SessionStore(state_dir=tmp_path),
    )


def test_happy_path_typed_to_spoken(tmp_path, spoken):
    out, speak = spoken
    engine = FakeEngine(reply="# Heading\n\nHello **world**.")
    reply = make_runner(engine, speak, tmp_path).run_turn("hi buddy")
    assert "Hello world." in reply
    assert "#" not in reply and "**" not in reply
    assert out == [reply]


def test_persists_returned_session_id(tmp_path, spoken):
    out, speak = spoken
    engine = FakeEngine(session_id="brand-new")
    make_runner(engine, speak, tmp_path).run_turn("x")
    assert SessionStore(state_dir=tmp_path).get("companion") == "brand-new"


def test_reuses_persisted_session_id_next_turn(tmp_path, spoken):
    out, speak = spoken
    engine = FakeEngine(session_id="s-return")
    runner = make_runner(engine, speak, tmp_path)
    runner.run_turn("first")
    runner.run_turn("second")
    assert engine.calls[0]["session_id"] is None
    assert engine.calls[1]["session_id"] == "s-return"


def test_engine_error_speaks_graceful_message(tmp_path, spoken):
    out, speak = spoken
    engine = FakeEngine(error=EngineError("cli blew up"))
    reply = make_runner(engine, speak, tmp_path).run_turn("x")
    assert "cli blew up" not in reply
    assert reply and out == [reply]


class FakeMemory:
    def __init__(self, *snippets):
        self._snippets = list(snippets)

    def search(self, query):
        return self._snippets


def test_only_retrieved_snippets_injected(tmp_path, spoken):
    out, speak = spoken
    engine = FakeEngine()
    runner = TurnRunner(
        engine=engine,
        speak=speak,
        agent=StubAgent(),
        sessions=SessionStore(state_dir=tmp_path),
        memory=FakeMemory("- the user lives in Bangalore"),
    )
    runner.run_turn("where do I live")
    sent = engine.calls[0]["text"]
    assert "the user lives in Bangalore" in sent
    assert "where do I live" in sent


def test_no_retrieval_no_injection(tmp_path, spoken):
    out, speak = spoken
    engine = FakeEngine()
    runner = TurnRunner(
        engine=engine,
        speak=speak,
        agent=StubAgent(),
        sessions=SessionStore(state_dir=tmp_path),
        memory=FakeMemory(),  # nothing retrieved
    )
    runner.run_turn("just a normal question")
    assert engine.calls[0]["text"] == "just a normal question"


def test_no_memory_configured_passes_text_verbatim(tmp_path, spoken):
    out, speak = spoken
    engine = FakeEngine()
    make_runner(engine, speak, tmp_path).run_turn("hello")
    assert engine.calls[0]["text"] == "hello"


def test_uses_agent_model(tmp_path, spoken):
    out, speak = spoken
    engine = FakeEngine()
    agent = StubAgent(name="companion", model="claude-sonnet-5")
    make_runner(engine, speak, tmp_path, agent=agent).run_turn("x")
    assert engine.calls[0]["model"] == "claude-sonnet-5"

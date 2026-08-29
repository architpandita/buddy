from __future__ import annotations

import pytest

from buddy.agents.registry import AgentRegistry
from buddy.agents.rotation import SessionRotator
from buddy.agents.sessions import SessionStore
from buddy.engine.claude_cli import EngineError, EngineResult
from buddy.loop.switchboard import Switchboard
from buddy.route.allowance import AllowanceGuard
from buddy.route.state import VapState


class FakeEngine:
    def __init__(self, reply="a reply", session_id="sess-x", error=None):
        self.reply, self.session_id, self.error = reply, session_id, error
        self.calls = []

    def send(self, text, agent, model, session_id):
        self.calls.append(dict(text=text, agent=agent.name, model=model, session_id=session_id))
        if self.error:
            raise self.error
        return EngineResult(reply=self.reply, session_id=self.session_id, meta={})


class FakeMemory:
    def __init__(self, hits=None):
        self.facts = []
        self._hits = hits or []

    def append_fact(self, t):
        self.facts.append(t)

    def search(self, q):
        return list(self._hits)


@pytest.fixture
def parts(tmp_path):
    registry = AgentRegistry(sessions=SessionStore(state_dir=tmp_path))
    allowance = AllowanceGuard(cap=100, path=tmp_path / "a.json")
    rotator = SessionRotator(registry, every_n=1000, summarize=lambda a, s: "card")
    engine = FakeEngine()
    spoken = []
    state = VapState()
    sb = Switchboard(
        engine=engine,
        registry=registry,
        allowance=allowance,
        rotator=rotator,
        memory=FakeMemory(),
        state=state,
        speak=spoken.append,
    )
    return sb, engine, spoken, state, allowance, registry


def test_ordinary_turn_routes_to_companion_and_speaks(parts):
    sb, engine, spoken, *_ = parts
    reply = sb.run_turn("how are you today")
    assert engine.calls[0]["agent"] == "companion"
    assert engine.calls[0]["model"] == "claude-haiku-4-5-20251001"
    assert spoken == [reply]


def test_preparsed_turn_never_reaches_engine(parts):
    sb, engine, spoken, *_ = parts
    out = sb.run_turn("stop")
    assert out == ""
    assert engine.calls == []


def test_remember_that_writes_memory_no_engine(parts, tmp_path):
    sb, engine, spoken, state, allowance, registry = parts
    sb._memory = FakeMemory()
    sb.run_turn("remember that my flight is at 6pm")
    assert sb._memory.facts == ["my flight is at 6pm"]
    assert engine.calls == []


def test_switch_to_agent_then_next_turn_uses_it(parts):
    sb, engine, spoken, state, *_ = parts
    sb.run_turn("switch to brainstorm")
    assert engine.calls == []
    sb.run_turn("what should I name the cat")
    assert engine.calls[0]["agent"] == "brainstorm"


def test_daily_cap_blocks_engine(parts, tmp_path):
    sb, engine, spoken, state, allowance, registry = parts
    for _ in range(100):
        allowance.record_turn()
    out = sb.run_turn("tell me a joke")
    assert engine.calls == []
    assert "limit" in out.lower()


def test_identical_question_served_from_cache(parts):
    sb, engine, spoken, *_ = parts
    sb.run_turn("what is the tallest mountain")
    assert len(engine.calls) == 1
    sb.run_turn("What is the tallest mountain?")
    assert len(engine.calls) == 1  # no second engine call


def test_records_one_allowance_turn_per_claude_call(parts):
    sb, engine, spoken, state, allowance, registry = parts
    assert allowance.remaining() == 100
    sb.run_turn("hello there")
    assert allowance.remaining() == 99


def test_session_id_persisted_per_agent(parts):
    sb, engine, spoken, state, allowance, registry = parts
    sb.run_turn("hi")
    assert registry.session_id("companion") == "sess-x"


def test_engine_error_speaks_graceful_message(parts):
    sb, engine, spoken, *_ = parts
    engine.error = EngineError("boom")
    out = sb.run_turn("hello")
    assert "boom" not in out and out in spoken


def test_full_route_chain_calls_each_stage_in_order(parts):
    sb, engine, spoken, state, allowance, registry = parts
    order = []
    sb._preparse = lambda text, **kw: order.append("preparse") or None
    orig_allowed = allowance.allowed
    allowance.allowed = lambda: order.append("allowance") or orig_allowed()
    orig_route = sb._route
    sb._route = lambda *a, **k: order.append("router") or orig_route(*a, **k)
    orig_get = registry.get
    registry.get = lambda n: order.append("registry") or orig_get(n)
    orig_take = sb._rotator.take_card
    sb._rotator.take_card = lambda a: order.append("rotation") or orig_take(a)
    real_send = engine.send
    engine.send = lambda *a, **k: order.append("engine") or real_send(*a, **k)

    sb.run_turn("just a normal question")
    # collapse the router's own internal registry.get lookup
    deduped = [s for i, s in enumerate(order) if i == 0 or s != order[i - 1]]
    assert deduped == ["preparse", "allowance", "router", "registry", "rotation", "engine"]

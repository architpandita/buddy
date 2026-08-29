from __future__ import annotations

import pytest

from buddy.agents.registry import AgentRegistry
from buddy.agents.sessions import SessionStore
from buddy.route.router import route

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-5"


@pytest.fixture
def registry(tmp_path):
    return AgentRegistry(sessions=SessionStore(state_dir=tmp_path))


def test_default_is_companion(registry):
    d = route("how's your day going", registry)
    assert d.agent == "companion" and d.model == HAIKU


def test_short_chatty_turn_to_companion_haiku(registry):
    d = route("what time is it", registry)
    assert d.agent == "companion" and d.model == HAIKU


def test_research_keywords_to_researcher_sonnet(registry):
    for phrase in ("look up the population of Chile", "research quantum error correction",
                   "find out when the next eclipse is"):
        d = route(phrase, registry)
        assert d.agent == "researcher", phrase
        assert d.model == SONNET


def test_brainstorm_keywords_to_brainstorm_sonnet(registry):
    d = route("brainstorm names for my podcast", registry)
    assert d.agent == "brainstorm" and d.model == SONNET


def test_tutor_keywords_to_tutor(registry):
    d = route("teach me how bubble sort works", registry)
    assert d.agent == "tutor"


def test_long_complex_turn_escalates_model(registry):
    long_turn = "so here is the situation " + "and then " * 50 + "what do you think"
    d = route(long_turn, registry)
    assert d.agent == "companion"
    assert d.model == SONNET  # escalated from haiku


def test_tool_need_forces_capable_agent(registry):
    d = route("search the web for today's weather", registry)
    assert d.agent == "researcher"
    assert "WebSearch" in registry.get(d.agent).allowed_tools


def test_voice_override_beats_rules(registry):
    d = route("brainstorm some ideas", registry, override_agent="tutor")
    assert d.agent == "tutor"


def test_model_override_respected(registry):
    d = route("hi", registry, override_model="claude-opus-4-8")
    assert d.model == "claude-opus-4-8"


def test_opus_never_auto_selected(registry):
    for phrase in ("hello", "research everything about opus the model",
                   "brainstorm " + "x " * 80):
        d = route(phrase, registry)
        assert "opus" not in d.model

from __future__ import annotations

import pytest

from buddy.agents.registry import AgentRegistry, UnknownAgent
from buddy.agents.sessions import SessionStore


@pytest.fixture
def registry(tmp_path):
    return AgentRegistry(sessions=SessionStore(state_dir=tmp_path))


def test_loads_all_five_agents(registry):
    assert set(registry.names()) == {
        "companion",
        "researcher",
        "tutor",
        "brainstorm",
        "scribe",
    }


def test_get_returns_agent_spec(registry):
    spec = registry.get("researcher")
    assert spec.model == "claude-sonnet-5"
    assert "WebSearch" in spec.allowed_tools


def test_unknown_agent_raises(registry):
    with pytest.raises(UnknownAgent):
        registry.get("butler")


def test_each_agent_has_independent_session_id(registry):
    registry.set_session_id("companion", "sess-companion")
    registry.set_session_id("brainstorm", "sess-brainstorm")
    assert registry.session_id("companion") == "sess-companion"
    assert registry.session_id("brainstorm") == "sess-brainstorm"
    assert registry.session_id("tutor") is None

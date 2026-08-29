from __future__ import annotations

import pytest

from buddy.agents.loader import AgentSpecError, load_agent

COMPANION = """\
---
model: claude-haiku-4-5-20251001
tools: []
max_turns: 2
style: short, conversational
---
You are Buddy's Companion. Keep replies to a sentence or two.
"""

RESEARCHER = """\
---
model: claude-sonnet-5
tools: [WebSearch, WebFetch, Write]
max_turns: 6
---
You research topics and write a brief.
"""


def _write(tmp_path, name, content):
    p = tmp_path / f"{name}.md"
    p.write_text(content)
    return p


def test_loads_frontmatter_fields(tmp_path):
    spec = load_agent(_write(tmp_path, "researcher", RESEARCHER))
    assert spec.model == "claude-sonnet-5"
    assert spec.allowed_tools == ["WebSearch", "WebFetch", "Write"]
    assert spec.max_turns == 6


def test_body_is_system_prompt(tmp_path):
    spec = load_agent(_write(tmp_path, "companion", COMPANION))
    assert spec.system_prompt == "You are Buddy's Companion. Keep replies to a sentence or two."


def test_name_comes_from_filename(tmp_path):
    spec = load_agent(_write(tmp_path, "companion", COMPANION))
    assert spec.name == "companion"


def test_empty_tools_list(tmp_path):
    spec = load_agent(_write(tmp_path, "companion", COMPANION))
    assert spec.allowed_tools == []


def test_missing_model_raises(tmp_path):
    bad = "---\ntools: []\n---\nno model here"
    with pytest.raises(AgentSpecError, match="model"):
        load_agent(_write(tmp_path, "broken", bad))


def test_missing_frontmatter_raises(tmp_path):
    with pytest.raises(AgentSpecError):
        load_agent(_write(tmp_path, "nofm", "just a body, no fence"))


def test_researcher_allowedtools_include_websearch():
    from buddy import config

    spec = load_agent(config.VAP_AGENTS_DIR / "researcher.md")
    assert "WebSearch" in spec.allowed_tools
    assert "WebFetch" in spec.allowed_tools


def test_optional_fields_default(tmp_path):
    minimal = "---\nmodel: claude-haiku-4-5-20251001\n---\nbody"
    spec = load_agent(_write(tmp_path, "min", minimal))
    assert spec.allowed_tools == []
    assert spec.max_turns == 1
    assert spec.style == ""

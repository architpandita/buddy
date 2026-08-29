"""Rules-only router (plan §4.3): length, keywords, tool-need. Free and instant.

Picks the agent and the model for a turn. A manual voice override (from the
pre-parser) always wins. Opus is never auto-selected — it's allowance-limited on
Pro, so it only appears when the caller passes it as an explicit override.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from buddy import config

# Phrases that need web tools -> only the Researcher has them.
_TOOL_NEED = re.compile(
    r"\b(search the web|look (this |it )?up|look up|google|find out|"
    r"what'?s the latest|current price of)\b"
)
_RESEARCH = re.compile(r"\b(research|dig into|fact.?check)\b")
_BRAINSTORM = re.compile(
    r"\b(brainstorm|ideas for|give me ideas|help me think|come up with)\b"
)
_TUTOR = re.compile(
    r"\b(teach me|help me understand|quiz me|walk me through|explain how|"
    r"why does .* work)\b"
)


@dataclass
class RouteDecision:
    agent: str
    model: str


def _pick_agent(text: str) -> str:
    if _TOOL_NEED.search(text) or _RESEARCH.search(text):
        return "researcher"
    if _BRAINSTORM.search(text):
        return "brainstorm"
    if _TUTOR.search(text):
        return "tutor"
    return "companion"


def route(
    text: str,
    registry,
    *,
    override_agent: str | None = None,
    override_model: str | None = None,
) -> RouteDecision:
    lowered = text.lower()
    agent = override_agent or _pick_agent(lowered)
    spec = registry.get(agent)

    model = spec.model
    if len(lowered.split()) > config.VAP_LONG_TURN_WORDS and model == config.VAP_FAST_MODEL:
        model = config.VAP_SMART_MODEL
    if override_model:
        model = override_model

    return RouteDecision(agent=agent, model=model)

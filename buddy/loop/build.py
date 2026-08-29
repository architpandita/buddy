"""Composition root for the voice-agent-plane. Tests never call this; they inject
fakes directly.
"""

from __future__ import annotations

from buddy import config
from buddy.agents.loader import load_agent
from buddy.agents.registry import AgentRegistry
from buddy.agents.rotation import SessionRotator
from buddy.agents.sessions import SessionStore
from buddy.engine.claude_cli import ClaudeCLIEngine
from buddy.loop.switchboard import Switchboard
from buddy.loop.turn import TurnRunner
from buddy.memory.facade import Memory
from buddy.research.brief import BriefWriter
from buddy.route.allowance import AllowanceGuard
from buddy.route.state import VapState

_SUMMARY_PROMPT = (
    "Summarise our conversation so far in under 120 words as plain notes I can "
    "use to resume it later. No preamble."
)


def ensure_dirs() -> None:
    config.VAP_SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    config.VAP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    config.VAP_MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def build_turn_runner(agent_name: str = "companion", speak=None) -> TurnRunner:
    """Single-agent runner (Phase 1–3) — still used by the plain text loop."""
    ensure_dirs()
    agent = load_agent(config.VAP_AGENTS_DIR / f"{agent_name}.md")
    engine = ClaudeCLIEngine(sandbox_dir=config.VAP_SANDBOX_DIR)
    return TurnRunner(
        engine=engine,
        agent=agent,
        speak=speak,
        sessions=SessionStore(),
        memory=Memory(),
    )


def build_switchboard(speak=None) -> Switchboard:
    """Full router + multi-agent switchboard (Phase 4)."""
    ensure_dirs()
    engine = ClaudeCLIEngine(sandbox_dir=config.VAP_SANDBOX_DIR)
    registry = AgentRegistry(sessions=SessionStore())

    def summarize(agent_name: str, session_id: str | None) -> str:
        if session_id is None:
            return ""
        spec = registry.get(agent_name)
        try:
            return engine.send(
                _SUMMARY_PROMPT, agent=spec, model=config.VAP_FAST_MODEL,
                session_id=session_id,
            ).reply
        except Exception:
            return ""

    return Switchboard(
        engine=engine,
        registry=registry,
        allowance=AllowanceGuard(),
        rotator=SessionRotator(registry, summarize=summarize),
        memory=Memory(),
        state=VapState(),
        speak=speak,
        brief_writer=BriefWriter(),
    )

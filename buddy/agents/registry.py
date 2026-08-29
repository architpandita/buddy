"""The session-per-agent switchboard (plan §4.4).

Loads every `agents/*.md` spec once and tracks each agent's own persistent Claude
session id via `SessionStore` — separate sessions keep contexts clean and small
(the research thread never pollutes the brainstorm thread).
"""

from __future__ import annotations

from pathlib import Path

from buddy import config
from buddy.agents.loader import AgentSpec, load_agent
from buddy.agents.sessions import SessionStore


class UnknownAgent(KeyError):
    pass


class AgentRegistry:
    def __init__(
        self,
        agents_dir: str | Path | None = None,
        sessions: SessionStore | None = None,
    ):
        self._dir = Path(agents_dir) if agents_dir is not None else config.VAP_AGENTS_DIR
        self._sessions = sessions or SessionStore()
        self._specs: dict[str, AgentSpec] = {
            p.stem: load_agent(p) for p in sorted(self._dir.glob("*.md"))
        }

    def names(self) -> list[str]:
        return sorted(self._specs)

    def get(self, name: str) -> AgentSpec:
        try:
            return self._specs[name]
        except KeyError:
            raise UnknownAgent(name) from None

    def session_id(self, name: str) -> str | None:
        return self._sessions.get(name)

    def set_session_id(self, name: str, session_id: str) -> None:
        self._sessions.set(name, session_id)

    def clear_session(self, name: str) -> None:
        self._sessions.clear(name)

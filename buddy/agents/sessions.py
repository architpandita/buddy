"""Per-agent persisted Claude session ids (short-term memory, plan §4.6).

One file per agent: `<state_dir>/<agent>.session` holding just the id. Deleted
by the janitor on conversation end (Phase 3).
"""

from __future__ import annotations

from pathlib import Path

from buddy import config


class SessionStore:
    def __init__(self, state_dir: str | Path | None = None):
        self._dir = Path(state_dir) if state_dir is not None else config.VAP_STATE_DIR

    def _path(self, agent: str) -> Path:
        return self._dir / f"{agent}.session"

    def get(self, agent: str) -> str | None:
        p = self._path(agent)
        if not p.exists():
            return None
        sid = p.read_text().strip()
        return sid or None

    def set(self, agent: str, session_id: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = self._path(agent).with_suffix(".session.tmp")
        tmp.write_text(session_id)
        tmp.replace(self._path(agent))

    def clear(self, agent: str) -> None:
        self._path(agent).unlink(missing_ok=True)

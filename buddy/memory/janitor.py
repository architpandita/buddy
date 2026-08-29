"""Housekeeping (plan §4.6 "Janitor").

- Session state (`~/.buddy/state/*.session`): purged on conversation end.
- Spoken-turn transcripts (`~/.buddy/transcripts/`): TTL in days, 0 = keep none.
- `~/.claude` accumulates its own session transcripts (`*.jsonl`) independently
  of Buddy — prune the stale ones on the same TTL.

Long-term memory under `~/.buddy/memory/` is never touched here.
"""

from __future__ import annotations

import time
from pathlib import Path

from buddy import config


class Janitor:
    def __init__(
        self,
        state_dir: str | Path | None = None,
        transcript_dir: str | Path | None = None,
        claude_home: str | Path | None = None,
        ttl_days: int | None = None,
    ):
        self._state_dir = Path(state_dir) if state_dir is not None else config.VAP_STATE_DIR
        self._transcript_dir = (
            Path(transcript_dir)
            if transcript_dir is not None
            else config.VAP_TRANSCRIPT_DIR
        )
        self._claude_home = (
            Path(claude_home) if claude_home is not None else Path.home() / ".claude"
        )
        self._ttl_days = (
            ttl_days if ttl_days is not None else config.VAP_TRANSCRIPT_TTL_DAYS
        )

    def purge_sessions(self, dry_run: bool = False) -> list[Path]:
        return self._remove(sorted(self._state_dir.glob("*.session")), dry_run)

    def prune_transcripts(self, dry_run: bool = False) -> list[Path]:
        return self._remove(self._expired(self._transcript_dir, "*"), dry_run)

    def prune_claude_home(self, dry_run: bool = False) -> list[Path]:
        return self._remove(self._expired(self._claude_home, "*.jsonl"), dry_run)

    def run(self, dry_run: bool = False) -> list[Path]:
        return (
            self.purge_sessions(dry_run)
            + self.prune_transcripts(dry_run)
            + self.prune_claude_home(dry_run)
        )

    # -- internals --------------------------------------------------------

    def _expired(self, root: Path, pattern: str) -> list[Path]:
        if not root.exists():
            return []
        files = [p for p in sorted(root.rglob(pattern)) if p.is_file()]
        if self._ttl_days <= 0:
            return files
        cutoff = time.time() - self._ttl_days * 86400
        return [p for p in files if p.stat().st_mtime < cutoff]

    @staticmethod
    def _remove(paths: list[Path], dry_run: bool) -> list[Path]:
        if not dry_run:
            for p in paths:
                p.unlink(missing_ok=True)
        return paths

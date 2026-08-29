"""Durable research briefs (plan §5.2).

After a research turn the full answer is persisted to
`<memory>/research/<topic-slug>.md` as a dated, query-stamped section; only a
short shaped summary is ever spoken. Briefs are append-only — a second question
on the same topic adds a section, it never rewrites the file (§4.6).
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

from buddy import config
from buddy.memory.store import _slug
from buddy.speech.shaper import shape_for_speech


class BriefWriter:
    def __init__(self, base_dir: str | Path | None = None):
        self._base = Path(base_dir) if base_dir is not None else config.VAP_MEMORY_DIR

    def write(
        self,
        topic: str,
        query: str,
        body: str,
        *,
        today: dt.date | None = None,
    ) -> Path:
        body = (body or "").strip()
        path = self._base / "research" / f"{_slug(topic)}.md"
        path.parent.mkdir(parents=True, exist_ok=True)

        date = (today or dt.date.today()).isoformat()
        section = f"---\ndate: {date}\nquery: {query}\n---\n\n{body}\n"

        existing = path.read_text() if path.exists() else ""
        blob = f"{existing}\n{section}" if existing else section

        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(blob)
        os.replace(tmp, path)
        return path

    def write_and_summarize(
        self,
        topic: str,
        query: str,
        body: str,
        *,
        today: dt.date | None = None,
    ) -> str:
        """Persist the full brief, return the short spoken summary."""
        self.write(topic, query, body, today=today)
        return shape_for_speech(body)

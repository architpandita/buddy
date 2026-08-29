"""Long-term memory: flat markdown, explicit writes only (plan §4.6).

    <base>/facts.md
    <base>/preferences.md
    <base>/projects/<slug>.md
    <base>/research/<slug>.md

Every write is an append of one `- ` bullet. Exact-duplicate lines are skipped.
Nothing here ever deletes or rewrites an existing line, and no write needs a
model call. Writes are atomic (temp file + `os.replace`).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from buddy import config


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "untitled"


class MemoryStore:
    def __init__(self, base_dir: str | Path | None = None):
        self._base = Path(base_dir) if base_dir is not None else config.VAP_MEMORY_DIR

    # -- public writes -------------------------------------------------------

    def append_fact(self, text: str) -> None:
        self._append(self._base / "facts.md", text)

    def append_preference(self, text: str) -> None:
        self._append(self._base / "preferences.md", text)

    def append_project_note(self, name: str, text: str) -> None:
        self._append(self._base / "projects" / f"{_slug(name)}.md", text)

    def append_research(self, topic: str, text: str) -> None:
        self._append(self._base / "research" / f"{_slug(topic)}.md", text)

    # -- internals --------------------------------------------------------

    def _append(self, path: Path, text: str) -> None:
        text = text.strip()
        if not text:
            return
        line = f"- {text}\n"

        existing = path.read_text() if path.exists() else ""
        if line in existing:
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(existing + line)
        os.replace(tmp, path)

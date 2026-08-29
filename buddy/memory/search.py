"""Keyword retrieval over the markdown memory store (plan §4.6).

No vectors. `search()` ranks bullet lines by how many query terms they contain
and returns the top ones, capped at a character budget so a turn never gets the
whole store injected. `load()` is explicit whole-file retrieval by name.
"""

from __future__ import annotations

import re
from pathlib import Path

from buddy import config

_WORD_RE = re.compile(r"[a-z0-9]+")


def _terms(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


class MemorySearch:
    def __init__(self, base_dir: str | Path | None = None):
        self._base = Path(base_dir) if base_dir is not None else config.VAP_MEMORY_DIR

    def _md_files(self) -> list[Path]:
        if not self._base.exists():
            return []
        return sorted(self._base.rglob("*.md"))

    def search(self, query: str, budget_chars: int | None = None) -> list[str]:
        wanted = set(_terms(query))
        if not wanted:
            return []
        if budget_chars is None:
            budget_chars = config.VAP_MEMORY_RETRIEVAL_BUDGET_CHARS

        scored: list[tuple[int, int, str]] = []
        for order, path in enumerate(self._md_files()):
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                score = len(wanted & set(_terms(line)))
                if score:
                    scored.append((score, order, line))

        scored.sort(key=lambda t: (-t[0], t[1]))

        out: list[str] = []
        used = 0
        for _score, _order, line in scored:
            if used + len(line) > budget_chars:
                break
            out.append(line)
            used += len(line)
        return out

    def load(self, name: str) -> str | None:
        target = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        for path in self._md_files():
            if path.stem == target:
                return path.read_text()
        return None

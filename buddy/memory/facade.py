"""One object that both writes and reads the markdown memory store.

The pre-parser needs `append_fact` (for "remember that…") and `search` (for
"what do you know about…") on the same handle; the switchboard's context
composer needs `search`. `Memory` is just `MemoryStore` + `MemorySearch` over
the same base directory.
"""

from __future__ import annotations

from pathlib import Path

from buddy.memory.search import MemorySearch
from buddy.memory.store import MemoryStore


class Memory:
    def __init__(self, base_dir: str | Path | None = None):
        self._store = MemoryStore(base_dir)
        self._search = MemorySearch(base_dir)

    # writes
    def append_fact(self, text: str) -> None:
        self._store.append_fact(text)

    def append_preference(self, text: str) -> None:
        self._store.append_preference(text)

    def append_project_note(self, name: str, text: str) -> None:
        self._store.append_project_note(name, text)

    def append_research(self, topic: str, text: str) -> None:
        self._store.append_research(topic, text)

    # reads
    def search(self, query: str, budget_chars: int | None = None) -> list[str]:
        return self._search.search(query, budget_chars)

    def load(self, name: str) -> str | None:
        return self._search.load(name)

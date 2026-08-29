"""Session rotation (plan §4.6, short-term memory).

Every N Claude turns for a given agent: summarise the session to a small card,
close the session, and reopen it on the next turn seeded with just the card. This
is a usage control, not a memory feature — it stops Buddy resending an
ever-growing transcript on every `--resume`.
"""

from __future__ import annotations

from typing import Callable

from buddy import config

Summarizer = Callable[[str, str | None], str]


class SessionRotator:
    def __init__(
        self,
        registry,
        every_n: int | None = None,
        max_chars: int | None = None,
        summarize: Summarizer | None = None,
    ):
        self._registry = registry
        self._every_n = every_n if every_n is not None else config.VAP_ROTATE_EVERY_N_TURNS
        self._max_chars = (
            max_chars if max_chars is not None else config.VAP_ROTATION_CARD_MAX_CHARS
        )
        self._summarize = summarize or (lambda agent, sid: "")
        self._counts: dict[str, int] = {}
        self._cards: dict[str, str] = {}

    def take_card(self, agent: str) -> str | None:
        """Pop the seed card for `agent`, if a rotation just produced one."""
        return self._cards.pop(agent, None)

    def count_turn(self, agent: str, session_id: str | None) -> None:
        n = self._counts.get(agent, 0) + 1
        self._counts[agent] = n
        if n % self._every_n == 0:
            card = (self._summarize(agent, session_id) or "").strip()
            self._cards[agent] = card[: self._max_chars]
            self._registry.clear_session(agent)

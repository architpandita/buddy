"""Hard daily turn cap + identical-question cache (plan §6.6, §6.7).

On Pro you spend a usage allowance shared with browser Claude; a runaway
assistant can lock you out of the browser. When the daily cap is hit Buddy says
so and stops — there is no degraded fallback.

Only real Claude turns are counted; pre-parsed turns call neither `record_turn`
nor the engine.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Callable

from buddy import config

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip().lower().rstrip("?.!")


class AllowanceGuard:
    def __init__(
        self,
        cap: int | None = None,
        path: str | Path | None = None,
        today: Callable[[], dt.date] | None = None,
    ):
        self._cap = cap if cap is not None else config.VAP_DAILY_TURN_CAP
        self._path = Path(path) if path is not None else config.VAP_ALLOWANCE_FILE
        self._today = today or dt.date.today
        self._cache: dict[str, str] = {}

    # -- daily cap --------------------------------------------------------

    def _load(self) -> int:
        try:
            data = json.loads(self._path.read_text())
        except (FileNotFoundError, ValueError):
            return 0
        if data.get("date") != self._today().isoformat():
            return 0
        return int(data.get("count", 0))

    def _save(self, count: int) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"date": self._today().isoformat(), "count": count})
        )

    def remaining(self) -> int:
        return max(0, self._cap - self._load())

    def allowed(self) -> bool:
        return self._load() < self._cap

    def record_turn(self) -> None:
        self._save(self._load() + 1)

    # -- identical-question cache ---------------------------------------

    def cached(self, text: str) -> str | None:
        return self._cache.get(_norm(text))

    def cache(self, text: str, reply: str) -> None:
        self._cache[_norm(text)] = reply

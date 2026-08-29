"""Pull the first complete sentence off a token stream so TTS can start
speaking while the rest of the reply is still generating (plan §4.5).
"""

from __future__ import annotations

import re
from typing import Iterable, Iterator

# Abbreviations whose trailing dot must not be read as a sentence end.
_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc",
    "e.g", "i.e", "a.m", "p.m", "no", "fig", "approx",
}
_TERMINATOR_RE = re.compile(r"[.!?]")


def _ends_sentence(buffer: str, dot_index: int) -> bool:
    tail = buffer[: dot_index + 1]
    word = re.split(r"[\s(]", tail.rstrip("."))[-1].lower()
    return word not in _ABBREVIATIONS


def first_sentence(chunks: Iterable[str]) -> tuple[str, Iterator[str]]:
    """Consume `chunks` until a sentence terminator; return that sentence and
    an iterator over whatever text is left (buffered remainder first)."""
    buffer = ""
    iterator = iter(chunks)

    for chunk in iterator:
        buffer += chunk
        search_from = 0
        while True:
            m = _TERMINATOR_RE.search(buffer, search_from)
            if not m:
                break
            idx = m.start()
            after = buffer[idx + 1 :]
            if (after == "" or after[0].isspace()) and _ends_sentence(buffer, idx):
                sentence = buffer[: idx + 1].strip()
                remainder = buffer[idx + 1 :].lstrip()
                return sentence, _prepend(remainder, iterator)
            search_from = idx + 1

    return buffer.strip(), iter(())


def _prepend(text: str, rest: Iterator[str]) -> Iterator[str]:
    if text:
        yield text
    yield from rest

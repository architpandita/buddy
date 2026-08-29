"""Turn Claude's terminal-flavoured markdown into something that reads well aloud.

Claude Code writes for a terminal — headers, bullets, code fences, inline
backticks. Spoken straight through `say` that sounds terrible. `shape_for_speech`
strips the markup and enforces a short spoken turn (plan §4.7).
"""

from __future__ import annotations

import re

from buddy import config

_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]*)`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_BOLD_ITALIC_RE = re.compile(r"(\*{1,3}|_{1,3})(\S.*?\S|\S)\1")
_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s{0,3}([-*+]|\d+\.)\s+", re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^\s{0,3}>\s?", re.MULTILINE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def shape_for_speech(text: str, max_sentences: int | None = None) -> str:
    if not text or not text.strip():
        return ""

    if max_sentences is None:
        max_sentences = config.SPOKEN_TURN_MAX_SENTENCES

    out = _FENCE_RE.sub(" ", text)
    out = _IMAGE_RE.sub(r"\1", out)
    out = _LINK_RE.sub(r"\1", out)
    out = _INLINE_CODE_RE.sub(r"\1", out)
    out = _HEADER_RE.sub("", out)
    out = _BULLET_RE.sub("", out)
    out = _BLOCKQUOTE_RE.sub("", out)
    out = _BOLD_ITALIC_RE.sub(r"\2", out)

    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\n{2,}", "\n", out)
    out = "\n".join(line.strip() for line in out.splitlines())
    out = out.strip()

    return _truncate(out, max_sentences)


def _truncate(text: str, max_sentences: int | None) -> str:
    if not max_sentences or max_sentences <= 0:
        return text
    flat = text.replace("\n", " ").strip()
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(flat) if s]
    if len(sentences) <= max_sentences:
        return text
    kept = " ".join(sentences[:max_sentences]).rstrip()
    if not kept.endswith(("...", "…")):
        kept += " …"
    return kept

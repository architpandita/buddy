"""Pre-parser (plan §4.2): the turns Buddy answers locally, without calling Claude.

`preparse(text, ...)` returns:
  - `None`  -> not a control command, forward to Claude
  - `""`    -> handled, say nothing (e.g. "stop")
  - a str   -> handled, speak this

This is the single largest allowance saver — it absorbs roughly a third of turns
at zero cost — so the matching is deliberately forgiving about case, leading
filler words ("uh", "okay, ..."), and trailing punctuation.
"""

from __future__ import annotations

import re

from buddy import config
from buddy.route.state import VapState

_FILLER = re.compile(r"^(uh|um|er|hmm|ok|okay|so|well|hey buddy|buddy|please)[\s,]+", re.I)

_REMEMBER = re.compile(r"^(?:remember|note)(?: that)?[,:]?\s+(.*)", re.I)
_MAKE_NOTE = re.compile(r"^make a note(?: that)?[,:]?\s+(.*)", re.I)
_SAVE_THIS = re.compile(r"^save (?:this|that)\b", re.I)
_SWITCH = re.compile(r"^(?:switch|change)(?: agent)?(?: to| into)?\s+(?:the\s+)?(\w+)", re.I)
_BIG_MODEL = re.compile(r"\b(think harder|think hard|use the (?:big|smart|large) model)\b", re.I)
_FAST_MODEL = re.compile(r"\b(think normally|use the (?:fast|small|quick) model)\b", re.I)
_REPEAT = re.compile(r"^(?:repeat that|say that again|what did you say|come again)\b", re.I)
_START_CONVO = re.compile(r"^(?:start|begin|enter|let'?s have)(?: a| the)? conversation\b", re.I)
_END_CONVO = re.compile(r"^(?:end|stop|exit|leave)(?: the| this)? conversation\b", re.I)
_STOP = re.compile(r"^(?:stop|cancel|never ?mind|forget it)\b", re.I)
_WHAT_KNOW = re.compile(r"^what do you know about\s+(.*)", re.I)


def _clean(text: str) -> str:
    s = text.strip()
    while True:
        stripped = _FILLER.sub("", s)
        if stripped == s:
            break
        s = stripped
    return s.strip().rstrip(".!?").strip()


def preparse(
    text: str,
    *,
    memory,
    state: VapState,
    last_reply: str | None = None,
) -> str | None:
    s = _clean(text)
    if not s:
        return None

    if _END_CONVO.match(s):
        state.conversation_mode = False
        return "Okay, ending conversation."

    if _START_CONVO.match(s):
        state.conversation_mode = True
        return "Okay, I'm listening."

    if _STOP.match(s):
        return ""

    m = _WHAT_KNOW.match(s)
    if m:
        topic = m.group(1).strip()
        hits = memory.search(topic)
        if not hits:
            return f"I don't have anything saved about {topic}."
        return " ".join(h.lstrip("- ").strip() for h in hits)

    if _REPEAT.match(s):
        return last_reply or "I haven't said anything yet."

    if _SAVE_THIS.match(s):
        if not last_reply:
            return "There's nothing to save yet."
        memory.append_fact(last_reply.strip())
        return "Saved."

    m = _MAKE_NOTE.match(s) or _REMEMBER.match(s)
    if m:
        fact = m.group(1).strip().rstrip(".!?").strip()
        if not fact:
            return None
        memory.append_fact(fact)
        return "Noted."

    m = _SWITCH.match(s)
    if m:
        agent = m.group(1).lower()
        state.active_agent = agent
        return f"Switched to {agent}."

    if _FAST_MODEL.search(s):
        state.model_override = None
        return "Back to the fast model."

    if _BIG_MODEL.search(s):
        state.model_override = config.VAP_SMART_MODEL
        return "Okay, thinking harder."

    return None

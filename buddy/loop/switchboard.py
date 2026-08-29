"""The full switchboard turn (plan §4.6).

Order per turn:
    pre-parser  ->  (if not handled locally)
    allowance cap  ->  identical-question cache  ->
    router  ->  registry  ->  session rotation  ->  engine  ->
    record turn + cache + count rotation  ->  shape + speak

One Claude call per turn, against the chosen agent's own session. No delegation.
"""

from __future__ import annotations

from typing import Callable

from buddy.engine.claude_cli import EngineError
from buddy.route.preparser import preparse as _preparse
from buddy.route.router import route as _route
from buddy.route.state import VapState
from buddy.speech.shaper import shape_for_speech
from buddy.tts.speaker import speak as _real_speak

_TROUBLE = "Sorry, something went wrong reaching Claude. Try again."
_CAPPED = "That's today's Claude limit reached. We'll pick this up tomorrow."


class Switchboard:
    def __init__(
        self,
        engine,
        registry,
        allowance,
        rotator,
        memory=None,
        state: VapState | None = None,
        speak: Callable[[str], None] | None = None,
        router: Callable = _route,
        preparser: Callable = _preparse,
        brief_writer=None,
    ):
        self._engine = engine
        self._registry = registry
        self._allowance = allowance
        self._rotator = rotator
        self._memory = memory
        self._brief_writer = brief_writer
        self._state = state or VapState()
        self._speak = speak or _real_speak
        self._route = router
        self._preparse = preparser
        self._last_reply: str | None = None

    def run_turn(self, text: str) -> str:
        handled = self._preparse(
            text, memory=self._memory, state=self._state, last_reply=self._last_reply
        )
        if handled is not None:
            if handled:
                self._speak(handled)
                self._last_reply = handled
            return handled

        if not self._allowance.allowed():
            self._speak(_CAPPED)
            return _CAPPED

        cached = self._allowance.cached(text)
        if cached is not None:
            self._speak(cached)
            self._last_reply = cached
            return cached

        decision = self._route(
            text,
            self._registry,
            override_agent=self._state.active_agent,
            override_model=self._state.model_override,
        )
        agent = self._registry.get(decision.agent)

        card = self._rotator.take_card(decision.agent)
        session_id = None if card else self._registry.session_id(decision.agent)
        prompt = self._compose(text, card)

        try:
            result = self._engine.send(
                prompt, agent=agent, model=decision.model, session_id=session_id
            )
        except EngineError:
            self._speak(_TROUBLE)
            return _TROUBLE

        if result.session_id:
            self._registry.set_session_id(decision.agent, result.session_id)

        self._allowance.record_turn()

        # A research turn keeps the full findings on disk; only the summary is spoken.
        if decision.agent == "researcher" and self._brief_writer is not None and result.reply:
            self._brief_writer.write(topic=text, query=text, body=result.reply)

        spoken = shape_for_speech(result.reply)
        self._allowance.cache(text, spoken)
        self._rotator.count_turn(decision.agent, result.session_id)

        self._speak(spoken)
        self._last_reply = spoken
        return spoken

    def _compose(self, text: str, card: str | None) -> str:
        parts: list[str] = []
        if card:
            parts.append(f"Summary of the conversation so far:\n{card}")
        snippets = self._memory.search(text) if self._memory is not None else []
        if snippets:
            parts.append(
                "Context you have previously been asked to remember "
                "(use only if relevant):\n" + "\n".join(snippets)
            )
        parts.append(text)
        return "\n\n".join(parts)

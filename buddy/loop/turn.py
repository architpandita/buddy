"""One utterance -> one spoken reply.

Wires the engine adapter + speech shaper + session store + one agent. Both front
ends (typed REPL in Phase 1, voice loop in Phase 2) call `run_turn`; it does the
speaking itself via the injected `speak` callable so callers stay thin.
"""

from __future__ import annotations

from typing import Callable

from buddy.agents.loader import AgentSpec
from buddy.agents.sessions import SessionStore
from buddy.engine.claude_cli import EngineError
from buddy.speech.shaper import shape_for_speech
from buddy.tts.speaker import speak as _real_speak

_TROUBLE = "Sorry, something went wrong reaching Claude. Try again."


class TurnRunner:
    def __init__(
        self,
        engine,
        agent: AgentSpec,
        speak: Callable[[str], None] | None = None,
        sessions: SessionStore | None = None,
        memory=None,
    ):
        self._engine = engine
        self._agent = agent
        self._speak = speak or _real_speak
        self._sessions = sessions or SessionStore()
        self._memory = memory

    def run_turn(self, text: str) -> str:
        agent = self._agent
        session_id = self._sessions.get(agent.name)
        prompt = self._with_memory(text)
        try:
            result = self._engine.send(
                prompt, agent=agent, model=agent.model, session_id=session_id
            )
        except EngineError:
            self._speak(_TROUBLE)
            return _TROUBLE

        if result.session_id:
            self._sessions.set(agent.name, result.session_id)

        spoken = shape_for_speech(result.reply)
        self._speak(spoken)
        return spoken

    def _with_memory(self, text: str) -> str:
        """Prepend only the snippets keyword-retrieved for this turn — never the
        whole store (plan §6.5). No memory configured -> text unchanged."""
        if self._memory is None:
            return text
        snippets = self._memory.search(text)
        if not snippets:
            return text
        block = "\n".join(snippets)
        return (
            "Context you have previously been asked to remember "
            f"(use only if relevant):\n{block}\n\n{text}"
        )

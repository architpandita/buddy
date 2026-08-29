"""Shared test fakes for the voice-agent-plane suite.

Nothing here shells out or hits the network. The one module that really runs
`claude` (`buddy.engine.claude_cli`) takes an injected *runner*; tests pass a
`FakeRunner` instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest


@dataclass
class RunnerCall:
    argv: list[str]
    env: dict[str, str]
    cwd: str | None = None


@dataclass
class FakeProcess:
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class FakeRunner:
    """Stand-in for the subprocess runner the engine adapter calls.

    `runner(argv, env) -> FakeProcess`. Records every call so tests can assert
    on the command line and environment that would have been used.
    """

    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.result = FakeProcess(stdout=stdout, stderr=stderr, returncode=returncode)
        self.calls: list[RunnerCall] = []

    def __call__(self, argv, env, cwd=None):
        self.calls.append(RunnerCall(argv=list(argv), env=dict(env), cwd=cwd))
        return self.result

    @property
    def last(self) -> RunnerCall:
        return self.calls[-1]


def stream_json(
    result: str = "PONG",
    session_id: str = "sess-abc",
    *,
    num_turns: int = 1,
    total_cost_usd: float = 0.01,
    duration_ms: int = 1234,
    extra_lines: list[str] | None = None,
) -> str:
    """Build a canned `--output-format stream-json` stdout blob."""
    lines = list(extra_lines or [])
    lines.append(
        json.dumps(
            {
                "type": "assistant",
                "session_id": session_id,
                "message": {"content": [{"type": "text", "text": result}]},
            }
        )
    )
    lines.append(
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": result,
                "session_id": session_id,
                "num_turns": num_turns,
                "total_cost_usd": total_cost_usd,
                "duration_ms": duration_ms,
            }
        )
    )
    return "\n".join(lines) + "\n"


@dataclass
class StubAgent:
    """Minimal stand-in for buddy.agents.loader.AgentSpec."""

    name: str = "companion"
    system_prompt: str = "You are a terse companion."
    allowed_tools: list[str] = field(default_factory=list)
    model: str = "claude-haiku-4-5-20251001"
    max_turns: int = 1


@pytest.fixture
def agent() -> StubAgent:
    return StubAgent()

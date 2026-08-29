"""Engine adapter: the one module that shells out to `claude -p`.

All CLI-specific command construction and stream-json parsing lives here. This
is the escape hatch to another backend and the seam where GPT/Gemini adapters
would slot in later (see docs/voice-assistant-plan.md §4.5).

The subprocess itself is injected as `runner(argv, env) -> proc` so the rest of
the system — and the tests — never actually spawn `claude`.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


class _Proc(Protocol):
    stdout: str
    stderr: str
    returncode: int


Runner = Callable[..., _Proc]


class EngineError(RuntimeError):
    """Raised when `claude -p` exits non-zero or returns an error result."""


@dataclass
class EngineResult:
    reply: str
    session_id: str
    meta: dict[str, Any] = field(default_factory=dict)


def default_runner(argv: list[str], env: dict[str, str], cwd: str | None = None) -> _Proc:
    return subprocess.run(argv, env=env, cwd=cwd, capture_output=True, text=True)


class ClaudeCLIEngine:
    def __init__(
        self,
        runner: Runner | None = None,
        sandbox_dir: str | os.PathLike[str] = ".",
        binary: str = "claude",
    ):
        self._runner = runner or default_runner
        self._sandbox_dir = str(sandbox_dir)
        self._binary = binary

    def send(self, text: str, agent, model: str, session_id: str | None) -> EngineResult:
        argv = self._build_argv(text, agent, model, session_id)
        env = self._build_env()
        proc = self._runner(argv, env, self._sandbox_dir)

        if proc.returncode != 0:
            raise EngineError(
                f"claude exited {proc.returncode}: {(proc.stderr or '').strip()}"
            )

        result_obj = self._parse_stream_json(proc.stdout)
        if result_obj is None:
            raise EngineError("no result object in claude stream-json output")
        if result_obj.get("is_error"):
            raise EngineError(f"claude returned error result: {result_obj.get('result')!r}")

        return EngineResult(
            reply=(result_obj.get("result") or "").strip(),
            session_id=result_obj.get("session_id") or session_id or "",
            meta={
                "total_cost_usd": result_obj.get("total_cost_usd"),
                "num_turns": result_obj.get("num_turns"),
                "duration_ms": result_obj.get("duration_ms"),
            },
        )

    # -- internals -------------------------------------------------------------

    def _build_argv(self, text, agent, model, session_id) -> list[str]:
        argv = [
            self._binary,
            "-p",
            text,
            "--output-format",
            "stream-json",
            "--verbose",
            "--model",
            model,
            "--append-system-prompt",
            agent.system_prompt,
            "--allowedTools",
            ",".join(agent.allowed_tools),
            "--max-turns",
            str(agent.max_turns),
        ]
        if session_id:
            argv += ["--resume", session_id]
        return argv

    def _build_env(self) -> dict[str, str]:
        env = dict(os.environ)
        # Never let a stray key silently bill paid API rates (plan §7).
        env.pop("ANTHROPIC_API_KEY", None)
        return env

    @staticmethod
    def _parse_stream_json(stdout: str) -> dict[str, Any] | None:
        result_obj: dict[str, Any] | None = None
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("type") == "result":
                result_obj = obj
        return result_obj

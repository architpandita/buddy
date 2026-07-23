"""Drives a real Claude Code session for a transcribed dev instruction."""

from __future__ import annotations

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ThinkingConfigDisabled,
    ThinkingConfigEnabled,
    query,
)

from buddy import config

# If Buddy is ever launched from inside an existing Claude Code terminal
# session (e.g. while developing Buddy itself), these env vars leak into the
# spawned `claude` subprocess and make it misdetect itself as a nested/child
# agent, sandboxing file writes to a fake home directory instead of `cwd`.
# The SDK already strips CLAUDECODE for this reason; clear the rest too.
_NESTED_SESSION_ENV_VARS = (
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_CODE_CHILD_SESSION",
    "CLAUDE_PID",
    "CLAUDE_EFFORT",
    "AI_AGENT",
    "CLAUDE_CODE_EXECPATH",
    "CLAUDE_CODE_SSE_PORT",
)


async def run_instruction(instruction: str) -> str:
    """Sends `instruction` to Claude Code against the active project dir.

    Returns the final result text (spoken back via TTS). Uses the current
    deep-think setting for model/effort/thinking budget on this call only.
    """
    state = config.state

    thinking = (
        ThinkingConfigEnabled(
            type="enabled",
            budget_tokens=config.DEEP_THINK_BUDGET_TOKENS,
            display="summarized",
        )
        if state.deep_think
        else ThinkingConfigDisabled(type="disabled")
    )

    options = ClaudeAgentOptions(
        cwd=str(state.active_project_dir),
        allowed_tools=config.ALLOWED_TOOLS,
        permission_mode=config.PERMISSION_MODE,
        model=state.model,
        effort=state.effort,
        thinking=thinking,
        env={var: "" for var in _NESTED_SESSION_ENV_VARS},
    )

    final_result = ""
    async for message in query(prompt=instruction, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"[claude] {block.text}")
        elif isinstance(message, ResultMessage):
            final_result = message.result or ""

    return final_result

"""Load an agent spec from a markdown file.

An agent file is frontmatter + body:

    ---
    model: claude-haiku-4-5-20251001
    tools: [WebSearch, Write]
    max_turns: 4
    style: short, conversational
    ---
    <the system prompt, appended to Claude's default>

Only `model` is required. The body becomes `--append-system-prompt`.
No external YAML dependency — the frontmatter is deliberately flat.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


class AgentSpecError(ValueError):
    pass


@dataclass
class AgentSpec:
    name: str
    system_prompt: str
    model: str
    allowed_tools: list[str] = field(default_factory=list)
    max_turns: int = 1
    style: str = ""


def load_agent(path: str | Path) -> AgentSpec:
    path = Path(path)
    text = path.read_text()
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise AgentSpecError(f"{path.name}: missing `---` frontmatter block")

    fields = _parse_frontmatter(m.group(1))
    body = m.group(2).strip()

    if "model" not in fields:
        raise AgentSpecError(f"{path.name}: required field `model` missing")

    return AgentSpec(
        name=path.stem,
        system_prompt=body,
        model=fields["model"],
        allowed_tools=_as_list(fields.get("tools", "")),
        max_turns=int(fields["max_turns"]) if "max_turns" in fields else 1,
        style=fields.get("style", ""),
    )


def _parse_frontmatter(block: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise AgentSpecError(f"bad frontmatter line: {line!r}")
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


def _as_list(value: str) -> list[str]:
    value = value.strip()
    if not value or value in ("[]", "[ ]"):
        return []
    value = value.strip("[]")
    return [item.strip() for item in value.split(",") if item.strip()]

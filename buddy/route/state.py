"""Runtime state for the voice-agent-plane switchboard.

Mutable, not persisted. Flipped only by the pre-parser's voice control commands
(plan §4.2) — "switch to <agent>", "think harder", etc.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VapState:
    active_agent: str | None = None      # None -> let the router decide
    model_override: str | None = None    # None -> let the router decide

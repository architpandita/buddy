"""Typed-input entrypoint: type a line, hear (and see) the answer.

    python -m buddy.textloop

The debug harness for the full switchboard — pre-parser, router, per-agent
sessions, allowance cap — without needing a mic.
"""

from __future__ import annotations

import sys

from buddy.loop.build import build_switchboard
from buddy.memory.janitor import Janitor


def main() -> None:
    runner = build_switchboard()
    print("Buddy text loop. Ctrl-D to quit.\n")
    try:
        while True:
            try:
                line = input("you > ").strip()
            except EOFError:
                print()
                break
            if not line:
                continue
            reply = runner.run_turn(line)
            print(f"buddy > {reply}\n")
    finally:
        Janitor().purge_sessions()  # conversation end: drop session state


if __name__ == "__main__":
    sys.exit(main())

"""Buddy entrypoint: voice -> Claude Code dev actions.

Run with the project venv active: `python main.py`
"""

import asyncio

from buddy.assistant import run

if __name__ == "__main__":
    asyncio.run(run())

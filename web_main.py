"""Buddy browser entrypoint: mic capture, push-to-talk, and TTS all happen in
a browser tab; this process only transcribes + runs Claude Code.

Run with the project venv active: `python web_main.py`, then open
http://127.0.0.1:8765 (or whatever buddy.config.WEB_HOST/WEB_PORT are set to).
"""

import uvicorn

from buddy import config

if __name__ == "__main__":
    uvicorn.run("buddy.web.server:app", host=config.WEB_HOST, port=config.WEB_PORT)

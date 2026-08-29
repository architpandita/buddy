"""Browser front end for the voice-agent-plane.

Same client-side model as Milestone-1's `buddy.web.server` (mic + TTS in the
tab), but routes transcribed text through the Phase-1 `TurnRunner` instead of the
code-editing `assistant.process_utterance`. Kept as a separate app so the two
front ends don't entangle.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from buddy.stt import whisper_transcriber

app = FastAPI()

_runner = None
_transcribe = whisper_transcriber.transcribe_wav_bytes


def configure(runner=None, transcribe=None) -> None:
    """Set the TurnRunner (and optionally a transcriber) the app uses."""
    global _runner, _transcribe
    if runner is not None:
        _runner = runner
    if transcribe is not None:
        _transcribe = transcribe


def _get_runner():
    global _runner
    if _runner is None:
        from buddy.loop.build import build_switchboard

        _runner = build_switchboard()
    return _runner


@app.post("/api/utterance")
async def handle_utterance(request: Request) -> JSONResponse:
    wav_bytes = await request.body()
    heard = (_transcribe(wav_bytes) or "").strip()
    response = _get_runner().run_turn(heard) if heard else ""
    return JSONResponse({"heard": heard, "response": response})

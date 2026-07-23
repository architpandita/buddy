"""Browser front end for Buddy: mic capture, push-to-talk, and TTS playback all
happen client-side in the page served here. This server only transcribes the
WAV the browser records and routes the resulting text through the same
control-command / Claude logic the CLI (`main.py`) uses -- see
`buddy.assistant.process_utterance`.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from buddy import assistant, config
from buddy.stt import whisper_transcriber

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI()


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/utterance")
async def handle_utterance(request: Request) -> JSONResponse:
    """Body is a raw 16kHz mono WAV file recorded and encoded in the browser."""
    wav_bytes = await request.body()
    heard = whisper_transcriber.transcribe_wav_bytes(wav_bytes)
    response = await assistant.process_utterance(heard)
    return JSONResponse(
        {
            "heard": heard,
            "response": response,
            "deep_think": config.state.deep_think,
            "active_project": str(config.state.active_project_dir),
        }
    )

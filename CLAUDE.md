# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Buddy is a Jarvis-style voice assistant. Milestone 1 (current state of this repo): speak a
dev instruction, it's transcribed locally with whisper.cpp, sent into a real Claude Code
session via the Claude Agent SDK, and the code change actually happens against a target
project directory. There are two interchangeable front ends, sharing the same backend
routing/transcription/agent code:

- **CLI** (`main.py`) — OS-level push-to-talk hotkey or wake word ("Hi Buddy"), mic capture
  via `sounddevice`, reply spoken via macOS `say`.
- **Browser** (`web_main.py`) — a local FastAPI server + single-page frontend. Mic capture,
  push-to-talk (button or held Space), and TTS playback (Web Speech API) all happen
  client-side in the tab; the server only transcribes and routes. No OS Accessibility
  permission needed for this path, since there's no global hotkey.

Later milestones (not yet built): YouTube video ingestion + discussion, live meeting
listening, whole-codebase context for pair programming.

## Running it

```bash
source .venv/bin/activate
python main.py          # CLI: global hotkey / wake word, mic+speaker via the OS
# or
python web_main.py      # Browser: open http://127.0.0.1:8765, mic+speaker via the tab
```

There is no test suite, linter, or build step configured in this repo yet.

One-time setup (whisper.cpp binary, wake-word `.onnx` model, macOS mic/accessibility
permissions) is documented in README.md — read it before assuming a dependency is missing
versus just not configured on this machine. The browser path only needs mic permission
granted to the browser itself (no Accessibility permission, since there's no global hotkey).

## Architecture: the trigger -> record -> transcribe -> route -> respond pipeline

`buddy/assistant.py: process_utterance(text) -> str` is the shared routing core both front
ends call — it does not speak the response itself, callers decide how (this is what lets the
CLI and browser server share one routing path). The flow for a single utterance:

1. **Trigger** — CLI: `buddy/audio/hotkey.py` (global push-to-talk via pynput) or
   `buddy/audio/wakeword.py` (openWakeWord listening for "Hi Buddy") call a shared
   `_on_trigger` callback feeding `_trigger_queue`; a second trigger while already recording
   stops it early. Browser: the frontend in `buddy/web/static/index.html` starts/stops
   recording on button hold or held Space, no server involvement until the utterance ends.
2. **Record** — CLI: `buddy/audio/capture.py` records from the mic and endpoints on silence
   (`record_until_silence`), returning 16kHz mono PCM16 samples. Browser: the page captures
   Float32 samples via a `ScriptProcessorNode` (routed through a zero-gain node to avoid mic
   echo through speakers), downsamples to 16kHz, and hand-encodes a WAV file in JS.
3. **Transcribe** — `buddy/stt/whisper_transcriber.py` shells out to a locally installed
   `whisper-cli` binary. `transcribe(samples)` (CLI, numpy array) and
   `transcribe_wav_bytes(wav_bytes)` (browser, raw WAV upload via `POST /api/utterance` in
   `buddy/web/server.py`) both funnel into the shared `_run_whisper_on_wav` helper.
4. **Route** — `process_utterance` first checks `_try_handle_control_command`, which
   intercepts voice commands Buddy answers locally without invoking Claude at all: "deep
   think on/off", "switch to project `<name>`", "stop"/"cancel"/"never mind". It returns
   `None` (not a control command, forward to Claude), or the response string (`""` counts as
   a handled no-op — callers must check `is not None`, not truthiness). Anything not handled
   locally is passed to `buddy/agent/claude_driver.py: run_instruction`.
5. **Agent** — `claude_driver.py` calls the Claude Agent SDK's `query()` against
   `config.state.active_project_dir`, using the model/effort/thinking settings implied by
   `config.state.deep_think`. It strips a set of `CLAUDE_CODE_*` / `AI_AGENT` env vars before
   spawning the `claude` subprocess — necessary because if Buddy is itself launched from
   inside a Claude Code terminal session, those env vars leak in and make the child `claude`
   process misdetect itself as nested, sandboxing its file writes instead of touching `cwd`.
6. **Respond** — CLI: `assistant._handle_utterance` speaks the `process_utterance` result via
   `buddy/tts/speaker.py` (macOS `say`; swap the body of `speak()` to change backends without
   touching callers). Browser: `buddy/web/server.py` returns the result as JSON and the page
   speaks it via `window.speechSynthesis` — the server never calls `speaker.speak()`.

## Config and runtime state

`buddy/config.py` is the single place for tunables: hotkey combo, wake-word model path +
threshold, whisper binary/model path, TTS voice, `WEB_HOST`/`WEB_PORT` for the browser
server, allowed Claude tools, permission mode, and the fast/deep-think model + effort presets
(`FAST_MODEL` = claude-sonnet-5, `DEEP_THINK_MODEL` = claude-opus-4-8). Named project
directories reachable via "switch to project `<name>`" live in `config.PROJECTS` — add repos
there, not in code elsewhere.

`config.state` is a module-level `RuntimeState` singleton (mutable, not persisted) holding
`active_project_dir` and `deep_think`, flipped only via the voice control commands in
`assistant.py`. Anything that needs "what project/model is currently active" should read
`config.state`, not `config.DEFAULT_PROJECT_DIR` / `FAST_MODEL` directly.

## Known tradeoff (deliberate, not a bug)

Buddy runs Claude Code with `permission_mode="acceptEdits"` (see `config.PERMISSION_MODE`) so
file edits apply without an interactive approval step — required for a hands-free assistant,
but it means Buddy can edit files in the active project without asking first. This is
intentional per the README; don't "fix" it by adding a confirmation step unless asked.

## Non-project directories

`skills/` in this repo root is a bundle of generic Claude Code plugin-development skills
(agent-development, hook-development, plugin-structure, tdd, etc.) — not part of Buddy's own
application code. Don't treat it as part of Buddy's architecture when reasoning about this
codebase.

# Buddy

A Jarvis-style voice assistant. Milestone 1: speak a dev instruction (via push-to-talk
hotkey or the wake word "Hi Buddy"), it's transcribed locally, sent into a real
Claude Code session, and the code change actually happens.

## One-time setup

### 1. Python env

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Claude Code CLI

The Agent SDK drives the `claude` CLI under the hood — make sure it's installed
and authenticated:

```bash
claude --version
```

### 3. Whisper.cpp (local STT)

```bash
brew install whisper-cpp
mkdir -p models/whisper
curl -L -o models/whisper/ggml-base.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
```

### 4. Wake word ("Hi Buddy")

This repo doesn't train the wake-word model for you — do it once:

1. Go to https://openwakeword.com/train (or use a local Piper-TTS based
   trainer such as `lgpearson1771/openwakeword-trainer`) and train a custom
   wake word for the phrase "Hi Buddy".
2. Save the resulting `.onnx` model to `models/wakeword/hi_buddy.onnx`.

If this file is missing, Buddy still runs fine — the wake word just stays
disabled and the push-to-talk hotkey is your only trigger.

### 5. macOS permissions

Grant your terminal (or whichever app runs `python main.py`) both:
- **Microphone** access (System Settings → Privacy & Security → Microphone)
- **Accessibility** access (System Settings → Privacy & Security → Accessibility)
  — required for the global push-to-talk hotkey.

## Running

Two interchangeable ways to talk to Buddy — same backend, different mic/speaker I/O:

### CLI (OS-level hotkey / wake word)

```bash
source .venv/bin/activate
python main.py
```

- Press **⌥ + Space** to start talking; press it again to stop early
  (otherwise it stops automatically after ~1.2s of silence).
- Or just say **"Hi Buddy"** if the wake-word model is installed.
- Replies are spoken via macOS `say`.
- Requires the Microphone and Accessibility permissions from step 5 above.

### Browser (mic/speaker via a tab, no Accessibility permission needed)

```bash
source .venv/bin/activate
python web_main.py
```

Then open **http://127.0.0.1:8765**. Press and hold the button (or hold **Space**) to talk,
release to send. Replies are spoken via the browser's built-in Web Speech API. Only
Microphone permission is needed (granted to your browser, the first time it asks) — there's
no global hotkey in this mode, so Accessibility access isn't required.

### Voice commands (work in both modes)

- Say **"deep think on"** / **"deep think off"** to toggle reasoning effort
  (Opus + extended thinking vs. fast Sonnet) for subsequent instructions.
- Say **"switch to project <name>"** to point Buddy at a different repo —
  add named projects in `buddy/config.py: PROJECTS`.

## Configuration

All tunables live in `buddy/config.py`: the hotkey combo, wake-word
threshold, whisper model path, target project directories, and the
fast/deep-think model + effort presets.

## Known tradeoff

Buddy runs Claude Code with `permission_mode="acceptEdits"` so file edits
apply without an interactive approval step — necessary for a hands-free
assistant, but it means Buddy can edit files in the active project without
asking first. Point `DEFAULT_PROJECT_DIR` / `PROJECTS` at repos you're
comfortable with it touching directly.

## Roadmap

Milestone 1 (this repo) is voice → Claude Code dev actions. Later phases:
YouTube video ingestion + discussion, live meeting listening, and
whole-codebase context for pair programming.

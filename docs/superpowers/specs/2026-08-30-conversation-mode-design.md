# Conversation mode — design

**Date:** 2026-08-30
**Status:** implemented 2026-08-31 (16 tests, suite green at 143)

## Goal

Alexa-style back-and-forth for the voice-agent-plane. Today every utterance needs
a fresh trigger ("Hi Buddy" or the hotkey). Conversation mode lets the user say
"start conversation" once and then keep talking — Buddy auto-listens after each
reply — until the user says "end conversation" or walks away.

Not in scope: barge-in (talking over Buddy's reply). Replies still queue-and-wait.
Wake word / VAD training is a separate task; conversation mode works with
push-to-talk alone.

## Behavior

- **Enter:** "start conversation" (also "begin conversation", "let's have a
  conversation", "enter conversation"). Buddy speaks a short confirmation
  ("Okay, I'm listening.") and sets `VapState.conversation_mode = True`.
- **Follow-up listening:** while the mode is on, after each spoken reply the voice
  loop opens an **onset window** of `VAP_CONVERSATION_ONSET_TIMEOUT_S` (8s). If
  the user starts speaking within it, the utterance is recorded and endpointed on
  `VAP_CONVERSATION_SILENCE_S` (4s) of trailing silence, then run as the next
  turn. No wake word needed.
- **Idle:** an onset window that elapses with no speech is an *empty window*.
  After `VAP_CONVERSATION_MAX_IDLE_WINDOWS` (3) consecutive empty windows — the
  first plus two retries — Buddy speaks "I'll be here — say start conversation
  when you're back." and sets `conversation_mode = False`. A non-empty window
  resets the counter.
- **Exit:** "end conversation" (also "stop conversation", "exit conversation",
  "leave conversation"). Buddy speaks "Okay, ending conversation." and sets
  `conversation_mode = False`. Matched **before** the generic `_STOP` rule so
  "stop conversation" ends the mode rather than being swallowed as a bare "stop".
- Hotkey and wake word keep working throughout. Conversation mode only adds the
  post-reply auto-listen; it does not disable the normal triggers.
- Typed loop (`buddy.textloop`) is unaffected — it has no `VapState`/voice loop
  and simply never reads `conversation_mode`.

## Components and changes

### `buddy/route/state.py`
Add one field:
```python
conversation_mode: bool = False
```

### `buddy/config.py`
Add three tunables near the other `VAP_*` voice settings:
```python
VAP_CONVERSATION_ONSET_TIMEOUT_S = 8.0   # wait this long for the user to start replying
VAP_CONVERSATION_SILENCE_S = 4.0         # trailing silence that ends the user's turn
VAP_CONVERSATION_MAX_IDLE_WINDOWS = 3    # consecutive empty windows before auto-exit
```

### `buddy/route/preparser.py`
Two new patterns, checked at the top of `preparse` (before `_STOP`):
```python
_START_CONVO = re.compile(r"^(?:start|begin|enter|let'?s have)(?: a| the)? conversation\b", re.I)
_END_CONVO   = re.compile(r"^(?:end|stop|exit|leave)(?: the| this)? conversation\b", re.I)
```
- `_START_CONVO` → `state.conversation_mode = True`; return `"Okay, I'm listening."`
- `_END_CONVO` → `state.conversation_mode = False`; return `"Okay, ending conversation."`

`preparse` already receives `state: VapState`, so no signature change.

### `buddy/audio/capture.py`
Add an optional `onset_timeout` to `record_until_silence`:
```python
def record_until_silence(silence_duration=SILENCE_DURATION_S,
                         max_seconds=MAX_RECORD_SECONDS,
                         stop_event=None,
                         onset_timeout=None) -> np.ndarray:
```
Semantics: if `onset_timeout` is set and no block has crossed
`SILENCE_RMS_THRESHOLD` by the time `onset_timeout` seconds of audio have been
read, break and return whatever was captured (typically empty). Existing callers
pass nothing and are unaffected. Implemented by counting blocks:
`onset_blocks = int(onset_timeout * SAMPLE_RATE / BLOCK_SIZE)`; inside the loop,
`if not heard_speech and len(blocks) >= onset_blocks: break`.

### `buddy/input/mic_intake.py`
Add a `follow_up()` method and a second injectable recorder. It does **not**
touch the trigger queue — it is a one-shot capture the voice loop calls directly.
```python
FollowUpRecorder = Callable[[threading.Event], "np.ndarray"]

def __init__(self, record=None, transcribe=None, follow_up_record=None):
    ...
    self._follow_up_record = follow_up_record or _default_follow_up_record

def follow_up(self) -> str | None:
    """One-shot listen for a follow-up turn. Returns the transcript, or None if
    the onset window elapsed silently or transcription failed."""
```
`_default_follow_up_record` calls `record_until_silence` with
`silence_duration=config.VAP_CONVERSATION_SILENCE_S` and
`onset_timeout=config.VAP_CONVERSATION_ONSET_TIMEOUT_S`. `follow_up()` reuses the
existing `_recording` / `_stop` events so `trigger()`'s "press again to stop"
still cancels a follow-up capture, and returns `None` for empty samples or a
`whisper-cli` failure (mirrors `utterances()`' skip-and-continue policy).

### `buddy/loop/voice.py`
`VoiceLoop` gains an optional `state`:
```python
def __init__(self, intake, turn_runner, state=None, speak=None):
```
`run()` factors the per-turn body into `_run_turn_safely(text)` (the existing
try/except), then after each triggered utterance drains follow-ups:
```python
for text in self._intake.utterances():
    self._run_turn_safely(text)
    self._drain_follow_ups()

def _drain_follow_ups(self):
    if self._state is None:
        return
    empty = 0
    while self._state.conversation_mode:
        follow = self._intake.follow_up()
        if follow is None:
            empty += 1
            if empty >= config.VAP_CONVERSATION_MAX_IDLE_WINDOWS:
                self._state.conversation_mode = False
                self._speak("I'll be here — say start conversation when you're back.")
            continue
        empty = 0
        self._run_turn_safely(follow)
```
The idle exit-line ("I'll be here…") is spoken by `VoiceLoop` itself. `VoiceLoop`
takes an optional `speak` callable (defaults to `buddy.tts.speaker.speak`) and
calls it when it flips `conversation_mode` off after the retry limit. This keeps
the exit message out of the switchboard and the preparser.

### `buddy/loop/switchboard.py`
Expose the state so the composition root can hand the same instance to the loop:
```python
@property
def state(self) -> VapState:
    return self._state
```

### `buddy/loop/build.py` and `buddy/voice_main.py`
`build_switchboard()` already builds a `VapState()`; no change there. `voice_main`:
```python
runner = build_switchboard()
...
VoiceLoop(intake=intake, turn_runner=runner, state=runner.state).run()
```

## Data flow (conversation mode on)

```
user: "start conversation"
  hotkey/wakeword -> intake.utterances() yields -> switchboard.run_turn
  -> preparse -> state.conversation_mode = True -> speak "Okay, I'm listening."
loop: _drain_follow_ups()
  intake.follow_up() -> record_until_silence(onset_timeout=8, silence=4)
    speech heard -> transcript "what's the weather"
  switchboard.run_turn("what's the weather") -> researcher/companion -> speak reply
  intake.follow_up() -> 8s silence -> None (empty 1)
  intake.follow_up() -> 8s silence -> None (empty 2)
  intake.follow_up() -> 8s silence -> None (empty 3) -> conversation_mode = False
  loop speaks "I'll be here - say start conversation when you're back."
back to intake.utterances(), waiting on the trigger queue
```

## Error handling

- `whisper-cli` failure inside `follow_up()` → returns `None`, counted as an empty
  window (does not crash the loop, does not spam turns).
- `run_turn` raising inside a follow-up → caught by `_run_turn_safely`, logged,
  loop continues; conversation mode stays on.
- Onset window while the user is mid-sentence at the 8s mark: `heard_speech` is
  already true, so the onset cutoff doesn't apply — normal 4s-silence
  endpointing takes over. No truncation of a reply that started in time.
- Wake word competing for the mic during a follow-up: `voice_main`'s `record`
  wrapper already pauses/resumes the `WakeWordListener` around a capture; the
  follow-up recorder is wrapped the same way.

## Testing

New / changed tests, all with fakes — no mic, no network:

- `tests/route/test_preparser.py`
  - `test_start_conversation_sets_mode` — flag True, spoken confirmation
  - `test_end_conversation_clears_mode` — flag False
  - `test_stop_conversation_ends_mode_not_bare_stop` — "stop conversation" hits
    `_END_CONVO`, returns the end line (not `""`)
  - `test_bare_stop_still_returns_empty` — regression: "stop" unchanged
- `tests/audio/test_capture.py` (new file; drive `record_until_silence` with a
  fake `sd.InputStream` / injected block source)
  - `test_onset_timeout_returns_early_on_silence`
  - `test_onset_timeout_does_not_fire_once_speech_heard`
  - `test_no_onset_timeout_preserves_existing_behavior`
- `tests/input/test_mic_intake.py`
  - `test_follow_up_returns_transcript_on_speech`
  - `test_follow_up_returns_none_on_empty_samples`
  - `test_follow_up_returns_none_on_transcription_failure`
  - `test_follow_up_does_not_consume_trigger_queue`
- `tests/loop/test_voice.py`
  - `test_no_state_means_no_follow_ups` (back-compat: existing tests pass
    `state=None` implicitly)
  - `test_follow_up_turn_runs_when_conversation_mode_on`
  - `test_three_empty_windows_exit_conversation_mode` + idle line spoken
  - `test_non_empty_window_resets_empty_counter`
  - `test_end_conversation_during_follow_up_stops_the_drain`

## Open decision resolved

Idle policy: **first window + 2 retries = 3 consecutive empty windows, then
auto-exit** (`VAP_CONVERSATION_MAX_IDLE_WINDOWS = 3`).

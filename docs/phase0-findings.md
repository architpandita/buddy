# Phase 0 — Validation Findings

**Date:** 2026-08-29
**Machine:** this MacBook (Darwin 24.5.0), `claude` CLI `2.1.251`, `whisper-cli` at
`/opt/homebrew/bin/whisper-cli`, model `models/whisper/ggml-base.en.bin`.
**Verdict:** ✅ **PASS — proceed to Phase 1.** No kill criterion tripped.

Spike scripts: `scratch/p0_roundtrip.sh` (+ `scratch/p0_*.jsonl` / `*.log`). Delete
`scratch/` after Phase 1 starts.

---

## 1. `claude -p`, `--resume`, `setup-token`

| Check | Result |
|---|---|
| `claude setup-token` | ✅ subcommand exists — "Set up a long-lived authentication token (requires Claude subscription)". Not run in this spike (interactive); run it once before deploying as a daemon. |
| OAuth (subscription) auth, no `ANTHROPIC_API_KEY` | ✅ `ANTHROPIC_API_KEY` unset; `claude -p` runs, `is_error: false`, `modelUsage` shows the real model. |
| `--output-format stream-json` / `json` | ✅ both work. `--output-format stream-json` **requires `--verbose`**. |
| `--resume <session_id>` | ✅ turn 2 resumed session `ef858bd8-…`, same `session_id` returned, context retained ("what did you just say?" → "PONG"). |
| `--model` (`claude-haiku-4-5-20251001`, `claude-sonnet-5`) | ✅ both accepted. |
| `--max-turns`, `--allowedTools ""`, `--append-system-prompt` | ✅ accepted. |

### `result` JSON fields available (telemetry for free — §4.5)

```
result, session_id, total_cost_usd, num_turns, duration_ms, duration_api_ms,
ttft_ms, usage, modelUsage, is_error, stop_reason, permission_denials, subtype, uuid
```

`total_cost_usd` **is reported on Pro but is notional** (not billed — Pro spends the
usage allowance, not dollars). Use `num_turns` + our own daily counter for allowance
control, not `total_cost_usd`.

**`--bare` is NOT usable.** It forces auth to `ANTHROPIC_API_KEY` / `apiKeyHelper`
only — it never reads the OAuth/keychain subscription credential ("Not logged in").
So the daemon must use the normal (non-bare) startup path.

---

## 2. Round-trip latency

Trivial turn ("say PONG"), Haiku, `--max-turns 1`, no tools:

| Working directory | Wall time | API portion (`duration_ms`) |
|---|---|---|
| **This repo dir** (`buddy/`) | **~23 s** (turn 1), ~13 s (turn 2) | ~5.5 s |
| **Clean sandbox dir** (`/tmp/p0sandbox`) | **~8–11 s** | ~2.3–4.3 s |

Realistic short conversational Haiku turn from the clean dir: **8.5 s wall**
(`ttft_ms` 3.3 s, `api_ms` 3.8 s). Sonnet trivial turn: ~7.7 s wall.

### The finding that matters

Running `claude -p` **inside the Buddy repo dir adds ~12–15 s of fixed overhead** —
it discovers this project's MCP servers (one, `kite`, has a 30 s connect timeout),
hooks, plugins and `CLAUDE.md`. **The daemon must `cwd` into a dedicated empty
sandbox directory** for every `claude -p` call. This also satisfies the §7 risk-table
"Sandbox dir" mitigation for free.

- Remaining ~5 s in the clean dir is Node CLI cold start + keychain read; unavoidable
  on the OAuth path (`--bare` would remove it but breaks auth — see §1).
- Mitigation per §4.5: **stream the first sentence to `say` while the rest generates**
  — perceived latency drops to ttft (~3 s) + `say` startup.

**Kill criterion "turn over 20 s":** not tripped, *provided the daemon runs from a
clean cwd*. From the repo dir it would trip. → Actionable config, not a kill.

---

## 3. Allowance headroom

Not stress-tested — deliberately. Exhausting the Pro allowance would lock the user out
of browser Claude (the whole risk the project exists to avoid).

Instead, instrument from turn 1:
- Log `num_turns` + a local monotonic daily counter per `claude -p` call.
- Ship the **hard daily turn cap** (§6.7 / Phase 4 `allowance.py`) *disabled-safe*:
  default cap low (e.g. 40), user raises it once they observe real headroom.
- Revisit this finding with real numbers after ~1 week of Phase 1–2 use.

**Kill criterion "50 turns exhausts the allowance":** unmeasured; treated as a
monitored risk with a conservative default cap, not a blocker.

---

## 4. How Whisper emits text on this machine

**None of the three shapes in the plan (file tail / stdin pipe / HTTP-from-external-
Whisper) apply.** There is no separate long-running Whisper process here.

Whisper in this repo is **`whisper-cli` invoked per-utterance, in-process**, by
`buddy/stt/whisper_transcriber.py`:
- `transcribe(samples: np.ndarray) -> str` — after `buddy.audio.capture` records the
  mic and endpoints on silence (CLI path).
- `transcribe_wav_bytes(wav_bytes) -> str` — for a WAV uploaded to
  `POST /api/utterance` (browser path).

Both are **batch, synchronous, return one string**. Latency: not separately measured
in this spike (base.en model, short utterance — typically < 1 s on M-series).

### Decision: input adapter shape for Phase 2

The Phase 2 input adapter is a thin **in-process `Iterator[str]`** wrapper over the
existing trigger → `capture` → `whisper_transcriber.transcribe` pipeline — **not** a
file/pipe/HTTP reader of an external process.

- Reuse `buddy/audio/hotkey.py` / `buddy/audio/wakeword.py` as the trigger.
- Reuse `buddy/audio/capture.record_until_silence`.
- Reuse `buddy/stt/whisper_transcriber.transcribe`.
- The HTTP variant already exists as FastAPI `POST /api/utterance` in
  `buddy/web/server.py` — keep it as the browser intake, same adapter interface.

This **simplifies Phase 2**: no new file-watching / rotation-handling code, and the
Phase 2 test list for `file_tail.py` / `stdin_pipe.py` / `http_in.py` collapses to one
`buddy/input/mic_intake.py` with fake-trigger + fake-transcriber tests.

> Update `voice-assistant-tdd-plan.md` §Phase 2.1 accordingly before starting Phase 2.

---

## 5. Actions carried into Phase 1

1. **Engine adapter must `cwd` into a dedicated empty sandbox dir** (create on daemon
   start, e.g. `~/.buddy/sandbox/`), not the project dir.
2. Engine adapter command: `claude -p --output-format stream-json --verbose --resume
   <id> --model <m> --append-system-prompt <p> --allowedTools <list> --max-turns <n>`.
3. Launcher **explicitly unsets `ANTHROPIC_API_KEY`** (confirmed already unset here;
   still enforce it — §7).
4. Run `claude setup-token` once during deployment setup; document in README.
5. Parse allowance from `num_turns` + local counter; **ignore `total_cost_usd`** for
   control decisions.
6. Stream first sentence to TTS to hide the ~5 s CLI cold-start.
7. `pytest` + `pytest-asyncio` → `requirements.txt`; create `tests/` + `pytest.ini`
   with a deselected-by-default `live` marker.

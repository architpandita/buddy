# Voice Agent Plane — TDD Implementation Plan

Companion to [`voice-assistant-plan.md`](./voice-assistant-plan.md). That doc is the
design; this doc is the build order, written test-first.

**Backend:** Claude Code CLI on a **Pro** subscription (`claude setup-token` for a
long-lived token, `claude -p --resume` per agent session). Whisper is already running
locally and out of scope — we only consume its transcript output.

---

## Ground rules

- **Red → green → refactor, one behavior at a time.** Write the failing test, watch it
  fail for the right reason, write the minimum code to pass, refactor.
- **`pytest`**, added to `requirements.txt` (`pytest`, `pytest-asyncio`). Tests live in
  `tests/` mirroring `buddy/`.
- **The `claude` subprocess is never hit in unit tests.** The engine adapter
  (`4.5`) is the only module that shells out; everything else takes it as an injected
  dependency and tests against a fake. One opt-in integration test
  (`-m live`, skipped by default) exercises the real CLI.
- **No network in the default suite.** `WebSearch`/`WebFetch` agents are tested through
  recorded fixtures.
- **Every phase ends green** — full suite passes, and the phase's manual smoke check
  in `voice-assistant-plan.md` §8 passes.
- **Guardrail test in every phase from 1 on:** the launcher unsets `ANTHROPIC_API_KEY`
  (risk table, §7) — assert it is absent from the subprocess env.

---

## Phase 0 — Validate (no product code, no TDD)

Spike scripts in `scratch/`, deleted after. Answer, with numbers written back into
`voice-assistant-plan.md`:

1. `claude setup-token` works; token drives `claude -p` non-interactively.
2. `claude -p --output-format stream-json --resume <id>` returns `result`,
   `session_id`, `total_cost_usd`, `num_turns`.
3. Real round-trip latency for a one-line prompt (Haiku, Sonnet).
4. How many turns the Pro allowance sustains before lockout.
5. How Whisper emits text on this machine — **file tail / stdin pipe / HTTP POST**.

**Kill criteria:** round-trip > 20 s, or 50 turns exhausts the allowance → change
backend before writing Phase 1.

Deliverable: a short `docs/phase0-findings.md` and the chosen input-adapter shape.

---

## Phase 1 — Text loop  ✅ complete (2026-08-29)

Typed input → engine adapter → session handling → speech shaper → `say`. One agent
(Companion / Haiku). Proves the core.

**Shipped:** `buddy/engine/claude_cli.py`, `buddy/speech/shaper.py`,
`buddy/speech/segmenter.py`, `buddy/agents/loader.py`, `buddy/agents/sessions.py`,
`buddy/loop/turn.py`, `buddy/loop/build.py`, `buddy/textloop.py`,
`agents/companion.md`, config `VAP_*` block. 41 tests green (`pytest`), 1 `live`
test deselected. Manual smoke: `echo '...' | python -m buddy.textloop` → 16 s wall,
plain spoken sentence, session id persisted to `~/.buddy/state/companion.session`.
**Watch:** `--resume` turns were slow/stalled under heavy local `claude` load during
the smoke — re-verify latency in Phase 2 on an idle machine.

### 1.1 Engine adapter — `buddy/engine/claude_cli.py`

Signature: `send(text, agent, model, session_id) -> EngineResult(reply, session_id, meta)`

Tests (`tests/engine/test_claude_cli.py`) drive a **fake subprocess runner** injected
into the adapter:

| Test | Asserts |
|---|---|
| `test_builds_command_flags` | argv has `-p`, `--output-format stream-json`, `--model`, `--append-system-prompt`, `--allowedTools`, `--max-turns` |
| `test_resume_flag_present_when_session_id_given` | `--resume <id>` included |
| `test_no_resume_flag_on_first_turn` | `session_id=None` → no `--resume` |
| `test_parses_stream_json_result` | `reply` == final `result` text |
| `test_extracts_session_id_from_stream` | returned `session_id` from JSON, not the input |
| `test_meta_carries_cost_turns_duration` | `meta` has `total_cost_usd`, `num_turns`, `duration_ms` |
| `test_strips_anthropic_api_key_from_env` | `ANTHROPIC_API_KEY` not in child env |
| `test_nonzero_exit_raises_EngineError` | stderr surfaced in exception |
| `test_malformed_json_line_is_skipped` | partial/garbage lines don't crash the parser |

Integration (`-m live`, opt-in): `test_live_roundtrip_haiku` — real `claude -p`,
asserts non-empty reply and a usable `session_id`.

### 1.2 Speech shaper — `buddy/speech/shaper.py`

`shape_for_speech(markdown_text) -> str`

| Test | Asserts |
|---|---|
| `test_strips_code_fences` | ` ```py ... ``` ` removed |
| `test_strips_headers_and_bullets` | `#`, `-`, `*` markers gone, text kept |
| `test_strips_inline_markdown` | `**bold**`, `` `code` ``, links → plain words |
| `test_collapses_whitespace` | no double blank lines |
| `test_truncates_to_spoken_turn_limit` | over N sentences → trimmed + "…" (limit in config) |
| `test_plain_text_passthrough` | already-plain input unchanged |

### 1.3 First-sentence streamer — `buddy/speech/segmenter.py`

`first_sentence(stream) -> (sentence, remainder_stream)` so TTS starts before generation
finishes (§4.5).

| Test | Asserts |
|---|---|
| `test_emits_on_first_terminator` | stops at first `. ! ?` |
| `test_handles_abbreviations` | "e.g." / "Dr." not treated as sentence end |
| `test_no_terminator_returns_whole_buffer_on_close` | flush on stream end |

### 1.4 TTS interface — `buddy/tts/speaker.py` (already exists — add a test + seam)

| Test | Asserts |
|---|---|
| `test_speak_invokes_say_with_configured_voice` | fake runner sees `say -v <voice>` |
| `test_speak_is_noop_on_empty_string` | no subprocess for `""` |

### 1.5 Agent spec loader — `buddy/agents/loader.py`

Agent = a markdown file with frontmatter (system prompt, tools, model, style, turn budget)
+ a persisted session id.

| Test | Asserts |
|---|---|
| `test_loads_frontmatter_fields` | model, allowedTools list, max_turns parsed |
| `test_body_is_system_prompt` | markdown body → `append_system_prompt` |
| `test_missing_required_field_raises` | no model → clear error |
| `test_defaults_when_optional_missing` | style/turn budget fall back to config |

### 1.6 Turn orchestrator — `buddy/loop/turn.py`

`run_turn(text) -> spoken_reply`. Wires: engine adapter + shaper + segmenter + speaker +
one agent. Session id persisted to `state/<agent>.session` (§4.6 short-term).

| Test | Asserts |
|---|---|
| `test_happy_path_typed_to_spoken` | fake engine → shaped text handed to fake speaker |
| `test_persists_returned_session_id` | state file updated with new id |
| `test_reuses_persisted_session_id_next_turn` | second call passes `--resume` |
| `test_engine_error_speaks_graceful_message` | EngineError → spoken "something went wrong", not a crash |

### 1.7 CLI entrypoint — `python -m buddy.textloop`

REPL: read stdin line → `run_turn` → print + speak. Manual smoke only; covered by 1.6.

**Phase 1 done when:** typed sentence in, spoken Haiku answer out, session resumes
across turns, `ANTHROPIC_API_KEY` guaranteed unset.

---

## Phase 2 — Voice intake  ✅ complete (2026-08-29)

Wire the Whisper input adapter chosen in Phase 0. From here on the loop is end-to-end
voice; the typed entrypoint stays as a test/debug harness.

**Shipped:** `buddy/input/mic_intake.py` (`MicIntake`), `buddy/loop/voice.py`
(`VoiceLoop`), `buddy/voice_main.py` (`python -m buddy.voice_main` — hotkey +
wake-word → intake → Companion runner), `buddy/web/vap_server.py` (browser
`POST /api/utterance` → `run_turn`, separate app from Milestone-1's server).
10 new tests, 51 total green.

**§2.2 `segment.py` dropped:** it assumed a streaming Whisper. Real STT here is
silence-endpointed batch — one full utterance per capture, no fragments to join.
Barge-in ("queue, don't interrupt") is handled structurally: `VoiceLoop` is one
sequential loop and `MicIntake` buffers triggers during a turn
(`test_turn_exception_does_not_kill_the_loop`, plus intake's queue).

**Smoke:** synthesized speech (`say -o`) → real `whisper-cli` → `MicIntake` →
`VoiceLoop` → `TurnRunner` → engine → "Tokyo is the capital of Japan.", 12.4 s.
Live mic + pynput hotkey + openWakeWord callback are the same thin adapters
Milestone-1 already uses; `intake.trigger` is their callback.

### 2.1 Input adapter — `buddy/input/mic_intake.py`

> **Revised per Phase 0 (`docs/phase0-findings.md` §4):** there is no external
> long-running Whisper process on this machine — file-tail / stdin-pipe / HTTP-from-
> external-Whisper do not apply. Whisper here is `whisper-cli` invoked per-utterance,
> in-process, by `buddy/stt/whisper_transcriber.py`. The adapter is a thin in-process
> wrapper over the existing trigger → `capture` → `transcribe` pipeline.

`utterances() -> Iterator[str]` — wires `buddy/audio/hotkey.py` /
`buddy/audio/wakeword.py` (trigger) → `buddy/audio/capture.record_until_silence` →
`buddy/stt/whisper_transcriber.transcribe`, yielding one string per utterance.

| Test | Asserts |
|---|---|
| `test_trigger_then_capture_then_transcribe_yields_text` | fake trigger fires → fake capture returns samples → fake transcriber string yielded |
| `test_empty_transcription_is_skipped` | `""` from whisper not yielded |
| `test_second_trigger_while_recording_stops_capture_early` | matches existing CLI behaviour |
| `test_transcriber_failure_yields_nothing_not_crash` | whisper non-zero exit → no yield, loop continues |

The browser HTTP intake already exists as FastAPI `POST /api/utterance` in
`buddy/web/server.py` (`transcribe_wav_bytes`) — keep it, feed its output through the
same `run_turn` path. `test_api_utterance_drives_run_turn`.

### 2.2 Debounce / segment — `buddy/input/segment.py`

Whisper may emit a phrase in fragments. `segment(lines, quiet_ms) -> Iterator[utterance]`.

| Test | Asserts |
|---|---|
| `test_joins_fragments_within_window` | two quick lines → one utterance |
| `test_flushes_after_quiet_period` | gap > quiet_ms → emit |
| `test_new_speech_during_tts_is_queued` (barge-in policy: queue, don't interrupt) |

### 2.3 Voice loop — `buddy/loop/voice.py`

`MicIntake.utterances()` → `run_turn()` (reused from 1.6, unchanged).

| Test | Asserts |
|---|---|
| `test_each_utterance_drives_run_turn` | intake yields text → `run_turn` called with it |
| `test_speaker_output_not_fed_back_as_input` | reply never re-enters the intake |
| `test_turn_exception_does_not_kill_the_loop` | one failed turn → loop continues |

**Phase 2 done when:** speaking to Whisper produces a spoken Claude reply, no typing.

---

## Phase 3 — Memory  ✅ complete (2026-08-29)

Markdown store, explicit writes only, keyword retrieval, janitor.

**Shipped:** `buddy/memory/store.py` (`MemoryStore` — append-only bullets to
`facts.md` / `preferences.md` / `projects/<slug>.md` / `research/<slug>.md`,
exact-line dedupe, atomic temp+replace, no delete method), `buddy/memory/search.py`
(`MemorySearch` — keyword-ranked bullet retrieval capped at
`VAP_MEMORY_RETRIEVAL_BUDGET_CHARS`, plus `load(name)` whole-file), extended
`TurnRunner` (optional `memory=`; prepends only retrieved snippets, never the
store), `buddy/memory/janitor.py` (`Janitor` — `purge_sessions`,
`prune_transcripts`, `prune_claude_home`, `run`, all with `dry_run`; TTL 0 = keep
none). Wired: `build_turn_runner` now passes `MemorySearch()`; `textloop` /
`voice_main` call `Janitor().purge_sessions()` on exit. `config.VAP_MEMORY_DIR`,
`VAP_TRANSCRIPT_DIR`, `VAP_TRANSCRIPT_TTL_DAYS`, `VAP_MEMORY_RETRIEVAL_BUDGET_CHARS`
added. 22 new tests, 73 total green.

**Smoke:** `append_fact("… favorite language is Rust")` (no model call) → ask
"what's my favorite language?" → retrieval injects the bullet → Claude answers
"Rust" (10.6 s) → `Janitor().purge_sessions()` removes `companion.session`.

**Not yet:** routing the *spoken* "remember that…" / "what do you know about…"
phrases to these functions — that's the Phase 4 pre-parser (§4.1). Phase 3 wires
retrieval-injection and the exit janitor; writes are exercised directly.

### 3.1 Store — `buddy/memory/store.py`

Layout per §4.6: `memory/facts.md`, `preferences.md`, `projects/<name>.md`,
`research/<topic>.md`.

| Test | Asserts |
|---|---|
| `test_append_fact_no_model_call` | writes a bullet to `facts.md`, engine never invoked |
| `test_write_preference_dedupes_exact_line` | identical line not appended twice |
| `test_project_note_creates_file_on_first_write` | `projects/foo.md` created |
| `test_never_deletes` | no code path removes a line (only append) |
| `test_write_is_atomic` | temp-file + rename, no partial file on crash |

### 3.2 Retrieval — `buddy/memory/search.py`

Keyword search over markdown + explicit file load. No vectors.

| Test | Asserts |
|---|---|
| `test_keyword_match_returns_ranked_snippets` | query terms → lines containing them, ranked by hit count |
| `test_load_named_file_returns_full_text` | "load project foo" → whole file |
| `test_no_match_returns_empty` | unrelated query → `[]` |
| `test_result_bounded_to_token_budget` | never returns more than config cap (§6.5) |

### 3.3 Memory injection into a turn — extend `buddy/loop/turn.py`

| Test | Asserts |
|---|---|
| `test_only_retrieved_snippets_injected` | not the whole store (§6.5) |
| `test_no_retrieval_no_injection` | plain turn unchanged |

### 3.4 Janitor — `buddy/memory/janitor.py`

| Test | Asserts |
|---|---|
| `test_purges_session_state_on_conversation_end` | `state/*.session` removed |
| `test_transcripts_past_ttl_deleted` | 7-day TTL, configurable to 0 |
| `test_prunes_stale_claude_home_sessions` | old `~/.claude` session files removed, recent kept |
| `test_ttl_zero_keeps_nothing` | |
| `test_dry_run_lists_without_deleting` | |

**Phase 3 done when:** "remember that X" persists to markdown with no Claude call;
"what do you know about X" answers from the store; janitor clears state on exit.

---

## Phase 4 — Router and agents (the switchboard)  ✅ complete (2026-08-30)

**Shipped:** `buddy/route/preparser.py` (`preparse` — remember/note/save,
what-do-you-know, switch-to-agent, think-harder, repeat, stop; filler- and
case-insensitive), `buddy/route/state.py` (`VapState`), `buddy/route/router.py`
(`route` — keyword + length + tool-need rules, escalates fast→smart on long
turns, Opus never auto-selected), `buddy/route/allowance.py` (`AllowanceGuard` —
persisted daily cap with midnight reset + identical-question cache),
`buddy/agents/registry.py` (`AgentRegistry` — loads all 5 specs, per-agent
sessions), `buddy/agents/rotation.py` (`SessionRotator` — summarise-and-reseed
every N turns), `buddy/loop/switchboard.py` (`Switchboard` — the full chain),
`buddy/memory/facade.py` (`Memory` — store+search on one handle),
`agents/{researcher,tutor,brainstorm,scribe}.md`. `build_switchboard()` wired
into `textloop` / `voice_main` / `vap_server`. New config: `VAP_LONG_TURN_WORDS`,
`VAP_ROTATE_EVERY_N_TURNS`, `VAP_ROTATION_CARD_MAX_CHARS`, `VAP_DAILY_TURN_CAP`,
`VAP_ALLOWANCE_FILE`. 46 new tests, 119 total green.

**Smoke (headless, fake engine):** "remember that my flight is at 6pm" → *Noted.*
(written, 0 engine calls); "what do you know about my flight" → *my flight is at
6pm* (0 calls); "stop" → silent (0 calls); "switch to brainstorm" → active agent
set (0 calls); routed turns land brainstorm→sonnet, companion→haiku,
researcher→sonnet; "think harder" flips the override; daily cap (3) blocks the
4th real turn before the engine.

**One bug the smoke caught:** the pre-parser needs `append_fact` *and* `search`
on one object → added the `Memory` facade; `MemorySearch` alone would have
crashed on the first "remember that".

### 4.1 Pre-parser — `buddy/route/preparser.py`

`preparse(text) -> PreParseResult | None` (None = forward to Claude). Absorbs ~⅓ of
turns at zero cost (§4.2) — the single largest allowance saver, so it is tested hard.

| Test | Asserts |
|---|---|
| `test_remember_that_routes_to_scribe_write` | "remember that…" → memory append, no Claude |
| `test_save_this_and_note_that_variants` | phrasing variants all caught |
| `test_switch_to_agent` | "switch to researcher" → active agent changed, spoken confirm |
| `test_use_the_big_model` / `test_think_harder` | model override flag set for next turn |
| `test_repeat_that_replays_last_reply` | last spoken reply re-spoken, no Claude |
| `test_stop_and_nevermind` | current turn cancelled |
| `test_what_do_you_know_about_x` | direct memory lookup, no Claude |
| `test_unmatched_returns_None` | ordinary sentence falls through |
| `test_case_and_filler_word_insensitive` | "uh, remember that..." still matches |

### 4.2 Router — `buddy/route/router.py`

`route(text, override) -> RouteDecision(agent, model)`. Rules only: length, keywords,
tool-need. Free and instant. Manual voice override always wins.

| Test | Asserts |
|---|---|
| `test_short_chatty_turn_to_companion_haiku` | |
| `test_research_keywords_to_researcher_sonnet` | "look up", "find out", "research" |
| `test_brainstorm_keywords_to_brainstorm_sonnet` | |
| `test_long_complex_turn_escalates_model` | length threshold → Sonnet |
| `test_tool_need_forces_capable_agent` | "search the web" never lands on a no-tool agent |
| `test_voice_override_beats_rules` | override agent/model respected |
| `test_opus_never_auto_selected` | Opus only on explicit override (Pro limit, §4.3) |
| `test_default_is_companion` | no signal → Companion |

### 4.3 Agent registry — `buddy/agents/registry.py`

Loads all `agents/*.md` (loader from 1.5), tracks each agent's live session id.

| Test | Asserts |
|---|---|
| `test_loads_all_five_agents` | Companion, Researcher, Tutor, Brainstorm, Scribe |
| `test_each_agent_has_independent_session_id` | switching agents doesn't cross sessions |
| `test_unknown_agent_name_raises` | |

### 4.4 Session rotation — `buddy/agents/rotation.py`

Every N turns: summarize to a ~200-token card, close session, reopen seeded with card
(§4.6). Usage control.

| Test | Asserts |
|---|---|
| `test_rotates_after_n_turns` | N configurable |
| `test_summary_card_bounded_to_200_tokens` | |
| `test_new_session_seeded_with_card` | first prompt after rotation includes card text |
| `test_rotation_transparent_to_caller` | `run_turn` return shape unchanged |

### 4.5 Allowance guard — `buddy/route/allowance.py`

Hard daily turn cap (§6.7). On hit: say so, stop. No degraded fallback.

| Test | Asserts |
|---|---|
| `test_counts_only_claude_turns` | pre-parsed turns don't count |
| `test_blocks_at_daily_cap` | cap+1 → spoken "daily limit reached", engine not called |
| `test_counter_resets_at_local_midnight` | |
| `test_identical_question_served_from_cache` | repeat question → cached reply, no turn spent (§6.6) |

### 4.6 Wire into the loop — extend `buddy/loop/turn.py`

Order: `preparse` → (if None) `allowance guard` → `router` → `registry` →
`rotation` → `engine`.

| Test | Asserts |
|---|---|
| `test_preparsed_turn_never_reaches_router_or_engine` | |
| `test_full_route_chain_for_claude_turn` | each stage called once, in order |

**Phase 4 done when:** "switch to brainstorm" / "think harder" / "remember that…" all
work by voice with no Claude call; ordinary turns land on the right agent+model;
daily cap enforced.

---

## Phase 5 — Research mode  ✅ complete (2026-08-30)

Web search with durable written briefs. `buddy/research/brief.py` (`BriefWriter`)
persists the full answer to `memory/research/<slug>.md` as a dated, query-stamped,
append-only section; the switchboard writes a brief only when the router picked
`researcher`, and speaks the shaped summary. Recorded stream fixture at
`tests/fixtures/streams/research.jsonl`; live roundtrip under `-m live`.

### 5.1 Researcher agent config — `agents/researcher.md`

`WebSearch, WebFetch, Write` · Sonnet · spoken summary + written brief. Covered by
1.5 / 4.3 loader tests; add `test_researcher_allowedtools_include_websearch`.

### 5.2 Brief writer — `buddy/research/brief.py`

After a research turn, persist the full answer to `memory/research/<topic>.md`;
speak only the summary.

| Test | Asserts |
|---|---|
| `test_brief_saved_to_research_dir` | slugified topic filename |
| `test_spoken_reply_is_summary_not_full_brief` | shaper limit applied to speech, full text to file |
| `test_brief_has_frontmatter_with_date_and_query` | |
| `test_existing_brief_on_same_topic_is_appended_not_overwritten` | (never auto-delete, §4.6) |

### 5.3 Research turn integration — `tests/research/test_research_turn.py`

Uses a **recorded `claude -p` stream fixture** (captured once from a real run,
committed). No live network in the default suite.

| Test | Asserts |
|---|---|
| `test_recorded_research_stream_produces_summary_and_brief` | |
| `test_max_turns_bounds_tool_loop` | `--max-turns` passed; runaway loop can't drain allowance (§6.2) |
| `test_websearch_only_when_router_picked_researcher` | |

Integration (`-m live`): `test_live_research_roundtrip` — real search, asserts a
non-empty brief file and a short spoken summary.

**Phase 5 done when:** "research X" speaks a short summary and leaves a dated markdown
brief in `memory/research/`, with the tool loop turn-bounded.

---

## Deferred (design seams already tested, not built)

| Item | Seam kept green |
|---|---|
| GPT / Gemini adapters | engine adapter interface `send(text, agent, model, session_id)` — a `FakeEngine` in tests already proves the seam |
| Agent-to-agent delegation | one call per turn is a router invariant (`test_full_route_chain` asserts single engine call) |
| Kokoro-82M TTS | `buddy/tts/speaker.py` one-function interface; swap body, tests unchanged |
| Wake word / VAD | Whisper owns listening; input adapter is line-in only |

---

## Test layout

```
tests/
  conftest.py            # FakeSubprocessRunner, FakeEngine, tmp memory dir, recorded streams
  engine/                # Phase 1
  speech/                # Phase 1
  agents/                # Phase 1, 4
  loop/                  # Phase 1, 2, 4
  input/                 # Phase 2
  memory/                # Phase 3
  route/                 # Phase 4
  research/              # Phase 5
  fixtures/streams/      # committed stream-json recordings
pytest.ini               # markers: live (deselected by default)
```

Run: `pytest` (fast, offline) · `pytest -m live` (hits the real CLI / network).

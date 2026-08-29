# Voice Agent Plane — Build Plan

**Status:** Final, pending Phase 0
**Target:** MacBook Air M1, 8 GB RAM, alongside an already-running local Whisper

---

## 1. Objective

A voice-driven control layer for Claude.

Local Whisper already listens and transcribes. This project picks up that text, turns it
into a real conversation with Claude, routes each turn to an appropriate agent, and
speaks the answer back.

It must stay light enough to sit beside Whisper on 8 GB, and must not burn through the
Pro usage allowance.

---

## 2. Scope

### In
- Transcript intake from existing Whisper
- Per-turn routing to one of several Claude agents
- Model selection (simple vs. complex)
- Short-term conversation context
- Long-term memory, explicit writes only
- Web search when asked
- Spoken output

### Out, for now
| Dropped | Note |
|---|---|
| GPT / Gemini adapters | Interface designed for it; not built |
| Agent-to-agent delegation | Router picks one agent per turn |
| Whisper itself | Already running, out of scope |
| Wake word, VAD | Whisper handles listening |
| Local LLM fallback | Will not fit in 8 GB |
| Vector database | Keyword search over markdown suffices |

---

## 3. Critical context

On Pro you are not paying per token. You are spending a usage allowance **shared with
your browser Claude usage**. A chatty assistant can lock you out of Claude in the browser.

Optimization target: **calls avoided** and **agent turns bounded**.

---

## 4. Design

```
[existing Whisper] --> transcript
        |
   input adapter
        |
   pre-parser  ---- handled locally? --> respond, no Claude call
        |
     router  ---- which agent? which model?
        |
   claude -p --resume <session for that agent>
        |
  speech shaper --> TTS
```

### 4.1 Input adapter

One small module, one of three shapes depending on what Whisper actually does:

- **File tail** — watch an append-only transcript file for new lines
- **Pipe / stdin** — read Whisper's stdout directly
- **HTTP endpoint** — small local listener Whisper POSTs to

Roughly 30 lines whichever it is. Determined in Phase 0.

### 4.2 Pre-parser (local, no Claude call)

Regex and lookup. Absorbs roughly a third of turns at zero cost:

- `remember that…` / `save this` / `note that…`
- `switch to <agent>`
- `use the big model` / `think harder`
- `repeat that`, `stop`, `nevermind`
- `what do you know about X` — direct memory lookup

This is the single largest allowance saver.

### 4.3 Router

Rules first: length, keywords, and whether tools are needed. Free and instant.
Picks the agent and the model. Manual override always available by voice.

Opus is limited on Pro. Haiku and Sonnet are the workhorses.

### 4.4 Agents — session-per-agent switchboard

Each agent is a markdown file (system prompt, tool allowlist, model, style, turn budget)
paired with **its own persistent Claude Code session ID**.

| Agent | Tools | Model | Shape |
|---|---|---|---|
| Companion (default) | none | Haiku | Short, conversational |
| Researcher | WebSearch, WebFetch, Write | Sonnet | Spoken summary + written brief |
| Tutor | Read (memory) | Haiku / Sonnet | Socratic, checks understanding |
| Brainstorm | none | Sonnet | Divergent, punchy |
| Scribe | Read, Write | Haiku | Memory operations only |

Separate sessions mean contexts stay clean and small — the research thread never
pollutes the brainstorm thread, and each stays cheap.

**One Claude call per turn.** No delegation. That is the simplification.

### 4.5 Engine adapter

```
send(text, agent, model, session_id) -> {reply, session_id, meta}
```

Wraps:

```
claude -p
  --output-format stream-json
  --resume <session_id>
  --model <model>
  --append-system-prompt <agent prompt>
  --allowedTools <allowlist>
  --max-turns <n>
```

JSON gives `result`, `session_id`, `total_cost_usd`, `duration_ms`, `num_turns` —
telemetry for free.

Stream the first complete sentence to TTS while the rest generates.

**All CLI-specific parsing lives here.** This file is the escape hatch to another
backend, and the seam where GPT/Gemini adapters would slot in later.

### 4.6 Memory

**Short-term — ephemeral.** The agent's session plus a small state card. Dies with the
conversation. Rotation: every N turns, summarize to a ~200-token card, close the session,
reopen seeded with the card. Usage control, not a memory feature.

**Long-term — explicit only.** Written on direct instruction. Flat markdown:

```
memory/
  facts.md
  preferences.md
  projects/<name>.md
  research/<topic>.md
CLAUDE.md          # auto-loaded by Claude Code each session
```

Simple writes need no model call. Retrieval is keyword search plus explicit file loading.
Never auto-deleted.

**Janitor.** Purge session state on conversation end. Transcripts on a 7-day TTL
(settable to zero). Prune `~/.claude`, which accumulates its own session transcripts
independently.

### 4.7 Speech out

Strip markdown, bullets, headers, code fences. Enforce short spoken turns — Claude Code
writes for a terminal and it reads badly aloud.

TTS behind a one-function interface:
- **v1: macOS `say`** with an enhanced voice. Zero RAM, zero load time, already installed.
- **Later: Kokoro-82M** quantized (~200 MB) if the voice grates. Drop-in swap.

---

## 5. Footprint

| | Idle | Peak |
|---|---|---|
| Python daemon | ~60 MB | ~80 MB |
| `claude -p` (Node, transient) | 0 | ~400 MB |
| `say` | ~0 | ~0 |

~60 MB resident. ~500 MB for a few seconds per turn. Nothing competes with Whisper.

---

## 6. Allowance control

1. Pre-parser handles turns without calling Claude
2. `--max-turns` bounds the agent loop — runaway tool loops drain far more than long chats
3. Session rotation stops resending long transcripts
4. Load only the active agent's prompt
5. Inject only retrieved memory, never the whole store
6. Cache repeated identical questions
7. Hard daily turn cap. On hit, it says so and stops. No degraded fallback.

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| Allowance exhaustion blocks browser Claude | Daily cap; pre-parser |
| `ANTHROPIC_API_KEY` in env silently bills paid API rates | Launcher explicitly unsets it |
| CLI output format changes between versions | Pin version; isolate parsing in adapter |
| Claude Code has bash + filesystem access | Sandbox dir; explicit `--allowedTools`; never `--dangerously-skip-permissions` |
| Coding agent used as a chat backend | API adapter is the graduation path |

Script auth: `claude setup-token` issues a long-lived token for a subscription account.

---

## 8. Phases

**Phase 0 — Validate.** Half a day, before any real code.
- Confirm `claude -p`, `--resume`, `setup-token` work
- Measure real round-trip latency
- Find how many turns the allowance supports
- Determine how Whisper emits text

*Kill criteria: turn over 20 s, or 50 turns exhausts the allowance → change backend.*

**Phase 1 — Text loop.** Typed input, engine adapter, session handling, speech shaper,
`say` output. One agent. Proves the core.

**Phase 2 — Voice.** Wire the Whisper input adapter. End-to-end voice from here on.

**Phase 3 — Memory.** Markdown store, explicit writes, keyword retrieval, janitor.

**Phase 4 — Router and agents.** The switchboard.

**Phase 5 — Research mode.** Web search with durable briefs.

**Deferred:** GPT/Gemini adapters, agent-to-agent delegation, Kokoro, wake word.

---

## 9. Stack

Python 3.11+ · SQLite · markdown · macOS `say` · Claude Code CLI (version-pinned)

No framework. Claude Code already provides the agent loop.

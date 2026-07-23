# Skill: Rigorous Debugging (Universal Heuristics + Race-Condition Playbook)

## Purpose
Use this skill when investigating a reported bug — especially one that's nondeterministic,
hard to reproduce, or where a shallow fix risks masking rather than resolving the cause.
Part 1 applies to any bug. Part 2 applies specifically to race conditions / concurrency bugs;
don't force its concrete techniques (interleavings, shared state) onto bugs where they don't
literally apply — instead, apply the *underlying principle* named in each entry.

---

## PART 1 — Universal Heuristics (apply to any bug)

### 1. Framing
- **Invariant, not symptom.** Before touching code, restate the bug as a violated invariant,
  not a symptom. "Users see stale data" → "invariant: read X must reflect the last committed
  write to X." A symptom has many causes; a violated invariant has an enumerable set of writers
  or code paths that could break it.
- **Distrust the label.** Treat the reporter's diagnosis ("it's a race condition," "it's a memory
  leak," "it's caching") as hypothesis #1, not ground truth. Ask: is this truly what's labeled, or
  is it deterministic/explicable under conditions not yet identified (specific input, specific
  environment, specific timing)?
- **The "what changed" bisect.** Before reading code, check whether the bug has a start time.
  Correlate with deploys, config changes, traffic/load changes, dependency bumps. A bug that
  "suddenly appeared" often means the failure mode existed all along and something recently
  widened its trigger conditions.
- **Reproduce-or-model rule.** Don't edit code until you have one of: a reproduction, or a
  written causal model of the failure (state precisely what sequence of events causes the bad
  outcome). Lacking both means the next step is evidence-gathering, not fixing.

### 2. Decomposition
- **Decompose by the unit whose behavior you can fully characterize** — not by file or module.
  The right unit is whichever piece of state, logic, or data flow lets you (a) state its invariant
  in one sentence and (b) exhaustively enumerate everything that can affect it. If you can't
  enumerate the influences, the unit is too large or under-instrumented — narrow it or add
  visibility first.
- **Keep tightly-coupled dependencies together.** Anything connected by an ordering, causal, or
  correctness constraint must stay in the same analysis unit. Splitting across such a constraint
  is how each half looks correct in isolation while the whole is broken.

### 3. Trade-off navigation
- **Instrument vs. reason.** If the bug reproduces frequently enough to observe with added
  logging/instrumentation in reasonable time, gather evidence rather than theorize. If it's too
  rare for that to be practical, reason from existing evidence and construct the failure
  synthetically. The deciding factor is *cost of one reproduction cycle* — nothing else.
- **Fix the cause vs. make it harmless.** Prefer changes that eliminate an entire *class* of
  failure (e.g., idempotency, validation, defensive defaults) over changes that patch one specific
  failure path, when the class-level fix is comparably cheap. A narrow fix addresses one instance;
  it often leaves the same root cause free to resurface elsewhere.
- **Mitigate now vs. root-fix now.** If there's an active incident, prioritize shipping something
  that reduces blast radius — *unless* the mitigation would destroy evidence needed to find the
  root cause. Rule: capture state (logs, snapshots, dumps) before any mitigation that changes the
  system's behavior or timing.

### 4. Failure anticipation
- **Check what the fix might break.** Before committing a fix, explicitly check it against
  everything adjacent that could interact badly with it (other consumers of the same resource,
  other code paths, cleanup on failure/crash). Fixes are a common source of *new* failure modes.
- **Check for a "quiet break" mode.** Ask: could this fix reduce the *frequency* of the bug
  without eliminating the *cause*? If a fix only lowers the odds of failure rather than making it
  provably impossible, treat the bug as unresolved until you can explain why it's now impossible,
  not just rarer.
- **Enumerate every source, not just the known ones.** Before concluding you've found "the"
  cause(s), explicitly search for other overlooked contributors (background jobs, other services,
  manual/admin processes, edge-case inputs). Fixes scoped only to the causes you noticed first are
  the standard way a "fixed" bug reopens later.

### 5. Verification
- **Verify by amplifying the failure condition, not by running more iterations.** The strongest
  cheap check is deliberately making the suspected failure condition more likely or forcing it
  outright, then confirming the bug can no longer occur under that forcing. Passing more normal-
  case runs is weak evidence; passing under deliberately adverse conditions is strong evidence.
- **The narration test for "done."** You're done when you can narrate the exact sequence of events
  that caused the failure, and explain concretely why your fix makes that sequence *impossible* —
  not merely unlikely. "It hasn't recurred since the deploy" does not meet this bar on its own.
- **Failing-check-first rule.** A fix isn't verified unless there's a check (automated test, or at
  minimum a manual reproduction script) that failed before the change and passes after. A fix
  without a previously-failing check is indistinguishable from coincidence.

### 6. When to stop and ask
- **The load-bearing-and-cheap rule.** Ask the user when an assumption is both (a) load-bearing —
  the whole approach changes if it's wrong — and (b) cheaper for them to confirm than for you to
  verify independently. Example: "Is this single-instance or multi-instance?" often meets both
  conditions and costs the user seconds to answer.
- **Proceed-and-state rule.** When an assumption is reversible, proceed on it but state it
  explicitly at the point of use, so it's visible and correctable later. Silent, unstated
  assumptions are the actual failure mode — not assumptions themselves.
- **One-way-door override.** Never proceed on an unconfirmed assumption for anything touching
  data integrity or irreversible actions (deletes, backfills, schema changes, production config
  changes bundled into the fix). The confidence bar for these rises to "confirmed," not "probable."

---

## PART 2 — Race-Condition-Specific Playbook

These are the Part 1 principles made concrete for nondeterministic concurrency bugs. Use these
techniques literally when the bug is a genuine race condition; for other bug types, re-derive
the equivalent concrete technique from the matching Part 1 principle instead of reusing these verbatim.

- **Decomposition unit = one piece of mutable state + every code path that touches it.** This is
  the concrete form of "decompose by the unit you can characterize" for concurrency bugs.
- **Second-race check.** Before committing a concurrency fix: check the new lock/ordering against
  every other lock the same code paths can hold (deadlock risk), and check what happens if a
  process dies mid-critical-section (leaked locks). This is the concrete form of "check what the
  fix might break."
- **Window-shrink detection.** The most common quiet-break mode for concurrency fixes: the fix
  narrows the race window instead of closing it, so failure rate drops sharply but the bug is
  still possible at higher load/scale. This is the concrete form of "check for a quiet break mode."
- **Enumerate the third writer.** Before finalizing a fix based on two known writers of shared
  state, explicitly search for a third (cron jobs, other services, admin scripts, migrations).
  This is the concrete form of "enumerate every source, not just the known ones."
- **Force the interleaving.** Inject a deliberate delay/breakpoint to force the suspected bad
  ordering; confirm the bug reproduces under that forcing before the fix, and cannot occur under
  the same forcing after the fix. This is the concrete form of "verify by amplifying the failure
  condition."

---

## Notes for extension
When encountering a new bug class (e.g., memory leaks, flaky UI tests, cost/billing overruns),
add a new "Part N" playbook following the same pattern: for each Part 1 principle, state the
concrete technique that instantiates it for that bug class, rather than writing a new set of
heuristics from scratch.
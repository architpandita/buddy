# Skill: Rigorous Technical Reasoning (Shared Preamble + Task Playbooks)

## Purpose
Use this skill for technical tasks where a shallow attempt looks fine but is actually wrong:
debugging, system/data-model design, and (future) other task classes. The skill has two layers:

- **Preamble** — principles that hold regardless of task type. Apply these always.
- **Task Playbooks** — for each task class, the *concrete instantiation* of each preamble
  principle, plus techniques specific to that task class. When starting a new task class not
  yet covered here, don't invent new principles — instantiate the preamble's principles for
  that class the way each playbook below does, then add what's genuinely new.

The preamble/playbook split exists because several early "universal" heuristics turned out to
be one task's heuristics wearing generic language. Confirmed cross-task (from debugging +
design so far): invariant-first framing, load-bearing-and-cheap asking, proceed-and-state,
one-way-door override. Everything else below is a per-task instantiation — check new task types
against this list before assuming a heuristic transfers unchanged.

---

## PREAMBLE — Cross-task principles

### Invariant-first framing
Before doing anything else, state the 1–3 invariants the system must hold — found (debugging)
or chosen (design). Everything else is downstream of these; work that doesn't serve an invariant
is feature work, not correctness work.
- *Debugging:* the invariant was violated — find where and why.
- *Design:* the invariant doesn't exist yet — choose it deliberately, and let it shape the model
  before any entities/nouns are drawn.

### Load-bearing-and-cheap asking
Ask the user a question when the answer (a) forks the approach — different answers lead to
structurally different work — and (b) is cheap for them to confirm relative to the cost of
guessing wrong. Don't ask about anything that only affects sizing/detail, not shape.
- *Debugging:* "single-instance or multi-instance?" — forks the whole causal analysis.
- *Design:* "can a booking span multiple resources?" — forks the schema shape.

### Proceed-and-state (with the cliff)
For non-forking or reversible assumptions, don't stall — state the assumption explicitly at the
point of use, including *what breaks if it's wrong* ("assuming single-region; multi-region later
means the conflict check needs a coordination layer"). Content without the cliff doesn't let the
user judge whether the assumption is safe for their actual situation.

### One-way-door override
Regardless of task type, anything irreversible or hard-to-undo gets confirmed, never assumed.
- *Debugging:* backfills, deletes, schema changes bundled into a fix.
- *Design:* any schema decision that fails the migration-cost test (see Design Playbook §2).
The confidence bar for these rises to "confirmed," not "probable," no matter how cheap the
question would otherwise seem to skip.

---

## TASK PLAYBOOK A — Debugging

### A1. Framing
- **Distrust the label.** Treat the reporter's diagnosis as hypothesis #1, not fact. Ask whether
  the failure is truly what's labeled, or deterministic under conditions not yet identified.
- **The "what changed" bisect.** Check for a start time; correlate with deploys, config, traffic,
  dependency changes. A "sudden" bug often means a long-standing trigger condition got wider.
- **Reproduce-or-model rule.** Don't edit code without a reproduction or a written causal model
  of the failure. Lacking both means the next step is evidence-gathering, not fixing.

### A2. Decomposition
- Decompose by the unit whose behavior you can fully characterize (state its invariant in one
  sentence; enumerate everything that can affect it) — not by file or module.
- Keep anything connected by an ordering/causal/correctness constraint in the same unit; splitting
  across such a constraint is how each half looks fine while the whole is broken.

### A3. Trade-off navigation
- **Instrument vs. reason:** decided by cost of one reproduction cycle — instrument if cheap,
  reason/force synthetically if rare.
- **Fix the cause vs. patch the instance:** prefer class-level fixes (idempotency, validation)
  over narrow patches when comparably cheap — narrow fixes leave the root cause free to resurface.
- **Mitigate now vs. root-fix now:** ship blast-radius reduction first during active incidents,
  *unless* it would destroy evidence — capture state before any timing-changing mitigation.

### A4. Failure anticipation
- Check the fix against everything adjacent it could interact badly with (other consumers,
  cleanup-on-crash, other code paths).
- **Quiet-break check (debugging instance): window-shrink.** A fix may reduce failure *frequency*
  without eliminating the *cause* — treat as unresolved until you can explain why it's now
  impossible, not just rarer.
- Enumerate every source of the failure, not just the ones noticed first (other services, cron
  jobs, admin scripts, edge-case inputs).

### A5. Verification
- **Cheapest strong check (debugging instance): force the failure condition.** Deliberately
  amplify or force the suspected trigger rather than running more normal-case iterations.
- **Narration test:** done = you can narrate the exact sequence that caused the failure and why
  the fix makes it *impossible*, not unlikely.
- **Failing-check-first rule:** no fix is verified without a check that failed before and passes
  after.

### A6. Race-condition-specific techniques (concrete instances of A1–A5 for concurrency bugs)
- Decomposition unit = one piece of mutable state + every code path touching it.
- **Second-race check:** before committing a fix, check the new lock/ordering against every other
  lock the same paths can hold, and what happens if a process dies mid-critical-section.
- **Window-shrink** is the literal failure mode here (see A4).
- **Enumerate the third writer** before finalizing a fix based on two known writers.
- **Force the interleaving:** inject a delay/breakpoint to force the bad ordering; confirm bug
  reproduces before the fix and cannot occur after, under the same forcing.

---

## TASK PLAYBOOK B — Greenfield Design

### B1. Framing
- Write down the 1–3 structural invariants first (see Preamble). Everything else follows from these.
- **Queries before nouns.** Write the top 5 queries the system must answer, with rough frequency/
  latency needs, before drawing any schema. The highest-frequency query shapes the model; the rest
  adapt to it. Starting from entity nouns is a framing error.
- **Under-specification triage — three buckets:**
  - **Ask** if the answer forks the architecture (see Preamble: load-bearing-and-cheap).
  - **Design flat, note the cliff** if the answer only changes sizing — design for the modest
    case and state explicitly where it breaks.
  - **Take the conservative default silently** if all plausible answers are handled the same way.
  - Anti-pattern: "design for flexibility" as a blanket answer. Flexibility is a targeted
    purchase at identified fork points, not a default stance.

### B2. Scoping
- **Migration-cost test** (the design-task equivalent of "atomic unit"): what does it cost to
  change this decision once there's production data?
  - *Day-one right:* anything whose change needs a semantic (not mechanical) migration — primary
    keys, core representation choices, tenancy boundaries.
  - *Deferrable:* anything additive (new columns, new types, reporting tables).
- **Walking-skeleton rule:** v1 = the thinnest slice that exercises every invariant end-to-end,
  not the smallest feature set by stakeholder ranking.
- **Build the seam, not the mechanism, on hinted-at future variation.** One concrete
  implementation behind a well-named interface point; generalize on the second concrete case,
  never the first.

### B3. Trade-off navigation
- **Enforce in schema vs. application:** schema/constraint-level if violation is unrepairable or
  embarrassing; application-level if cheap to detect and fix later.
- **Precompute vs. compute-on-read:** decided by (read/write ratio) × (consistency tolerance of
  the read). Split the display path (can be eventually consistent) from the commit/enforcement
  path (must be strict) rather than sharing one mechanism for both.
- **Ranges vs. discrete slots** (or the domain-general version: continuous vs. quantized
  representation): quantized if the domain naturally quantizes and every legal case fits fixed
  units; continuous the moment one requirement breaks quantization. Don't hybridize — a hybrid
  inherits both models' failure modes.
- **Build vs. reuse:** reuse the *primitive* (standardized, solved sub-problems), build the
  *policy* (your actual business rules). Nothing off-the-shelf fits your policy; nothing you
  build will out-cook a solved standard.

### B4. Failure anticipation
- **Concurrent-writers drill on paper:** for each invariant, imagine two simultaneous operations
  that individually satisfy it — trace whether the design rejects one. Check-then-act designs
  fail this; constraint-enforced designs pass. (This is A5's "force the interleaving," applied
  before code exists.)
- **Quiet-break check (design instance): expressiveness gaps.** Designs break less from load than
  from the model being unable to represent a real case. Catch early with a **weird-case ledger**:
  write 10 concrete awkward-but-legal scenarios as literal data before finalizing; each must map
  to one unambiguous row/state without a special-case flag.
- **Deletion-and-history check:** decide deliberately (not by default) whether records are mutable
  or append-only with history — this is a migration-cost-test item, decide it now.
- **Load the hot cell, not the average.** Estimate the worst single contended unit (busiest
  resource/tenant/hour), not the system-wide average — serialization points contend locally.

### B5. Verification
- **Cheapest strong check (design instance): scenario walkthrough with literal data.** Hand-
  execute 5 concrete end-to-end stories against the schema — actual rows, actual queries, actual
  constraint checks. Prose review hides ambiguity that literal data doesn't.
- **Query-plan sanity** on the #1 query from framing: name the specific index, don't say "we'll
  add one."
- **Narration test, design edition:** done = you can name each invariant's specific enforcing
  mechanism and show the weird-case ledger passing. "The schema supports it" without naming the
  mechanism is not done.
- **Pre-mortem one-liner:** complete "six months in, this design causes pain because ___" three
  times. All three deferrable → ship. Any one a migration-cost item → stop and address it now.

### B6. When to stop and ask
- Same Preamble rule, reversibility term rewired: ask when an assumption forks the architecture
  **and** fails the migration-cost test — because in design, wrong assumptions get built, not
  just wasted-time-costed.
- **Question budget:** at most 2–3 questions, only architecture-forking ones, asked *alongside* a
  provisional design built on stated (with-cliff) defaults — not instead of one. A design with
  flagged forks gives the user something to react to; bare questions give them homework.

---

## Notes for extension
When adding a new task-class playbook (e.g., API design, performance optimization, code review):
1. Instantiate each Preamble principle for the new task class explicitly — don't restate it, name
   the concrete form it takes (as A1–A6 and B1–B6 do).
2. Identify that task class's specific **quiet-break mode** (how a fix/design looks right but
   silently isn't) and **cheapest strong check** (the verification technique unique to the task
   shape) — these have been the most task-specific parts across debugging and design, and are
   worth eliciting deliberately rather than assumed to transfer.
3. After 3+ playbooks exist, re-audit the Preamble: anything appearing in all playbooks unchanged
   is confirmed universal; anything that had to bend gets moved into the relevant playbook instead.
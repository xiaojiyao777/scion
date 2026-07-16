# Scion v0.4 Direct-Runtime Research Task

*Branch: `v0.4-dev`*
*Last updated: 2026-07-16*

This is the active task source. Read it with
`scion/docs/status/current-state.md`; use
`scion/design/scion-architecture-v3.md` as the architecture tie-breaker.
Chronology and large evidence tables belong in focused experiment reports.

## Objective

Close v0.4 only when the small direct V3 runtime demonstrates useful,
maintainable research behavior on both warehouse and CVRP:

```text
complete problem/current-source context
  -> one durable Hypothesis call
  -> structural Hypothesis Contract
  -> one durable Code call bound to approved H and complete SourceLedger
  -> structural Patch Contract
  -> Workspace -> Verification -> Protocol -> Safe Features -> Decision
```

Framework tests alone do not close v0.4. CVRP still needs an independently
validated useful candidate and a later clean multi-round run showing that the
agent can use evidence without accumulating framework noise.

## Non-Negotiable Boundaries

- V3 owns the architecture; the v0.4 direct-runtime addendum narrows obsolete
  retry/budget/context examples.
- LLM output is tainted. It cannot write Protocol verdicts, Decision inputs,
  scheduler state, or promotion state.
- CVRP/warehouse algorithm semantics stay problem-owned. Generic core owns
  lifecycle, contracts, lineage, replay identity, and safe data movement.
- Contract checks structure and approved-H/source binding; Verification checks
  executable correctness; Protocol owns comparative science; Decision maps the
  trusted verdict and hard safety flags deterministically.
- Normal candidates make exactly one H and one C call. Provider SDK retry is
  zero. Invalid H/C terminates that durable attempt.
- Do not add a Scion prompt/session/tool/file/item/token budget, content cap,
  top-k selection, truncation, automatic retry, semantic stop counter, or a
  heavier gate. The 30-second solver limit is a scientific subprocess limit.
- Do not force a research surface/action/target in open controls.
- Formal fresh roots use a clean exact pushed commit and one guarded wrapper
  launch. Diagnostic eval-only continuations use a distinct copied root and
  are never presented as fresh formal roots.
- Poll experiments observationally at low frequency, normally every three
  minutes. Polling must never trigger another provider attempt.
- Preserve user-owned `scion/docs/v0.4-measurement-readiness.md` and unrelated
  untracked documents.

## Accepted Runtime Contract

- One immutable `ProposalContextSnapshot` owns each provider request.
- H receives current problem facts, complete verified current source, and one
  canonical lossless record per visible screening observation.
- C receives one approved H and one complete SourceLedger. Multi-file and
  ordered same-file `exact_replace` edits retain source owner, provenance, and
  digest; stale or ambiguous composition fails closed.
- A single active branch is the v0.4 default. `continue_explore` reuses its
  verified cumulative workspace; `queue_validate` re-evaluates the exact
  candidate without another H/C call.
- Proposal-only mechanism evidence is excluded from DecisionFeatures and
  gates. It may inform the next H but cannot manufacture causal certainty.
- Promotion remains atomic and requires complete formal evidence.

## Current Evidence

Warehouse is resolved: the direct loop found a screening-positive cumulative
candidate, expanded it without a provider call, then correctly abandoned it on
the locked validation split. This proves the eval-only escalation path and
negative lifecycle integrity; it is not a retained algorithm.

CVRP R4 proved two substantive evaluated algorithm rounds but both were
negative. R5 exposed an overly narrow one-change-object-per-file instruction;
the serial same-file typed-edit repair is pushed at `56ba4851` and R6 exercised
it live.

R6 is complete and valid:

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-causal-feedback-r6-2r-gpt56sol-20260715T153632Z-claw`;
- exactly `2H/2C`, four successful attempts, retry=`0`;
- `64/64` valid screening pairs, no candidate/champion/infra failure;
- R1 route-cap-aware regret repair: case `0/4/4`, pair `9/16/7`, median
  `-3.25`, CI `[-9.25,0]`, `continue_explore`;
- H2 received the complete single R1 record plus verified current source and
  changed direction from repair tuning to local-search swap-star;
- cumulative R1+R2 candidate: case `5/1/2`, pair `20/11/1`, median `+3.5`,
  CI `[-11,12]`, `queue_validate`;
- exact branch code hash:
  `0d9c2ce5cd62dd88c4666fcfed7a6ef14001a07caf171a6af346c74c4706535a`;
- branch state: `ready_validate`; champion v1 unchanged.

The R2 signal was uncertain and heterogeneous. X lost `-55`; ALNS iterations
fell `1857 -> 789`; round-2 comparative runtime was unavailable because all
champion results were cached. The exact same candidate first completed a
fresh, disjoint eight-case validation in root
`v04-cvrp-r6-r2-exact-validation-1r-gpt56sol-20260715T180743Z-claw`:

- no new H/C/provider/trace activity;
- `32/32` valid pairs with fully fresh champion runtime;
- case `6/1/1`, pair `25/5/2`, median `+7.75`, CI `[0,77]`;
- runtime median ratio `1.0111` with 32 high-confidence pairs;
- `expand_validation / VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN`;
- branch `validating_expand`, candidate hash unchanged, champion v1 unchanged.

The repaired copied-state continuation then completed the preregistered
12-case expanded validation in root
`v04-cvrp-r6-r2-expanded-validation-1r-gpt56sol-20260715T201008Z-claw`:

- no new H/C/provider/trace or formal-candidate activity;
- `48/48` valid pairs with fully fresh champion runtime;
- case `8/2/2`, pair `33/13/2`, median `+6.5`, CI `[-7.25,47.75]`;
- runtime median ratio `1.0118`, median delta `+367.5 ms`, and `35/48`
  slower candidate pairs;
- `queue_frozen / VALIDATION_EXPAND_EXHAUSTED_MARGINAL_PASS`;
- branch `ready_frozen`, expand count one, candidate hash unchanged, champion
  v1 unchanged.

This is a marginal pass to an independent frozen holdout, not validation
certainty or promotion. Gains are concentrated on X-n120/X-n157/X-n190;
F-n72 and tai150a regress, tai75d is seed-sensitive, and the CI crosses zero.
Initial VNS time rises `+164.8%` while ALNS iterations fall `44.9%` relative to
champion. Formal mechanism evidence is empty, so do not causally attribute the
result to swap-star.

The exact candidate then completed its independent frozen continuation in root
`v04-cvrp-r6-r2-frozen-evaluation-1r-gpt56sol-20260715T213106Z-claw`:

- no new H/C/provider/trace or formal-candidate activity;
- deterministic evenly spaced frozen cases X-n139, X-n204, X-n251, X-n327,
  X-n401, X-n573, X-n641, and X-n1001 with seeds `[61,67,89]`;
- `24` attempted, `22` valid, and two invalid comparisons involving champion
  timeouts;
- on valid evidence, case `5/0/3`, pair `13/1/8`, median `+81.5`, CI
  `[0,337]`;
- Protocol `fail / INCOMPLETE_EVIDENCE + CHAMPION_RUNTIME_FAILURE` and
  Decision `abandon / INCOMPLETE_RUNTIME_EVIDENCE`;
- candidate hash and champion v1 unchanged; no promotion dossier.

This is promising partial evidence, not a frozen pass. The 120-second tier
systematically ran past its scientific limit, and the two failed pairs exposed
a shared baseline deadline defect. Do not rerun, extend, or reinterpret this
terminal root.

The fresh four-round R7 root
`v04-cvrp-direct-longitudinal-r7-4r-gpt56sol-20260715T232619Z-claw`
then completed only its first screening matrix before a core persistence
exception stopped the campaign:

- exactly `1H/1C`, no provider retry or replacement;
- substantive destroy-repair pair-weight hypothesis and implementation;
- `32/32` attempted, `22` valid, `10` candidate failures, and zero champion
  failures;
- the generated patch left four deleted marginal-weight names in three
  rejection branches, causing ten `NameError` fallbacks;
- Protocol correctly failed screening and Decision correctly abandoned for
  `CANDIDATE_RUNTIME_FAILURE`;
- canonical feedback then incorrectly asserted
  `valid_pairs == len(pair_feedback)` even though candidate-only failures are
  intentionally retained as synthetic screening losses;
- the correct R7 accounting was `22 valid + 10 candidate failures = 32 pair
  feedback rows`;
- wrapper exit `1`, postrun classification `valid_but_incomplete`, zero
  effective completed rounds, and no promotion.

R7 is a terminal diagnostic root, not a four-round scientific result. Its
common deadline behavior was healthy: formal 30/45-second rows produced no
champion timeout or watchdog failure. Do not resume or relaunch it.

Fresh four-round R8 is terminal and read-only:

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r8-4r-gpt56sol-20260716T002051Z-claw`;
- clean detached runtime:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-4a42ee3f`;
- exact commit: `4a42ee3f98bed4cde90e4a9be54fe79aefe5585d`;
- requested/effective typed rounds: `4/1`;
- exactly `2H/2C`, four successful durable calls, no retry, replacement, or
  output ceiling; the transport ceiling is null and there is no truncation
  evidence;
- R1 implemented route-cap-aware regret repair with a bounded depth-2 ejection
  chain and completed `32/32` valid screening pairs;
- R1 case `1/1/6`, pair `4/8/20`, median `0`, CI `[-0.5,0]`, Protocol
  `SCREENING_FAIL_WIN_RATE`, Decision `continue_explore`;
- H2 received R1 objective, case, pair, and mechanism observations plus the
  Protocol failure, explicitly used that evidence, and moved to a materially
  different cross-exchange local-search mechanism; the old projection omitted
  outer Decision `continue_explore`, so this is partial longitudinal carryover,
  not complete feedback fidelity;
- C2 registered `_cross_exchange` without defining it and deleted the
  `_or_opt_1` header; V1b correctly returned
  `research_rejected / V1b_undefined_names` before Protocol;
- wrapper/postrun exits are zero, overall status is
  `valid_but_incomplete / incomplete`, and champion v1 is unchanged.

R8 exposed a P0 resume-safety defect: after the correct rejection, SQLite
retained the clean R1 hash, the final card retained failed-C2 as current, and
the physical durable workspace still contained failed C2. Never resume R8.
Candidate patches must be isolated until Verification succeeds, rejected
staging must be deleted and the clean identity persisted, and reopen must
recompute and compare physical/current/last-clean hashes. R8 also exposed a P1
legacy report false negative for typed `verification_fail`; a corrected
read-only query reports two gate outcomes, one V1b failure, and intercept rate
`0.5`.

## Current Framework Repair

R6 and its exact validation exposed four evidence-integrity problems:

1. Its v2 R2 formal artifact binds a champion base and cumulative code hash to
   only the incremental `local_search.py` patch. Champion plus that artifact
   produces `0cc217...`, not the live cumulative `0d9c2ce...` workspace.
2. Canonical feedback injected legacy `unknown` fields into a problem-owned
   evidence envelope, omitted Protocol outcome/scope, and allowed display
   schema evolution to duplicate a durable observation.
3. Cross-stage branch evidence retained screening facts while replacing their
   reason codes with validation reasons, producing a mixed resume/status card.
4. The launcher treated the formal-candidate index as a single-hop terminal
   artifact. A second resume copied candidate metadata but lost the inherited
   ownership index held in the source root's outer resume snapshot.

The current repair:

- records v3 `patch` as the current proposal and
  `replay_materialization` as the complete champion-to-current closure;
- separates proposal/cumulative digests and file attribution;
- validates base identity, closure content, candidate identity, and final code
  hash in recorder, fixed replay, and postrun materialization;
- preserves v1/v2 reader compatibility;
- keeps problem-owned envelopes typed and marks CVRP ALNS diagnostics as
  hypothesis attribution `unbound`;
- labels cumulative-vs-champion and case/pair aggregation scopes, includes
  Protocol outcome, removes cross-metric pair median, and reconciles formal
  pair counts with retained pair rows fail-closed;
- uses stable natural identity to upgrade an old durable row without duplicate
  H feedback;
- atomically replaces current protocol stage/stats/runtime/ref/reasons, exposes
  `latest_protocol_evidence`, and retains one compact latest record per stage;
- keeps full experiment history in append-only events/raw metrics instead of
  duplicating it into provider context;
- covers validation/frozen continue, abandon, and frozen promotion paths, and
  allows Protocol `continue` to re-enter exploration from validation/frozen;
- validates and flattens inherited plus source-live formal candidate indexes
  into one immutable union in the new root, while leaving the new live index
  empty for current-invocation accounting;
- fails preparation on noncanonical refs, row/metadata identity conflicts,
  missing or unindexed metadata, snapshot tampering, or mismatched ownership.

The frozen audit added two narrower repairs before another generative run:

- the problem-owned CVRP baseline now exposes the tighter of the runner
  deadline and its existing `BASELINE_TIME_FRACTION=0.80` absolute search
  deadline, and every expensive VNS neighborhood polls that deadline inside
  its nested candidate scan before returning the current valid incumbent;
- validation/frozen champion/shared evidence-acquisition failures remain
  Protocol failures but bypass Decision into durable `BLOCKED_INFRA`, preserve
  the raw partial-evidence ref, and require the existing explicit operator
  resume; the pre-block stage is persisted across process restart;
- two independent timeout results are exposed as `dual_runtime_failure`
  instead of the over-broad `shared_process_failure`; candidate-only runtime
  failure still hard-abandons.

R7 added two more narrow correctness repairs without increasing solver work or
governance weight:

- Verification now performs a stdlib `symtable` unresolved-name scan after
  syntax and before interface checks over complete primary and additional
  candidate modules. It rejects the exact four stale R7 names in milliseconds
  without executing candidate code or scheduling a retry;
- canonical screening history now reconciles pair feedback against
  `valid_pairs + candidate_failed_pairs`, while retaining exact W/L/T checks
  and excluding champion/shared/missing-output invalid rows from feedback.

The R8 repair slice now isolates each unverified patch in a candidate staging
tree and records a typed verified-candidate ownership artifact before a
two-phase `prepared -> committed` promotion. A promotion journal retains the
old durable workspace until the typed commit and branch state are committed.
On reopen, a persisted base identity rolls the physical promotion back; a
persisted candidate identity plus a valid typed commit completes promotion;
all conflicting identity combinations fail closed. A rolled-back journal keeps
the exact hypothesis owner until that uncommitted hypothesis is durably
terminalized, so a HypothesisStore failure remains recoverable on the next
reopen. Rejected staging is discarded even if hypothesis-status persistence
fails. A committed candidate
whose formal evaluation was interrupted is restored only for an explicit
screening eval-only continuation: the exact active-H candidate is evaluated
with `0H/0C`, one Protocol/Decision, and then marked completed. The active-H
typed commit takes precedence over old formal artifacts; strict legacy fallback
is allowed only when no typed marker exists.

Stale reconciliation now uses the same boundary instead of replacing the
durable workspace first: it rebases from the newly locked champion into an
isolated staging tree, records a content-addressed `commit_kind=reconcile`
artifact, promotes through the journal, and recovers an interrupted formal
screening as `action=reconcile` with `0H/0C`. Contract or Verification rejection
is pre-Protocol, keeps the old durable/hash/marker intact, and emits the typed
gate event plus StepRecord/check provenance. Typed commits bind the canonical H
content, lineage, base, patch, code, and executable identities; promotion
recovery verifies backup/candidate/durable trees before any destructive action.

The Decision boundary now writes a typed SQLite completion intent. Pending
screening Decisions, plus any-stage `CONTINUE_EXPLORE`,
`VALIDATION_REPAIR_REQUIRED`, or `ABANDON`, atomically commit the post-Decision
Branch, H status, completed marker, and typed decision fact. Startup converges
an unfinished intent before branch restore and makes no provider or Protocol
call. ABANDON cleanup is post-commit and uses a deterministic archive receipt,
so archive, partial-delete, and restart remain idempotent and identity checked.
It also:

- projects typed Contract/Verification failures through legacy reports and
  exposes stable `failed_check`, `failure_code`, and `failure_detail` without
  synthesizing a pre-Decision `decision_reason`; Contract opportunities include
  all gate outcomes, while Verification opportunities exclude Contract-failed
  attempts;
- exposes the outer Decision in canonical next-H screening history;
- labels CVRP `unbound` mechanism telemetry as association-only;
- tells destroy/repair proposals to propagate and poll the existing monotonic
  deadline context inside nested searches.

These are lifecycle, reporting, and generation-guidance repairs. They add no
research gate, provider retry, semantic budget, truncation, or solver work.

The final affected transaction/report/guidance review set passes `198`; the
standard Scion suite passes `2034` with `1` skipped in `462.74s`. `compileall` and
`git diff --check` pass. Boundary coverage includes same-file cross-round edits,
create/delete, full reversion to champion, activation files, absent and
partially missing indexes, inherited resume indexes,
closure/content/base/final-hash tampering, promotion and Decision crash
recovery, exact pending-evaluation ownership, stale reconciliation, legacy
terminal-H recovery, and partial ABANDON cleanup.

Nonblocking P2 debt remains explicit: a process death after a local Protocol
returns but before intent preparation, or during an ordinary nonterminal
retained transition, may replay that Protocol with at-least-once semantics;
the typed recovery fact and canonical branch history do not reconstruct every
rich experiment/DecisionFeatures projection after that crash. Target-first
source projection remains an architectural simplification, and strict postrun
acceptance still lacks a cross-artifact count comparison. None is grounds to
add a retry, weaken source completeness/Verification/Protocol, or block R9.

A real X-n1001 seed-61 compliance probe with a 30-second scientific limit now
returns a feasible 43-route incumbent with exit `0` in `23.78s`; construction
used `20.745s`, initial VNS used `2.522s`, and the solver reported
`stop_reason=time_limit`.

## Execution Queue

1. Commit and push the independently reviewed R8 transactional workspace,
   Decision completion, typed-failure reporting, feedback-semantics, and
   deadline-guidance repair, staging only the intended files.
2. Launch fresh four-round R9 from that exact clean pushed commit with no
   resume source. Audit H/C accounting, physical/hash/lineage continuity,
   Protocol/Decision transitions, and deadline compliance.
3. Analyze every durable R9 observation and repair only evidence-backed
   framework defects; do not convert a rejected hypothesis into a retry.
4. Expand to a separate clean eight-round experiment only if the four-round
   terminal evidence still leaves adaptation or reproducibility unresolved.

Two, four, and eight are requested observation counts, not retry budgets or
automatic stop rules. Each generative experiment uses a distinct clean root;
terminal roots remain read-only.

## Verification and Git Discipline

- Server `claw` Python:
  `/home/clawd/miniconda3/envs/claw/bin/python`.
- WSL `scion` is for large/concurrent batches only after a fresh connectivity
  and preflight check.
- Run focused affected tests first, then the standard Scion suite, compileall,
  and `git diff --check`.
- Inspect `git status` before staging. Never stage the excluded user document
  or unrelated historical untracked files.
- The user has authorized direct stage/commit/push and subsequent experiment,
  analysis, and optimization work within these boundaries.

## Pointers

- Current state: `scion/docs/status/current-state.md`
- V3 authority: `scion/design/scion-architecture-v3.md`
- Direct-runtime addendum:
  `scion/design/scion-architecture-v3-v0.4-direct-runtime-addendum.md`
- Main audit:
  `scion/reports/v04-v3-runtime-and-research-effectiveness-audit-20260712.md`
- Gate/host-control audit:
  `scion/reports/v04-gate-and-host-control-audit-20260712.md`
- R5 terminal report:
  `scion/docs/experiments/v0.4/v04-cvrp-direct-causal-feedback-r5-postrun-20260715.md`
- R6 terminal report:
  `scion/docs/experiments/v0.4/v04-cvrp-direct-causal-feedback-r6-postrun-20260715.md`
- R6-R2 exact validation report:
  `scion/docs/experiments/v0.4/v04-cvrp-r6-r2-exact-validation-postrun-20260715.md`
- R6-R2 expanded validation report:
  `scion/docs/experiments/v0.4/v04-cvrp-r6-r2-expanded-validation-postrun-20260715.md`
- R6-R2 frozen evaluation report:
  `scion/docs/experiments/v0.4/v04-cvrp-r6-r2-frozen-evaluation-postrun-20260715.md`
- R7 stopped analysis:
  `scion/docs/experiments/v0.4/v04-cvrp-direct-longitudinal-r7-stopped-analysis-20260715.md`
- R8 stopped analysis:
  `scion/docs/experiments/v0.4/v04-cvrp-direct-longitudinal-r8-stopped-analysis-20260716.md`
- Multi-hop lineage repair report:
  `scion/docs/experiments/v0.4/v04-resume-formal-candidate-lineage-repair-20260715.md`

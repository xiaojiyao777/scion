# Scion v0.4 Direct-Runtime Research Task

*Branch: `v0.4-dev`*
*Last updated: 2026-07-15*

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

The R2 signal is uncertain and heterogeneous. X loses `-55`; ALNS iterations
fall `1857 -> 789`; round-2 comparative runtime is unavailable because all
champion results were cached. Do not promote or attribute the gain to
swap-star before fresh validation.

## Current Framework Repair

R6 exposed two evidence-integrity problems:

1. Its v2 R2 formal artifact binds a champion base and cumulative code hash to
   only the incremental `local_search.py` patch. Champion plus that artifact
   produces `0cc217...`, not the live cumulative `0d9c2ce...` workspace.
2. Canonical feedback injected legacy `unknown` fields into a problem-owned
   evidence envelope, omitted Protocol outcome/scope, and allowed display
   schema evolution to duplicate a durable observation.

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
  H feedback.

The final formal-artifact/resume/postrun slice passes `21` tests, the complete
unit suite passes `707`, and the standard repository-root suite passes `1926` with
`1` skipped. Boundary coverage includes same-file cross-round edits,
create/delete, full reversion to champion, activation files, absent and
partially missing indexes, inherited resume indexes, and
closure/content/base/final-hash tampering.

## Execution Queue

1. Stage only owned files, commit, and push `v0.4-dev`.
2. Prepare a distinct eval-only continuation from the pushed clean runtime by
   copying the complete R6 campaign workspace. Do not materialize from the
   broken v2 R2 artifact.
3. Before launch, prove copied branch/workspace/state/hash equality, data
   identity, wrapper hash, resume manifest, and zero new provider intent.
4. Launch once manually with `--rounds 1`, `--resume-from-campaign`, no
   completion preflight, no force flags, and low-frequency polling.
5. Audit validation using current-invocation deltas: no new H/C transitions or
   traces, one validation Protocol result, fresh champion runtime, unchanged
   candidate identity.
6. After validation, start a separate clean four-round generative CVRP run to
   test longitudinal evidence use. Expand to eight rounds only if four still
   leaves adaptation or reproducibility unresolved.

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
